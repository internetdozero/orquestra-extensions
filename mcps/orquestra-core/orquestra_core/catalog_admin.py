"""Adding and removing MCP servers in the OrquestraAI catalog."""

from __future__ import annotations

import re
from typing import Any

from . import bridge, catalog, paths

_MCP_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def _validate_id(mcp_id: str) -> str:
    name = (mcp_id or "").strip()
    if not _MCP_ID.match(name):
        raise ValueError("mcp_id must be 1-64 characters of letters, digits, dots, underscores or dashes")
    return name


def _text(value: str, label: str) -> str:
    text = (value or "").strip()
    if not text:
        raise ValueError(f"{label} must not be empty")
    return text


def _deploy(saved_note: str) -> dict[str, Any]:
    """Compile the catalog outward, keeping the saved-state hint on failure."""
    try:
        return bridge.mcp_deploy()
    except RuntimeError as error:
        raise RuntimeError(f"{error} ({saved_note}; rerun orquestra --mcp-deploy)") from error


def create_mcp(
    mcp_id: str,
    name: str,
    description: str,
    command: str,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
    global_enabled: bool = True,
) -> dict[str, Any]:
    """Register a new server in `mcps.json`, then propagate it to every harness."""
    identifier = _validate_id(mcp_id)
    data = catalog.read_catalog()
    if identifier in data["mcps"]:
        raise ValueError(f"MCP server '{identifier}' already exists")

    entry = {
        "id": identifier,
        "name": _text(name, "name"),
        "description": _text(description, "description"),
        "command": _text(command, "command"),
        "args": [str(item) for item in (args or [])],
        "env": {str(key): str(value) for key, value in (env or {}).items()},
        "globalEnabled": bool(global_enabled),
        "enabledHarnesses": [],
    }
    data["mcps"][identifier] = entry
    managed = data.setdefault("managedIds", [])
    if identifier not in managed:
        managed.append(identifier)

    backup = catalog.save_catalog(data, "pre-create-mcp")
    deploy = _deploy(f"catalog saved at {paths.catalog_path()}")
    return {
        "id": identifier,
        "created": True,
        "catalog": str(paths.catalog_path()),
        "backup": str(backup) if backup else None,
        "changed": deploy.get("changed", []),
        "targets": deploy.get("targets", 0),
        "servers": deploy.get("servers", 0),
        "globalEnabled": entry["globalEnabled"],
        "enabledHarnesses": [],
    }


def delete_mcp(mcp_id: str) -> dict[str, Any]:
    """Drop a server from `mcps.json` and from every harness config."""
    identifier = _validate_id(mcp_id)
    data = catalog.read_catalog()
    if identifier not in data["mcps"]:
        raise ValueError(f"unknown MCP server '{identifier}'")
    data["mcps"].pop(identifier)
    # Keep the id in managedIds for this deploy: that membership is what tells
    # the serializers the block is stale and has to be stripped from each
    # config. The native deploy shrinks managedIds again once it succeeds.
    if identifier not in data.setdefault("managedIds", []):
        data["managedIds"].append(identifier)

    backup = catalog.save_catalog(data, "pre-delete-mcp")
    deploy = _deploy(f"catalog saved at {paths.catalog_path()}")
    return {
        "id": identifier,
        "deleted": True,
        "catalog": str(paths.catalog_path()),
        "backup": str(backup) if backup else None,
        "changed": deploy.get("changed", []),
        "targets": deploy.get("targets", 0),
        "servers": deploy.get("servers", 0),
        "managed": identifier in catalog.read_catalog().get("managedIds", []),
    }
