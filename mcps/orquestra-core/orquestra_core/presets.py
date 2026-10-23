"""Built-in preset definitions and preset management for the OrquestraAI control plane."""

from __future__ import annotations

import json
import re
from typing import Any

from . import bridge, catalog, fsutil, paths, skills
from .errors import MissingPreset

# Maximum length accepted for a preset ID (guards against absurdly long inputs).
_MAX_ID_LEN = 64

# Characters allowed in a preset ID: lowercase letters, digits, hyphens, underscores.
_SAFE_ID = re.compile(r"^[a-z0-9_-]{1,64}$")

BUILTIN_PRESETS: list[dict[str, Any]] = [
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


def _custom_entries(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Custom profiles, reading canonical `custom` first, legacy `presets` after."""
    entries: list[dict[str, Any]] = []
    for key in ("custom", "presets"):
        raw = data.get(key)
        if isinstance(raw, list):
            entries.extend(item for item in raw if isinstance(item, dict))
    return entries


def _load_custom_file() -> dict[str, Any]:
    """Read presets.json if it exists; return empty structure otherwise."""
    path = paths.presets_path()
    if not path.is_file():
        return {"active": None, "custom": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"active": None, "custom": []}
    if not isinstance(data, dict):
        return {"active": None, "custom": []}
    return data


def _write_custom_file(custom: list[dict[str, Any]], active: Any) -> None:
    """Persist the canonical shape (`custom` + `active`) atomically."""
    text = json.dumps({"custom": custom, "active": active}, indent=2) + "\n"
    fsutil.atomic_write_text(paths.presets_path(), text)


def list_presets() -> list[dict[str, Any]]:
    """Return all mission presets (built-ins + custom) with active and builtin tags."""
    data = _load_custom_file()
    active_id: str | None = data.get("active")
    custom_raw: list[dict[str, Any]] = _custom_entries(data)

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


def slugify(name: str) -> str:
    """`Game Dev` -> `game-dev`; runs of punctuation collapse to one dash."""
    slug = re.sub(r"[^a-z0-9_-]+", "-", (name or "").strip().lower()).strip("-")
    return slug or "preset"


def _live_skill_ids() -> list[str]:
    """Ids projected in the global scope, the fleet-wide skill baseline."""
    return sorted(
        row["id"] for row in skills.list_skills("global") if row.get("enabled")
    )


def _live_mcp_ids() -> list[str]:
    """Ids globally enabled in the catalog, the fleet-wide MCP baseline."""
    return sorted(
        row["id"] for row in catalog.list_mcps() if row.get("globalEnabled")
    )


def save_preset(
    name: str,
    description: str = "",
    skills: list[str] | None = None,
    mcps: list[str] | None = None,
    icon: str = "custom",
) -> dict[str, Any]:
    """Create or update a custom preset, persisting it to presets.json."""
    clean_name = (name or "").strip()
    if not clean_name:
        raise ValueError("a preset needs a name")
    preset_id = slugify(clean_name)
    _validate_id(preset_id)
    if preset_id in _BUILTIN_IDS:
        raise ValueError(
            f"cannot overwrite built-in preset '{preset_id}'; pick another name"
        )
    preset: dict[str, Any] = {
        "id": preset_id,
        "name": clean_name,
        "description": (description or "").strip(),
        "icon": (icon or "custom").strip() or "custom",
        "skills": list(skills) if skills is not None else _live_skill_ids(),
        "mcps": list(mcps) if mcps is not None else _live_mcp_ids(),
        "harnessSkills": {},
        "harnessMcps": {},
        "allSkills": False,
        "allMcps": False,
        "builtin": False,
        "active": False,
    }
    data = _load_custom_file()
    custom = [entry for entry in _custom_entries(data) if str(entry.get("id")) != preset_id]
    custom.append(preset)
    _write_custom_file(custom, data.get("active"))
    return preset


def delete_preset(preset_id: str) -> dict[str, Any]:
    """Remove one custom preset; built-ins and unknown ids raise."""
    _validate_id(preset_id)
    if preset_id in _BUILTIN_IDS:
        raise ValueError(f"Cannot delete built-in preset '{preset_id}'")
    data = _load_custom_file()
    custom = _custom_entries(data)
    kept = [entry for entry in custom if str(entry.get("id")) != preset_id]
    if len(kept) == len(custom):
        raise MissingPreset(f"Preset '{preset_id}' not found")
    active = data.get("active")
    if active == preset_id:
        active = None
    _write_custom_file(kept, active)
    return {"id": preset_id, "deleted": True, "message": f"Preset '{preset_id}' deleted."}
