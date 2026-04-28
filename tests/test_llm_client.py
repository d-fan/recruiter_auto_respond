import asyncio
import json
from collections.abc import AsyncGenerator

import httpx
import pytest
import respx
from httpx import Response
from tenacity.wait import wait_none

from recruiter_auto_respond.llm_client import LLMClient


@pytest.fixture
async def llm_client() -> AsyncGenerator[LLMClient, None]:
    # Use a fixed URL for tests to ensure respx matches consistently
    # regardless of environment settings.
    client = LLMClient("http://localhost:8080/v1", model_name="test-model")

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
async def test_classify_message_malformed_json(llm_client: LLMClient) -> None:
    respx.post("http://localhost:8080/v1/chat/completions").mock(
        return_value=Response(200, content="invalid json")
    )

    result = await llm_client.classify_message("Hello")
    assert result is False


@respx.mock
@pytest.mark.asyncio
async def test_classify_message_missing_field(llm_client: LLMClient) -> None:
    respx.post("http://localhost:8080/v1/chat/completions").mock(
        return_value=Response(200, json={"choices": [{"message": {"content": "{}"}}]})
    )

    result = await llm_client.classify_message("Hello")
    assert result is False


@respx.mock
@pytest.mark.asyncio
async def test_classify_message_wrong_type(llm_client: LLMClient) -> None:
    respx.post("http://localhost:8080/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "choices": [
                    {"message": {"content": json.dumps({"isRecruiter": "maybe"})}}
                ]
            },
        )
    )

    result = await llm_client.classify_message("Hello")
    assert result is False


@respx.mock
@pytest.mark.asyncio
async def test_bearer_auth() -> None:
    client = LLMClient(
        "http://localhost:8080/v1", model_name="test-model", api_key="test-key"
    )

    route = respx.post("http://localhost:8080/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={"choices": [{"message": {"content": '{"isRecruiter": true}'}}]},
        )
    )

    try:
        await client.classify_message("Hello")
        assert "Authorization" in route.calls.last.request.headers
        assert route.calls.last.request.headers["Authorization"] == "Bearer test-key"
    finally:
        await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_basic_auth() -> None:
    client = LLMClient(
        "http://localhost:8080/v1",
        model_name="test-model",
        user="user",
        password="pass",
    )

    route = respx.post("http://localhost:8080/v1/chat/completions").mock(
        return_value=Response(200, json={"choices": [{"message": {"content": "{}"}}]})
    )

    try:
        await client.classify_message("Hello")
        assert "Authorization" in route.calls.last.request.headers
        # Basic Auth for user:pass is dXNlcjpwYXNz
        assert route.calls.last.request.headers["Authorization"] == "Basic dXNlcjpwYXNz"
    finally:
        await client.close()


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

    # Patch the wait configuration of the retry object
    monkeypatch.setattr(llm_client._retry_config, "wait", wait_none())

    result = await llm_client.classify_message("Hello")
    assert result is True
    expected_calls = 3
    assert route.call_count == expected_calls


@respx.mock
@pytest.mark.asyncio
async def test_generate_reply_success(llm_client: LLMClient) -> None:
    respx.post("http://localhost:8080/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "choices": [{"message": {"content": "I am interested in this role."}}]
            },
        )
    )

    result = await llm_client.generate_reply("Recruiter email body")
    assert result == "I am interested in this role."


@respx.mock
@pytest.mark.asyncio
async def test_generate_reply_failure(llm_client: LLMClient) -> None:
    respx.post("http://localhost:8080/v1/chat/completions").mock(
        return_value=Response(500)
    )

    result = await llm_client.generate_reply("Recruiter email body")
    assert result is None


@respx.mock
@pytest.mark.asyncio
async def test_parallel_limit() -> None:
    test_limit = 2
    client = LLMClient(
        "http://localhost:8080/v1", model_name="test-model", parallel_limit=test_limit
    )

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

    respx.post("http://localhost:8080/v1/chat/completions").mock(
        side_effect=mock_handler
    )

    try:
        tasks = [client.classify_message(f"Msg {i}") for i in range(5)]
        results = await asyncio.gather(*tasks)

        expected_results = 5
        assert len(results) == expected_results
        assert all(results)
        assert peak_requests == test_limit
    finally:
        await client.close()
