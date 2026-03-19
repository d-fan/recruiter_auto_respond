import json

import pytest

# Expected structure for /v1/chat/completions (OpenAI compatible)
LLM_COMPLETION_RESPONSE = {
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
    assert "choices" in data
    assert isinstance(data["choices"], list)
    assert len(data["choices"]) > 0

    choice = data["choices"][0]
    assert "message" in choice
    assert "content" in choice["message"]

    # We expect JSON content in the message
    content = choice["message"]["content"]
    parsed = json.loads(content)
    assert "isRecruiter" in parsed
    assert isinstance(parsed["isRecruiter"], bool)


if __name__ == "__main__":
    pytest.main([__file__])
