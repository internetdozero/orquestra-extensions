"""Creating skills in the vault and retiring them without hard deletes."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any

from . import fsutil, paths, skills

_SKILL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,63}$")
_NEEDS_QUOTES = re.compile(r"""[:"'\[\]{}#]|^\s|\s$""")


def _validate_id(skill_id: str) -> str:
    """Skill ids are letters, digits and dashes so they survive every scope path."""
    name = (skill_id or "").strip()
    if not _SKILL_ID.match(name):
        raise ValueError("skill_id must be 1-64 characters of letters, digits or dashes")
    return name


def _clean(value: str, label: str) -> str:
    text = " ".join((value or "").split())
    if not text:
        raise ValueError(f"{label} must not be empty")
    return text


def _yaml(value: str) -> str:
    if _NEEDS_QUOTES.search(value):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _manifest(name: str, description: str, body: str) -> str:
    content = body.strip()
    if not content:
        raise ValueError("instructions_markdown must not be empty")
    return (
        "---\n"
        f"name: {_yaml(name)}\n"
        f"description: {_yaml(description)}\n"
        "---\n\n"
        f"{content}\n"
    )


def _script_name(name: str) -> str:
    candidate = (name or "").strip()
    if not candidate or candidate.startswith(".") or "/" in candidate or "\\" in candidate:
        raise ValueError(f"invalid script name '{name}'")
    if candidate in {".", ".."}:
        raise ValueError(f"invalid script name '{name}'")
    return candidate


def create_skill(
    skill_id: str,
    name: str,
    description: str,
    instructions_markdown: str,
    scripts: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Write a new `SKILL.md` (plus optional scripts) into the master vault."""
    skill = _validate_id(skill_id)
    directory = paths.skills_library() / skill
    if directory.exists():
        raise ValueError(f"skill '{skill}' already exists at {directory}")

    manifest = _manifest(_clean(name, "name"), _clean(description, "description"), instructions_markdown)
    files: list[str] = []
    try:
        (directory / "scripts").mkdir(parents=True, exist_ok=True)
        fsutil.atomic_write_text(directory / "SKILL.md", manifest)
        for filename, content in (scripts or {}).items():
            target = directory / "scripts" / _script_name(filename)
            fsutil.atomic_write_text(target, content if content.endswith("\n") else content + "\n", 0o644)
            files.append(str(target.relative_to(directory)))
    except BaseException:
        shutil.rmtree(directory, ignore_errors=True)
        raise

    return {
        "id": skill,
        "created": True,
        "path": str(directory / "SKILL.md"),
        "tokens": skills.estimate_tokens(manifest),
        "bytes": len(manifest.encode("utf-8")),
        "scripts": files,
    }


def delete_skill(skill_id: str) -> dict[str, Any]:
    """Unlink a skill from every scope, then archive its vault directory."""
    directory = skills.skill_dir(skill_id)
    unlinked: list[str] = []
    for scope in [paths.GLOBAL_SCOPE, *paths.harness_ids()]:
        link = paths.active_root() / scope / directory.name
        if not os.path.lexists(link):
            continue
        if link.is_dir() and not link.is_symlink():
            raise ValueError(f"{link} is a real directory; refusing to delete it")
        link.unlink()
        unlinked.append(str(link))

    archived_root = fsutil.unique_directory(paths.backups_dir(), f"deleted-skills-{fsutil.timestamp()}")
    destination = archived_root / directory.name
    shutil.move(str(directory), str(destination))
    skills.clear_cache()
    return {
        "id": directory.name,
        "deleted": True,
        "unlinked": unlinked,
        "backup": str(destination),
    }
