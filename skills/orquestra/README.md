# OrquestraAI Meta-Skill

Official meta-skill for autonomous AI agent harnesses operating within the OrquestraAI ecosystem.

## Overview

This skill teaches agents (Codex, Claude Code, Antigravity, Grok, Hermes, etc.) the core operational rules of OrquestraAI:
- Single Source of Truth (`~/.orquestra/`)
- Non-destructive configuration policies
- Temporary storage rules (RAM protection)
- Surgical skill & MCP enabling without prompt bloat

## Usage

In any Orquestra-managed harness, this skill is active either globally or per-harness:
```bash
orquestra --fleet-status
```

## Verification

Enforce file-size limits across all files:
```bash
bash scripts/check-file-size.sh
```
