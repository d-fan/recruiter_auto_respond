import asyncio
import base64
import json
import logging

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import settings


class LLMClient:
    """Client for classification using a local LLM (e.g., llama.cpp)."""

    def __init__(self, api_url: str) -> None:
        self.api_url = api_url
        self.semaphore = asyncio.Semaphore(settings.PARALLEL_LIMIT)
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

    def _get_headers(self) -> dict[str, str]:
        """Generate authentication headers based on settings."""
        if settings.LLM_USER and settings.LLM_PASS:
            auth_str = f"{settings.LLM_USER}:{settings.LLM_PASS}"
            encoded_auth = base64.b64encode(auth_str.encode()).decode()
            return {"Authorization": f"Basic {encoded_auth}"}
        return {"Authorization": f"Bearer {settings.LLM_API_KEY}"}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        reraise=True,
    )
    async def _call_llm(self, body: str) -> bool:
        """Internal method to call the LLM API with retries."""
        # Simple character-based truncation to stay within context limits
        truncated_body = body[: settings.LLM_MAX_CONTEXT]

        async with httpx.AsyncClient() as client:
            logging.info(f"Posting to {self.api_url}/chat/completions")
            response = await client.post(
                f"{self.api_url}/chat/completions",
                headers=self._get_headers(),
                json={
                    "model": "gpt-oss-120b",
                    "messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": truncated_body},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.1,
                },
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()

            try:
                content = data["choices"][0]["message"]["content"]
                result = json.loads(content)
                return bool(result.get("isRecruiter", False))
            except (KeyError, IndexError, json.JSONDecodeError) as e:
                logging.error(f"Failed to parse LLM response: {e}")
                return False

    async def classify_message(self, body: str) -> bool:
        """Determine if a message is from a recruiter."""
        logging.info("Classifying message with LLM...")
        async with self.semaphore:
            try:
                return await self._call_llm(body)
            except Exception as e:
                logging.error(f"LLM classification failed after retries: {e}")
                return False
