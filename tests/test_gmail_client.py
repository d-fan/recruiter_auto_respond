import pytest
from unittest.mock import MagicMock
from recruiter_auto_respond.gmail_client import GmailClient

@pytest.fixture
def mock_service():
    return MagicMock()

@pytest.fixture
def gmail_client(mock_service):
    return GmailClient(mock_service)

@pytest.mark.asyncio
async def test_fetch_messages(gmail_client, mock_service):
    # Setup mock response
    mock_list = mock_service.users().messages().list().execute
    mock_list.return_value = {
        "messages": [
            {"id": "msg1", "threadId": "thread1"},
            {"id": "msg2", "threadId": "thread2"}
        ]
    }

    messages = await gmail_client.fetch_messages("query")
    
    assert len(messages) == 2
    assert messages[0]["id"] == "msg1"
    mock_service.users().messages().list.assert_called_with(userId='me', q='query')

@pytest.mark.asyncio
async def test_fetch_message_body(gmail_client, mock_service):
    # Setup mock response for messages().get().execute()
    mock_get = mock_service.users().messages().get().execute
    mock_get.return_value = {
        "payload": {
            "body": {
                "data": "SGVsbG8gd29ybGQ=" # "Hello world" in base64
            }
        }
    }

    body = await gmail_client.fetch_message_body("msg1")
    
    assert "Hello world" in body
    mock_service.users().messages().get.assert_called_with(userId='me', id='msg1', format='full')

@pytest.mark.asyncio
async def test_add_label(gmail_client, mock_service):
    mock_service.users().messages().modify().execute.return_value = {}
    
    await gmail_client.add_label("msg1", "label_id")
    
    mock_service.users().messages().modify.assert_called_with(
        userId='me', 
        id='msg1', 
        body={'addLabelIds': ['label_id']}
    )
