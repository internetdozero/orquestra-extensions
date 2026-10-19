# session-relay-mcp

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-stdio-6B4FBB.svg)](https://modelcontextprotocol.io)

Pass the baton between AI coding agents. `session-relay-mcp` reads the session
stores that Codex, Claude Code, Antigravity, OpenCode, Freebuff and Grok already
keep on your machine and turns them into inspectable history plus a one-call
handoff brief — no cloud service and no copy-pasting context between agents.

## Why

Every harness writes its own private session format. When one agent gets stuck,
the next one starts blind: what was the goal, which files changed, what failed?
This MCP server answers those questions from local files, so an operator or a
different agent can resume the work immediately.

- **Cross-harness** — one interface over six local stores.
- **Strictly read-only** — SQLite is opened `mode=ro` with `query_only`, JSONL
  and JSON are only read. Stores are fingerprinted in tests to prove nothing is
  written.
- **Baton-pass brief** — `handoff_context` returns Goal, Files touched, Last
  observed state, Blocker and Suggested next steps as markdown.
- **Bounded** — giant Freebuff chats (hundreds of MB) are read from a capped
  tail; search has a byte budget.

## Supported harnesses

| Harness | Source | Notes |
| --- | --- | --- |
| Codex | `~/.codex/thread_history_1.sqlite` | Turns, messages, shell/file/MCP tool items, turn errors |
| Claude Code | `~/.claude/projects/*/*.jsonl` | User/assistant turns, tool_use and tool_result blocks |
| Antigravity | `~/.gemini/antigravity/brain/*/.system_generated/logs/transcript.jsonl` | Planner responses, tool calls, error messages |
| OpenCode | `~/.local/share/opencode/opencode.db` | Sessions, messages, text/tool/patch parts |
| Freebuff / Manicode | `~/.config/manicode/projects/*/chats/*/chat-messages.json` | Chat blocks and tool calls; falls back to `message-history.json` |
| Grok | `~/.grok/sessions/session_search.sqlite` + `prompt_history.jsonl` | Prompt history and search index; Grok stores no tool events there |

Missing or empty stores return friendly empty states with warnings instead of
errors.

## Install

```bash
pipx install .
# or
uv tool install .
# or a plain virtual environment
python3 -m venv .venv && .venv/bin/pip install .
```

Installing exposes the `session-relay` console script; `python3 -m
session_relay.server` works without it.

## MCP client setup

The server speaks MCP over stdio and needs no arguments.

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "session-relay": { "command": "session-relay", "args": [] }
  }
}
```

**Codex** (`~/.codex/config.toml`):

```toml
[mcp_servers.session-relay]
command = "session-relay"
args = []
```

**Cursor** (`~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "session-relay": { "command": "session-relay", "args": [] }
  }
}
```

**Antigravity** (`~/.gemini/config/mcp_config.json`):

```json
{
  "mcpServers": {
    "session-relay": { "command": "session-relay", "args": [] }
  }
}
```

**OrquestraAI** (`~/.orquestra/mcps.json`):

```json
"session-relay": {
  "id": "session-relay",
  "name": "Session Relay (Cross-Harness)",
  "description": "Read-only cross-harness session inspection and handoff briefs.",
  "command": "session-relay",
  "args": [],
  "env": {},
  "globalEnabled": true,
  "enabledHarnesses": []
}
```

## Tools

| Tool | Inputs | Returns |
| --- | --- | --- |
| `list_recent_sessions` | `harness?`, `limit?` (default 5) | `{count, sessions[], warnings[]}` newest first |
| `inspect_session` | `harness`, `session_id?` (default `latest`), `max_turns?` (default 10) | `{session, event_count, events[]}` |
| `handoff_context` | `source_harness`, `session_id?` | Markdown brief with goal, files, state, blocker and next steps |
| `search_sessions_history` | `query`, `harness?`, `limit?` (default 10) | `{query, count, hits[], warnings[]}` with snippets |

Harness ids: `codex`, `claude`, `antigravity`, `opencode`, `freebuff`, `grok`
(aliases: `claude-code`, `gemini`, `manicode`, `open-code`, `xai`).

## Example workflow

```text
list_recent_sessions(limit=5)
inspect_session(harness="codex", session_id="latest", max_turns=3)
handoff_context(source_harness="codex")
search_sessions_history(query="deploy", harness="claude")
```

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `SESSION_RELAY_HOME` | `$HOME` | Alternate home root, useful for fixtures and tests |

No configuration is required for normal use.

## Known limits

- Freebuff chats over 16 MB expose only their last 12 MB; turn counts above
  4 MB fall back to the chat's recorded message count.
- Grok's local index contains prompts, not assistant or tool events, so its
  briefs are goal-focused.
- Codex search scans item text in a large database; expect a few hundred
  milliseconds on very large histories.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e . pytest
.venv/bin/python -m pytest tests/ -q
bash scripts/check-file-size.sh
```

## License

MIT — see [LICENSE](LICENSE).
