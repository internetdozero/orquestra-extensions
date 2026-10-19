"""Skill vault scanning and atomic symlink projection into active scopes."""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import paths

_FRONTMATTER = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n?", re.S)
_HEADING = re.compile(r"^#+\s+")
_CACHE: dict[str, tuple[int, int, "SkillMeta"]] = {}


@dataclass(frozen=True)
class SkillMeta:
    """Everything a listing needs from one `SKILL.md`."""

    name: str
    description: str
    tokens: int


def estimate_tokens(text: str) -> int:
    """Cheap token weight: one token per four characters, never zero."""
    return max(1, math.ceil(len(text) / 4))


def _frontmatter(text: str) -> dict[str, str]:
    """Parse the flat `key: value` pairs of a leading YAML block."""
    match = _FRONTMATTER.match(text)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip().lower()] = value.strip().strip("\"'")
    return fields


def _fallback_description(text: str) -> str:
    """First prose line after the frontmatter, used when none is declared."""
    body = _FRONTMATTER.sub("", text, count=1)
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not _HEADING.match(stripped):
            return stripped
    return ""


def _meta(path: Path) -> SkillMeta:
    """Read one `SKILL.md`, memoized on (mtime, size) so repeats stay cheap."""
    stat = path.stat()
    key = str(path)
    cached = _CACHE.get(key)
    if cached and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
        return cached[2]
    text = path.read_text(encoding="utf-8", errors="replace")
    fields = _frontmatter(text)
    meta = SkillMeta(
        name=fields.get("name") or path.parent.name,
        description=fields.get("description") or _fallback_description(text),
        tokens=estimate_tokens(text),
    )
    _CACHE[key] = (stat.st_mtime_ns, stat.st_size, meta)
    return meta


def clear_cache() -> None:
    """Drop memoized metadata; used by tests that rewrite the vault."""
    _CACHE.clear()


def _skill_id(skill_id: str) -> str:
    """Validate an id so it can never escape the library."""
    name = (skill_id or "").strip()
    if not name or name in {".", ".."} or "/" in name or "\\" in name or name.startswith("."):
        raise ValueError(f"invalid skill id '{skill_id}'")
    return name


def skill_dir(skill_id: str) -> Path:
    """Resolve a skill id to a library directory that really holds a SKILL.md."""
    name = _skill_id(skill_id)
    directory = paths.skills_library() / name
    if not (directory / "SKILL.md").is_file():
        raise ValueError(f"skill '{name}' was not found in {paths.skills_library()}")
    return directory


def _link_path(scope: str, skill_id: str) -> Path:
    return paths.active_scope(scope) / skill_id


def _present(scope: str, skill_id: str) -> bool:
    return os.path.lexists(_link_path(scope, skill_id))


def _ensure_link(scope: str, skill_id: str, target: Path) -> bool:
    """Point `active/<scope>/<id>` at the vault atomically; True when it moved."""
    link = _link_path(scope, skill_id)
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink() and os.readlink(link) == str(target):
        return False
    if link.exists() and not link.is_symlink():
        raise ValueError(f"{link} is a real directory; refusing to replace it")
    temporary = link.with_name(f".{link.name}.tmp-{os.getpid()}")
    if os.path.lexists(temporary):
        os.unlink(temporary)
    os.symlink(target, temporary)
    os.replace(temporary, link)
    return True


def _drop_link(scope: str, skill_id: str) -> bool:
    """Remove one projection symlink; True when something was removed."""
    link = _link_path(scope, skill_id)
    if not os.path.lexists(link):
        return False
    if link.is_dir() and not link.is_symlink():
        raise ValueError(f"{link} is a real directory; refusing to delete it")
    link.unlink()
    return True


def _targets(scope: str) -> list[str]:
    """Global changes fan out to every harness projection, not just `global`."""
    if scope == paths.GLOBAL_SCOPE:
        return [paths.GLOBAL_SCOPE, *paths.harness_ids()]
    return [scope]


def list_skills(scope: str = paths.GLOBAL_SCOPE) -> list[dict[str, Any]]:
    """Describe every vault skill and whether this scope currently projects it."""
    name = (scope or paths.GLOBAL_SCOPE).strip()
    paths.active_scope(name)  # validates the scope before touching the vault
    library = paths.skills_library()
    if not library.is_dir():
        raise ValueError(f"skill library not found at {library}")
    rows: list[dict[str, Any]] = []
    for entry in sorted(library.iterdir(), key=lambda item: item.name):
        manifest = entry / "SKILL.md"
        if not manifest.is_file():
            continue
        meta = _meta(manifest)
        inherited = name != paths.GLOBAL_SCOPE and _present(paths.GLOBAL_SCOPE, entry.name)
        rows.append(
            {
                "id": entry.name,
                "name": meta.name,
                "description": meta.description,
                "tokens": meta.tokens,
                "enabled": _present(name, entry.name),
                "is_inherited": inherited,
            }
        )
    return rows


def enable_skill(skill_id: str, scope: str = paths.GLOBAL_SCOPE) -> dict[str, Any]:
    """Project a skill into a scope, fanning out to every harness for `global`."""
    name = (scope or paths.GLOBAL_SCOPE).strip()
    target = skill_dir(skill_id)
    changed = [s for s in _targets(name) if _ensure_link(s, target.name, target)]
    return {
        "id": target.name,
        "scope": name,
        "enabled": True,
        "changed": changed,
        "scopes": _targets(name),
        "tokens": _meta(target / "SKILL.md").tokens,
        "path": str(_link_path(name, target.name)),
    }


def disable_skill(skill_id: str, scope: str = paths.GLOBAL_SCOPE) -> dict[str, Any]:
    """Remove a skill from a scope, fanning out to every harness for `global`."""
    name = (scope or paths.GLOBAL_SCOPE).strip()
    target = skill_dir(skill_id)
    removed = [s for s in _targets(name) if _drop_link(s, target.name)]
    meta = _meta(target / "SKILL.md")
    return {
        "id": target.name,
        "scope": name,
        "enabled": False,
        "removed": removed,
        "scopes": _targets(name),
        "tokens_saved": meta.tokens if removed else 0,
    }
