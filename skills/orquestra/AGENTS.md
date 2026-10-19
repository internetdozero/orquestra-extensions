# AGENTS.md

file_size_cap: 300
file_size_soft: 250

Those two lines are the size rule. Count with `wc -l`. A hand-written file at the soft number gets no new behavior; split it first. A file over the cap is a broken tree. Generated files, lockfiles, and vendored code are outside the cap.

## What this is

The official OrquestraAI meta-skill that instructs autonomous agent harnesses (Antigravity, Codex, Claude Code, Grok, Hermes, etc.) on safe control plane usage, fleet topology, and MCP interaction without token waste.

## Layout

- `SKILL.md` — Agent prompt and operational instructions for OrquestraAI.
- `scripts/check-file-size.sh` — Size enforcement script.
- `README.md` — Repository overview.

## Commands

- Check file size: `bash scripts/check-file-size.sh`

## While editing

- Read this file before adding code or docs.
- Keep `SKILL.md` strictly under size limits and eliminate redundant explanations covered by `orquestra-core` MCP tool schemas.
- Commit each coherent slice locally.
