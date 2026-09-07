from collections.abc import AsyncGenerator

import ollama

from vigilant.config import settings

SYSTEM_PROMPT = "You are the cybersecurity AI agent for the VIGILANT project."


class LLMService:
    """Service to handle communication with the local LLM via Ollama."""

    def __init__(self, host: str | None = None) -> None:
        """Initialize the Ollama async client using centralized settings by default.

        Args:
            host: Optional override for the Ollama base URL. Falls back to
                ``settings.ollama_base_url`` when not provided.
        """
        self.client = ollama.AsyncClient(host=host or settings.ollama_base_url)

    async def generate_stream(self, prompt: str, model: str | None = None) -> AsyncGenerator[str, None]:
        """Stream response tokens from the LLM based on the user prompt.

        Args:
            prompt: The user's input prompt.
            model: The model name requested by the caller. Falls back to
                ``settings.default_llm_model`` when not provided.
        """
        stream = await self.client.chat(
            model=model or settings.default_llm_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            stream=True,
        )

        async for chunk in stream:
            content = chunk.get("message", {}).get("content", "")
            if content:
                yield content
