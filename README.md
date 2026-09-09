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
make ollama-model # list Ollama models and pull qwen2.5:14b if none are installed
make up-ui         # core stack + temporary Open WebUI dev frontend, on :3000
make test
make lint
```

### GPU requirements (NVIDIA)

Hermes Agent enforces a **hard minimum of 64K tokens of context** on the
configured model (`agent_init.py::_enforce_minimum_context`) — this is not
configurable below that value, regardless of `hermes/config.yaml`. Running
`qwen2.5:14b` at a 64K context window on CPU is impractically slow (tens of
seconds to minutes per turn just for prefill). **A CUDA-capable GPU is
required** for acceptable latency; without one, expect every request —
including a plain "hola" — to take 30s+.

Setup steps on the host:

1. Install the NVIDIA Container Toolkit and register the `nvidia` runtime
   with Docker:

   ```bash
   curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
     sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
   curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
     sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
     sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

   sudo apt-get update
   sudo apt-get install -y nvidia-container-toolkit
   sudo nvidia-ctk runtime configure --runtime=docker
   sudo systemctl restart docker
   ```

2. Verify the runtime is registered:

   ```bash
   docker info | grep -i runtime
   # Should list: nvidia
   ```

3. Smoke-test GPU access from a container:

   ```bash
   docker run --rm --gpus all nvidia/cuda:12.6.0-base-ubuntu24.04 nvidia-smi
   ```

The `ollama` service in `docker-compose.yml` is already configured with
`runtime: nvidia` plus a `deploy.resources.reservations.devices` GPU
reservation (kept for compatibility across Compose versions), so no further
compose changes should be needed once the host-level runtime is registered.

Confirm GPU offload is actually happening by checking Ollama's logs after a
request:

```bash
docker compose logs ollama --tail=50 | grep -i "offload\|inference compute"
# Expect: "offloaded 49/49 layers to GPU" and library=CUDA
```

### Performance-relevant env vars (ollama service)

| Variable | Value | Why |
|---|---|---|
| `OLLAMA_KEEP_ALIVE` | `24h` | Without this, Ollama unloads the model after 5 min of inactivity, forcing a full reload (~30-40s) on the next request. |
| `OLLAMA_FLASH_ATTENTION` | `1` | Required to enable KV-cache quantization; also speeds up prefill on long contexts. |
| `OLLAMA_KV_CACHE_TYPE` | `q8_0` | Roughly halves KV-cache memory at 64K context vs. f16, with minimal quality loss. |

With GPU offload + the settings above, a warm request at the enforced 64K
context (~10.5K tokens of fixed prompt overhead from Hermes's system prompt
and tool schemas) completes in ~1.6s on an NVIDIA GB10. A cold request (model
not yet loaded) still costs ~30-40s once, until `OLLAMA_KEEP_ALIVE` keeps it
resident.

### Ollama models

List the models installed in the Ollama container:

```bash
docker exec -it vigilant-ollama ollama list
```

If the list is empty, download a model by replacing `<nombre-modelo>` as needed:

```bash
docker exec -it vigilant-ollama ollama pull <nombre-modelo>
```

The `make ollama-model` target uses `qwen2.5:14b` by default. To select another
model, pass `OLLAMA_MODEL`:

```bash
make ollama-model OLLAMA_MODEL=<nombre-modelo>
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
