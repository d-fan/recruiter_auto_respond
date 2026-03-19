import asyncio
import json
from collections.abc import AsyncGenerator

import httpx
import pytest
import respx
from httpx import Response

from recruiter_auto_respond.config import settings
from recruiter_auto_respond.llm_client import LLMClient


@pytest.fixture
async def llm_client() -> AsyncGenerator[LLMClient, None]:
    client = LLMClient(settings.LLM_API_URL)
    yield client
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_classify_message_true(llm_client: LLMClient) -> None:
    respx.post("http://localhost:8080/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "choices": [
                    {"message": {"content": json.dumps({"isRecruiter": True})}}
                ]
            },
        )
    )

    result = await llm_client.classify_message("Hello")
    assert result is True


@respx.mock
@pytest.mark.asyncio
async def test_classify_message_false(llm_client: LLMClient) -> None:
    respx.post("http://localhost:8080/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "choices": [
                    {"message": {"content": json.dumps({"isRecruiter": False})}}
                ]
            },
        )
    )

    result = await llm_client.classify_message("Hello")
    assert result is False


@respx.mock
@pytest.mark.asyncio
async def test_bearer_auth(
    llm_client: LLMClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(settings, "LLM_USER", None)

    route = respx.post("http://localhost:8080/v1/chat/completions").mock(
        return_value=Response(200, json={"choices": [{"message": {"content": "{}"}}]})
    )

    await llm_client.classify_message("Hello")
    assert "Authorization" in route.calls.last.request.headers
    assert route.calls.last.request.headers["Authorization"] == "Bearer test-key"


@respx.mock
@pytest.mark.asyncio
async def test_basic_auth(
    llm_client: LLMClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "LLM_USER", "user")
    monkeypatch.setattr(settings, "LLM_PASS", "pass")

    route = respx.post("http://localhost:8080/v1/chat/completions").mock(
        return_value=Response(200, json={"choices": [{"message": {"content": "{}"}}]})
    )

    await llm_client.classify_message("Hello")
    assert "Authorization" in route.calls.last.request.headers
    # Basic Auth for user:pass is dXNlcjpwYXNz
    assert route.calls.last.request.headers["Authorization"] == "Basic dXNlcjpwYXNz"


@respx.mock
@pytest.mark.asyncio
async def test_retry_on_failure(
    llm_client: LLMClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Fail twice then succeed
    route = respx.post("http://localhost:8080/v1/chat/completions")
    success_json = {"choices": [{"message": {"content": '{"isRecruiter": true}'}}]}
    route.side_effect = [
        Response(500),
        Response(502),
        Response(200, json=success_json),
    ]

    # Patch retry wait to speed up test
    monkeypatch.setattr(
        "recruiter_auto_respond.llm_client.wait_exponential", lambda **kwargs: None
    )

    result = await llm_client.classify_message("Hello")
    assert result is True
    expected_call_count = 3
    assert route.call_count == expected_call_count


@respx.mock
@pytest.mark.asyncio
async def test_parallel_limit(
    llm_client: LLMClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    test_limit = 2
    monkeypatch.setattr(settings, "PARALLEL_LIMIT", test_limit)
    # Re-initialize the semaphore in the client because it was
    # created with the default limit
    llm_client.semaphore = asyncio.Semaphore(test_limit)

    peak_requests = 0
    current_requests = 0

    async def mock_handler(request: httpx.Request) -> Response:
        nonlocal current_requests, peak_requests
        current_requests += 1
        peak_requests = max(peak_requests, current_requests)
        await asyncio.sleep(0.05)
        current_requests -= 1
        success_content = '{"isRecruiter": true}'
        return Response(
            200, json={"choices": [{"message": {"content": success_content}}]}
        )

    respx.post("http://localhost:8080/v1/chat/completions").mock(side_effect=mock_handler)

    tasks = [llm_client.classify_message(f"Msg {i}") for i in range(5)]
    results = await asyncio.gather(*tasks)

    expected_results_count = 5
    assert len(results) == expected_results_count
    assert all(results)
    assert peak_requests == test_limit
