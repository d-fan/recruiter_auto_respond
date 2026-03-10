"""
Conformance test for Gmail API.
This file documents the expected structure of Gmail API responses.
Based on official Google API documentation.
"""

# Expected structure for messages.list
MESSAGES_LIST_RESPONSE = {
    "messages": [
        {"id": "msg_123", "threadId": "thread_123"},
        {"id": "msg_456", "threadId": "thread_456"}
    ],
    "nextPageToken": "token_abc",
    "resultSizeEstimate": 2
}

# Expected structure for messages.get
MESSAGES_GET_RESPONSE = {
    "id": "msg_123",
    "threadId": "thread_123",
    "labelIds": ["INBOX", "UNREAD"],
    "snippet": "Hello, this is a test email...",
    "payload": {
        "partId": "",
        "mimeType": "text/plain",
        "filename": "",
        "headers": [
            {"name": "Subject", "value": "Test Subject"},
            {"name": "From", "value": "recruiter@example.com"}
        ],
        "body": {
            "size": 28,
            "data": "SGVsbG8sIHRoaXMgaXMgYSB0ZXN0IGVtYWls..."
        }
    },
    "sizeEstimate": 150
}

def test_placeholder():
    # This is a placeholder since we can't run real API calls without credentials
    pass
