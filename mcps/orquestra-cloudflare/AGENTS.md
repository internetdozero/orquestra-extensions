# AGENTS.md

file_size_cap: 300
file_size_soft: 250

Those two lines are the size rule. Count with `wc -l`. A hand-written file at the
soft number gets no new behavior; split it first. A file over the cap is a broken
tree. Generated files, lockfiles and vendored code are outside the cap.

## What this is

`cloudflare-mcp` is a Model Context Protocol server that replaces fragmented
Cloudflare markdown references with deterministic, typed tool calls for D1 SQL,
Workers, KV, R2, DNS and on-demand documentation search.

## Layout

Group by capability. The entry point only wires tool bodies to modules.

- `cloudflare_mcp/config.py` — env settings, zone map parsing, token masking.
- `cloudflare_mcp/client.py` — Cloudflare v4 REST client (retries, pagination,
  envelopes).
- `cloudflare_mcp/wrangler.py` — wrangler config discovery/parsing and the local
  CLI runner used as the no-token fallback.
- `cloudflare_mcp/result.py` — the `ToolResult` envelope and the `safe` wrapper.
- `cloudflare_mcp/d1.py` — D1 inventory, SQL execution, schema inspection.
- `cloudflare_mcp/workers.py` — worker inventory, routes, deployments, tail.
- `cloudflare_mcp/storage.py` — KV namespaces/values and R2 buckets/objects.
- `cloudflare_mcp/dns.py` — zones and DNS record CRUD.
- `cloudflare_mcp/docs.py` — bundled corpus plus local markdown scoring.
- `cloudflare_mcp/data/docs_index.json` — the bundled documentation corpus
  (data, so it is outside the size cap and shipped via a hatch force-include).
- `cloudflare_mcp/server.py` — MCP tool registrations and the stdio entry point.
- `shim/cloudflare-mcp` — console shim installed into `~/.local/bin`.
- `tests/` — fake Cloudflare API, per-module tests (incl. `test_wrangler.py`)
  and the MCP wiring test.

## Commands

- Check file size: `bash scripts/check-file-size.sh`
- Install (isolated runtime at `~/.local/share/cloudflare-mcp/runtime`):
  `python3 -m venv ~/.local/share/cloudflare-mcp/runtime && ~/.local/share/cloudflare-mcp/runtime/bin/pip install ".[dev]"`
- Install the shim: `install -m 0755 shim/cloudflare-mcp ~/.local/bin/cloudflare-mcp`
- Run: `~/.local/bin/cloudflare-mcp` (stdio MCP)
- Test: `TMPDIR=/var/tmp/testing ~/.local/share/cloudflare-mcp/runtime/bin/pytest`

## Safety

- Never use `/tmp` (RAM-backed). Scratch files and tests use `/var/tmp/testing`.
- Credentials come from the environment only. Tokens are masked in every tool
  output (`mask_token`), never logged and never written to a config file.
- Reads are safe by default; `cf_kv_set` and `cf_dns_upsert` are the only writers,
  and `cf_dns_upsert` is idempotent by record type + name.

## While editing

- Read this file before adding code.
- A section banner inside a file means it is already two modules.
- Keep every tool returning the `ToolResult` envelope; a bare `list` annotation
  breaks the SDK's output-schema validation at call time.
