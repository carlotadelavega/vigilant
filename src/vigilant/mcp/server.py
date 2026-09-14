from __future__ import annotations

import shutil
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from vigilant.mcp.tools.analyze_pcap import ActorAnalysis, analyze_actors
from vigilant.mcp.tools.ingest_pcap import (
    QUARANTINE_ROOT,
    IngestError,
    IngestResult,
    ingest_pcap_ref,
)

mcp = FastMCP("vigilant-network")


@mcp.tool()
async def ping() -> str:
    """Health-check tool used to verify MCP connectivity (Hermes <-> VIGILANT, FastAPI <-> VIGILANT)."""
    return "pong"


@mcp.tool()
async def ingest_pcap(pcap_ref: str) -> IngestResult | IngestError:
    """
    Resolve and validate a staged pcap/pcapng attachment into a
    quarantined local file. Must be called before analyze_pcap_file; its
    output path is the only valid input to analyze_pcap_file.

    pcap_ref: the exact reference from the
    `[pcap attachment staged: pcap_ref=...]` marker. Do not pass raw bytes,
    base64 content, or a filesystem path.
    """
    return await ingest_pcap_ref(pcap_ref)


@mcp.tool()
async def analyze_pcap_file(pcap_path: str, top_n: int = 10, verbose: bool = True) -> ActorAnalysis:
    """
    Analyze a quarantined network traffic capture for suspicious activities.

    `pcap_path` MUST be a path previously returned by `ingest_pcap`; paths
    outside the quarantine root are rejected. The quarantined file (and its
    per-request directory) is deleted immediately after analysis completes,
    regardless of success or failure.
    """
    resolved = Path(pcap_path).resolve()
    quarantine_root_resolved = QUARANTINE_ROOT.resolve()
    if quarantine_root_resolved not in resolved.parents:
        raise ValueError("pcap_path must be a path returned by ingest_pcap")

    try:
        return await analyze_actors(str(resolved), top_n, verbose)
    finally:
        request_dir = resolved.parent
        shutil.rmtree(request_dir, ignore_errors=True)


def main() -> None:
    """Entrypoint for running the MCP server over stdio (local Hermes profile)."""
    mcp.run()


if __name__ == "__main__":
    main()
