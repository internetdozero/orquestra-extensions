# orquestra-extensions

Unified monorepo for the official OrquestraAI skills and MCP servers.

- `skills/<skill-id>/SKILL.md` — one folder per skill, importable via
  `orquestra-extensions.git#skills/<skill-id>`.
- `mcps/<mcp-id>/` — one Python package per MCP server (`pyproject.toml`).

Legacy standalone repos remain as pull-through fallbacks until every
consumer tracks this monorepo.

## `mcps/orquestra-web-search` — Web Search (Exa)

One MCP tool, `web_search`: a query in, up to 100 pages out, each with `title`,
`url`, `published_date`, `author` and Exa `highlights` (the passages that answer
the query). A missing key, `401`, `402`, `429` and network failures come back as
`{error, error_status}`, never as an empty list. The key stays server-side;
nothing is deployed.

```bash
cd mcps/orquestra-web-search
python3 -m venv .venv && .venv/bin/pip install -e . pytest
EXA_API_KEY=... .venv/bin/python -m web_search.server --query "exa highlights api"
.venv/bin/python -m pytest tests/ -q                 # offline unit suite
.venv/bin/python -m pytest tests/ -q -m integration  # real MCP stdio + Exa
```

The `integration` test is excluded from the default run: it spawns the server,
performs the MCP handshake, calls `web_search` against Exa and skips itself when
no key resolves or the network is unreachable.

MCP client entry: `{"command": "web-search", "args": [], "env": {"EXA_API_KEY": "..."}}`
(or `python3 -m web_search.server` when the script is not on `PATH`).

The key is read from the server's environment first, and when that is empty the
server loads it by itself: the nearest `.env` above the installed package (the
repository root here), otherwise the nearest `.env` above the working
directory. `WEB_SEARCH_ENV_FILE=/path/to/file` overrides both, so a client that
passes no `env` block still works without any manual export. Only
`EXA_API_KEY` is copied and it never overwrites an exported value. The empty
placeholder lives in [`.env.example`](.env.example); local `.env` files are
gitignored.
