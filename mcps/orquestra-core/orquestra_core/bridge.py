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
    report = _json(run(*argv), f"vault http {service}")
    if not isinstance(report, dict):
        raise BridgeError("vault http did not return a result object")
    return report


def vault_exec(service: str, command: list[str]) -> dict[str, Any]:
    """CLI command with stored credentials injected in memory by the binary."""
    report = _json(run("vault", "exec", service, "--", *command), f"vault exec {service}")
    if not isinstance(report, dict):
        raise BridgeError("vault exec did not return a result object")
    return report
