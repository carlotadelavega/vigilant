from pathlib import Path
from typing import Any

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from vigilant.api.v1 import pcap_staging
from vigilant.api.v1.chat_schema import ChatMessage
from vigilant.mcp.server import mcp
from vigilant.mcp.tools import ingest_pcap as ingest_module


async def test_ping_tool_returns_pong() -> None:
    """The ping tool should confirm connectivity by returning 'pong'."""
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("ping", {})

        assert result.content[0].text == "pong"  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_ingest_pcap_resolves_staged_reference(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The MCP argument is the staged reference, not base64 file content."""
    staging_root = tmp_path / "staging"
    quarantine_root = tmp_path / "quarantine"
    monkeypatch.setattr(pcap_staging, "STAGING_ROOT", staging_root)
    monkeypatch.setattr(ingest_module, "STAGING_ROOT", staging_root)
    monkeypatch.setattr(ingest_module, "QUARANTINE_ROOT", quarantine_root)

    capture = Path(__file__).parents[2] / "data/pcaps/arp-icmp.pcapng"
    ref = pcap_staging._stage_bytes(capture.read_bytes())

    result = await ingest_module.ingest_pcap_ref(ref)

    assert result["ok"] is True
    assert Path(result["quarantined_path"]).is_file()  # type: ignore[arg-type]


def test_stage_pcap_attachment_resolves_open_webui_file_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Open WebUI file IDs are resolved from its shared uploads directory."""
    uploads_root = tmp_path / "uploads"
    staging_root = tmp_path / "staging"
    monkeypatch.setattr(pcap_staging, "OPEN_WEBUI_UPLOADS_ROOT", uploads_root)
    monkeypatch.setattr(pcap_staging, "STAGING_ROOT", staging_root)

    capture = Path(__file__).parents[2] / "data/pcaps/arp-icmp.pcapng"
    file_id = "a828a4b2-3023-4603-af46-cfd2e3ec96d5"
    uploads_root.mkdir()
    (uploads_root / f"{file_id}_arp-icmp.pcapng").write_bytes(capture.read_bytes())

    messages = [
        ChatMessage(
            role="user",
            content=[
                {
                    "type": "file",
                    "file": {"file_id": file_id, "filename": "arp-icmp.pcapng"},
                }
            ],
        )
    ]

    staged = pcap_staging.stage_pcap_attachments(messages)

    assert "pcap_ref=" in staged[0]["content"][0]["text"]  # type: ignore[index]


def test_stage_pcap_id_embedded_in_open_webui_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Open WebUI may flatten the attachment into text before proxying it."""
    uploads_root = tmp_path / "uploads"
    staging_root = tmp_path / "staging"
    monkeypatch.setattr(pcap_staging, "OPEN_WEBUI_UPLOADS_ROOT", uploads_root)
    monkeypatch.setattr(pcap_staging, "STAGING_ROOT", staging_root)

    capture = Path(__file__).parents[2] / "data/pcaps/arp-icmp.pcapng"
    file_id = "e0c7984a-c133-4924-926c-ca69cd1f632d"
    uploads_root.mkdir()
    (uploads_root / f"{file_id}_arp-icmp.pcapng").write_bytes(capture.read_bytes())

    messages = [ChatMessage(role="user", content=f"Analiza el archivo {file_id}")]

    staged = pcap_staging.stage_pcap_attachments(messages)

    assert "pcap_ref=" in staged[0]["content"]  # type: ignore[operator]


def test_main_runs_mcp_server(monkeypatch: pytest.MonkeyPatch) -> None:
    """The console entrypoint should start MCP over its default transport."""
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def fake_run(*args: Any, **kwargs: Any) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr(mcp, "run", fake_run)

    from vigilant.mcp.server import main

    main()

    assert calls == [((), {})]
