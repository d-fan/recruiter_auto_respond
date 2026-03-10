import logging

class LLMClient:
    """Client for classification using a local LLM (e.g., llama.cpp)."""
    def __init__(self, api_url: str):
        self.api_url = api_url

    async def classify_message(self, body: str) -> bool:
        """Determine if a message is from a recruiter."""
        logging.info("Classifying message with LLM...")
        return False
