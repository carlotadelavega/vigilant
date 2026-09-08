from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from vigilant.api.router import api_router
from vigilant.config import settings
from vigilant.mcp.server import mcp

mcp.settings.streamable_http_path = "/"
if mcp.settings.transport_security is not None:
    mcp.settings.transport_security.allowed_hosts.append("vigilant-backend:8000")


def _mcp_session_manager_started() -> bool:
    """Return whether MCP's session manager has already been started.

    MCP does not currently expose this state through a public API. Keep this
    workaround isolated so it is easy to revisit when upgrading the SDK.
    """
    return mcp.session_manager._has_started


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Start the MCP session manager alongside the FastAPI app lifecycle."""
    if _mcp_session_manager_started():
        yield
        return

    async with mcp.session_manager.run():
        yield


app = FastAPI(title=settings.project_name, lifespan=lifespan)
app.include_router(api_router)


@app.get("/mcp/health", include_in_schema=False)
async def mcp_health() -> dict[str, str]:
    """Report that the MCP endpoint is mounted and available."""
    return {"status": "ok"}


app.mount("/mcp", mcp.streamable_http_app())


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe endpoint."""
    return {"status": "ok"}
