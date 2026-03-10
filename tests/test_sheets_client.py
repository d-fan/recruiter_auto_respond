from unittest.mock import MagicMock

import pytest

from recruiter_auto_respond.sheets_client import SheetsClient


@pytest.fixture
def mock_service():
    return MagicMock()


@pytest.fixture
def sheets_client(mock_service):
    return SheetsClient(mock_service)


@pytest.mark.asyncio
async def test_get_message_ids(sheets_client, mock_service):
    # Setup mock response for spreadsheets().values().get().execute()
    mock_get = mock_service.spreadsheets().values().get().execute
    mock_get.return_value = {
        "values": [
            ["msg1"],
            ["msg2"],
            ["msg3"],
        ]
    }

    message_ids = await sheets_client.get_message_ids("sheet_id")

    assert message_ids == {"msg1", "msg2", "msg3"}
    mock_service.spreadsheets().values().get.assert_called_with(
        spreadsheetId="sheet_id", range="Emails!B2:B"
    )


@pytest.mark.asyncio
async def test_append_row(sheets_client, mock_service):
    mock_append = mock_service.spreadsheets().values().append().execute
    mock_append.return_value = {}

    row_data = [
        "thread1",
        "msg1",
        "2026-03-10",
        "recruiter@example.com",
        "me@example.com",
        "Job",
        "Body",
    ]
    await sheets_client.append_row("sheet_id", row_data)

    mock_service.spreadsheets().values().append.assert_called_with(
        spreadsheetId="sheet_id",
        range="Emails!A1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [row_data]},
    )
