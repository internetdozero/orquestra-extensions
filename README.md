# orquestra-extensions

Unified monorepo for the official OrquestraAI skills and MCP servers.

- `skills/<skill-id>/SKILL.md` — one folder per skill, importable via
  `orquestra-extensions.git#skills/<skill-id>`.
- `mcps/<mcp-id>/` — one Python package per MCP server (`pyproject.toml`).

Legacy standalone repos remain as pull-through fallbacks until every
consumer tracks this monorepo.
