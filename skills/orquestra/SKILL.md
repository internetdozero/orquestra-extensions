---
name: orquestra
description: Operational guide for autonomous AI agents inside the OrquestraAI ecosystem. Teaches fleet topology, single-source-of-truth rules, non-destructive config management, and safe control-plane interaction.
---

# OrquestraAI Operational Guide

OrquestraAI is the unified control plane managing the multi-harness agent fleet (Codex, Claude Code, Antigravity, Grok, Hermes, Copilot, etc.) on this machine.

Agents must operate with strict adherence to the ecosystem's architecture and safety rules.

## 1. System Topology & Single Source of Truth

All configurations and skills are centrally managed under `~/.orquestra/`:

```
~/.orquestra/
├── AGENTS.md            # Master instructions (symlinked to all harnesses)
├── mcps.json            # Canonical MCP registry (compiled to harness configs)
├── vault/skills/        # Canonical user skill vault
├── skills-library/      # Installed skill repositories
└── active/<harness>/    # Projected symlinks for each harness
```

- **Global Scope:** Skills symlinked across all harnesses.
- **Harness Scope:** Skills symlinked exclusively to a specific harness.
- **Compiled Configs:** Each harness config (e.g., `mcp_config.json`, `opencode.jsonc`) is a compiled projection of `mcps.json`.

## 2. Mandatory Rules of Engagement

1. **Never edit harness configs directly:**
   Direct edits to target harness configuration files (such as `~/.gemini/config/mcp_config.json`, `~/.codex/...`, or `~/.claude/...`) are forbidden. They will be wiped whenever Orquestra deploys. Always use `orquestra-core` MCP tools or the CLI.

2. **Preserve projection symlinks:**
   Skills in active harness folders are symlinks. Never delete, replace with plain folders, or unlink them manually. Use the control plane to enable or disable skills.

3. **RAM Protection & Scratch Files:**
   Never write scratch files, mock repos, or build artifacts to `/tmp`. On Linux, `/tmp` is a RAM-backed `tmpfs`; consuming it directly exhausts memory and triggers kernel OOM kills. Always use `/var/tmp/testing/`.

4. **Token & Context Hygiene:**
   Active skills inject prompt instructions into every turn. Only enable skills relevant to the current mission, and disable them or switch presets when done.

5. **Terminal Command Condensation:**
   Always prefix shell commands with `rtk` (e.g., `rtk cargo check`, `rtk git status`) to suppress terminal verbosity and eliminate context bloat.

## 3. Interaction Protocol: MCP vs CLI

- **In-Session (MCP available):**
  When `orquestra-core` MCP tools are available, always call the typed tools directly (`orquestra_enable_skill`, `orquestra_list_skills`, `orquestra_toggle_mcp`, `orquestra_fleet_status`). Tool signatures and arguments are self-describing.

- **Shell / Terminal Fallback:**
  If operating in a terminal or inside a harness where the MCP is unavailable, use the native CLI binary:
  ```bash
  orquestra --fleet-status      # Check harness bridge status
  orquestra --mcp-status        # Inspect active MCP servers
  orquestra --bridge-status     # Verify projection symlinks
  ```
