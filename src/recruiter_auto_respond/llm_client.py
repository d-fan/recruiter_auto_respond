import json
import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential


class LLMClient:
    """Client for classification using a local LLM (e.g., llama.cpp)."""

    def __init__(self, api_url: str, api_key: str = "sk-no-key-required") -> None:
        self.api_url = api_url
        self.api_key = api_key

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def classify_message(self, body: str) -> bool:
        """Determine if a message is from a recruiter.

        Uses an OpenAI-compatible endpoint with JSON mode.
        """
        logging.info("Classifying message with LLM...")

        prompt = (
            "You are an assistant that classifies emails. "
            "Determine if the following email is from a recruiter "
            "or a job-related inquiry. "
            'Respond ONLY with a JSON object: {"is_recruiter": true} '
            'or {"is_recruiter": false}.\n\n'
            f"Email Body:\n{body}"
        )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": "gpt-3.5-turbo",  # Placeholder
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.0,
                },
                timeout=60.0,
            )
            response.raise_for_status()
            result = response.json()

            # OpenAI-compatible structure: result['choices'][0]['message']['content']
            content = result["choices"][0]["message"]["content"]
            data = json.loads(content)
            return bool(data.get("is_recruiter", False))

