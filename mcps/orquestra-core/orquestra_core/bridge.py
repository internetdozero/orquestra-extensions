"""Subprocess wrapper around the native `orquestra` binary and its JSON reports."""

from __future__ import annotations

import json
import subprocess
from typing import Any

from . import paths
from .errors import BridgeError

TIMEOUT = 180


def run(*args: str, timeout: int = TIMEOUT) -> subprocess.CompletedProcess[str]:
    """Execute the native binary once, capturing both streams without a shell."""
    command = [paths.binary(), *args]
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as error:
        raise BridgeError(f"the native '{command[0]}' binary is not installed") from error
    except subprocess.TimeoutExpired as error:
        raise BridgeError(f"'{' '.join(command)}' timed out after {timeout}s") from error


def _json(proc: subprocess.CompletedProcess[str], label: str) -> Any:
    """Return parsed stdout, or raise with the tail of the binary's diagnostics."""
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        tail = detail[-1] if detail else "no output"
        raise BridgeError(f"{label} failed (exit {proc.returncode}): {tail}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as error:
        raise BridgeError(f"{label} returned malformed JSON: {error}") from error


def mcp_set(mcp_id: str, scope: str, enabled: bool) -> dict[str, Any]:
    """Flip one server's state exactly as the desktop switch does."""
    state = "on" if enabled else "off"
    return _json(run("--mcp-set", mcp_id, scope, state), f"--mcp-set {mcp_id} {scope} {state}")


def mcp_status() -> dict[str, Any]:
    """Status summary of all MCP servers and harness targets."""
    report = _json(run("mcp", "status", "--json"), "mcp status")
    if not isinstance(report, dict):
        raise BridgeError("mcp status did not return a status object")
    return report


def mcp_inspect(mcp_id: str, reveal: bool = False) -> dict[str, Any]:
    """Detailed inspection of an MCP server registration."""
    argv = ["mcp", "inspect", mcp_id, "--json"]
    if reveal:
        argv.append("--reveal")
    report = _json(run(*argv), f"mcp inspect {mcp_id}")
    if not isinstance(report, dict):
        raise BridgeError(f"mcp inspect {mcp_id} did not return an object")
    return report


def mcp_test_connection(mcp_id: str, timeout_ms: int = 5000) -> dict[str, Any]:
    """Test connection and protocol handshake for an MCP server."""
    report = _json(
        run("mcp", "test-connection", mcp_id, "--timeout", str(timeout_ms), "--json"),
        f"mcp test-connection {mcp_id}",
    )
    if not isinstance(report, dict):
        raise BridgeError(f"mcp test-connection {mcp_id} did not return a report object")
    return report


def mcp_tools_list(mcp_id: str, timeout_ms: int = 5000) -> dict[str, Any]:
    """List available tools exposed by an MCP server."""
    report = _json(
        run("mcp", "tools-list", mcp_id, "--timeout", str(timeout_ms), "--json"),
        f"mcp tools-list {mcp_id}",
    )
    if not isinstance(report, dict):
        raise BridgeError(f"mcp tools-list {mcp_id} did not return a tools list object")
    return report


def mcp_call_tool(
    mcp_id: str,
    tool_name: str,
    args: dict[str, Any] | None = None,
    timeout_ms: int = 15000,
) -> dict[str, Any]:
    """Dynamically invoke a tool on an MCP server over stdio transport."""
    argv = ["mcp", "call-tool", mcp_id, tool_name, "--timeout", str(timeout_ms), "--json"]
    if args is not None:
        argv.extend(["--args", json.dumps(args)])
    report = _json(run(*argv), f"mcp call-tool {mcp_id} {tool_name}")
    if not isinstance(report, dict):
        raise BridgeError(f"mcp call-tool {mcp_id} {tool_name} did not return a result object")
    return report


def mcp_targets() -> list[dict[str, Any]]:
    """List all supported AI agent harness targets and their sync status."""
    report = _json(run("mcp", "targets", "--json"), "mcp targets")
    if not isinstance(report, list):
        raise BridgeError("mcp targets did not return a list")
    return report


def mcp_deploy() -> dict[str, Any]:
    """Recompile the catalog into every installed harness config."""
    return _json(run("--mcp-deploy"), "--mcp-deploy")


def bridge_status() -> list[dict[str, Any]]:
    """Harness link state for every known harness."""
    report = _json(run("--bridge-status"), "--bridge-status")
    if not isinstance(report, list):
        raise BridgeError("--bridge-status did not return a list of harnesses")
    return report


def apply_preset(preset_id: str) -> dict[str, Any]:
    """Activate a named mission preset across all harnesses."""
    return _json(run("--preset", preset_id), f"--preset {preset_id}")


def deploy_bridge() -> dict[str, Any]:
    """Back up and symlink every installed harness into the fleet projection."""
    return _json(run("--bridge-deploy"), "--bridge-deploy")


def vault_list() -> list[dict[str, Any]]:
    """Masked credential services; zero secrets reach the caller."""
    report = _json(run("vault", "list", "--json"), "vault list")
    if not isinstance(report, list):
        raise BridgeError("vault list did not return a list of services")
    return report


def vault_http(
    service: str,
    endpoint: str,
    method: str = "GET",
    headers_json: str | None = None,
    body: str | None = None,
    key_tag: str | None = None,
    key_number: int | None = None,
) -> dict[str, Any]:
    """Blind HTTP with the stored credential injected inside the binary."""
    argv = [
        "vault", "http",
        "--service", service,
        "--endpoint", endpoint,
        "--method", method,
        "--json",
    ]
    if headers_json is not None:
        argv += ["--headers", headers_json]
    if body is not None:
        argv += ["--body", body]
    if key_tag is not None:
        argv += ["--key-tag", key_tag]
    if key_number is not None:
        argv += ["--key-number", str(key_number)]
    report = _json(run(*argv), f"vault http {service}")
    if not isinstance(report, dict):
        raise BridgeError("vault http did not return a result object")
    return report


def vault_exec(
    service: str,
    command: list[str],
    key_number: int | None = None,
) -> dict[str, Any]:
    """CLI command with stored credentials injected in memory by the binary."""
    argv = ["vault", "exec", service]
    if key_number is not None:
        argv += ["--key-number", str(key_number)]
    argv += ["--", *command]
    report = _json(run(*argv), f"vault exec {service}")
    if not isinstance(report, dict):
        raise BridgeError("vault exec did not return a result object")
    return report


def vault_set_enabled(service: str, enabled: bool) -> dict[str, Any]:
    """Flip the operator kill-switch; the blind proxy refuses disabled services."""
    state = "on" if enabled else "off"
    report = _json(
        run("vault", "set-enabled", service, state, "--json"),
        f"vault set-enabled {service}",
    )
    if not isinstance(report, dict):
        raise BridgeError("vault set-enabled did not return a service object")
    return report


def vault_inspect(service: str) -> dict[str, Any]:
    """Inspect credential service details, masked keys, health, and tags."""
    report = _json(run("vault", "inspect", service, "--json"), f"vault inspect {service}")
    if not isinstance(report, dict):
        raise BridgeError(f"vault inspect {service} did not return an object")
    return report


def vault_rotate(
    service: str, next_key: bool = True, key_number: int | None = None
) -> dict[str, Any]:
    """Advance the active key pointer or rotate a specific key in the pool."""
    argv = ["vault", "rotate", service, "--json"]
    if next_key:
        argv.append("--next")
    if key_number is not None:
        argv.extend(["--key-number", str(key_number)])
    report = _json(run(*argv), f"vault rotate {service}")
    if not isinstance(report, dict):
        raise BridgeError(f"vault rotate {service} did not return an object")
    return report


def vault_test(service: str, key_number: int | None = None) -> dict[str, Any]:
    """Ping provider verify endpoint, measure latency, and persist observed health."""
    argv = ["vault", "test", service, "--json"]
    if key_number is not None:
        argv.extend(["--key-number", str(key_number)])
    report = _json(run(*argv), f"vault test {service}")
    if not isinstance(report, dict):
        raise BridgeError(f"vault test {service} did not return a test result object")
    return report


def vault_presets() -> list[dict[str, Any]]:
    """List built-in provider presets with headers, env vars, and metadata fields."""
    report = _json(run("vault", "presets", "--json"), "vault presets")
    if not isinstance(report, list):
        raise BridgeError("vault presets did not return a list")
    return report


def vault_audit() -> dict[str, Any]:
    """Diagnostic check of storage encryption, 0600 file permissions, and backups."""
    report = _json(run("vault", "audit", "--json"), "vault audit")
    if not isinstance(report, dict):
        raise BridgeError("vault audit did not return an audit report")
    return report


def vault_add_key(service: str, key: str, tag: str | None = None) -> dict[str, Any]:
    """Push a new key to an existing service pool."""
    argv = ["vault", "add-key", service, "--key", key, "--json"]
    if tag is not None:
        argv.extend(["--tag", tag])
    report = _json(run(*argv), f"vault add-key {service}")
    if not isinstance(report, dict):
        raise BridgeError(f"vault add-key {service} did not return a service object")
    return report


def vault_remove_key(service: str, key_number: int) -> dict[str, Any]:
    """Remove a key from the pool by 1-based key number."""
    argv = ["vault", "remove-key", service, "--key-number", str(key_number), "--json"]
    report = _json(run(*argv), f"vault remove-key {service}")
    if not isinstance(report, dict):
        raise BridgeError(f"vault remove-key {service} did not return a service object")
    return report


def vault_set_primary(service: str, key_number: int) -> dict[str, Any]:
    """Set the primary active key by 1-based key number."""
    argv = ["vault", "set-primary", service, "--key-number", str(key_number), "--json"]
    report = _json(run(*argv), f"vault set-primary {service}")
    if not isinstance(report, dict):
        raise BridgeError(f"vault set-primary {service} did not return a service object")
    return report
