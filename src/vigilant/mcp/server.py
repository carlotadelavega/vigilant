from mcp.server.fastmcp import FastMCP

from vigilant.mcp.tools.analyze_pcap import ActorAnalysis, analyze_actors

mcp = FastMCP("vigilant-network")


@mcp.tool()
async def ping() -> str:
    """Health-check tool used to verify MCP connectivity (Hermes <-> VIGILANT, FastAPI <-> VIGILANT)."""
    return "pong"


@mcp.tool()
async def analyze_pcap_file(pcap_path: str, top_n: int = 10, verbose: bool = True) -> ActorAnalysis:
    """Analyze a network traffic log file for suspicious activities."""
    return await analyze_actors(pcap_path, top_n, verbose)


def main() -> None:
    """Entrypoint for running the MCP server over stdio (local Hermes profile)."""
    mcp.run()


if __name__ == "__main__":
    main()
