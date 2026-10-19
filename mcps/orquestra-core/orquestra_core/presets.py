"""Built-in preset definitions and preset management for the OrquestraAI control plane."""

from __future__ import annotations

import json
import re
from typing import Any

from . import bridge, paths

# Maximum length accepted for a preset ID (guards against absurdly long inputs).
_MAX_ID_LEN = 64

# Characters allowed in a preset ID: lowercase letters, digits, hyphens, underscores.
_SAFE_ID = re.compile(r"^[a-z0-9_-]{1,64}$")

BUILTIN_PRESETS: list[dict[str, Any]] = [
    {
        "id": "stealth",
        "name": "Stealth",
        "description": "Zero-bloat profile: one lightweight skill plus core MCPs",
        "skills": ["rtk"],
        "mcps": ["headroom", "idea-vault", "orquestra-core"],
        "all_skills": False,
        "all_mcps": False,
        "icon": "shield",
        "builtin": True,
    },
    {
        "id": "rust-dev",
        "name": "Rust Dev",
        "description": "Systems and low-level work",
        "skills": ["rtk", "modular-start", "github"],
        "mcps": ["github", "rea", "idea-vault", "orquestra-core"],
        "all_skills": False,
        "all_mcps": False,
        "icon": "cpu",
        "builtin": True,
    },
    {
        "id": "web-fullstack",
        "name": "Web Fullstack",
        "description": "Frontend and cloud work",
        "skills": ["rtk", "github", "generative_ui"],
        "mcps": ["puppeteer", "canva", "github", "idea-vault", "cloudflare"],
        "all_skills": False,
        "all_mcps": False,
        "icon": "globe",
        "builtin": True,
    },
    {
        "id": "full-power",
        "name": "Full Power",
        "description": "Every skill in the vault and every MCP server in the catalog",
        "skills": [],
        "mcps": [],
        "all_skills": True,
        "all_mcps": True,
        "icon": "zap",
        "builtin": True,
    },
]

_BUILTIN_IDS: set[str] = {p["id"] for p in BUILTIN_PRESETS}


def _load_custom_file() -> dict[str, Any]:
    """Read presets.json if it exists; return empty structure otherwise."""
    path = paths.presets_path()
    if not path.is_file():
        return {"active": None, "presets": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"active": None, "presets": []}
    if not isinstance(data, dict):
        return {"active": None, "presets": []}
    return data


def list_presets() -> list[dict[str, Any]]:
    """Return all mission presets (built-ins + custom) with active and builtin tags."""
    data = _load_custom_file()
    active_id: str | None = data.get("active")
    custom_raw: list[dict[str, Any]] = data.get("presets", [])

    # Index custom entries by id for O(1) lookup; they shadow nothing in built-ins.
    custom_by_id: dict[str, dict[str, Any]] = {}
    for entry in custom_raw:
        if isinstance(entry, dict) and "id" in entry:
            custom_by_id[str(entry["id"])] = entry

    result: list[dict[str, Any]] = []

    # Built-ins first, preserving canonical order.
    for preset in BUILTIN_PRESETS:
        row = dict(preset)
        row["active"] = row["id"] == active_id
        result.append(row)

    # Custom-only entries (those not overriding a built-in id).
    for cid, entry in custom_by_id.items():
        if cid in _BUILTIN_IDS:
            continue
        row = dict(entry)
        row["builtin"] = False
        row["active"] = cid == active_id
        result.append(row)

    return result


def _validate_id(preset_id: str) -> None:
    """Raise ValueError if preset_id is empty, too long, or contains unsafe characters."""
    if not preset_id or not preset_id.strip():
        raise ValueError("preset_id must not be empty")
    if len(preset_id) > _MAX_ID_LEN:
        raise ValueError(
            f"preset_id is too long ({len(preset_id)} chars, max {_MAX_ID_LEN})"
        )
    if not _SAFE_ID.match(preset_id):
        raise ValueError(
            f"invalid preset_id '{preset_id}': only lowercase letters, digits, "
            "hyphens and underscores are allowed"
        )


def apply_preset(preset_id: str) -> dict[str, Any]:
    """Validate preset_id, then delegate to the native binary via bridge.apply_preset."""
    _validate_id(preset_id)
    return bridge.apply_preset(preset_id)
