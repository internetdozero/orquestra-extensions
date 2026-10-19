# cloudflare-mcp

Unified **Model Context Protocol** server for Cloudflare infrastructure. It replaces
fragmented reference markdown (and ad-hoc `wrangler` guessing) with deterministic,
typed tool calls:

| Tool | Purpose |
| --- | --- |
| `cf_system_status` | Verify auth, account id, zone map and capability reachability |
| `cf_d1_query` | Execute SQL against a named D1 database (rows, changes, duration) |
| `cf_d1_list_databases` | List D1 databases with ids and creation timestamps |
| `cf_d1_schema` | Table/view DDL for a database, optionally a single table |
| `cf_list_workers` | Workers with environments, routes, deployments, modified dates |
| `cf_kv_get` / `cf_kv_set` | Read/write Workers KV keys (ttl + metadata) |
| `cf_r2_list_buckets` | List R2 buckets (cursor pagination) |
| `cf_dns_list` / `cf_dns_upsert` | DNS record query + idempotent create/update |
| `cf_search_docs` | On-demand documentation/snippet lookup (keeps context clean) |

## Architecture

```
cloudflare_mcp/
  config.py    environment configuration + zone mapping + token masking
  client.py    Cloudflare v4 REST client (retries, pagination)
  wrangler.py  wrangler config discovery/parsing + local CLI fallback runner
  result.py    the {ok, result|error} envelope and the safe() wrapper
  data/        bundled documentation corpus (shipped as package data)
  d1.py        D1 listing, SQL execution, schema inspection
  workers.py   Worker inventory, routes, deployments, wrangler tail
  storage.py   KV and R2 operations
  dns.py       Zones and DNS record CRUD
  docs.py      Keyword/semantic scoring over a bundled corpus + local markdown dirs
  server.py    MCP tool definitions and stdio entry point
```

Every file stays well under the 300-400 line limit; tools return a stable
`{"ok": bool, "result" | "error"}` envelope.

## Configuration

| Variable | Meaning |
| --- | --- |
| `CLOUDFLARE_API_TOKEN` | API token (never printed, only last 4 chars in status) |
| `CLOUDFLARE_ACCOUNT_ID` | Account id used for account scoped endpoints |
| `CLOUDFLARE_ZONE_MAP` | `{"example.com": "<zone_id>"}` or `example.com=<zone_id>,...` |
| `CLOUDFLARE_API_BASE` | Override API base (defaults to v4 endpoint) |
| `CLOUDFLARE_MCP_TIMEOUT` / `CLOUDFLARE_MCP_RETRIES` | HTTP timeout / retry budget |
| `CLOUDFLARE_MCP_WRANGLER_FALLBACK` | `0` disables the local `wrangler` fallback |
| `CLOUDFLARE_MCP_DOCS_DIRS` | `os.pathsep` separated markdown dirs indexed for `cf_search_docs` |

When no token is configured but a local `wrangler.toml|json|jsonc` exists, D1 and
Worker operations fall back to the local `wrangler` CLI.

## Install

```bash
python3 -m venv ~/.local/share/cloudflare-mcp/runtime
~/.local/share/cloudflare-mcp/runtime/bin/pip install ".[dev]"
install -m 0755 shim/cloudflare-mcp ~/.local/bin/cloudflare-mcp
```

## Tests

```bash
TMPDIR=/var/tmp/testing ~/.local/share/cloudflare-mcp/runtime/bin/pytest
```

Tests mock all Cloudflare API traffic (no network, no tokens) and run scratch
files under `/var/tmp/testing` only — never `/tmp`.