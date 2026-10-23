---
name: orquestra
description: Operational guide for autonomous AI agents inside the OrquestraAI ecosystem. Teaches fleet topology, single-source-of-truth rules, native CLI operations, orquestra-core MCP tools, and mission presets.
---

# OrquestraAI Operational Guide

OrquestraAI is the unified control plane managing the multi-harness agent fleet (Codex, Claude Code, Antigravity, Grok, Hermes, Copilot, etc.) on this machine.

Agents must operate with strict adherence to the ecosystem's architecture, non-destructive configuration rules, and token-efficient execution.

## 1. System Topology & Single Source of Truth

All configurations, skills, and presets are centrally managed under `~/.orquestra/`. The master vault is `skills-library/`:

```
~/.orquestra/
├── AGENTS.md            # Master instructions (symlinked to all harnesses)
├── mcps.json            # Canonical MCP registry (compiled to harness configs)
├── presets.json         # Custom and active mission preset definitions
├── skills-library/      # Canonical master vault for all installed skills
└── active/<harness>/    # Projected symlinks for each harness (and global baseline)
```

- **Master Vault (`skills-library/`):** The single canonical repository for all available skills. Skills are never duplicated across harnesses; they are symlinked from here.
- **Global Scope:** Skills projected to all harnesses via universal baseline links.
- **Harness Scope:** Skills projected exclusively to specific harnesses (e.g., `active/antigravity/`, `active/codex/`).
- **Compiled Configs:** Each harness configuration file (e.g., `mcp_config.json`, `opencode.jsonc`, `claude.json`) is an outward projection compiled directly from `mcps.json`.

## 2. Interaction Protocol & CLI Reference

When shell interaction is required or MCP tools are unavailable, use the native `orquestra` CLI binary. Always prefix commands with `rtk` to condense terminal output:

- `rtk orquestra --bridge-status`: Inspect harness projection link status and fleet health as JSON.
- `rtk orquestra --bridge-deploy`: Back up and link every installed harness into the fleet projection (JSON report).
- `rtk orquestra --mcp-status`: Print the master MCP catalog and enabled states as JSON.
- `rtk orquestra --mcp-deploy`: Compile active MCPs from `mcps.json` into all harness configuration files.
- `rtk orquestra --mcp-set <id> <scope> <on|off>`: Toggle individual MCP servers (`scope`: `global` or a specific harness like `antigravity`, `state`: `on` or `off`).
- `rtk orquestra --preset <id>`: Apply a mission preset (e.g., `rtk orquestra --preset full-power` or a custom id from `presets.json`).
- `rtk orquestra vault list`: List credential services with health and masked keys (zero secrets).
- `rtk orquestra vault http --service <id> --endpoint <url> [--method GET]`: Blind HTTP request with the stored credential injected by the binary.
- `rtk orquestra vault exec <service> [--] <argv…>`: Run a command with stored credentials injected in memory; output is scrubbed.

## 3. MCP Control Plane (`orquestra-core`)

When the `orquestra-core` MCP server is active, prefer calling typed tools over invoking the shell CLI:

### Skill Management
- `orquestra_list_skills(scope="global")`: List skills in the vault, token weights, and whether a scope projects them.
- `orquestra_enable_skill(skill_id, scope="global")`: Activate a skill in a scope (`global` propagates the symlink to every harness).
- `orquestra_disable_skill(skill_id, scope="global")`: Deactivate a skill and prune its projection symlink.
- `orquestra_create_skill(skill_id, name, description, instructions_markdown, scripts=None)`: Author a new skill in `skills-library/<id>/SKILL.md` with optional helper scripts.
- `orquestra_delete_skill(skill_id)`: Safe-archive a skill: unlinks from all scopes and moves the vault folder to `backups/deleted-skills-<stamp>/`.

### MCP Catalog Management
- `orquestra_list_mcps()`: Read registered MCP servers with their global and per-harness activation state from `mcps.json`.
- `orquestra_toggle_mcp(mcp_id, scope="global", enabled=True)`: Toggle an MCP server and recompile harness configs via the native deploy pipeline.
- `orquestra_create_mcp(mcp_id, name, description, command, args=None, env=None, global_enabled=True)`: Register a new server in `mcps.json` and deploy it outward.
- `orquestra_delete_mcp(mcp_id)`: Back up the catalog, remove the server definition, and redeploy harness configs.

### Fleet & Instructions
- `orquestra_fleet_status()`: Report harness bridge links, sync states, and projection health.
- `orquestra_read_instructions()`: Read the master `~/.orquestra/AGENTS.md` inherited across all harnesses.
- `orquestra_append_mission_rule(section_title, rule_content)`: Append a scoped directive to a section in `AGENTS.md` with automated timestamped backup.

### Credentials (blind vault)
- `orquestra_vault_list()`: List credential services with health, kill-switch state and masked keys. No secrets are ever returned.
- `orquestra_vault_http(service_id, endpoint, method="GET", headers=None, body=None)`: Blind HTTP request; the binary injects the stored key and scrubs it from the response.
- `orquestra_vault_exec(service_id, command)`: Run a CLI command with stored credentials injected in memory; output is scrubbed.
- Never ask the operator to paste a secret into chat: register it in the Vault and reference it by `service_id`.

### Mission presets
- `orquestra_list_presets()`: Built-in `full-power` plus custom profiles from `~/.orquestra/presets.json`.
- `orquestra_apply_preset(preset_id)`: Activate a preset across all harnesses.
- `orquestra_save_preset(name, ...)` / `orquestra_delete_preset(preset_id)`: Manage custom presets (built-ins are protected).

## 4. Mission Presets

Mission presets allow instantaneous switching of active skills and MCP servers to match current operational goals, preserving context tokens and avoiding prompt bloat:

- **Dynamic Orchestration:** Presets atomically reconfigure both the skills projections (`active/<harness>/`) and the outward MCP configurations (`mcps.json` -> harness configs) in a single operation.
- **Curated & Workflow Profiles:**
  - `full-power`: The only built-in. Maximizes fleet capabilities by enabling every skill in the vault and every registered MCP server.
  - Custom profiles: Operator-defined presets in `~/.orquestra/presets.json` (see `orquestra_save_preset`), e.g. a minimal `review-mode` or a local-only profile.

## 5. Mandatory Rules of Engagement

1. **Never edit target harness configs directly:** Direct edits to `mcp_config.json`, `opencode.jsonc`, or `claude.json` will be overwritten by `orquestra --mcp-deploy`. Always use `orquestra-core` tools or `orquestra --mcp-set`.
2. **Preserve projection symlinks:** Never delete or replace symlinks in `active/` manually. Use `orquestra_disable_skill` or `--preset`.
3. **RAM Protection & Scratch Space:** Never write scratch files or temporary builds to `/tmp` (RAM-backed `tmpfs`). Always use `/var/tmp/testing/`.
4. **Token Hygiene:** Always prefix CLI commands with `rtk` and deactivate unused skills when transitioning between tasks.
