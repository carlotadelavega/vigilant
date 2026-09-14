from fastapi import APIRouter

from vigilant.api.v1 import chat, pcap_staging

api_router = APIRouter()
api_router.include_router(chat.router, prefix="/v1", tags=["OpenAI Compatible Chat"])
api_router.include_router(pcap_staging.pcap_router, prefix="/v1", tags=["PCAP Staging"])
