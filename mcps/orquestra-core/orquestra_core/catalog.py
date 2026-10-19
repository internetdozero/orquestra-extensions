"""The OrquestraAI MCP catalog: reading state and toggling servers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import bridge, fsutil, paths

FIELDS = ("id", "name", "description", "command", "args", "globalEnabled", "enabledHarnesses")


def read_catalog() -> dict[str, Any]:
    """Load `mcps.json`, failing with a hint when OrquestraAI has not started yet."""
    path = paths.catalog_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"MCP catalog not found at {path}; launch OrquestraAI once") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"MCP catalog at {path} is not valid JSON: {error}") from error
    if not isinstance(data.get("mcps"), dict):
        raise ValueError(f"MCP catalog at {path} has no 'mcps' object")
    return data


def save_catalog(catalog: dict[str, Any], prefix: str) -> Path | None:
    """Back up and atomically replace `mcps.json`, keeping it private."""
    path = paths.catalog_path()
    backup = fsutil.backup_file(path, paths.backups_dir(), prefix, ".json")
    text = json.dumps(catalog, indent=2, ensure_ascii=False) + "\n"
    fsutil.atomic_write_text(path, text, 0o600)
    return backup


def find_mcp(mcp_id: str) -> dict[str, Any]:
    """Return one catalog entry, or raise when the id is unknown."""
    entry = read_catalog()["mcps"].get(mcp_id)
    if entry is None:
        raise ValueError(f"unknown MCP server '{mcp_id}'")
    return entry


def list_mcps() -> list[dict[str, Any]]:
    """Every registered server with its effective state, sorted by id."""
    servers = read_catalog()["mcps"].values()
    rows = [{key: server.get(key) for key in FIELDS} for server in servers]
    return sorted(rows, key=lambda row: row["id"])


def toggle_mcp(mcp_id: str, scope: str = paths.GLOBAL_SCOPE, enabled: bool = True) -> dict[str, Any]:
    """Flip one server in the catalog, then recompile every harness config.

    The catalog is edited here (atomically, with a backup) instead of through
    `--mcp-set` so the returned `changed` list is the deploy's real answer.
    A harness cannot opt out of a globally enabled server, matching the
    desktop rule: disable it globally first.
    """
    name = (scope or paths.GLOBAL_SCOPE).strip()
    data = read_catalog()
    entry = data["mcps"].get(mcp_id)
    if entry is None:
        raise ValueError(f"unknown MCP server '{mcp_id}'")

    if name == paths.GLOBAL_SCOPE:
        entry["globalEnabled"] = bool(enabled)
    else:
        paths.active_scope(name)  # rejects unknown harness scopes
        if entry.get("globalEnabled") and not enabled:
            raise ValueError(
                f"'{mcp_id}' is inherited from Global; disable it in Global first"
            )
        harnesses = [item for item in entry.get("enabledHarnesses", []) if item != name]
        if enabled:
            harnesses.append(name)
        entry["enabledHarnesses"] = sorted(harnesses)

    backup = save_catalog(data, "pre-toggle-mcp")
    deploy = bridge.mcp_deploy()
    updated = find_mcp(mcp_id)
    return {
        "id": mcp_id,
        "scope": name,
        "enabled": bool(enabled),
        "changed": deploy.get("changed", []),
        "targets": deploy.get("targets", 0),
        "servers": deploy.get("servers", 0),
        "backup": str(backup) if backup else None,
        "globalEnabled": updated.get("globalEnabled"),
        "enabledHarnesses": updated.get("enabledHarnesses", []),
    }
