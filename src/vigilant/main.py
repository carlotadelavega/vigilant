"""FastAPI application entrypoint for the VIGILANT platform."""

from fastapi import FastAPI

from vigilant.api.router import api_router
from vigilant.config import settings

app = FastAPI(title=settings.project_name)
app.include_router(api_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe endpoint."""
    return {"status": "ok"}
