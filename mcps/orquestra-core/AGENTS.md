# AGENTS.md

file_size_cap: 400
file_size_soft: 300

Those two lines are the size rule. Count with `wc -l`. A hand-written file at the soft number gets no new behavior; split it first. A file over the cap is a broken tree. Generated files, lockfiles, and vendored code are outside the cap.

## What this is

`orquestra-core-mcp` is a local MCP server that exposes the OrquestraAI control plane to any agent: skill activation, MCP server toggles, fleet bridge state and the master `AGENTS.md`.

## Layout

The entry point only wires modules. A module is split once it owns two capabilities.

- `orquestra_core/paths.py` — `~/.orquestra` layout resolution, scope validation, native binary discovery.
- `orquestra_core/skills.py` — `SKILL.md` metadata and token estimates, symlink projection into `active/<scope>`.
- `orquestra_core/skill_admin.py` — skill creation in the vault and archive-on-delete.
- `orquestra_core/fsutil.py` — atomic text writes, timestamped backups, collision-free names.
- `orquestra_core/bridge.py` — subprocess wrapper around the native `orquestra` binary and its JSON reports.
- `orquestra_core/fleet.py` — condenses `--bridge-status` output for the fleet tool; delegates `--bridge-deploy`.
- `orquestra_core/catalog.py` — reads `mcps.json`, saves it atomically, toggles through `--mcp-set` plus `--mcp-deploy`.
- `orquestra_core/catalog_admin.py` — registers and retires MCP servers, then redeploys.
- `orquestra_core/instructions.py` — master `AGENTS.md` reads, section-scoped appends, backups, atomic writes.
- `orquestra_core/presets.py` — built-in preset definitions, merge with custom `presets.json`, delegate apply to bridge.
- `orquestra_core/server.py` — MCP entrypoint: registers tools, parses args, runs stdio transport.
- `tests/conftest.py` — throwaway `ORQUESTRA_HOME` fixture with a fake native binary.
- `tests/test_core.py` — skills, catalog, instructions and bridge behavior.
- `tests/test_lifecycle.py` — skill and MCP creation, archival and removal.
- `tests/test_presets.py` — preset listing, apply (happy path + validation), unknown-id errors, bridge deploy.

## Commands

- Check file size: `bash scripts/check-file-size.sh`
- Install: `python3 -m venv .venv && .venv/bin/pip install -e . pytest`
- Run: `.venv/bin/python3 -m orquestra_core.server` (stdio MCP)
- Test: `.venv/bin/python3 -m pytest tests/ -q`

## Data

Everything lives under `~/.orquestra` and is discovered, never hard-coded:

- `skills-library/<id>/SKILL.md` — master vault.
- `active/global/<id>` and `active/<harness>/<id>` — symlinks the harnesses read.
- `mcps.json` — the MCP catalog OrquestraAI compiles into every harness config.
- `AGENTS.md` — master instructions symlinked into each harness.

`ORQUESTRA_HOME` overrides the root and `ORQUESTRA_BIN` overrides the binary; both exist for tests.

## While editing

- Read this file before adding code.
- Import only a module's public surface.
- Shell out through `bridge.py`; never reimplement OrquestraAI's catalog or deploy logic.
- Writes are atomic and backed up before they replace anything.
- Commit each coherent slice locally. Do not push unless asked.
