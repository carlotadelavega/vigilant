from typing import Any

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from vigilant.mcp.server import mcp


async def test_ping_tool_returns_pong() -> None:
    """The ping tool should confirm connectivity by returning 'pong'."""
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("ping", {})

        assert result.content[0].text == "pong"  # type: ignore[union-attr]


def test_main_runs_mcp_server(monkeypatch: pytest.MonkeyPatch) -> None:
    """The console entrypoint should start MCP over its default transport."""
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def fake_run(*args: Any, **kwargs: Any) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr(mcp, "run", fake_run)

    from vigilant.mcp.server import main

    main()

    assert calls == [((), {})]
