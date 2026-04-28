import asyncio
import base64
import json
import logging
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from .error_handling import is_transient_error


class LLMClient:
    """Client for LLM operations using a local server (e.g., llama.cpp)."""

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
        self.classification_system_prompt = (
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
        self.reply_system_prompt = (
            "You are a professional software engineer with a focus on senior backend "
            "and infrastructure roles. Draft a concise, polite reply to the "
            "recruiter email provided.\n"
            "Express interest in learning more about the role and suggest a brief "
            "sync if the role aligns with a senior backend/infrastructure focus.\n"
            "Keep the tone helpful but firm on scope.\n"
            "Respond ONLY with the text of the reply.\n"
            "Do NOT include a signature or a subject line."
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.aclose()

    def _get_headers(self) -> dict[str, str]:
        """Generate authentication headers based on credentials.

        Returns:
            A dictionary containing the Authorization header, or empty if no
            credentials are provided.
        """
        if self.user and self.password:
            auth_str = f"{self.user}:{self.password}"
            encoded_auth = base64.b64encode(auth_str.encode()).decode()
            return {"Authorization": f"Basic {encoded_auth}"}
        if self.api_key:
            return {"Authorization": f"Bearer {self.api_key}"}
        return {}

    async def _request_llm(
        self,
        system_prompt: str,
        user_content: str,
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.1,
    ) -> str | None:
        """Internal method to call the LLM API with retries and semaphore.

        Args:
            system_prompt: The system prompt to use.
            user_content: The user content (email body).
            response_format: Optional JSON schema or type.
            temperature: Sampling temperature.

        Returns:
            The raw text content of the LLM response, or None if it fails.
        """

        async def _call() -> str | None:
            async with self.semaphore:
                # Simple character-based truncation to stay within context limits
                truncated_body = user_content[: self.max_context]
                url = self.api_url.join("chat/completions")

                logging.info("Posting to %s", url)
                payload = {
                    "model": self.model_name,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": truncated_body},
                    ],
                    "temperature": temperature,
                }
                if response_format:
                    payload["response_format"] = response_format

                response = await self.client.post(
                    url,
                    headers=self._get_headers(),
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

                try:
                    content = data["choices"][0]["message"]["content"]
                    if isinstance(content, str):
                        return content
                    return None
                except (KeyError, IndexError) as e:
                    logging.error("Failed to parse LLM response: %s", e)
                    return None

        try:
            return await self._retry_config(_call)
        except Exception as e:
            logging.error(f"LLM request failed: {e}")
            return None

    async def classify_message(self, body: str) -> bool:
        """Determine if a message is from a recruiter.

        Args:
            body: The email body content to classify.

        Returns:
            True if identified as a recruiter, False otherwise.
        """
        logging.info("Classifying message with LLM...")
        try:
            content = await self._request_llm(
                system_prompt=self.classification_system_prompt,
                user_content=body,
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            if not content:
                return False

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
        except Exception as e:
            logging.error(f"LLM classification failed: {e}")
            return False

    async def generate_reply(self, body: str) -> str | None:
        """Generate a professional draft reply to a recruiter email.

        Args:
            body: The email body content.

        Returns:
            The generated reply text, or None if generation fails.
        """
        logging.info("Generating draft reply with LLM...")
        try:
            content = await self._request_llm(
                system_prompt=self.reply_system_prompt,
                user_content=body,
                temperature=0.7,
            )
            if isinstance(content, str):
                return content
            return None
        except Exception as e:
            logging.error(f"LLM reply generation failed: {e}")
            return None
