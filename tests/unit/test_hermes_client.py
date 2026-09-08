from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest

from vigilant.services import hermes_client as hermes_module
from vigilant.services.hermes_client import HermesClient, HermesClientError


class FakeResponse:
    def __init__(self, payload: Any, lines: list[str] | None = None) -> None:
        self._payload = payload
        self._lines = lines or []

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self._payload

    async def aiter_lines(self) -> AsyncIterator[str]:
        for line in self._lines:
            yield line


class FakeStream:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response

    async def __aenter__(self) -> FakeResponse:
        return self.response

    async def __aexit__(self, *_args: object) -> None:
        return None


class FakeAsyncClient:
    def __init__(self, **_kwargs: Any) -> None:
        self.response = FakeResponse({})
        self.stream_response = FakeResponse({})
        self.requests: list[tuple[str, str, dict[str, Any]]] = []

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.requests.append(("GET", url, kwargs))
        return self.response

    async def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.requests.append(("POST", url, kwargs))
        return self.response

    def stream(self, method: str, url: str, **kwargs: Any) -> FakeStream:
        self.requests.append((method, url, kwargs))
        return FakeStream(self.stream_response)


@pytest.fixture(autouse=True)
def fake_http_client(monkeypatch: pytest.MonkeyPatch) -> FakeAsyncClient:
    client = FakeAsyncClient()
    monkeypatch.setattr(hermes_module.httpx, "AsyncClient", lambda **_kwargs: client)
    return client


@pytest.mark.asyncio
async def test_list_models_returns_data_and_headers(fake_http_client: FakeAsyncClient) -> None:
    fake_http_client.response = FakeResponse({"data": [{"id": "hermes"}]})
    client = HermesClient("http://hermes/v1", "secret")

    result = await client.list_models()

    assert result == [{"id": "hermes"}]
    assert fake_http_client.requests == [
        ("GET", "http://hermes/v1/models", {"headers": {"Authorization": "Bearer secret"}})
    ]


@pytest.mark.asyncio
async def test_chat_completion_returns_response(fake_http_client: FakeAsyncClient) -> None:
    fake_http_client.response = FakeResponse({"id": "completion"})
    client = HermesClient("http://hermes/v1", "secret")

    result = await client.chat_completion([{"role": "user", "content": "hi"}], "hermes")

    assert result == {"id": "completion"}
    assert fake_http_client.requests[0][2]["json"] == {
        "model": "hermes",
        "messages": [{"role": "user", "content": "hi"}],
        "stream": False,
    }


@pytest.mark.asyncio
async def test_chat_completion_stream_decodes_sse_and_stops_at_done(fake_http_client: FakeAsyncClient) -> None:
    fake_http_client.stream_response = FakeResponse(
        {}, ["comment", 'data: {"id": "one"}', "data: [DONE]", 'data: {"id": "ignored"}']
    )
    client = HermesClient("http://hermes/v1", "secret")

    result = [chunk async for chunk in client.chat_completion_stream([], "hermes")]

    assert result == [{"id": "one"}]


@pytest.mark.asyncio
async def test_chat_completion_stream_raises_for_malformed_sse(fake_http_client: FakeAsyncClient) -> None:
    fake_http_client.stream_response = FakeResponse({}, ["data: not-json"])
    client = HermesClient("http://hermes/v1", "secret")

    with pytest.raises(HermesClientError, match="Malformed SSE chunk"):
        _ = [chunk async for chunk in client.chat_completion_stream([], "hermes")]


@pytest.mark.asyncio
async def test_chat_completion_stream_sends_stream_request(fake_http_client: FakeAsyncClient) -> None:
    fake_http_client.stream_response = FakeResponse({}, [])
    client = HermesClient("http://hermes/v1", "secret")

    _ = [chunk async for chunk in client.chat_completion_stream([], "hermes")]

    assert fake_http_client.requests[0][2]["json"]["stream"] is True
    assert fake_http_client.requests[0][0] == "POST"


@pytest.mark.asyncio
async def test_http_error_is_propagated(fake_http_client: FakeAsyncClient) -> None:
    class ErrorResponse(FakeResponse):
        def raise_for_status(self) -> None:
            raise httpx.HTTPStatusError(
                "bad", request=httpx.Request("GET", "http://hermes"), response=httpx.Response(500)
            )

    fake_http_client.response = ErrorResponse({})

    with pytest.raises(httpx.HTTPStatusError):
        await HermesClient("http://hermes/v1").list_models()
