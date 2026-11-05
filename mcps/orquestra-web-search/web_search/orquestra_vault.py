"""Search through OrquestraAI's blind vault without exposing its Exa key."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

ENDPOINT = "https://api.exa.ai/search"
TIMEOUT_SECONDS = 40


def _binary() -> str | None:
    """Locate the same native CLI used by the Orquestra Core MCP."""
    override = os.environ.get("ORQUESTRA_BIN", "").strip()
    if override:
        return override
    found = shutil.which("orquestra")
    if found:
        return found
    fallback = Path.home() / ".local" / "bin" / "orquestra"
    return str(fallback) if fallback.is_file() else None


def _run(binary: str, *args: str, timeout: int = 8) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [binary, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _exa_service(binary: str) -> str | None:
    """Find the enabled Exa-preset service using masked metadata only."""
    try:
        result = _run(binary, "vault", "list", "--json")
        services = json.loads(result.stdout) if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None
    if not isinstance(services, list):
        return None
    for service in services:
        total_keys = service.get("totalKeys", 0) if isinstance(service, dict) else 0
        if (
            isinstance(service, dict)
            and service.get("preset") == "exa"
            and service.get("enabled") is True
            and isinstance(total_keys, int)
            and total_keys > 0
        ):
            service_id = service.get("id")
            return service_id if isinstance(service_id, str) and service_id else None
    return None


def search(
    query: str,
    num_results: int,
    include_domains: list[str] | None,
    start_published_date: str | None,
) -> dict[str, Any] | None:
    """Return Exa's API payload through the vault, or ``None`` for fallback.

    The CLI injects the key inside OrquestraAI and returns only a scrubbed
    response. Missing CLI/service, a disabled vault service or request failure
    leave the environment/``.env`` provider available as fallback.
    """
    binary = _binary()
    if binary is None:
        return None
    service_id = _exa_service(binary)
    if service_id is None:
        return None

    body: dict[str, Any] = {
        "query": query,
        "type": "auto",
        "numResults": num_results,
        "contents": {"highlights": True},
    }
    if include_domains:
        body["includeDomains"] = include_domains
    if start_published_date:
        body["startPublishedDate"] = start_published_date
    headers = json.dumps({"content-type": "application/json"}, separators=(",", ":"))
    serialized_body = json.dumps(body, separators=(",", ":"))

    try:
        result = _run(
            binary,
            "vault",
            "http",
            "--service",
            service_id,
            "--endpoint",
            ENDPOINT,
            "--method",
            "POST",
            "--headers",
            headers,
            "--body",
            serialized_body,
            "--json",
            timeout=TIMEOUT_SECONDS,
        )
        response = json.loads(result.stdout) if result.returncode == 0 else None
        if (
            not isinstance(response, dict)
            or not isinstance(response.get("status"), int)
            or not 200 <= response["status"] < 300
            or not isinstance(response.get("body"), str)
        ):
            return None
        payload = json.loads(response["body"])
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) and isinstance(payload.get("results"), list) else None
