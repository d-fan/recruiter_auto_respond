import asyncio
import logging
from collections.abc import Sequence
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential


class SheetsClient:
    """Client for syncing results to Google Sheets using Google API Client Library.

    All methods use asyncio.to_thread to wrap blocking operations.
    """

    def __init__(self, service: Any) -> None:
        self.service = service

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def get_message_ids(self, spreadsheet_id: str) -> set[str]:
        """Fetch existing message IDs from the 'Emails' sheet, column B.

        Assumes the structure: Thread ID, Message ID, Date, ...
        """
        logging.info(f"Fetching message IDs from spreadsheet {spreadsheet_id}")

        def _fetch() -> set[str]:
            # Range B2:B covers all message IDs except the header
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=spreadsheet_id, range="Emails!B2:B")
                .execute()
            )
            values = result.get("values", [])
            # Flatten the list of lists into a set of strings
            return {row[0] for row in values if row}

        return await asyncio.to_thread(_fetch)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def append_row(
        self,
        spreadsheet_id: str,
        row_data: Sequence[str | int | float],
    ) -> None:
        """Append a new row to the 'Emails' sheet."""
        logging.info(f"Appending row to spreadsheet {spreadsheet_id}")

        def _append() -> None:
            body = {"values": [list(row_data)]}
            self.service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range="Emails!A1",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body=body,
            ).execute()

        await asyncio.to_thread(_append)
