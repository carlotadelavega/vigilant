from typing import Any

import pytest
from fastapi.testclient import TestClient

from vigilant.api.v1 import chat as chat_module


def test_models_falls_back_when_hermes_unreachable(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /v1/models should degrade to a single fallback entry if Hermes is down."""

    async def raise_connection_error() -> list[dict[str, Any]]:
        raise ConnectionError("hermes unreachable")

    monkeypatch.setattr(chat_module.hermes_client, "list_models", raise_connection_error)

    response = client.get("/v1/models")

    assert response.status_code == 200
    body = response.json()
    assert body["data"][0]["owned_by"] == "vigilant-fallback"


def test_models_returns_hermes_models(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /v1/models should expose model metadata returned by Hermes."""

    async def fake_list_models() -> list[dict[str, Any]]:
        return [{"id": "hermes-agent", "created": 123}]

    monkeypatch.setattr(chat_module.hermes_client, "list_models", fake_list_models)

    response = client.get("/v1/models")

    assert response.status_code == 200
    assert response.json()["data"] == [{"id": "hermes-agent", "object": "model", "created": 123, "owned_by": "hermes"}]


def test_chat_completions_requires_messages(client: TestClient) -> None:
    """POST /v1/chat/completions should reject an empty messages list."""
    response = client.post("/v1/chat/completions", json={"model": "hermes-agent", "messages": []})

    assert response.status_code == 400


def test_chat_completions_proxies_to_hermes(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /v1/chat/completions should return Hermes's completion payload verbatim."""

    async def fake_chat_completion(messages: list[dict[str, str]], model: str) -> dict[str, Any]:
        return {"id": "chatcmpl-test", "model": model, "choices": []}

    monkeypatch.setattr(chat_module.hermes_client, "chat_completion", fake_chat_completion)

    response = client.post(
        "/v1/chat/completions",
        json={"model": "hermes-agent", "messages": [{"role": "user", "content": "hi"}]},
    )

    assert response.status_code == 200
    assert response.json()["id"] == "chatcmpl-test"


def test_chat_completions_returns_502_when_hermes_fails(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /v1/chat/completions should surface a clean 502 if Hermes errors out."""

    async def raise_error(messages: list[dict[str, str]], model: str) -> dict[str, Any]:
        raise RuntimeError("boom")

    monkeypatch.setattr(chat_module.hermes_client, "chat_completion", raise_error)

    response = client.post(
        "/v1/chat/completions",
        json={"model": "hermes-agent", "messages": [{"role": "user", "content": "hi"}]},
    )

    assert response.status_code == 502


def test_chat_completions_streams_sse(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Streaming requests should relay Hermes chunks as OpenAI-compatible SSE."""

    async def fake_stream(messages: list[dict[str, str]], model: str) -> Any:
        yield {"id": "chunk", "model": model, "messages": messages}

    monkeypatch.setattr(chat_module.hermes_client, "chat_completion_stream", fake_stream)

    response = client.post(
        "/v1/chat/completions",
        json={"model": "hermes-agent", "stream": True, "messages": [{"role": "user", "content": "hi"}]},
    )

    assert response.status_code == 200
    assert response.text == (
        'data: {"id": "chunk", "model": "hermes-agent", '
        '"messages": [{"role": "user", "content": "hi"}]}\n\n'
        "data: [DONE]\n\n"
    )
