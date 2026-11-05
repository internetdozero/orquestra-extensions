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

MCP client entry: `{"command": "web-search", "args": []}` (or
`python3 -m web_search.server` when the script is not on `PATH`).

When OrquestraAI is installed, the server first searches the enabled Exa-preset
credential in its vault and sends the query through Orquestra's blind HTTP
proxy; the raw key never enters the MCP process. If the vault CLI or an enabled
Exa credential is unavailable, it falls back to `EXA_API_KEY` from the server
environment, then from the nearest `.env` above the installed package or
working directory. `WEB_SEARCH_ENV_FILE=/path/to/file` overrides the `.env`
lookup. Only `EXA_API_KEY` is copied from a file and an exported value always
wins. The empty placeholder lives in [`.env.example`](.env.example); local
`.env` files are gitignored.
