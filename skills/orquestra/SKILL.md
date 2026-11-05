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

### Granular Skills Management (`orquestra skills`)
- `rtk orquestra skills list [--format table|json|wide] [--official] [--has-scripts] [--filter <term>]`: List skills with token counts and projection state.
- `rtk orquestra skills info <id>`: Comprehensive inspection: tokens, scripts, and projection matrix across all scopes.
- `rtk orquestra skills enable <id> [--scope <harness>]`: Activate a skill in a scope (`global` projects to all harnesses).
- `rtk orquestra skills disable <id> [--scope <harness>]`: Deactivate a skill and prune its projection symlink.
- `rtk orquestra skills batch <enable|disable> [--scope <harness>]`: Bulk enable or disable all vault skills for a scope.
- `rtk orquestra skills summary [--json]`: Fleet-wide summary of active vs total skill projections per scope.
- `rtk orquestra skills validate <id|path>`: Validate manifest frontmatter, ID safety, and directory security limits.
- `rtk orquestra skills create <id> --name <name> --desc <text>`: Scaffold a new skill in the master vault.
- `rtk orquestra skills import <dir|url[#subpath]> [--enable]`: Import and validate a skill from folder or git repo.
- `rtk orquestra skills export <id> <dest>`: Export skill folder and scripts to a destination directory.
- `rtk orquestra skills content <id> [--set <file>]`: View or update raw `SKILL.md` manifest in vault.
- `rtk orquestra skills delete <id> [--yes]`: Safe-archive skill into timestamped backup directory.

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
- `rtk orquestra vault list [--preset <name>] [--enabled-only] [--search <term>]`: List credential services with health and masked keys.
- `rtk orquestra vault inspect <id> [--reveal] [--key-number <N>]`: Service details, masked keys, health, and tags.
- `rtk orquestra vault add-key <id> --key <secret> [--tag <tag>]`: Push a new key to an existing service pool.
- `rtk orquestra vault remove-key <id> --key-number <N>`: Remove key from pool by 1-based number.
- `rtk orquestra vault set-primary <id> --key-number <N>`: Set primary active key in pool.
- `rtk orquestra vault rotate <id> [--next] [--key-number <N>]`: Advance active key pointer or rotate specific key.
- `rtk orquestra vault test <id> [--key-number <N>]`: Ping provider verify endpoint and measure roundtrip latency.
- `rtk orquestra vault presets [--json]`: Discover provider credential presets (headers, env vars, metadata).
- `rtk orquestra vault audit [--json]`: Check at-rest encryption, 0600 file permissions, and backups.
- `rtk orquestra vault http --service <id> --endpoint <url> [--method GET] [--key-number <N>] [--key-tag <tag>]`: Blind HTTP request.
- `rtk orquestra vault exec <service> [--key-number <N>] [--] <argv…>`: Run a command with stored credentials injected in memory; output is scrubbed.

### Sessions Management (`orquestra sessions`)
- `rtk orquestra sessions list [--harness <h>] [--limit <N>] [--compact]`: Discover sessions across harnesses.
- `rtk orquestra sessions inspect <harness> <id> [--turns <N>]`: Load ordered conversation turns and tool events.
- `rtk orquestra sessions export <harness> <id> [--format md|json] [--output <path>]`: Full transcript export.
- `rtk orquestra sessions pin <harness> <id> [--label <text>]` / `unpin`: Manage retention exemptions.
- `rtk orquestra sessions purge [--older-than <days>] [--dry-run]`: Safe retention cleanup skipping active/pinned sessions.
- `rtk orquestra sessions delete <harness> <id> [--force]`: Surgical deletion enforcing safety guards.
- `rtk orquestra sessions policy [--get|--set ...]`: Query or update TTLs and auto-purge settings.
- `rtk orquestra sessions watch [--harness <h>]`: Real-time tracking of active turns and touched files.

## 3. MCP Control Plane (`orquestra-core`)

When the `orquestra-core` MCP server is active, prefer calling typed tools over invoking the shell CLI:

### Skill Management
- `orquestra_list_skills(scope="global", filter_text=None, official_only=False, has_scripts_only=False)`: List skills in vault with token weights, projection status, and optional filtering.
- `orquestra_inspect_skill(skill_id, scope="global")`: Inspect detailed skill metadata, scripts, and per-scope projection matrix.
- `orquestra_enable_skill(skill_id, scope="global")`: Activate a skill in a scope (`global` propagates the symlink to every harness).
- `orquestra_disable_skill(skill_id, scope="global")`: Deactivate a skill, prune symlink, and report inherited state.
- `orquestra_batch_skills(action="enable"|"disable", scope="global")`: Bulk toggle all skills in the vault for a scope.
- `orquestra_skills_summary()`: Fleet-wide metrics on total skills and active projections per scope.
- `orquestra_validate_skill(target)`: Audit SKILL.md frontmatter (`name`, `description`), ID safety, and security limits.
- `orquestra_get_skill_content(skill_id)`: Read raw `SKILL.md` markdown content.
- `orquestra_set_skill_content(skill_id, content)`: Atomically validate and update `SKILL.md` in the vault.
- `orquestra_import_skill(source, subpath=None, scope="global", enable=False)`: Import from local directory or git URL (`url#subpath`).
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
- `orquestra_vault_inspect(service_id)`: Inspect complete metadata, pool health, and key tags.
- `orquestra_vault_rotate(service_id, next_key=True, key_number=None)`: Rotate key pool or advance pointer.
- `orquestra_vault_test(service_id, key_number=None)`: Ping provider verify endpoint, measure latency, and persist health.
- `orquestra_vault_presets()`: Discover built-in provider presets (headers, env vars, metadata).
- `orquestra_vault_audit()`: Audit security posture of local storage encryption and file permissions.
- `orquestra_vault_http(service_id, endpoint, method="GET", headers=None, body=None, timeout=30.0, key_number=None, key_tag=None)`: Blind HTTP request; the binary injects stored key and scrubs response.
- `orquestra_vault_exec(service_id, command, timeout=60.0, key_number=None)`: Run a CLI command with stored credentials injected in memory; output is scrubbed.
- `orquestra_vault_set_enabled(service_id, enabled)`: Flip the service kill-switch; the blind proxy refuses disabled services.
- Never ask the operator to paste a secret into chat: register it in the Vault and reference it by `service_id`.

### Mission presets
- `orquestra_list_presets()`: Built-in `full-power` plus custom profiles from `~/.orquestra/presets.json`.
- `orquestra_apply_preset(preset_id)`: Activate a preset across all harnesses.
- `orquestra_save_preset(name, ...)` / `orquestra_delete_preset(preset_id)`: Manage custom presets (built-ins are protected).

### Session Observability, Relay & Retention (`orquestra-session-relay`)
- `list_recent_sessions(harness=None, limit=5, compact=False)`: Discover sessions across all 9 harnesses with pin and alive status.
- `inspect_session(harness=None, session_id="latest", max_turns=10)`: Inspect conversation turns, tool calls, and error states.
- `search_sessions_history(query, harness=None, limit=10, project_path=None, search_content=True)`: Search across full transcripts or metadata.
- `handoff_context(source_harness=None, target_harness=None, session_id="latest")`: Synthesize structured Goal/Files/State/Blocker/Next brief.
- `export_session(harness, session_id="latest", format="markdown", output_path=None)`: Export unabridged transcripts to Markdown or JSON.
- `pin_session(harness, session_id, label=None)` / `unpin_session` / `list_pinned_sessions`: Manage retention exemptions in `sessions_policy.json`.
- `estimate_purge(older_than_days=None, harness=None, session_ids=None)`: Dry-run estimation of purgeable candidates and bytes.
- `purge_sessions(older_than_days=None, harness=None, session_ids=None, dry_run=True)`: Safe batch purge protecting pinned and active sessions.
- `delete_session(harness, session_id, force=False)`: Surgical session deletion enforcing safety guards.
- `get_retention_policy()` / `set_retention_policy(...)`: Configure retention TTLs, intervals, and per-harness overrides.
- `watch_active_agent(harness=None)`: Live inspection of active running turn, current tool, and touched files.
- `tail_agent_activity(harness=None, lines=15)` / `audit_agent(harness, session_id=None)`: Streamable telemetry and lightweight audits.

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
