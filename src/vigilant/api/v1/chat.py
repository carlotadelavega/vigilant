import json
import time
from collections.abc import AsyncGenerator
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from vigilant.config import settings
from vigilant.services.hermes_client import HermesClient, HermesClientError

router = APIRouter()
hermes_client = HermesClient()


class ChatMessage(BaseModel):
    """A single message in a chat completion request."""

    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request payload."""

    model: str
    messages: list[ChatMessage]
    stream: bool = False


class ModelInfo(BaseModel):
    """OpenAI-compatible model descriptor."""

    id: str
    object: Literal["model"] = "model"
    created: int
    owned_by: str


class ModelList(BaseModel):
    """OpenAI-compatible list of available models."""

    object: Literal["list"] = "list"
    data: list[ModelInfo]


@router.get("/models")
async def list_models() -> ModelList:
    """Fetch available models dynamically from Hermes."""
    try:
        hermes_models = await hermes_client.list_models()
        return ModelList(
            data=[
                ModelInfo(
                    id=model["id"],
                    created=model.get("created", int(time.time())),
                    owned_by="hermes",
                )
                for model in hermes_models
            ]
        )
    except (httpx.HTTPError, HermesClientError):  # noqa: BLE001 - Hermes unavailable falls back to a single default entry.
        return ModelList(
            data=[
                ModelInfo(
                    id=settings.default_llm_model,
                    created=int(time.time()),
                    owned_by="vigilant-fallback",
                )
            ]
        )


async def hermes_stream_to_openai_sse(messages: list[dict[str, str]], model_name: str) -> AsyncGenerator[str, None]:
    """Relay Hermes's streamed chat completion chunks to the client as SSE.

    Args:
        messages: OpenAI-format message list forwarded from the client request.
        model_name: The model requested by the client, forwarded to Hermes.
    """
    async for chunk in hermes_client.chat_completion_stream(messages, model=model_name):
        yield f"data: {json.dumps(chunk)}\n\n"
    yield "data: [DONE]\n\n"


@router.post("/chat/completions", response_model=None)
async def chat_completions(request: ChatCompletionRequest) -> StreamingResponse | dict[str, object]:
    """Handle chat completion requests by proxying them to Hermes."""
    if not request.messages:
        raise HTTPException(status_code=400, detail="No messages provided.")

    messages = [message.model_dump() for message in request.messages]

    if request.stream:
        return StreamingResponse(
            hermes_stream_to_openai_sse(messages, request.model),
            media_type="text/event-stream",
        )

    try:
        return await hermes_client.chat_completion(messages, model=request.model)
    except Exception as exc:  # noqa: BLE001 - surfaced as a clean 502 to the client.
        raise HTTPException(status_code=502, detail="Failed to reach Hermes.") from exc
