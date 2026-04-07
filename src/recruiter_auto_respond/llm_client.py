import asyncio
import base64
import json
import logging
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from .config import settings


def _is_transient_error(exception: BaseException) -> bool:
    """Predicate for tenacity to retry only on transient failures.

    Retries on network-level errors and HTTP 5xx or 429 status codes.
    """
    if isinstance(exception, httpx.HTTPStatusError):
        # Retry on 5xx or 429 (Rate Limit)
        status_500 = 500
        status_429 = 429
        return (
            exception.response.status_code >= status_500
            or exception.response.status_code == status_429
        )
    return isinstance(exception, httpx.RequestError)


class LLMClient:
    """Client for LLM operations using a local server (e.g., llama.cpp)."""

    def __init__(self, api_url: str, api_key: str = "sk-no-key-required") -> None:
        """Initialize the LLM client.

        Args:
            api_url: The base URL of the LLM API (e.g., http://localhost:8080/v1).
            api_key: Optional API key for authentication.
        """
        if not api_url.endswith("/"):
            api_url += "/"
        self.api_url = httpx.URL(api_url)
        self.api_key = api_key
        self.semaphore = asyncio.Semaphore(settings.PARALLEL_LIMIT)
        self.client = httpx.AsyncClient(timeout=60.0)
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
            'Respond ONLY with a JSON object: {"is_recruiter": true/false}'
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
        """Generate authentication headers based on settings.

        Returns:
            A dictionary containing the Authorization header.
        """
        # Prioritize Basic Auth if provided, else Bearer Token
        if getattr(settings, "LLM_USER", None) and getattr(settings, "LLM_PASS", None):
            auth_str = f"{settings.LLM_USER}:{settings.LLM_PASS}"
            encoded_auth = base64.b64encode(auth_str.encode()).decode()
            return {"Authorization": f"Basic {encoded_auth}"}

        # Use provided api_key or fall back to settings
        token = self.api_key
        if not token or token == "sk-no-key-required":
            token = getattr(settings, "LLM_API_KEY", "sk-no-key-required")

        return {"Authorization": f"Bearer {token}"}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception(_is_transient_error),
        reraise=True,
    )
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
        async with self.semaphore:
            # Simple character-based truncation to stay within context limits
            max_context = getattr(settings, "LLM_MAX_CONTEXT", 70000)
            truncated_body = user_content[:max_context]
            url = self.api_url.join("chat/completions")

            logging.info("Posting to %s", url)
            payload = {
                "model": getattr(settings, "LLM_MODEL_NAME", "gpt-3.5-turbo"),
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
            is_recruiter = result.get("is_recruiter") or result.get("isRecruiter")

            if not isinstance(is_recruiter, bool):
                logging.error(
                    "LLM response 'is_recruiter' field is not a boolean: %s",
                    is_recruiter,
                )
                return False

            return is_recruiter
        except Exception as e:
            logging.error("LLM classification failed after retries: %s", e)
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
            logging.error("LLM reply generation failed after retries: %s", e)
            return None

