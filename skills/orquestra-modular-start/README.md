# modular-start

Mandatory skill for AI coding agents to initialize new projects without degenerating into multi-thousand-line monoliths.

Before writing the first line of code, the agent initializes git, writes a concise root `AGENTS.md` (defining file-size caps and module ownership), and commits each coherent slice locally without interrupting the operator. Works across any programming language or stack.

## Install

```bash
npx skills add internetdozero/modular-start
```

Compatible with AI agent harnesses that support the Agent Skills specification (Grok, OpenAI Codex, Anthropic Claude Code, Cursor, GitHub Copilot, Google Antigravity, Freebuff, and other CLI-supported harnesses).

Activates automatically on new projects, scaffolds, and empty repositories. `/modular-start` forces execution.

## Contents

| File | Purpose |
| --- | --- |
| `SKILL.md` | Core workflow: git init, `.gitignore`, `AGENTS.md`, commits, modular layout |
| `assets/AGENTS.md` | Baseline contract the agent copies to the project root |
| `assets/gitignore` | Clean starting point, extended for the target stack in the initial commit |
| `scripts/check-file-size.sh` | Enforces `file_size_cap` on all hand-written files |

Default template limits are 300 lines (soft stop: split before growing) and 400 lines (hard cap). The project's root `AGENTS.md` defines the authoritative limits.

## License

MIT
