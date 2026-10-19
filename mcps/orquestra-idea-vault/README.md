# idea-vault-mcp

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-stdio-6B4FBB.svg)](https://modelcontextprotocol.io)

A local, zero-network idea vault and inter-agent blackboard exposed as a Model
Context Protocol server. One SQLite file, eight tools, no Notion, no cloud
account and no background service.

## Why

Capturing a thought should not cost a browser tab, an API key or a
subscription. `idea-vault-mcp` gives every MCP-capable agent on your machine the
same fast scratchpad and a shared note board, backed by a single SQLite file
under `~/.local/share/idea-vault/ideas.sqlite3`.

- **Instant** — a tool call is a local SQLite write or read (single-digit
  milliseconds); WAL mode keeps concurrent agents from blocking each other.
- **Zero infrastructure** — only the Python standard library `sqlite3` plus the
  official `mcp` SDK.
- **Two capabilities** — a durable idea vault and an asynchronous blackboard for
  hand-offs between agents working at the same time.
- **Readable output** — structured JSON results and one-call markdown export
  grouped by category.

## Install

From this repository:

```bash
pipx install .
# or
uv tool install .
# or a plain virtual environment
python3 -m venv .venv && .venv/bin/pip install .
```

Installing exposes the `idea-vault` console script. You can also run the module
directly:

```bash
python3 -m idea_vault.server
```

## MCP client setup

The server speaks MCP over stdio and takes no required arguments.

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "idea-vault": {
      "command": "idea-vault",
      "args": []
    }
  }
}
```

**Codex** (`~/.codex/config.toml`):

```toml
[mcp_servers.idea-vault]
command = "idea-vault"
args = []
```

**Cursor** (`~/.cursor/mcp.json` or `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "idea-vault": { "command": "idea-vault", "args": [] }
  }
}
```

**Antigravity** (`~/.gemini/config/mcp_config.json`):

```json
{
  "mcpServers": {
    "idea-vault": { "command": "idea-vault", "args": [] }
  }
}
```

**OrquestraAI** (`~/.orquestra/mcps.json`):

```json
"idea-vault": {
  "id": "idea-vault",
  "name": "Idea Vault (Local SQLite)",
  "description": "Local SQLite idea capture plus inter-agent blackboard.",
  "command": "idea-vault",
  "args": [],
  "env": {},
  "globalEnabled": true,
  "enabledHarnesses": []
}
```

If `idea-vault` is not on `PATH`, use
`"command": "python3", "args": ["-m", "idea_vault.server"]` instead.

## Tools

| Tool | Inputs | Returns |
| --- | --- | --- |
| `record_idea` | `project`, `title`, `description?`, `category?`, `priority?`, `tags?` | Stored idea with `id` and a confirmation message |
| `list_ideas` | `project?`, `status?` (default `open`), `category?`, `priority?` | `{count, status, ideas[]}` ordered by priority |
| `search_ideas` | `query`, `project?` | `{query, count, ideas[]}` matching title, description or tags |
| `update_idea_status` | `idea_id`, `status` | Updated idea, or a not-found error |
| `export_ideas_markdown` | `project` | `{project, count, markdown}` grouped by category |
| `post_board_note` | `project`, `topic`, `note`, `sender?`, `target?` | Stored note with `id` |
| `read_board_notes` | `project`, `topic?`, `unread_only?`, `mark_as_read?`, `target?` | `{count, notes[]}` |
| `clear_board_notes` | `project`, `topic?`, `include_unread?` | `{deleted, scope, message}` |

Allowed values: `category` is `feature`, `architecture`, `bug`, `ux` or `idea`;
`priority` is `low`, `medium`, `high` or `critical`; `status` is `open`,
`in_progress`, `completed` or `archived`. `tags` accepts a list or a
comma-separated string and is stored as JSON.

## Example workflow

```text
record_idea(project="OrquestraAI", title="Cache tray render", category="ux",
            priority="high", tags=["tray", "perf"])
post_board_note(project="OrquestraAI", topic="contract",
                note="IPC field names are frozen; update the frontend first.",
                sender="claude-code", target="all")
read_board_notes(project="OrquestraAI", mark_as_read=True)
export_ideas_markdown(project="OrquestraAI")
```

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `IDEA_VAULT_DB_PATH` | `~/.local/share/idea-vault/ideas.sqlite3` | Database file; parent directories and schema are created on startup |

Both tables (`ideas` and `blackboard_notes`) are created automatically. The
database stores only local text; nothing leaves the machine.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e . pytest
.venv/bin/python -m pytest tests/ -q
bash scripts/check-file-size.sh
```

## License

MIT — see [LICENSE](LICENSE).
