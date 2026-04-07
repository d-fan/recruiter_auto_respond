import json
from typing import Any, cast

import pytest

# Expected structure for /v1/chat/completions (OpenAI compatible)
LLM_COMPLETION_RESPONSE: dict[str, Any] = {
    "id": "chatcmpl-123",
    "object": "chat.completion",
    "created": 1677652288,
    "model": "gpt-oss-120b",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": '{"isRecruiter": true}',
            },
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 9, "completion_tokens": 12, "total_tokens": 21},
}


def test_llm_response_structure() -> None:
    """Verify that the mock LLM response matches the expected structure."""
    data = LLM_COMPLETION_RESPONSE

    # Top-level fields
    assert "id" in data
    assert isinstance(data["id"], str)
    assert data["object"] == "chat.completion"
    assert isinstance(data["created"], int)
    assert isinstance(data["model"], str)

    # Choices
    assert "choices" in data
    assert isinstance(data["choices"], list)
    assert len(data["choices"]) > 0

    choice = cast(dict[str, Any], data["choices"][0])
    assert "message" in choice
    assert choice["message"]["role"] == "assistant"
    assert "content" in choice["message"]

    # We expect JSON content in the message
    content = cast(str, choice["message"]["content"])
    parsed = json.loads(content)
    assert "isRecruiter" in parsed
    assert isinstance(parsed["isRecruiter"], bool)

    # Usage
    assert "usage" in data
    usage = cast(dict[str, Any], data["usage"])
    assert isinstance(usage["total_tokens"], int)


if __name__ == "__main__":
    pytest.main([__file__])
