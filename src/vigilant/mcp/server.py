"""Minimal Network MCP server (VIG-108).

Exposes VIGILANT's network-related tools over MCP for consumption by both
Hermes (at reasoning time) and FastAPI's own MCPClient (for direct calls).
For the MVP this ships a single placeholder tool; real network tools
(topology lookup, asset inventory, etc.) land here per the target architecture.
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("vigilant-network")


@mcp.tool()
async def ping() -> str:
    """Health-check tool used to verify MCP connectivity (Hermes <-> VIGILANT, FastAPI <-> VIGILANT)."""
    return "pong"


# Future network tools, per the target architecture:
# @mcp.tool()
# async def get_network_topology() -> dict[str, Any]: ...
# @mcp.tool()
# async def list_assets(subnet: str | None = None) -> list[dict[str, Any]]: ...


def main() -> None:
    """Entrypoint for running the MCP server over stdio (local Hermes profile)."""
    mcp.run()


if __name__ == "__main__":
    main()
