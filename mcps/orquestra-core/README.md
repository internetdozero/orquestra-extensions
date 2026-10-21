# orquestra-core-mcp

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-stdio-6B4FBB.svg)](https://modelcontextprotocol.io)

An MCP control plane for [OrquestraAI](https://github.com/internetdozero). It lets
an agent change its own harness fleet instead of asking a human to click through a
desktop app: activate skills just in time, flip MCP servers on and off, read the
master `AGENTS.md`, append a mission rule, and check which harnesses are linked.

## Why

Every harness — Codex, Claude Code, Antigravity, OpenCode, Kilo, Copilot, Grok,
Hermes, Freebuff — reads the same three projections under `~/.orquestra`:

```
~/.orquestra/
├── skills-library/<id>/SKILL.md   master vault of every skill
├── active/<scope>/<id>            symlinks the harnesses actually read
├── mcps.json                      catalog compiled into each harness config
└── AGENTS.md                      master instructions, symlinked per harness
```

Editing that tree by hand is fragile: a half-written catalog or a real directory
where a symlink belongs breaks a harness silently. This server performs the same
operations OrquestraAI itself performs — atomic symlink swaps, catalog changes
through the native binary, backed-up instruction edits — and exposes them as MCP
tools with structured results.

- **Just-in-time skills** — enable a skill for one harness, or globally, and it
  is projected into every harness scope immediately.
- **Fleet-aware** — a global toggle fans out to all harness projections, so you
  never leave one harness reading a stale scope.
- **Native delegation** — every catalog change ends in `orquestra
  --mcp-deploy`, so this server cannot drift from OrquestraAI's own
  serializers and the returned `changed` list is the deploy's real answer.
- **Safe writes** — symlinks are created at a temporary name and `os.replace`d;
  `AGENTS.md` is copied to `~/.orquestra/backups/` before an atomic replace.
- **Readable estimates** — each skill reports an approximate token weight so an
  agent can reason about context budget before loading it.

## Install

From this repository:

```bash
python3 -m venv .venv && .venv/bin/pip install .
```

or with pipx / uv:

```bash
pipx install .
uv tool install .
```

Installing exposes the `orquestra-core` console script. You can also run the
module directly: `python3 -m orquestra_core.server`.

Requirements: Python 3.10+, the official `mcp` SDK, and the native `orquestra`
binary on `PATH` for the catalog and fleet tools (`~/.local/bin/orquestra` is
found automatically, `ORQUESTRA_BIN` overrides it).

## MCP client setup

The server speaks MCP over stdio and needs no arguments.

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "orquestra-core": { "command": "orquestra-core", "args": [] }
  }
}
```

**Codex** (`~/.codex/config.toml`):

```toml
[mcp_servers.orquestra-core]
command = "orquestra-core"
args = []
```

**Cursor** (`~/.cursor/mcp.json` or `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "orquestra-core": { "command": "orquestra-core", "args": [] }
  }
}
```

**Antigravity** (`~/.gemini/config/mcp_config.json`):

```json
{
  "mcpServers": {
    "orquestra-core": { "command": "orquestra-core", "args": [] }
  }
}
```

**OrquestraAI** (`~/.orquestra/mcps.json`, then `orquestra --mcp-deploy`):

```json
"orquestra-core": {
  "id": "orquestra-core",
  "name": "Orquestra Core (Control Plane)",
  "description": "Just-in-time skills, MCP toggles, fleet status and master rules.",
  "command": "orquestra-core",
  "args": [],
  "env": {},
  "globalEnabled": true,
  "enabledHarnesses": []
}
```

If `orquestra-core` is not on `PATH`, use
`"command": "python3", "args": ["-m", "orquestra_core.server"]` instead.

## Tools

| Tool | Inputs | Returns |
| --- | --- | --- |
| `orquestra_list_skills` | `scope?` (default `global`) | `[{id, name, description, tokens, enabled, is_inherited}]` |
| `orquestra_enable_skill` | `skill_id`, `scope?` | `{id, scope, enabled, changed[], scopes[], tokens, path}` |
| `orquestra_disable_skill` | `skill_id`, `scope?` | `{id, scope, enabled, removed[], scopes[], tokens_saved}` |
| `orquestra_list_mcps` | — | `[{id, name, description, command, args, globalEnabled, enabledHarnesses}]` |
| `orquestra_toggle_mcp` | `mcp_id`, `scope?`, `enabled?` | `{id, scope, enabled, changed[], targets, servers, backup, globalEnabled, enabledHarnesses}` |
| `orquestra_read_instructions` | — | master `AGENTS.md` as text |
| `orquestra_append_mission_rule` | `section_title`, `rule_content` | `{section, path, changed, lines_added, bytes, backup}` |
| `orquestra_fleet_status` | — | `{count, installed, bridged, unbridged[], harnesses[]}` |
| `orquestra_create_skill` | `skill_id`, `name`, `description`, `instructions_markdown`, `scripts?` | `{id, created, path, tokens, bytes, scripts[]}` |
| `orquestra_delete_skill` | `skill_id` | `{id, deleted, unlinked[], backup}` |
| `orquestra_create_mcp` | `mcp_id`, `name`, `description`, `command`, `args?`, `env?`, `global_enabled?` | `{id, created, changed[], targets, servers, backup}` |
| `orquestra_delete_mcp` | `mcp_id` | `{id, deleted, changed[], targets, servers, backup}` |
| `orquestra_list_presets` | — | `[{id, name, description, skills[], mcps[], all_skills, all_mcps, icon, builtin, active}]` |
| `orquestra_apply_preset` | `preset_id` | `{preset, applied, changed[], errors[]}` |
| `orquestra_deploy_bridge` | — | `{deployed, harnesses[], errors[]}` |

`scope` is `global` or a harness id discovered from `~/.orquestra/active`
(`antigravity`, `claude`, `codex`, `copilot`, `freebuff`, `grok`, `hermes`,
`kilo`, `opencode`). `enabled` on a harness scope means "projected into that
harness"; `is_inherited` means the global scope also projects it.

`orquestra_vault_http.method` is a JSON-schema enum: `GET`, `POST`, `PUT`,
`PATCH`, `DELETE`, `HEAD` or `OPTIONS`. Anticipated failures are returned as
MCP tool errors (`isError: true`) with the actionable reason; unexpected bugs
remain server-side crashes rather than being mislabeled as input mistakes.

### Example prompts

```
List my skills and tell me which ones cost the most context.
Enable the "playwright" skill globally, then confirm every harness sees it.
Disable "kubernetes" for codex only.
Turn off the "puppeteer" MCP server and redeploy.
Append a rule under "Safety": never rewrite migration files without a backup.
Which harnesses are currently bridged?
```

### Mission Presets

```
List all available mission presets and tell me which one is active.
Apply the stealth preset to minimize my context footprint.
Switch to the rust-dev preset for this session.
Apply full-power and then list my active skills to confirm.
Run bridge deploy to sync all harness symlinks.
```

## Behavior notes

- `orquestra_list_skills` memoizes `SKILL.md` metadata on `(mtime, size)`;
  repeat calls over a 400-skill vault stay in the low milliseconds.
- Enabling a skill that is already projected is a no-op (`changed: []`).
- A real directory where a skill symlink belongs is never deleted or replaced;
  the tool returns an explanatory error instead.
- `orquestra_append_mission_rule` matches the section heading case-insensitively,
  prefixes bare lines with `- `, and creates the section when it is missing.
- `orquestra_create_skill` accepts `[A-Za-z0-9-]` ids, quotes YAML values that
  need it, and removes the half-written folder if any script name is rejected.
- `orquestra_delete_skill` unlinks every scope first, then moves the vault
  folder to `backups/deleted-skills-<stamp>/`; nothing is hard-deleted.
- `orquestra_create_mcp` writes the entry and its `managedIds` membership in one
  atomic catalog replace, then deploys, so a crash cannot leave half a server.
- `orquestra_toggle_mcp` edits the catalog in place and deploys; a harness cannot
  opt out of a globally enabled server, so disable it globally first, matching
  the desktop rule. Unknown harness scopes are rejected before any write.
- `orquestra_delete_mcp` drops the entry but deliberately leaves its managed id
  for the deploy: that membership is what marks the block stale, so the
  serializers purge it from every harness config.
- `ORQUESTRA_HOME` relocates the whole tree (used by the test suite).

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install -e . pytest
.venv/bin/python -m pytest tests/ -q
bash scripts/check-file-size.sh
```

Tests build a throwaway `ORQUESTRA_HOME` under `/var/tmp/testing/` with a fake
native binary, so they never touch a real `~/.orquestra`.

## License

MIT — see [LICENSE](LICENSE).
