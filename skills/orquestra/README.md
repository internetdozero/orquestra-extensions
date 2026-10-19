# OrquestraAI Meta-Skill

Official operational guide and meta-skill for autonomous AI agent harnesses operating within the OrquestraAI ecosystem.

## Overview

This skill teaches agents (Antigravity, Codex, Claude Code, Grok, Hermes, Copilot, etc.) the core operational rules of OrquestraAI:
- Single Source of Truth (`~/.orquestra/skills-library/` master vault, `mcps.json`, `AGENTS.md`)
- Non-destructive configuration policies & compilation pipelines
- Safe control-plane interaction via `orquestra-core` MCP tools
- Headless CLI operations & mission presets
- RAM safety (`/var/tmp/testing/` instead of `/tmp`) and token condensation (`rtk`)

## CLI Quick Reference

When operating without MCP tools or in scripts, use the native `orquestra` binary:

```bash
rtk orquestra --bridge-status                 # Inspect harness projection link status as JSON
rtk orquestra --bridge-deploy                 # Back up and link every installed harness
rtk orquestra --mcp-status                    # Print master MCP catalog as JSON
rtk orquestra --mcp-deploy                    # Compile active MCPs into harness configs
rtk orquestra --mcp-set <id> <scope> <on|off> # Toggle individual MCP server
rtk orquestra --preset <id>                   # Apply a mission preset (e.g. stealth, full-power)
```

## MCP Tools (`orquestra-core`)

The `orquestra-core` MCP server exposes programmatic control over the fleet:
- **Skills:** `orquestra_list_skills`, `orquestra_enable_skill`, `orquestra_disable_skill`, `orquestra_create_skill`, `orquestra_delete_skill`
- **MCP Catalog:** `orquestra_list_mcps`, `orquestra_toggle_mcp`, `orquestra_create_mcp`, `orquestra_delete_mcp`
- **Fleet & Rules:** `orquestra_fleet_status`, `orquestra_read_instructions`, `orquestra_append_mission_rule`

## Mission Presets

Switch active skills and MCP servers dynamically per workflow:
- `stealth`: Zero-bloat profile for minimal token footprint
- `rust-dev` / `web-fullstack`: Targeted dev environments
- `full-power`: Unrestricted access to all skills and MCPs
- Custom presets in `~/.orquestra/presets.json`

## Verification

Enforce file-size limits across all files:
```bash
bash scripts/check-file-size.sh
```
