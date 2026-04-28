import base64
import logging
from typing import Any, cast

from .base_client import BaseClient


class GmailClient(BaseClient):
    """Client for Gmail operations."""

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

        return await self._run_async(_fetch_all)

    async def fetch_message_metadata(self, message_id: str) -> dict[str, Any]:
        """Fetch metadata for a specific message (e.g., internalDate)."""
        logging.debug(f"Fetching metadata for message: {message_id}")

        def _fetch() -> dict[str, Any]:
            return cast(
                dict[str, Any],
                self.service.users()
                .messages()
                .get(
                    userId="me",
                    id=message_id,
                    format="minimal",
                    fields="id,threadId,internalDate",
                )
                .execute(),
            )

        return await self._run_async(_fetch)

    async def fetch_message_body(self, message_id: str) -> str:
        """Fetch and decode message body."""
        logging.info(f"Fetching body for message: {message_id}")

        def _fetch() -> str:
            msg = (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )

            def _extract_body(payload: dict[str, Any]) -> str:
                mime_type = payload.get("mimeType")
                body_data = payload.get("body", {}).get("data", "")
                if mime_type == "text/plain" and body_data:
                    return cast(str, body_data)
                if "parts" in payload:
                    for part in payload["parts"]:
                        found = _extract_body(part)
                        if found:
                            return found
                return ""

            encoded = _extract_body(msg.get("payload", {}))
            if not encoded:
                return ""

            padding = (-len(encoded)) % 4
            if padding:
                encoded += "=" * padding
            try:
                decoded = base64.urlsafe_b64decode(encoded)
                return decoded.decode("utf-8", errors="replace")
            except Exception:
                logging.warning(f"Failed to decode body for message {message_id}")
                return ""

        return await self._run_async(_fetch)

    async def add_label(self, message_id: str, label_id: str) -> None:
        """Add a label to a message."""
        logging.debug(f"Adding label '{label_id}' to message {message_id}")

        def _add() -> None:
            self.service.users().messages().modify(
                userId="me", id=message_id, body={"addLabelIds": [label_id]}
            ).execute()

        await self._run_async(_add)

    async def get_or_create_label(self, label_name: str) -> str:
        """Get or create label and return ID."""
        logging.info(f"Getting or creating label: {label_name}")

        def _get_create() -> str:
            results = self.service.users().labels().list(userId="me").execute()
            for label in results.get("labels", []):
                if label["name"].lower() == label_name.lower():
                    return cast(str, label["id"])

            new_label = (
                self.service.users()
                .labels()
                .create(
                    userId="me",
                    body={
                        "name": label_name,
                        "labelListVisibility": "labelShow",
                        "messageListVisibility": "show",
                    },
                )
                .execute()
            )
            return cast(str, new_label["id"])

        return await self._run_async(_get_create)
