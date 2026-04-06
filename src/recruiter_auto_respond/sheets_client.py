import logging
from collections.abc import Sequence

from .base_client import BaseClient


class SheetsClient(BaseClient):
    """Client for syncing results to Google Sheets."""

    async def get_message_ids(self, spreadsheet_id: str) -> set[str]:
        """Fetch existing message IDs from the 'Emails' sheet, column B."""
        logging.info(f"Fetching message IDs from spreadsheet {spreadsheet_id}")

        def _fetch() -> set[str]:
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=spreadsheet_id, range="Emails!B2:B")
                .execute()
            )
            return {row[0] for row in result.get("values", []) if row}

        return await self._run_async(_fetch)

    async def append_row(
        self,
        spreadsheet_id: str,
        row_data: Sequence[str | int | float],
    ) -> None:
        """Append a new row to the 'Emails' sheet."""
        logging.info(f"Appending row to spreadsheet {spreadsheet_id}")

        def _append() -> None:
            self.service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range="Emails!A1",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": [list(row_data)]},
            ).execute()

        await self._run_async(_append)
