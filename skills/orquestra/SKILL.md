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

### Harness skill ownership

- The bridge imports existing harness skills into the Orquestra vault, backs up native files before replacing them, and leaves harness-facing skill paths as symlinks into the managed projection.
- Freebuff's canonical global skill path is `~/.agents/skills`; legacy Freebuff/Manicode locations are linked only when their parent directories already exist.
- Treat project-local `.agents/skills` as project-owned content. It is not part of the global Freebuff inventory and must not be adopted into the user vault automatically.

## 2. Interaction Protocol & CLI Reference

When shell interaction is required or MCP tools are unavailable, use the native `orquestra` CLI binary. Always prefix commands with `rtk` to condense terminal output:

### Bridge & Fleet Status
- `rtk orquestra --bridge-status`: Inspect harness projection link status and fleet health as JSON.
- `rtk orquestra --bridge-deploy`: Back up and link every installed harness into the fleet projection (JSON report).
- `rtk orquestra --preset <id>`: Apply a mission preset (e.g., `rtk orquestra --preset full-power` or a custom id from `presets.json`).

### Granular MCP Management (`orquestra mcp`)
- `rtk orquestra mcp list [--format table|json|wide]`: Inspect MCP catalog with global and per-harness activation.
- `rtk orquestra mcp status [--json]`: Fleet-wide MCP metrics, server counts, and harness sync breakdown.
- `rtk orquestra mcp inspect <id> [--reveal] [--json]`: Server configuration, command, args, environment, and headers.
- `rtk orquestra mcp add <id> --command <cmd> [--desc <text>]`: Register a new MCP server.
- `rtk orquestra mcp remove <id> [--yes]`: Unregister an MCP server from catalog.
- `rtk orquestra mcp enable <id> [--scope <harness>]`: Enable an MCP server globally or for a specific harness.
- `rtk orquestra mcp disable <id> [--scope <harness>]`: Disable an MCP server globally or for a specific harness.
- `rtk orquestra mcp deploy [--json]`: Recompile active MCP servers into all harness configuration files.
- `rtk orquestra mcp targets [--json]`: List recognized agent harnesses, installation status, and config paths.
- `rtk orquestra mcp test-connection <id> [--timeout <ms>]`: Protocol handshake and roundtrip latency check.
- `rtk orquestra mcp tools-list <id> [--timeout <ms>]`: Introspect tools and parameter schemas on a server.
- `rtk orquestra mcp call-tool <id> <tool> [--args '<json>'] [--timeout <ms>]`: Dynamic on-demand tool execution.

### Blind Vault Operations (`orquestra vault`)
- `rtk orquestra vault list`: List credential services with health and masked keys (zero secrets).
- `rtk orquestra vault http --service <id> --endpoint <url> [--method GET]`: Blind HTTP request with stored credential.
- `rtk orquestra vault exec <service> [--] <argv…>`: Run a command with stored credentials injected in memory; output is scrubbed.

## 3. MCP Control Plane (`orquestra-core`)

When the `orquestra-core` MCP server is active, prefer calling typed tools over invoking the shell CLI:

### Skill Management
- `orquestra_list_skills(scope="global")`: List skills in the vault, token weights, and whether a scope projects them.
- `orquestra_enable_skill(skill_id, scope="global")`: Activate a skill in a scope (`global` propagates the symlink to every harness).
- `orquestra_disable_skill(skill_id, scope="global")`: Deactivate a skill and prune its projection symlink.
- `orquestra_create_skill(skill_id, name, description, instructions_markdown, scripts=None)`: Author a new skill in `skills-library/<id>/SKILL.md` with optional helper scripts.
- `orquestra_delete_skill(skill_id)`: Safe-archive a skill: unlinks from all scopes and moves the vault folder to `backups/deleted-skills-<stamp>/`.

### MCP Catalog & Granular Operations
- `orquestra_list_mcps()`: Read registered MCP servers with global and per-harness activation state.
- `orquestra_toggle_mcp(mcp_id, scope="global", enabled=True)`: Toggle an MCP server and recompile harness configs.
- `orquestra_mcp_status()`: Return fleet-wide MCP server counts, active states, and harness sync breakdown.
- `orquestra_inspect_mcp(mcp_id, reveal=False)`: Inspect full server configuration, environment variables, and scopes.
- `orquestra_test_mcp_connection(mcp_id, timeout_ms=5000)`: Test connection, verify transport, and check protocol latency.
- `orquestra_list_mcp_tools(mcp_id, timeout_ms=5000)`: Introspect exposed tool definitions and schemas on demand.
- `orquestra_call_mcp_tool(mcp_id, tool_name, arguments=None, timeout_ms=15000)`: Execute a tool dynamically without mounting it.
- `orquestra_list_harness_targets()`: List all supported AI agent harness targets and config file paths.
- `orquestra_create_mcp(mcp_id, name, description, command, args=None, env=None, global_enabled=True)`: Register a new server.
- `orquestra_delete_mcp(mcp_id)`: Back up catalog, remove server, and redeploy harness configs.

#### Dynamic Tool Execution Pattern
To keep system prompts and token footprints small, agents can leave heavy or rarely-used MCP servers unmounted in harness configs. When a specific tool is required, query its schema via `orquestra_list_mcp_tools(mcp_id)` and execute it directly via `orquestra_call_mcp_tool(mcp_id, tool_name, arguments)`. This provides full capability with zero context bloat.

### Fleet & Instructions
- `orquestra_fleet_status()`: Report harness bridge links, sync states, and projection health.
- `orquestra_read_instructions()`: Read the master `~/.orquestra/AGENTS.md` inherited across all harnesses.
- `orquestra_append_mission_rule(section_title, rule_content)`: Append a scoped directive to a section in `AGENTS.md` with automated timestamped backup.

### Credentials (blind vault)
- `orquestra_vault_list()`: List credential services with health, kill-switch state and masked keys. No secrets are ever returned.
- `orquestra_vault_http(service_id, endpoint, method="GET", headers=None, body=None)`: Blind HTTP request; the binary injects the stored key and scrubs it from the response.
- `orquestra_vault_exec(service_id, command)`: Run a CLI command with stored credentials injected in memory; output is scrubbed.
- `orquestra_vault_set_enabled(service_id, enabled)`: Flip the service kill-switch; the blind proxy refuses disabled services.
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
