"""Unit tests for vigilant.api.v1.chat endpoints."""

from collections.abc import AsyncGenerator
from types import TracebackType
from typing import Any, Self

import httpx
import pytest
from fastapi.testclient import TestClient

from vigilant.api.v1 import chat as chat_module
from vigilant.config import settings


class _FakeResponse:
    """Minimal stand-in for an httpx.Response used by list_models."""

    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeAsyncClient:
    """Stand-in for httpx.AsyncClient supporting async context manager usage."""

    def __init__(self, response: _FakeResponse | None = None, raise_error: bool = False) -> None:
        self._response = response
        self._raise_error = raise_error

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        return None

    async def get(self, url: str) -> _FakeResponse:
        if self._raise_error:
            raise httpx.RequestError("connection refused", request=httpx.Request("GET", url))
        assert self._response is not None
        return self._response


class _FakeLLMService:
    """Stand-in for LLMService used to test streaming without a real Ollama instance."""

    def __init__(self, tokens: list[str]) -> None:
        self._tokens = tokens
        self.last_model: str | None = None

    async def generate_stream(self, prompt: str, model: str | None = None) -> AsyncGenerator[str, None]:
        self.last_model = model
        for token in self._tokens:
            yield token


def test_list_models_success(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    """GET /v1/models should return models reported by a healthy Ollama instance."""
    fake_response = _FakeResponse(200, {"models": [{"name": "llama3.1"}, {"name": "mistral"}]})
    monkeypatch.setattr(chat_module.httpx, "AsyncClient", lambda: _FakeAsyncClient(response=fake_response))

    response = client.get("/v1/models")

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "list"
    assert {model["id"] for model in body["data"]} == {"llama3.1", "mistral"}


def test_list_models_falls_back_when_ollama_unreachable(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    """GET /v1/models should fall back to the default model when Ollama is unreachable."""
    monkeypatch.setattr(chat_module.httpx, "AsyncClient", lambda: _FakeAsyncClient(raise_error=True))

    response = client.get("/v1/models")

    assert response.status_code == 200
    body = response.json()
    assert body["data"][0]["id"] == settings.default_llm_model
    assert body["data"][0]["owned_by"] == "vigilant-fallback"


def test_list_models_raises_502_on_non_200_from_ollama(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    """GET /v1/models should surface a 502 when Ollama responds with a non-200 status."""
    fake_response = _FakeResponse(500, {})
    monkeypatch.setattr(chat_module.httpx, "AsyncClient", lambda: _FakeAsyncClient(response=fake_response))

    response = client.get("/v1/models")

    assert response.status_code == 502


def test_chat_completions_rejects_empty_messages(client: TestClient) -> None:
    """POST /v1/chat/completions should reject a request with no messages."""
    response = client.post(
        "/v1/chat/completions",
        json={"model": "llama3.1", "messages": [], "stream": False},
    )

    assert response.status_code == 400


def test_chat_completions_non_streaming_returns_placeholder(client: TestClient) -> None:
    """POST /v1/chat/completions without streaming should return the static placeholder message."""
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "llama3.1",
            "messages": [{"role": "user", "content": "hola"}],
            "stream": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["choices"][0]["message"]["content"] == "[VIGILANT]: Please enable streaming in Open WebUI."
    assert body["model"] == "llama3.1"


def test_chat_completions_streaming_forwards_model_and_tokens(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    """POST /v1/chat/completions with streaming should forward tokens and the requested model."""
    fake_service = _FakeLLMService(tokens=["Hola", " mundo"])
    monkeypatch.setattr(chat_module, "llm_service", fake_service)

    with client.stream(
        "POST",
        "/v1/chat/completions",
        json={
            "model": "mistral",
            "messages": [{"role": "user", "content": "hola"}],
            "stream": True,
        },
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    assert "Hola" in body
    assert "data: [DONE]" in body
    assert fake_service.last_model == "mistral"
