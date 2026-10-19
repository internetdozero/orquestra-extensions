"""End-to-end MCP stdio handshake driving all five tools in dry_run mode."""

from __future__ import annotations

import json
import os
import select
import subprocess
import sys
import time
from typing import Any

import pytest

TIMEOUT = 30.0

EXPECTED_TOOLS = [
    "janitor_system_health",
    "janitor_scan_orphans",
    "janitor_sweep_processes",
    "janitor_clean_caches",
    "janitor_oom_inspect",
]


class Client:
    """Minimal newline-delimited JSON-RPC client for the stdio transport."""

    def __init__(self) -> None:
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "janitor.server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        self._id = 0

    def send(self, payload: dict[str, Any]) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(payload).encode() + b"\n")
        self.proc.stdin.flush()

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._id += 1
        want = self._id
        self.send({"jsonrpc": "2.0", "id": want, "method": method, "params": params or {}})
        deadline = time.time() + TIMEOUT
        assert self.proc.stdout is not None
        while time.time() < deadline:
            ready, _, _ = select.select([self.proc.stdout], [], [], 1.0)
            if not ready:
                continue
            line = self.proc.stdout.readline()
            if not line:
                break
            message = json.loads(line)
            if message.get("id") == want:
                assert "error" not in message, message.get("error")
                return message["result"]
        raise AssertionError(f"no response for {method} id={want}")

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.request("tools/call", {"name": name, "arguments": arguments})

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait(timeout=10)


@pytest.fixture(scope="module")
def client() -> Any:
    c = Client()
    c.request(
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "janitor-tests", "version": "0"},
        },
    )
    c.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    yield c
    c.close()


def _payload(result: dict[str, Any]) -> Any:
    content = result.get("content") or []
    if content:
        assert content[0]["type"] == "text", result
        return json.loads(content[0]["text"])
    # Empty containers come back without a text block, only structured output.
    structured = result.get("structuredContent")
    if isinstance(structured, dict) and "result" in structured:
        return structured["result"]
    return structured


def test_tools_list_exposes_all_five(client: Client) -> None:
    result = client.request("tools/list")
    names = sorted(tool["name"] for tool in result["tools"])
    assert names == sorted(EXPECTED_TOOLS)
    for tool in result["tools"]:
        assert tool["description"], tool["name"]


def test_system_health_tool(client: Client) -> None:
    result = _payload(client.call("janitor_system_health", {}))
    assert {"ram", "swap", "tmp", "cpu", "top_processes", "alert"} <= set(result)
    assert isinstance(result["alert"], bool)
    assert 0 <= result["ram"]["used_percent"] <= 100
    assert len(result["top_processes"]) <= 5


def test_scan_orphans_tool_returns_a_list(client: Client) -> None:
    rows = _payload(client.call("janitor_scan_orphans", {}))
    assert isinstance(rows, list), type(rows)
    for row in rows:
        assert {"pid", "name", "memory_mb", "cpu_percent", "command", "ppid", "reason"} <= set(row)


def test_sweep_dry_run_reports_and_refuses(client: Client) -> None:
    result = _payload(
        client.call("janitor_sweep_processes", {"target_type": "orphans", "dry_run": True})
    )
    assert result["dry_run"] is True
    for row in result["results"]:
        assert row["action"] in {"would_terminate", "refused"}
    refused = _payload(
        client.call("janitor_sweep_processes", {"pids": [1], "dry_run": True})
    )
    assert refused["results"][0]["action"] == "refused"


def test_clean_caches_dry_run(client: Client) -> None:
    result = _payload(
        client.call("janitor_clean_caches", {"dry_run": True, "older_than_hours": 6})
    )
    assert result["dry_run"] is True and result["older_than_hours"] == 6
    assert set(result["targets"]) == {"sockets", "staging", "testing_scratch"}
    for item in result["items"]:
        assert item["action"] in {"would_remove", "skipped"}
        assert item["path"].startswith("/") and "/tmp/" != item["path"][:5]


def test_clean_caches_validation_error_is_reported(client: Client) -> None:
    result = _payload(client.call("janitor_clean_caches", {"older_than_hours": -1}))
    assert "older_than_hours" in result["error"]


def test_oom_inspect_tool(client: Client) -> None:
    result = _payload(client.call("janitor_oom_inspect", {}))
    assert {"scale", "count", "processes", "note"} <= set(result)
    scores = [row["oom_score"] for row in result["processes"]]
    assert scores == sorted(scores, reverse=True)


def test_sweep_bad_arguments_return_error_object(client: Client) -> None:
    result = _payload(client.call("janitor_sweep_processes", {}))
    assert "provide pids" in result["error"]