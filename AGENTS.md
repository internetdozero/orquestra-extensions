# orquestra-extensions — agent guide

- One skill per `skills/<skill-id>/` folder; the folder name is the vault id.
- Every skill folder holds a `SKILL.md` with `name:` + `description:` frontmatter.
- Keep skill folders self-contained; shared helpers live in `skills/<id>/scripts/`.
- One MCP per `mcps/<mcp-id>/` package with a `pyproject.toml` console script.
- Never commit secrets; MCP env keys stay operator-side.

## Process Execution & Polling Protocol (No Blind Sleeps)
- **Forbidden:** NEVER use static blind sleep commands (e.g. `sleep 60`, `sleep 600`) to wait for time to pass, background jobs, or test runs to finish.
- **Active Execution:** Run verification commands (`pytest`, `python -m unittest`, `cargo check`) directly in the foreground. If a shift has remaining time, the agent must NEVER sleep; it must continuously run active sweeps, write missing unit tests, fuzz inputs, or pull tasks from the Idea Vault.

## Temporary Files & Storage Policy (Strict)
- **Forbidden Path:** NEVER create or write scratch files, mock repositories, temporary test venvs, or artifacts inside `/tmp/`. On this Linux machine, `/tmp` is a RAM-backed `tmpfs`; consuming it directly exhausts physical RAM and causes the kernel OOM Killer to crash critical user processes.
- **Designated Scratch Path:** All temporary files, test scripts, sandbox tests, and audit venvs MUST use `/var/tmp/testing/` (create if absent: `mkdir -p /var/tmp/testing`). Always remove transient test assets upon test completion.
