"""
Conformance test for LLM API (OpenAI-compatible).
This file documents the expected structure of LLM API responses.
Based on OpenAI Chat Completions API documentation.
"""

from typing import Any

# Expected structure for /v1/chat/completions
LLM_CHAT_COMPLETIONS_RESPONSE = {
    "id": "chatcmpl-123",
    "object": "chat.completion",
    "created": 1677652288,
    "model": "gpt-3.5-turbo-0613",
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


def _validate_llm_response(response: dict[str, Any]) -> None:
    # Basic structural validation for an OpenAI-compatible chat completion response
    assert isinstance(response, dict)
    assert "id" in response
    assert isinstance(response["id"], str)
    assert "choices" in response
    assert isinstance(response["choices"], list)
    assert len(response["choices"]) > 0

    choice = response["choices"][0]
    assert isinstance(choice, dict)
    assert "message" in choice
    assert isinstance(choice["message"], dict)
    assert "content" in choice["message"]
    assert isinstance(choice["message"]["content"], str)

    # We expect JSON content in the message
    import json

    content = choice["message"]["content"]
    parsed_content = json.loads(content)
    assert isinstance(parsed_content, dict)
    assert "isRecruiter" in parsed_content
    assert isinstance(parsed_content["isRecruiter"], bool)


def test_conformance() -> None:
    # This test validates that the documented example responses conform
    # to the expected LLM API response schema.
    _validate_llm_response(LLM_CHAT_COMPLETIONS_RESPONSE)
