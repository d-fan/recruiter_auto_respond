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


def _validate_messages_list_response(response):
    # Basic structural validation for a Gmail messages.list response
    assert isinstance(response, dict)
    assert "messages" in response
    assert isinstance(response["messages"], list)

    for message in response["messages"]:
        assert isinstance(message, dict)
        assert "id" in message
        assert isinstance(message["id"], str)
        assert "threadId" in message
        assert isinstance(message["threadId"], str)

    # nextPageToken is optional in the API, but here we document it as present
    if "nextPageToken" in response:
        assert isinstance(response["nextPageToken"], str)

    assert "resultSizeEstimate" in response
    assert isinstance(response["resultSizeEstimate"], int)


def _validate_messages_get_response(response):
    # Basic structural validation for a Gmail messages.get response
    assert isinstance(response, dict)

    # Top-level required fields
    assert "id" in response
    assert isinstance(response["id"], str)
    assert "threadId" in response
    assert isinstance(response["threadId"], str)

    assert "labelIds" in response
    assert isinstance(response["labelIds"], list)
    for label in response["labelIds"]:
        assert isinstance(label, str)

    assert "snippet" in response
    assert isinstance(response["snippet"], str)

    # Payload structure
    assert "payload" in response
    payload = response["payload"]
    assert isinstance(payload, dict)

    # Common payload fields
    assert "partId" in payload
    assert isinstance(payload["partId"], str)
    assert "mimeType" in payload
    assert isinstance(payload["mimeType"], str)
    assert "filename" in payload
    assert isinstance(payload["filename"], str)

    # Headers: list of {name: str, value: str}
    assert "headers" in payload
    assert isinstance(payload["headers"], list)
    for header in payload["headers"]:
        assert isinstance(header, dict)
        assert "name" in header
        assert isinstance(header["name"], str)
        assert "value" in header
        assert isinstance(header["value"], str)

    # Body: {size: int, data: str}
    assert "body" in payload
    body = payload["body"]
    assert isinstance(body, dict)
    assert "size" in body
    assert isinstance(body["size"], int)
    assert "data" in body
    assert isinstance(body["data"], str)

    # Additional documented fields
    assert "sizeEstimate" in response
    assert isinstance(response["sizeEstimate"], int)


def test_conformance():
    # This test validates that the documented example responses conform
    # to the expected Gmail API response schema at a basic structural level.
    _validate_messages_list_response(MESSAGES_LIST_RESPONSE)
    _validate_messages_get_response(MESSAGES_GET_RESPONSE)
