import asyncio
import base64
import logging
from typing import Any, cast

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
        """Fetch all messages matching the query, handling pagination."""
        logging.info(f"Fetching messages for query: {query}")

        def _fetch_all() -> list[dict[str, Any]]:
            messages: list[dict[str, Any]] = []
            next_page_token = None

            while True:
                results = (
                    self.service.users()
                    .messages()
                    .list(userId="me", q=query, pageToken=next_page_token)
                    .execute()
                )
                messages.extend(results.get("messages", []))
                next_page_token = results.get("nextPageToken")
                if not next_page_token:
                    break

            return messages

        return await asyncio.to_thread(_fetch_all)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def fetch_message_body(self, message_id: str) -> str:
        """Fetch the body of a specific message.

        Extracts plain text content from the message, handling multipart structures.
        """
        logging.info(f"Fetching body for message: {message_id}")

        def _fetch() -> str:
            msg = (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )

            def _extract_body(payload: dict[str, Any]) -> str:
                """Recursively extract text/plain part from payload."""
                mime_type = payload.get("mimeType")
                body_data = payload.get("body", {}).get("data", "")

                if mime_type == "text/plain" and body_data:
                    return cast(str, body_data)

                if "parts" in payload:
                    for part in payload["parts"]:
                        found_body = _extract_body(part)
                        if found_body:
                            return found_body

                return ""

            encoded_body = _extract_body(msg.get("payload", {}))
            if not encoded_body:
                return ""

            def _decode_base64url(data: str) -> bytes:
                """Decode a base64url string, adding padding if necessary."""
                missing_padding = (-len(data)) % 4
                if missing_padding:
                    data += "=" * missing_padding
                return base64.urlsafe_b64decode(data)

            # Decode from base64url, handling missing padding
            try:
                decoded_bytes = _decode_base64url(encoded_body)
                return decoded_bytes.decode("utf-8", errors="replace")
            except Exception as e:
                logging.warning(f"Failed to decode body for message {message_id}: {e}")
                return ""

        return await asyncio.to_thread(_fetch)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def add_label(self, message_id: str, label_id: str) -> None:
        """Add a label to a specific message."""
        logging.debug(f"Adding label '{label_id}' to message {message_id}")

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
                    return cast(str, label["id"])

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
            return cast(str, new_label["id"])

        return await asyncio.to_thread(_get_create)
