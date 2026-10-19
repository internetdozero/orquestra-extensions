# agent-orchestrator

Agent orchestration skill for multi-agent workflows. Defines strict read-only boundaries for orchestrator agents, dispatches structured English prompts to Builder agents, provides concise Portuguese explanations to users, and establishes quality guardrails without stifling engineering capability.

## Install

```bash
npx skills add internetdozero/agent-orchestrator
```

Compatible with Agent Skills standard harnesses (OrquestraAI, Claude Code, Grok, Codex, Antigravity, Cursor).

## What it contains

| File | Purpose |
| --- | --- |
| `SKILL.md` | Core rules, orchestrator boundaries, dispatch templates, and builder guardrails |
| `references/templates.md` | Reusable English prompt dispatch templates and feedback checklists |

## Commands

- Check file size: `bash scripts/check-file-size.sh`
- Run: not yet
- Test: not yet

## License

MIT License.
