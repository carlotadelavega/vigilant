---
name: pcap-analysis
description: Use whenever the user asks to analyze, inspect, or investigate a network capture (.pcap/.pcapng) attached to the conversation via VIGILANT. Covers requests like "analiza este pcap", "revisa esta captura de tráfico", "busca actividad sospechosa en este fichero de red". Do NOT call analyze_pcap_file directly with a path guessed from the prompt — it will fail, since VIGILANT never accepts attacker-controlled paths directly.
---

# VIGILANT pcap analysis

Analyzing a network capture through VIGILANT is a mandatory two-step tool
sequence. Do not skip step 1, and never attempt to construct a filesystem
path, encode attachment bytes, or fetch a resource yourself.

Any pcap/pcapng attachment is staged by vigilant-backend before your turn
even starts: the raw binary content is written to disk in code, and you
only ever see a short text marker in the conversation, e.g.:

    [pcap attachment staged: pcap_ref=3f9a2b7c1e4d4a9f8b6c0d1e2f3a4b5c, filename=arp-icmp.pcapng]

That `pcap_ref` value is the only thing you need — pass it through
verbatim, exactly as written, to the ingest tool. Do not modify it, do not
try to decode/re-encode it, and do not attempt to read or transcribe the
attachment's binary content yourself under any circumstance.

## Steps

1. **Ingest** — find the `pcap_ref=...` marker in the conversation and
   call `mcp__vigilant_network__ingest_pcap` with `pcap_ref` set to that
   exact token. This resolves the staged attachment, validates it is a
   genuine pcap/pcapng file, and materializes it in VIGILANT's quarantine
   directory.

   - If no `pcap_ref=...` marker is present in the conversation, there is
     no attachment for VIGILANT to analyze — say so and ask the user to
     attach a capture file, rather than guessing or proceeding.
   - If the result has `"ok": false`, stop and report the `reason` field
     in plain terms: `ref_not_found` → "no encuentro el adjunto, puede
     que haya expirado o ya se haya procesado"; `invalid_magic_bytes` →
     "el fichero no parece ser un pcap/pcapng válido"; `exceeds_max_size`
     → "el fichero supera el límite permitido"; `invalid_ref` → "la
     referencia del adjunto no es válida". Do not retry with a guessed
     path or ref, and do not fall back to any other tool (execute_code,
     tshark, filesystem tools, etc.).

2. **Analyze** — only if step 1 returned `"ok": true`, call
   `mcp__vigilant_network__analyze_pcap_file` with `pcap_path` set to the
   exact `quarantined_path` value returned by step 1. Pass through
   `top_n`/`verbose` if the user specified preferences; otherwise use the
   tool defaults.

   - The quarantined file is deleted automatically right after this call,
     so step 2 can only run once per `pcap_ref`. A `pcap_ref` is also
     single-use at the staging layer — if the user wants another pass at
     the same capture, ask them to re-attach it.

3. **Report** — summarize the structured result for the user (top actors,
   protocols, conversations, and especially any IP with more than one
   associated MAC under `ip_mac_relations`, which indicates possible ARP
   spoofing). Do not paste the raw JSON verbatim; translate it into a
   short, technically precise summary.

## Explicit non-goals

- Never call `analyze_pcap_file` with a path taken from the user prompt
  or any path you construct yourself.
- Never call `mcp__vigilant_network__list_resources` or `read_resource`
  as part of this flow — the attachment is not an MCP server resource.
- Never attempt to read, quote, encode, or transcribe the attachment's
  binary content yourself; you cannot do this reliably, and it is not
  needed — the `pcap_ref` marker is sufficient.
- Never fall back to `execute_code`, `tshark`, `tcpdump`, filesystem MCP
  tools, or shell commands to work around a failed ingest or analyze
  call. Report the structured error instead.
- If `ingest_pcap` is not present in the current tool list, say so
  plainly and stop.