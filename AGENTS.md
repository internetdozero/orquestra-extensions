# orquestra-extensions — agent guide

- One skill per `skills/<skill-id>/` folder; the folder name is the vault id.
- Every skill folder holds a `SKILL.md` with `name:` + `description:` frontmatter.
- Keep skill folders self-contained; shared helpers live in `skills/<id>/scripts/`.
- One MCP per `mcps/<mcp-id>/` package with a `pyproject.toml` console script.
- Never commit secrets; MCP env keys stay operator-side.
