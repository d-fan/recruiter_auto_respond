from unittest.mock import MagicMock, call

import pytest

from recruiter_auto_respond.gmail_client import GmailClient


@pytest.fixture
def mock_service() -> MagicMock:
    return MagicMock()


@pytest.fixture
def gmail_client(mock_service: MagicMock) -> GmailClient:
    return GmailClient(mock_service)


@pytest.mark.asyncio
async def test_fetch_messages_pagination(
    gmail_client: GmailClient, mock_service: MagicMock
) -> None:
    # Setup mock for multiple pages
    mock_list = mock_service.users().messages().list

    # Page 1 response
    mock_list.return_value.execute.side_effect = [
        {
            "messages": [{"id": "msg1", "threadId": "t1"}],
            "nextPageToken": "token2",
        },
        # Page 2 response
        {
            "messages": [{"id": "msg2", "threadId": "t2"}],
            # No next token
        },
    ]

    messages = await gmail_client.fetch_messages("query")

    expected_messages_count = 2
    assert len(messages) == expected_messages_count
    assert messages[0]["id"] == "msg1"
    assert messages[1]["id"] == "msg2"

    # Verify calls
    mock_list.assert_has_calls(
        [
            call(userId="me", q="query", pageToken=None),
            call().execute(),
            call(userId="me", q="query", pageToken="token2"),
            call().execute(),
        ]
    )


@pytest.mark.asyncio
async def test_fetch_message_body_multipart(
    gmail_client: GmailClient, mock_service: MagicMock
) -> None:
    # Setup mock for complex multipart message
    mock_get = mock_service.users().messages().get().execute
    mock_get.return_value = {
        "payload": {
            "mimeType": "multipart/alternative",
            "parts": [
                {
                    "mimeType": "text/html",
                    "body": {"data": "PGh0bWw+aGk8L2h0bWw+"},  # <html>hi</html>
                },
                {
                    "mimeType": "text/plain",
                    "body": {"data": "SGVsbG8gd29ybGQ="},  # Hello world
                },
            ],
        }
    }

    body = await gmail_client.fetch_message_body("msg1")

    assert body == "Hello world"


@pytest.mark.asyncio
async def test_add_label(
    gmail_client: GmailClient, mock_service: MagicMock
) -> None:
    mock_service.users().messages().modify().execute.return_value = {}

    await gmail_client.add_label("msg1", "label_id")

    mock_service.users().messages().modify.assert_called_with(
        userId="me", id="msg1", body={"addLabelIds": ["label_id"]}
    )


@pytest.mark.asyncio
async def test_get_or_create_label_existing(
    gmail_client: GmailClient, mock_service: MagicMock
) -> None:
    mock_list = mock_service.users().labels().list().execute
    mock_list.return_value = {
        "labels": [
            {"name": "INBOX", "id": "INBOX"},
            {"name": "Recruiter", "id": "label_123"},
        ]
    }

    label_id = await gmail_client.get_or_create_label("Recruiter")

    assert label_id == "label_123"
    mock_service.users().labels().create.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_create_label_new(
    gmail_client: GmailClient, mock_service: MagicMock
) -> None:
    mock_list = mock_service.users().labels().list().execute
    mock_list.return_value = {"labels": [{"name": "INBOX", "id": "INBOX"}]}

    mock_create = mock_service.users().labels().create().execute
    mock_create.return_value = {"id": "new_label_id"}

    label_id = await gmail_client.get_or_create_label("Recruiter")

    assert label_id == "new_label_id"
    mock_service.users().labels().create.assert_called()


@pytest.mark.asyncio
async def test_fetch_message_metadata(
    gmail_client: GmailClient, mock_service: MagicMock
) -> None:
    mock_get = mock_service.users().messages().get
    mock_get.return_value.execute.return_value = {
        "id": "msg1",
        "threadId": "t1",
        "internalDate": "1616198400000",
    }

    metadata = await gmail_client.fetch_message_metadata("msg1")

    assert metadata["id"] == "msg1"
    assert metadata["internalDate"] == "1616198400000"

    mock_get.assert_called_with(
        userId="me",
        id="msg1",
        format="minimal",
        fields="id,threadId,internalDate",
    )
