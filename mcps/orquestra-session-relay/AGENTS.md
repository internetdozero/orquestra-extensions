# AGENTS.md

file_size_cap: 300
file_size_soft: 250

Those two lines are the size rule. Count with `wc -l`. A hand-written file at the soft number gets no new behavior; split it first. A file over the cap is a broken tree. Generated files, lockfiles, and vendored code are outside the cap.

## What this is

`session-relay-mcp` exposes read-only, cross-harness session inspection and context handoff over MCP stdio.

## Layout

Group by capability. The entry point only wires modules. A shared module exists only after a second capability needs the same behavior.

- `session_relay/models.py` — session, event and search-hit dataclasses.
- `session_relay/paths.py` — home resolution, env override, timestamp and text helpers.
- `session_relay/discovery.py` — adapter registry and cross-harness recent-session merge.
- `session_relay/handoff.py` — the baton-pass brief synthesizer.
- `session_relay/server.py` — MCP entrypoint and the four tool registrations.
- `session_relay/adapters/base.py` — adapter interface and JSONL/turn helpers.
- `session_relay/adapters/{codex,claude,antigravity,opencode,freebuff,grok}.py` — one read-only adapter per harness storage format.
- `session_relay/adapters/grok_store.py` — Grok folder/subagent discovery and summary metadata.
- `session_relay/adapters/grok_events.py` — Grok chat-history and subagent event mapping.
- `session_relay/adapters/codex_items.py` — Codex thread-item to event mapping.
- `session_relay/adapters/opencode_parts.py` — OpenCode message/part to event mapping.
- `session_relay/adapters/freebuff_store.py` — bounded readers for very large Freebuff chat JSON.
- `session_relay/adapters/freebuff_desktop.py` — read-only Freebuff Desktop v2 SQLite (`desktop:<slug>:<thread-id>` ids, `parts_json` mapping).
- `tests/` — per-adapter fixtures, handoff and MCP wiring tests.

## Commands

- Check file size: `bash scripts/check-file-size.sh`
- Install: `python3 -m venv .venv && .venv/bin/pip install -e . pytest`
- Run: `.venv/bin/python3 -m session_relay.server` (stdio MCP)
- Test: `.venv/bin/python3 -m pytest tests/ -q`

## Safety

Foreign harness session databases and files are opened read-only (`mode=ro`, `query_only`, plain reads). Never write into `~/.codex`, `~/.claude`, `~/.gemini`, `~/.local/share/opencode`, `~/.config/manicode` or `~/.config/freebuff-desktop`.

## While editing

- Read this file before adding code.
- Import only a module's public surface.
- A section banner inside a file means it is already two modules.
- A nested AGENTS.md is only for a subtree with different commands or a different cap. The closest file wins.
- Commit each coherent slice locally. Do not push unless asked.
