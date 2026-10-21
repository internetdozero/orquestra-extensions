"""Real MCP handshake over stdio: initialize, list tools, call ``web_search``.

This is the only test that reaches Exa. It is marked ``integration`` and the
default run excludes it, so the unit suite stays offline and free. Run it with
``pytest -m integration``; it also skips itself when no key resolves or when
Exa is unreachable.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import sys
from pathlib import Path
from typing import Any

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from web_search import env_file

pytestmark = pytest.mark.integration

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
EXA_HOST = ("api.exa.ai", 443)
NETWORK_TIMEOUT_SECONDS = 5


def _payload(result: Any) -> dict[str, Any]:
    """Take the tool payload from structured content or the JSON text block."""
    if getattr(result, "structured_content", None):
        return result.structured_content
    for block in result.content or []:
        text = getattr(block, "text", "")
        if text:
            return json.loads(text)
    return {}


def _require_live_search() -> None:
    """Skip unless a key resolves and Exa is reachable from here."""
    if not (os.environ.get("EXA_API_KEY", "").strip() or env_file.load(("EXA_API_KEY",))):
        pytest.skip("EXA_API_KEY is not configured")
    try:
        with socket.create_connection(EXA_HOST, timeout=NETWORK_TIMEOUT_SECONDS):
            pass
    except OSError as error:
        pytest.skip(f"no network route to {EXA_HOST[0]}: {error}")


async def _call_server(
    cwd: Path, query: str, num_results: int
) -> tuple[list[str], dict[str, Any], bool]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, (str(PACKAGE_ROOT), env.get("PYTHONPATH", "")))
    )
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "web_search.server"],
        env=env,
        cwd=str(cwd),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            result = await session.call_tool(
                "web_search", {"query": query, "num_results": num_results}
            )
            names = sorted(tool.name for tool in tools.tools)
            return names, _payload(result), bool(getattr(result, "is_error", False))


def test_web_search_tool_answers_over_stdio(tmp_path: Path) -> None:
    _require_live_search()
    query = "cloudflare durable objects alarms"

    names, payload, is_error = asyncio.run(_call_server(tmp_path, query, 2))

    assert names == ["web_search"]
    assert not is_error, payload
    assert payload["query"] == query
    assert payload["count"] == len(payload["results"])
    assert payload["count"] >= 1
    first = payload["results"][0]
    assert first["url"].startswith("http")
    assert first["title"]
    assert isinstance(first["highlights"], list)
