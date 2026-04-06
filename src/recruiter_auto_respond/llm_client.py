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

from .config import settings
from .error_handling import is_transient_error


class LLMClient:
    """Client for classification using a local LLM."""

    def __init__(self, api_url: str) -> None:
        if not api_url.endswith("/"):
            api_url += "/"
        self.api_url = httpx.URL(api_url)
        self.semaphore = asyncio.Semaphore(settings.PARALLEL_LIMIT)
        self.client = httpx.AsyncClient(timeout=60.0)
        self._retry_config = AsyncRetrying(
            retry=retry_if_exception(is_transient_error),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )
        self.system_prompt = (
            "You are an expert recruitment assistant. Analyze the email "
            "content provided.\n"
            "Determine if it is a message from a recruiter reaching out about "
            "a specific job opportunity.\n"
            'EXCLUDE: Automated alerts, newsletters, or rejections.\n'
            'INCLUDE: Personalized outreach, requests for resume, or '
            'interview invitations.\n'
            'Respond ONLY with JSON: {"isRecruiter": true/false}'
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.aclose()

    def _get_headers(self) -> dict[str, str]:
        if settings.LLM_USER and settings.LLM_PASS:
            raw_auth = f"{settings.LLM_USER}:{settings.LLM_PASS}"
            auth = base64.b64encode(raw_auth.encode()).decode()
            return {"Authorization": f"Basic {auth}"}
        return {"Authorization": f"Bearer {settings.LLM_API_KEY}"}

    async def classify_message(self, body: str) -> bool:
        """Classify message as recruiter or not."""

        async def _call() -> bool:
            async with self.semaphore:
                truncated_body = body[: settings.LLM_MAX_CONTEXT]
                response = await self.client.post(
                    self.api_url.join("chat/completions"),
                    headers=self._get_headers(),
                    json={
                        "model": settings.LLM_MODEL_NAME,
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
                return bool(json.loads(content).get("isRecruiter"))

        try:
            return await self._retry_config(_call)
        except Exception as e:
            logging.error(f"LLM classification failed: {e}")
            return False
