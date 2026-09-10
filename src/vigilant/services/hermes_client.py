import json
from collections.abc import AsyncGenerator
from typing import Any, cast

import httpx

from vigilant.config import settings


class HermesClientError(RuntimeError):
    """Raised when Hermes's API server returns an unexpected response."""


class HermesClient:
    """Thin async wrapper around Hermes Agent's `/v1/chat/completions` endpoint."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        """Initialize the client using centralized settings by default.

        Args:
            base_url: Optional override for Hermes's OpenAI-compatible base URL.
            api_key: Optional override for the Hermes API server key.
        """
        self._base_url = (base_url or settings.hermes_base_url).rstrip("/")
        self._api_key = api_key or settings.hermes_api_key
        self._client = httpx.AsyncClient(timeout=60.0)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        """Build the Authorization header expected by Hermes's API server."""
        return {"Authorization": f"Bearer {self._api_key}"}

    async def list_models(self) -> list[dict[str, Any]]:
        """Fetch the list of models Hermes currently exposes."""
        response = await self._client.get(f"{self._base_url}/models", headers=self._headers())
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        return cast(list[dict[str, Any]], data.get("data", []))

    async def chat_completion(self, messages: list[dict[str, str]], model: str) -> dict[str, Any]:
        """Send a non-streaming chat completion request to Hermes.

        Args:
            messages: OpenAI-format message list.
            model: The model/profile alias to request from Hermes.
        """
        response = await self._client.post(
            f"{self._base_url}/chat/completions",
            headers=self._headers(),
            json={"model": model, "messages": messages, "stream": False},
        )
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result

    async def chat_completion_stream(
        self, messages: list[dict[str, str]], model: str
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream a chat completion from Hermes, yielding decoded SSE chunk payloads.

        Args:
            messages: OpenAI-format message list.
            model: The model/profile alias to request from Hermes.
        """
        async with self._client.stream(
            "POST",
            f"{self._base_url}/chat/completions",
            headers=self._headers(),
            json={"model": model, "messages": messages, "stream": True},
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line.removeprefix("data: ").strip()
                if payload == "[DONE]":
                    return
                try:
                    yield json.loads(payload)
                except json.JSONDecodeError as exc:
                    raise HermesClientError(f"Malformed SSE chunk from Hermes: {payload!r}") from exc
