from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from recruiter_auto_respond.main import Pipeline, PipelineClients, main


@pytest.fixture
def mock_gmail_client():
    return AsyncMock()


@pytest.fixture
def mock_sheets_client():
    return AsyncMock()


@pytest.fixture
def mock_llm_client():
    return AsyncMock()


@pytest.fixture
def mock_state_manager():
    return AsyncMock()


@pytest.fixture
def pipeline(
    mock_gmail_client, mock_sheets_client, mock_llm_client, mock_state_manager
):
    clients = PipelineClients(
        gmail=mock_gmail_client,
        sheets=mock_sheets_client,
        llm=mock_llm_client,
        state=mock_state_manager,
    )
    return Pipeline(
        clients=clients,
        label_name="Recruiter",
    )


@pytest.mark.asyncio
async def test_pipeline_run_no_messages(
    pipeline, mock_state_manager, mock_gmail_client
):
    # Mock state
    mock_state_manager.load_state.return_value = {
        "last_run_timestamp": "2024-01-01T00:00:00.000Z"
    }
    # Mock no messages
    mock_gmail_client.fetch_messages.return_value = []

    await pipeline.run()

    mock_gmail_client.fetch_messages.assert_called_once()
    mock_gmail_client.fetch_message_metadata.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_run_with_messages(
    pipeline, mock_state_manager, mock_gmail_client, mock_llm_client, mock_sheets_client
):
    # Mock state
    mock_state_manager.load_state.return_value = {
        "last_run_timestamp": "2024-01-01T00:00:00.000Z"
    }
    # Mock messages
    mock_gmail_client.fetch_messages.return_value = [{"id": "msg1", "threadId": "t1"}]
    mock_gmail_client.fetch_message_metadata.return_value = {
        "id": "msg1",
        "threadId": "t1",
        "internalDate": str(
            int(
                datetime(2024, 1, 1, 0, 0, 1, tzinfo=timezone.utc).timestamp() * 1000
            )
        ),
    }
    mock_gmail_client.get_or_create_label.return_value = "label123"
    mock_gmail_client.fetch_message_body.return_value = "Hello recruiter"
    mock_llm_client.classify_message.return_value = True
    mock_sheets_client.get_message_ids.return_value = set()

    await pipeline.run()

    mock_gmail_client.fetch_message_body.assert_called_once_with("msg1")
    mock_llm_client.classify_message.assert_called_once_with("Hello recruiter")
    mock_gmail_client.add_label.assert_called_once_with("msg1", "label123")
    mock_state_manager.update_watermark.assert_called_once()


@pytest.mark.asyncio
async def test_pipeline_hard_stop_on_failure(
    pipeline, mock_state_manager, mock_gmail_client, mock_llm_client
):
    # Mock state
    mock_state_manager.load_state.return_value = {
        "last_run_timestamp": "2024-01-01T00:00:00.000Z"
    }
    # Mock messages: msg1 fails, msg2 should not be processed
    msg1_dt = datetime(2024, 1, 1, 0, 0, 1, tzinfo=timezone.utc)
    msg1_ts = str(int(msg1_dt.timestamp() * 1000))
    msg2_dt = datetime(2024, 1, 1, 0, 0, 2, tzinfo=timezone.utc)
    msg2_ts = str(int(msg2_dt.timestamp() * 1000))

    mock_gmail_client.fetch_messages.return_value = [
        {"id": "msg1", "threadId": "t1"},
        {"id": "msg2", "threadId": "t2"},
    ]
    mock_gmail_client.fetch_message_metadata.side_effect = [
        {"id": "msg1", "threadId": "t1", "internalDate": msg1_ts},
        {"id": "msg2", "threadId": "t2", "internalDate": msg2_ts},
    ]
    mock_gmail_client.get_or_create_label.return_value = "label123"

    # msg1 fails on fetch_message_body
    mock_gmail_client.fetch_message_body.side_effect = [
        Exception("API Error"),
        "Body 2",
    ]

    await pipeline.run()

    # msg1 was attempted
    mock_gmail_client.fetch_message_body.assert_called()

    # Verify that even if msg2 was attempted (due to parallel execution
    # before the event was set), the watermark only includes msg1 if it
    # was successful.
    # In our implementation of process_messages, we break at the first failure.
    update_watermark_call = mock_state_manager.update_watermark.call_args[0][0]
    assert len(update_watermark_call) == 0  # No successful messages before failure


@pytest.mark.asyncio
async def test_main_pipeline_success():
    """Test the full pipeline with mocked clients and successful processing."""

    # Mock settings
    with patch("recruiter_auto_respond.main.settings") as mock_settings:
        mock_settings.GMAIL_LABEL_NAME = "recruiter"
        mock_settings.GOOGLE_SHEET_ID = "sheet_id"
        mock_settings.PARALLEL_LIMIT = 5
        mock_settings.LLM_API_URL = "http://llm"
        mock_settings.LLM_API_KEY = "key"
        mock_settings.STATE_FILE = "state.json"

        # Mock StateManager
        mock_state_manager = MagicMock()
        mock_state_manager.load_state = AsyncMock(
            return_value={"last_run_timestamp": "2023-01-01T00:00:00.000Z"}
        )
        mock_state_manager.update_watermark = AsyncMock(
            return_value="2023-01-01T01:00:00.000Z"
        )

        # Mock Clients
        mock_gmail = AsyncMock()
        mock_sheets = AsyncMock()
        mock_llm = AsyncMock()
        mock_llm.close = AsyncMock()

        # 1. Mock Gmail: fetch_messages
        mock_gmail.fetch_messages.return_value = [{"id": "msg1", "threadId": "t1"}]

        # 2. Mock Gmail: fetch_message_metadata
        mock_gmail.fetch_message_metadata.return_value = {
            "id": "msg1",
            "threadId": "t1",
            "internalDate": str(
                int(
                    datetime(2023, 1, 1, 1, 0, 0, tzinfo=timezone.utc).timestamp()
                    * 1000
                )
                + 100  # Ensure it's after the watermark
            ),
        }

        # 3. Mock Gmail: get_or_create_label
        mock_gmail.get_or_create_label.return_value = "label_id"

        # 4. Mock Gmail: fetch_message_body
        mock_gmail.fetch_message_body.return_value = "Recruiter email body"

        # 5. Mock LLM: classify_message
        mock_llm.classify_message.return_value = True

        # 6. Mock Sheets: get_message_ids
        mock_sheets.get_message_ids.return_value = set()

        # Patch all components
        with patch(
            "recruiter_auto_respond.main.setup_clients",
            return_value=(mock_gmail, mock_sheets, mock_llm, mock_state_manager),
        ), patch(
            "argparse.ArgumentParser.parse_args",
            return_value=MagicMock(dry_run=False),
        ):
            await main()

            # Verify interactions
            mock_gmail.fetch_messages.assert_called_once()
            mock_llm.classify_message.assert_called_once_with("Recruiter email body")
            mock_gmail.add_label.assert_called_once_with("msg1", "label_id")
            mock_sheets.get_message_ids.assert_called_once_with("sheet_id")
            mock_sheets.append_row.assert_called_once()
            mock_state_manager.update_watermark.assert_called_once()
            mock_llm.close.assert_called_once()
