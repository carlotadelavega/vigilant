from fastapi import APIRouter

from vigilant.api.v1 import chat

api_router = APIRouter()
api_router.include_router(chat.router, prefix="/v1", tags=["OpenAI Compatible Chat"])
