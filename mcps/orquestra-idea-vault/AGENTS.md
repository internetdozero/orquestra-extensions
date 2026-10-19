# AGENTS.md

file_size_cap: 400
file_size_soft: 300

Those two lines are the size rule. Count with `wc -l`. A hand-written file at the soft number gets no new behavior; split it first. A file over the cap is a broken tree. Generated files, lockfiles, and vendored code are outside the cap.

## What this is

`idea-vault-mcp` is a local MCP server exposing a SQLite idea vault and an inter-agent blackboard over stdio.

## Layout

Group by capability. The entry point only wires modules. A shared module exists only after a second capability needs the same behavior.

- `idea_vault/store.py` — database path resolution, connection, schema bootstrap, value validation.
- `idea_vault/ideas.py` — idea CRUD, filtered listing, search, markdown export.
- `idea_vault/blackboard.py` — async collaboration notes between agents.
- `idea_vault/serializers.py` — rows to dicts, tag parsing/serialization.
- `idea_vault/server.py` — MCP entrypoint: registers tools, parses args, runs stdio transport.
- `tests/conftest.py` — shared throwaway-vault fixtures.
- `tests/test_vault.py` — schema, idea CRUD, search and export tests.
- `tests/test_blackboard.py` — blackboard messaging, MCP registration and path wiring tests.

## Commands

- Check file size: `bash scripts/check-file-size.sh`
- Install: `python3 -m venv .venv && .venv/bin/pip install -e . pytest`
- Run: `.venv/bin/python3 -m idea_vault.server` (stdio MCP)
- Test: `.venv/bin/python3 -m pytest tests/ -q`

## Data

Default database: `~/.local/share/idea-vault/ideas.sqlite3` (override with `IDEA_VAULT_DB_PATH` or `--db`).

## While editing

- Read this file before adding code.
- Import only a module's public surface.
- A section banner inside a file means it is already two modules.
- A nested AGENTS.md is only for a subtree with different commands or a different cap. The closest file wins.
- Commit each coherent slice locally. Do not push unless asked.
