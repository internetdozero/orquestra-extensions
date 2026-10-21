# AGENTS.md

file_size_cap: 400
file_size_soft: 300

Those two lines are the size rule. Count with `wc -l`. A hand-written file at the soft number gets no new behavior; split it first. A file over the cap is a broken tree. Generated files, lockfiles, and vendored code are outside the cap.

## What this is

`janitor-mcp` is a local MCP server that reports Linux system health (RAM, swap, `/tmp` tmpfs), reaps orphaned development workers safely and cleans stale transient caches.

## Layout

The entry point only wires modules. A module is split once it owns two capabilities.

- `janitor/health.py` — RAM/swap from `/proc/meminfo`, `/tmp` tmpfs use, CPU load, top-5 RSS processes, alert flag.
- `janitor/orphans.py` — scans this user's `/proc` entries for orphaned dev workers and dead parents, with reasons.
- `janitor/sweep.py` — SIGTERM → 3s → SIGKILL termination behind an immutable protected denylist.
- `janitor/caches.py` — age-gated removal of dead `~/.orquestra/*.sock`, `.codex` staging dirs, `/var/tmp/testing/` scratch.
- `janitor/oom.py` — reads `/proc/<pid>/oom_score{,_adj}` for agent runners and recommends sacrifice priority.
- `janitor/server.py` — MCP tool registration and entry point.
- `janitor/schema.py` — closed target vocabularies published as tool enums.
- `janitor/errors.py` — actionable errors for expected input and system-state failures.
- `tests/` — unit tests; every temporary fixture lives under `/var/tmp/testing/`, never `/tmp`.
- `tests/test_schema.py` — published enums and MCP error behavior.

## Commands

- Check file size: `bash scripts/check-file-size.sh`
- Install: `python3 -m venv .venv && .venv/bin/pip install -e . pytest`
- Run: `.venv/bin/python3 -m janitor.server` (stdio MCP)
- Test: `.venv/bin/python3 -m pytest tests/ -q`

## While editing

- Read this file before adding code.
- Import only a module's public surface.
- A section banner inside a file means it is already two modules.
- Never write, test or sandbox anything in `/tmp/`; use `/var/tmp/testing/`.
- Never kill denylisted processes (session leaders, shells, compositors, OrquestraAI); the denylist in `sweep.py` is immutable.
- Commit each coherent slice locally. Do not push unless asked.