from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


class MCPClient:
    """Thin async wrapper for calling tools on a single MCP server over streamable-http."""

    def __init__(self, server_url: str) -> None:
        """Initialize the client for a specific MCP server endpoint.

        Args:
            server_url: Full URL of the target MCP server's streamable-http endpoint,
                e.g. ``http://vigilant-backend:8000/mcp``.
        """
        self._server_url = server_url

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[ClientSession]:
        """Open a short-lived MCP session for a single call."""
        async with streamablehttp_client(self._server_url) as (read, write, _get_session_id):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session

    async def list_tools(self) -> list[str]:
        """Return the names of tools exposed by the target MCP server."""
        async with self._session() as session:
            result = await session.list_tools()
            return [tool.name for tool in result.tools]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Invoke a tool by name on the target MCP server and return its raw result content.

        Args:
            name: Tool name as registered on the MCP server.
            arguments: JSON-serializable arguments matching the tool's input schema.
        """
        async with self._session() as session:
            result = await session.call_tool(name, arguments)
            return result.content
