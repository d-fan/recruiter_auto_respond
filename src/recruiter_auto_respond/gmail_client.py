import asyncio
import base64
import logging
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential


class GmailClient:
    """Client for fetching and labeling Gmail messages using Google API Client Library.

    All methods use asyncio.to_thread to wrap blocking operations.
    """

    def __init__(self, service: Any) -> None:
        self.service = service

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def fetch_messages(self, query: str) -> list[dict[str, Any]]:
        """Fetch messages matching the query."""
        logging.info(f"Fetching messages for query: {query}")

        def _fetch() -> list[dict[str, Any]]:
            results = (
                self.service.users()
                .messages()
                .list(userId="me", q=query)
                .execute()
            )
            return results.get("messages", [])

        return await asyncio.to_thread(_fetch)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def fetch_message_body(self, message_id: str) -> str:
        """Fetch the body of a specific message.

        Extracts plain text content from the message.
        """
        logging.info(f"Fetching body for message: {message_id}")

        def _fetch() -> str:
            msg = (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )

            # Extraction logic for message body
            def _extract_body(payload: dict[str, Any]) -> str:
                if "parts" in payload:
                    for part in payload["parts"]:
                        if part["mimeType"] == "text/plain":
                            return part.get("body", {}).get("data", "")
                        if "parts" in part:
                            body = _extract_body(part)
                            if body:
                                return body
                return payload.get("body", {}).get("data", "")

            def _decode_base64url(data: str) -> bytes:
                """Decode a base64url string, adding padding if necessary."""
                missing_padding = (-len(data)) % 4
                if missing_padding:
                    data += "=" * missing_padding
                return base64.urlsafe_b64decode(data)

            encoded_body = _extract_body(msg.get("payload", {}))
            if not encoded_body:
                return ""

            # Decode from base64url, handling missing padding
            decoded_bytes = _decode_base64url(encoded_body)
            return decoded_bytes.decode("utf-8")

        return await asyncio.to_thread(_fetch)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def add_label(self, message_id: str, label_id: str) -> None:
        """Add a label to a specific message."""
        logging.info(f"Adding label '{label_id}' to message {message_id}")

        def _add() -> None:
            self.service.users().messages().modify(
                userId="me", id=message_id, body={"addLabelIds": [label_id]}
            ).execute()

        await asyncio.to_thread(_add)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def get_or_create_label(self, label_name: str) -> str:
        """Get or create a label by name and return its ID."""
        logging.info(f"Getting or creating label: {label_name}")

        def _get_create() -> str:
            results = self.service.users().labels().list(userId="me").execute()
            labels = results.get("labels", [])
            for label in labels:
                if label["name"].lower() == label_name.lower():
                    return label["id"]

            # Not found, create it
            label_body = {
                "name": label_name,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            }
            new_label = (
                self.service.users()
                .labels()
                .create(userId="me", body=label_body)
                .execute()
            )
            return new_label["id"]

        return await asyncio.to_thread(_get_create)
