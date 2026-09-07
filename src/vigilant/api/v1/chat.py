"""OpenAI-compatible chat completion endpoints backed by the VIGILANT LLM service."""

import json
import time
from collections.abc import AsyncGenerator
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from vigilant.config import settings
from vigilant.services.llm_service import LLMService

router = APIRouter()
llm_service = LLMService()


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


class ChatMessageResponse(BaseModel):
    """Assistant message returned in a non-streaming chat completion."""

    role: Literal["assistant"] = "assistant"
    content: str


class ChatCompletionChoice(BaseModel):
    """A single completion choice."""

    index: int
    message: ChatMessageResponse
    finish_reason: str


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible non-streaming chat completion response."""

    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]


@router.get("/models")
async def list_models() -> ModelList:
    """Fetch available models dynamically from the local Ollama instance."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{settings.ollama_base_url}/api/tags")
            if response.status_code != 200:
                raise HTTPException(status_code=502, detail="Failed to fetch models from Ollama")

            ollama_data = response.json()

            models_list: list[ModelInfo] = [
                ModelInfo(
                    id=model["name"],
                    created=int(time.time()),
                    owned_by="ollama",
                )
                for model in ollama_data.get("models", [])
            ]

            return ModelList(data=models_list)
    except httpx.RequestError:
        return ModelList(
            data=[
                ModelInfo(
                    id=settings.default_llm_model,
                    created=int(time.time()),
                    owned_by="vigilant-fallback",
                )
            ]
        )


async def vigilant_agent_stream(user_prompt: str, model_name: str) -> AsyncGenerator[str, None]:
    """Stream real token responses from the VIGILANT LLM service using Server-Sent Events.

    Args:
        user_prompt: The last user message content to send to the LLM.
        model_name: The model requested by the client, echoed back in each chunk
            and forwarded to the underlying Ollama call.
    """
    request_id = f"chatcmpl-{int(time.time())}"
    created_time = int(time.time())

    async for token in llm_service.generate_stream(user_prompt, model=model_name):
        chunk = {
            "id": request_id,
            "object": "chat.completion.chunk",
            "created": created_time,
            "model": model_name,
            "choices": [{"index": 0, "delta": {"content": token}, "finish_reason": None}],
        }
        yield f"data: {json.dumps(chunk)}\n\n"

    final_chunk = {
        "id": request_id,
        "object": "chat.completion.chunk",
        "created": created_time,
        "model": model_name,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    yield f"data: {json.dumps(final_chunk)}\n\n"
    yield "data: [DONE]\n\n"


@router.post("/chat/completions", response_model=None)
async def chat_completions(request: ChatCompletionRequest) -> StreamingResponse | ChatCompletionResponse:
    """Handle chat completion requests using the real VIGILANT agent pipeline."""
    if not request.messages:
        raise HTTPException(status_code=400, detail="No messages provided.")

    last_user_message = request.messages[-1].content

    if request.stream:
        return StreamingResponse(
            vigilant_agent_stream(last_user_message, request.model),
            media_type="text/event-stream",
        )

    return ChatCompletionResponse(
        id=f"chatcmpl-{int(time.time())}",
        created=int(time.time()),
        model=request.model,
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatMessageResponse(content="[VIGILANT]: Please enable streaming in Open WebUI."),
                finish_reason="stop",
            )
        ],
    )
