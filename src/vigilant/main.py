from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from vigilant.api.router import api_router
from vigilant.config import settings
from vigilant.mcp.server import mcp


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Start the MCP session manager alongside the FastAPI app lifecycle."""
    if mcp.session_manager._has_started:
        yield
        return

    async with mcp.session_manager.run():
        yield


app = FastAPI(title=settings.project_name, lifespan=lifespan)
app.include_router(api_router)


@app.get("/mcp", include_in_schema=False)
async def mcp_health() -> dict[str, str]:
    """Report that the MCP endpoint is mounted and available."""
    return {"status": "ok"}


app.mount("/mcp", mcp.streamable_http_app())


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe endpoint."""
    return {"status": "ok"}
