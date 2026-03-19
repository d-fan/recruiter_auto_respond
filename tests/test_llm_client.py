import asyncio
import json
from collections.abc import AsyncGenerator

import pytest
import respx
from httpx import Response
from recruiter_auto_respond.config import settings
from recruiter_auto_respond.llm_client import LLMClient


@pytest.fixture
async def llm_client() -> AsyncGenerator[LLMClient, None]:
    client = LLMClient(api_url="http://localhost:8080/v1")
    yield client
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_classify_message_recruiter(llm_client: LLMClient) -> None:
    respx.post("http://localhost:8080/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={"choices": [{"message": {"content": json.dumps({"isRecruiter": True})}}]},
        )
    )

    result = await llm_client.classify_message("Recruiter message")
    assert result is True


@respx.mock
@pytest.mark.asyncio
async def test_classify_message_not_recruiter(llm_client: LLMClient) -> None:
    respx.post("http://localhost:8080/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps({"isRecruiter": False})}}]
            },
        )
    )

    result = await llm_client.classify_message("Normal email")
    assert result is False


@respx.mock
@pytest.mark.asyncio
async def test_bearer_auth(llm_client: LLMClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(settings, "LLM_USER", None)
    monkeypatch.setattr(settings, "LLM_PASS", None)

    route = respx.post("http://localhost:8080/v1/chat/completions").mock(
        return_value=Response(
            200, json={"choices": [{"message": {"content": '{"isRecruiter": true}'}}]}
        )
    )

    await llm_client.classify_message("Hello")
    assert route.calls.last.request.headers["Authorization"] == "Bearer test-key"


@respx.mock
@pytest.mark.asyncio
async def test_basic_auth(llm_client: LLMClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LLM_USER", "user")
    monkeypatch.setattr(settings, "LLM_PASS", "pass")

    route = respx.post("http://localhost:8080/v1/chat/completions").mock(
        return_value=Response(
            200, json={"choices": [{"message": {"content": '{"isRecruiter": true}'}}]}
        )
    )

    await llm_client.classify_message("Hello")
    # Basic Auth for user:pass -> Base64(user:pass)
    # "user:pass" -> "dXNlcjpwYXNz"
    assert route.calls.last.request.headers["Authorization"] == "Basic dXNlcjpwYXNz"


@respx.mock
@pytest.mark.asyncio
async def test_retry_on_failure(llm_client: LLMClient, monkeypatch: pytest.MonkeyPatch) -> None:
    # Fail twice then succeed
    route = respx.post("http://localhost:8080/v1/chat/completions")
    route.side_effect = [
        Response(500),
        Response(500),
        Response(
            200, json={"choices": [{"message": {"content": '{"isRecruiter": true}'}}]}
        ),
    ]

    result = await llm_client.classify_message("Hello")
    assert result is True
    assert route.call_count == 3


@respx.mock
@pytest.mark.asyncio
async def test_concurrency_limit(llm_client: LLMClient) -> None:
    respx.post("http://localhost:8080/v1/chat/completions").mock(
        return_value=Response(
            200, json={"choices": [{"message": {"content": '{"isRecruiter": true}'}}]}
        )
    )

    tasks = [llm_client.classify_message(f"Msg {i}") for i in range(5)]
    results = await asyncio.gather(*tasks)
    assert len(results) == 5
    assert all(results)
