"""Unit tests for vigilant.services.llm_service.LLMService."""

from collections.abc import AsyncIterator
from typing import Any

import pytest

from vigilant.config import settings
from vigilant.services import llm_service as llm_service_module
from vigilant.services.llm_service import LLMService


class _FakeOllamaStream:
    """Minimal async iterator mimicking the Ollama streaming chat response."""

    def __init__(self, contents: list[str]) -> None:
        self._contents = contents

    def __aiter__(self) -> AsyncIterator[dict[str, Any]]:
        async def _iterator() -> AsyncIterator[dict[str, Any]]:
            for content in self._contents:
                yield {"message": {"content": content}}

        return _iterator()


class _FakeOllamaAsyncClient:
    """Stand-in for ollama.AsyncClient that records call arguments."""

    def __init__(self, host: str) -> None:
        self.host = host
        self.last_call_kwargs: dict[str, Any] = {}

    async def chat(self, **kwargs: Any) -> _FakeOllamaStream:
        self.last_call_kwargs = kwargs
        return _FakeOllamaStream(["Hola", " mundo"])


@pytest.fixture
def fake_ollama_client(monkeypatch: pytest.MonkeyPatch) -> type[_FakeOllamaAsyncClient]:
    """Patch ollama.AsyncClient with the fake implementation for the duration of a test."""
    monkeypatch.setattr(llm_service_module.ollama, "AsyncClient", _FakeOllamaAsyncClient)
    return _FakeOllamaAsyncClient


def test_llm_service_uses_settings_host_by_default(
    fake_ollama_client: type[_FakeOllamaAsyncClient],
) -> None:
    """LLMService should default to settings.ollama_base_url when no host is given."""
    service = LLMService()

    assert isinstance(service.client, _FakeOllamaAsyncClient)
    assert service.client.host == settings.ollama_base_url


def test_llm_service_uses_explicit_host_override(
    fake_ollama_client: type[_FakeOllamaAsyncClient],
) -> None:
    """LLMService should honor an explicit host override over settings."""
    service = LLMService(host="http://custom-ollama:11434")

    assert service.client.host == "http://custom-ollama:11434"


async def test_generate_stream_yields_tokens_and_uses_default_model(
    fake_ollama_client: type[_FakeOllamaAsyncClient],
) -> None:
    """generate_stream should yield each token and request settings.default_llm_model."""
    service = LLMService()

    tokens = [token async for token in service.generate_stream("hola")]

    assert tokens == ["Hola", " mundo"]
    assert service.client.last_call_kwargs["model"] == settings.default_llm_model


async def test_generate_stream_honors_explicit_model_override(
    fake_ollama_client: type[_FakeOllamaAsyncClient],
) -> None:
    """generate_stream should forward an explicit model override to the Ollama client."""
    service = LLMService()

    tokens = [token async for token in service.generate_stream("hola", model="mistral")]

    assert tokens == ["Hola", " mundo"]
    assert service.client.last_call_kwargs["model"] == "mistral"
