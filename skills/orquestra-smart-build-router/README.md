# smart-build-router

Intelligently route build, test, and typecheck commands based on the exact change surface. Prevents wasteful test cascades, unneeded builds, and CPU overheating by only executing checks relevant to touched files.

## Features
- **Change Surface Detection:** Maps touched paths to specific verification domains.
- **Frontend vs Backend Isolation:** Never runs Rust tests for pure React changes, and vice-versa.
- **Thermal & Resource Guardrails:** Avoids redundant full-suite release compilations during daily development loops.
- **Universal & Harness Agnostic:** Works across Claude Code, Antigravity, Grok, Codex, and OpenCode.

## License
MIT
