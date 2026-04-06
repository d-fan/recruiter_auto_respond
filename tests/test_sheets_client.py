from unittest.mock import MagicMock

import pytest

from recruiter_auto_respond.sheets_client import SheetsClient


@pytest.fixture  # type: ignore[untyped-decorator]
def mock_service() -> MagicMock:
    return MagicMock()


@pytest.fixture  # type: ignore[untyped-decorator]
def sheets_client(mock_service: MagicMock) -> SheetsClient:
    return SheetsClient(mock_service)


@pytest.mark.asyncio  # type: ignore[untyped-decorator]
async def test_get_message_ids(
    sheets_client: SheetsClient, mock_service: MagicMock
) -> None:
    # Setup mock response for spreadsheets().values().get().execute()
    mock_get = mock_service.spreadsheets().values().get().execute
    mock_get.return_value = {"values": [["msg1"], ["msg2"], ["msg3"]]}

    message_ids = await sheets_client.get_message_ids("sheet_id")

    assert message_ids == {"msg1", "msg2", "msg3"}
    mock_service.spreadsheets().values().get.assert_called_with(
        spreadsheetId="sheet_id", range="Emails!B2:B"
    )


@pytest.mark.asyncio  # type: ignore[untyped-decorator]
async def test_append_rows(
    sheets_client: SheetsClient, mock_service: MagicMock
) -> None:
    mock_append = mock_service.spreadsheets().values().append().execute
    mock_append.return_value = {}

    rows_data = [
        ["thread1", "msg1", "2026-03-10"],
        ["thread2", "msg2", "2026-03-11"],
    ]
    await sheets_client.append_rows("sheet_id", rows_data)

    mock_service.spreadsheets().values().append.assert_called_with(
        spreadsheetId="sheet_id",
        range="Emails!A1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": rows_data},
    )
