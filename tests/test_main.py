from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from recruiter_auto_respond.main import main


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
            return_value={"last_run_timestamp": "2023-01-01T00:00:00Z"}
        )
        mock_state_manager.update_watermark = AsyncMock(
            return_value="2023-01-01T01:00:00Z"
        )

        # Mock Clients
        mock_gmail = AsyncMock()
        mock_sheets = AsyncMock()
        mock_llm = AsyncMock()

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
            "recruiter_auto_respond.main.StateManager", return_value=mock_state_manager
        ), patch(
            "recruiter_auto_respond.main.setup_clients",
            return_value=(mock_gmail, mock_sheets, mock_llm),
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
            mock_sheets.append_rows.assert_called_once()
            mock_state_manager.update_watermark.assert_called_once()


@pytest.mark.asyncio
async def test_main_pipeline_dry_run():
    """Test the pipeline in dry-run mode."""

    # Mock settings
    with patch("recruiter_auto_respond.main.settings") as mock_settings:
        mock_settings.GMAIL_LABEL_NAME = "recruiter"
        mock_settings.GOOGLE_SHEET_ID = "sheet_id"
        mock_settings.PARALLEL_LIMIT = 5
        mock_settings.LLM_API_URL = "http://llm"
        mock_settings.LLM_API_KEY = "key"

        # Mock StateManager
        mock_state_manager = MagicMock()
        mock_state_manager.load_state = AsyncMock(
            return_value={"last_run_timestamp": "2023-01-01T00:00:00Z"}
        )
        mock_state_manager.update_watermark = AsyncMock(
            return_value="2023-01-01T01:00:00Z"
        )

        # Mock Clients
        mock_gmail = AsyncMock()
        mock_sheets = AsyncMock()
        mock_llm = AsyncMock()

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
            ),
        }

        # 3. Mock Gmail: get_or_create_label
        mock_gmail.get_or_create_label.return_value = "label_id"

        # 4. Mock Gmail: fetch_message_body
        mock_gmail.fetch_message_body.return_value = "Recruiter email body"

        # 5. Mock LLM: classify_message
        mock_llm.classify_message.return_value = True

        # Patch all components
        with patch(
            "recruiter_auto_respond.main.StateManager", return_value=mock_state_manager
        ), patch(
            "recruiter_auto_respond.main.setup_clients",
            return_value=(mock_gmail, mock_sheets, mock_llm),
        ), patch(
            "argparse.ArgumentParser.parse_args",
            return_value=MagicMock(dry_run=True),
        ):
            await main()

            # Verify interactions
            mock_gmail.fetch_messages.assert_called_once()
            mock_llm.classify_message.assert_called_once()
            # label should NOT be added in dry run
            mock_gmail.add_label.assert_not_called()
            # sheets should NOT be touched in dry run
            mock_sheets.get_message_ids.assert_not_called()
            mock_sheets.append_rows.assert_not_called()
            mock_state_manager.update_watermark.assert_called_once()
