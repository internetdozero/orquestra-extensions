# janitor-mcp

Linux system health, orphan-process sweeper and transient cache cleaner for
agentic workspaces, exposed as a local MCP server (stdio, no network).

Reports RAM/swap/`/tmp` tmpfs pressure, detects orphaned development workers
(headless browsers, dead agent runners, detached compilers), sweeps them behind
an immutable protected denylist (SIGTERM → 3s → SIGKILL, `dry_run` by default)
and removes age-gated stale sockets and scratch caches.

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python3 -m janitor.server   # stdio MCP (same as the `janitor` script)
```

## Test

```bash
.venv/bin/pip install -e . pytest
.venv/bin/python3 -m pytest tests/ -q
bash scripts/check-file-size.sh
```

## Installed console shim

`~/.local/bin/janitor` points at the isolated runtime
`~/.local/share/janitor-mcp/runtime`, independent of this checkout. It is
registered as `janitor` in `~/.orquestra/mcps.json`; `orquestra --mcp-deploy`
compiles it into every harness config.

## Storage rule

Never create files in `/tmp/` (it is RAM-backed tmpfs here); all scratch must
live under `/var/tmp/testing/`.

## License

MIT — see [LICENSE](LICENSE).