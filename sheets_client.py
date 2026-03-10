import logging
from typing import Set, Sequence, Union

class SheetsClient:
    """Client for syncing results to Google Sheets."""
    def __init__(self, service=None) -> None:
        self.service = service

    async def get_message_ids(self, spreadsheet_id: str) -> Set[str]:
        """Fetch existing message IDs from the sheet."""
        logging.info(f"Fetching message IDs from spreadsheet {spreadsheet_id}")
        return set()

    async def append_row(
        self, 
        spreadsheet_id: str, 
        row_data: Sequence[Union[str, int, float]]
    ) -> None:
        """Append a new row to the sheet."""
        logging.info(f"Appending row to spreadsheet {spreadsheet_id}: {row_data}")
        pass
