# VIGILANT

Verification of Intent and Generation of Intelligent Logic for Automated actions
against Network and systems security Threats.

## MVP architecture (Fase 1: MVP Vertical)

```
Open WebUI (dev-only) --> vigilant-backend (FastAPI) --> Hermes Agent --> Ollama
                                    |                          |
                                    +---------- MCP -----------+
                                    (Network MCP server + client)
```

- `vigilant-backend` (FastAPI): OpenAI-compatible proxy for the frontend
  (`/v1/chat/completions`, `/v1/models`), forwarding to Hermes. Also hosts the
  minimal Network MCP server at `/mcp` and includes a standalone MCP client
  for direct, non-chat tool calls.
- `hermes`: agentic orchestrator (Nous Research Hermes Agent). Owns model
  selection and MCP-based tool reasoning. Configured via `hermes/config.yaml`.
- `ollama`: local LLM runtime used as Hermes's model provider.
- `open-webui` (docker-compose.dev-ui.yml only): temporary frontend for
  development. Not the target UI — see comments in that file.

## Getting started

```bash
uv lock          # generate/refresh uv.lock (requires network access)
uv sync
make up           # core stack: ollama + hermes + vigilant-backend
make up-ui         # core stack + temporary Open WebUI dev frontend, on :3000
make test
make lint
```

## Project layout

```
src/vigilant/
├── config.py              # Settings (Hermes URL/key, project metadata)
├── main.py                # FastAPI app: mounts api_router (/v1) and MCP (/mcp)
├── api/
│   ├── router.py
│   └── v1/chat.py         # OpenAI-compatible chat proxy -> Hermes
├── services/
│   ├── hermes_client.py   # HTTP client for Hermes's OpenAI-compatible API
│   └── mcp_client.py      # Direct MCP client, independent of the chat flow
└── mcp/
    └── server.py          # Minimal Network MCP server
```
