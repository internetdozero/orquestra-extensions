"""Blind credential-vault operations through the native OrquestraAI binary.

Every function here is a thin bridge over ``orquestra vault <branch>``.
The binary owns storage, injection and scrubbing; this module only
validates input shape and maps binary refusals to actionable errors.
No secret is ever read from disk or held in a Python variable.
"""

from __future__ import annotations

import json
import shlex
from typing import Any

from . import bridge
from .errors import BridgeError, UnknownVaultService, VaultRequestError
from .schema import HttpMethod

_KNOWN_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")


def _refusal(error: BridgeError, service: str) -> Exception:
    """Map a binary refusal to the actionable error the agent can use."""
    message = str(error)
    if "unknown vault service" in message:
        return UnknownVaultService(message)
    return VaultRequestError(f"vault request for '{service}' failed: {message}")


def list_services() -> list[dict[str, Any]]:
    """List credential services with health and masked keys; zero secrets."""
    try:
        services = bridge.vault_list()
        for service in services:
            active_index = service.get("activeKeyIndex")
            if isinstance(active_index, int) and not isinstance(active_index, bool):
                service["activeKeyNumber"] = active_index + 1
        return services
    except BridgeError as error:
        raise VaultRequestError(f"vault list failed: {error}") from error


def execute_http(
    service_id: str,
    endpoint: str,
    method: HttpMethod = "GET",
    headers: dict[str, str] | None = None,
    body: Any | None = None,
    timeout: float = 30.0,
    key_number: int | None = None,
) -> dict[str, Any]:
    """Blind HTTP request; the stored credential is injected by the binary.

    ``timeout`` is validated but the binary applies its own transport
    timeouts; it is kept so existing callsites do not change shape.
    """
    name = (service_id or "").strip()
    if not name:
        raise VaultRequestError("service_id must not be empty")
    target = (endpoint or "").strip()
    if not target:
        raise VaultRequestError("endpoint must not be empty")
    verb = (method or "GET").upper()
    if verb not in _KNOWN_METHODS:
        allowed = ", ".join(f"'{item}'" for item in _KNOWN_METHODS)
        raise VaultRequestError(f"unknown method '{method}'; expected one of: {allowed}")
    if timeout <= 0:
        raise VaultRequestError("timeout must be positive")
    _validate_key_number(key_number)

    headers_json = json.dumps(headers) if headers else None
    if body is None:
        body_str = None
    elif isinstance(body, str):
        body_str = body
    else:
        try:
            body_str = json.dumps(body)
        except (TypeError, ValueError) as error:
            raise VaultRequestError(f"body is not JSON-serializable: {error}") from error
    try:
        result = bridge.vault_http(
            name, target, verb, headers_json, body_str, key_number=key_number
        )
        return _include_used_key_number(result)
    except BridgeError as error:
        raise _refusal(error, name) from error


def execute_exec(
    service_id: str,
    command: list[str] | str,
    timeout: float = 60.0,
    key_number: int | None = None,
) -> dict[str, Any]:
    """CLI command with stored credentials injected in memory by the binary.

    ``timeout`` is validated but the binary applies its own process
    limits; it is kept so existing callsites do not change shape.
    """
    name = (service_id or "").strip()
    if not name:
        raise VaultRequestError("service_id must not be empty")
    parts = list(command) if isinstance(command, list) else shlex.split(command)
    if not parts:
        raise VaultRequestError("command must not be empty")
    if timeout <= 0:
        raise VaultRequestError("timeout must be positive")
    _validate_key_number(key_number)
    try:
        result = bridge.vault_exec(name, parts, key_number)
        return _include_used_key_number(result)
    except BridgeError as error:
        raise _refusal(error, name) from error


def _validate_key_number(key_number: int | None) -> None:
    if key_number is not None and (
        isinstance(key_number, bool) or not isinstance(key_number, int) or key_number < 1
    ):
        raise VaultRequestError("key_number must be a positive 1-based integer")


def _include_used_key_number(result: dict[str, Any]) -> dict[str, Any]:
    """Keep the native zero-based field and add a human-friendly key number."""
    used_index = result.get("usedKeyIndex")
    if isinstance(used_index, int) and not isinstance(used_index, bool):
        result["usedKeyNumber"] = used_index + 1
    return result


def set_service_enabled(service_id: str, enabled: bool) -> dict[str, Any]:
    """Flip the operator kill-switch; the blind proxy refuses disabled services."""
    name = (service_id or "").strip()
    if not name:
        raise VaultRequestError("service_id must not be empty")
    if not isinstance(enabled, bool):
        raise VaultRequestError("enabled must be true or false")
    try:
        return bridge.vault_set_enabled(name, enabled)
    except BridgeError as error:
        raise _refusal(error, name) from error
