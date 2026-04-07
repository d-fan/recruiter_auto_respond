import asyncio
import base64
import json
import logging

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from .error_handling import is_transient_error


class LLMClient:
    """Client for classification using a local LLM."""

    def __init__(  # noqa: PLR0913
        self,
        api_url: str,
        model_name: str,
        parallel_limit: int = 1,
        max_context: int = 4096,
        api_key: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ) -> None:
        """Initialize the LLM client.

        Args:
            api_url: The base URL of the LLM API (e.g., http://localhost:8080/v1).
            model_name: The name of the model to use.
            parallel_limit: Maximum number of parallel requests.
            max_context: Maximum characters for truncation.
            api_key: API Key for authentication.
            user: Basic Auth username.
            password: Basic Auth password.
        """
        if not api_url.endswith("/"):
            api_url += "/"
        self.api_url = httpx.URL(api_url)
        self.model_name = model_name
        self.max_context = max_context
        self.api_key = api_key
        self.user = user
        self.password = password
        self.semaphore = asyncio.Semaphore(parallel_limit)
        self.client = httpx.AsyncClient(timeout=60.0)
        self._retry_config = AsyncRetrying(
            retry=retry_if_exception(is_transient_error),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )
        self.system_prompt = (
            "You are an expert recruitment assistant. Analyze the "
            "email content provided.\n"
            "Determine if it is a message from a recruiter, hiring manager, or "
            "talent acquisition professional reaching out about a specific job "
            "opportunity or scheduling an interview.\n\n"
            'EXCLUDE: Automated job alerts, newsletters, LinkedIn "suggested jobs", '
            "or rejection emails.\n"
            "INCLUDE: Personalized outreach, requests for your resume, or "
            "invitations to interview.\n\n"
            'Respond ONLY with a JSON object: {"isRecruiter": true/false}'
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.aclose()

    def _get_headers(self) -> dict[str, str]:
        """Generate authentication headers based on credentials.

        Returns:
            A dictionary containing the Authorization header.
        """
        if self.user and self.password:
            auth_str = f"{self.user}:{self.password}"
            encoded_auth = base64.b64encode(auth_str.encode()).decode()
            return {"Authorization": f"Basic {encoded_auth}"}
        return {"Authorization": f"Bearer {self.api_key}"}

    async def classify_message(self, body: str) -> bool:
        """Classify message as recruiter or not."""

        async def _call() -> bool:
            async with self.semaphore:
                truncated_body = body[: self.max_context]
                url = self.api_url.join("chat/completions")
                logging.info("Posting to %s", url)
                response = await self.client.post(
                    url,
                    headers=self._get_headers(),
                    json={
                        "model": self.model_name,
                        "messages": [
                            {"role": "system", "content": self.system_prompt},
                            {"role": "user", "content": truncated_body},
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.1,
                    },
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                result = json.loads(content)

                if not isinstance(result, dict):
                    logging.error(
                        "LLM classification returned non-object JSON: %r", result
                    )
                    return False

                # Handle both possible keys from different prompts while preserving
                # a valid False value from the primary key.
                if "isRecruiter" in result:
                    is_recruiter = result["isRecruiter"]
                else:
                    is_recruiter = result.get("is_recruiter")

                if isinstance(is_recruiter, bool):
                    return is_recruiter

                logging.error(
                    "LLM classification returned non-boolean value: %r", is_recruiter
                )
                return False

        try:
            return await self._retry_config(_call)
        except Exception as e:
            logging.error(f"LLM classification failed: {e}")
            return False
