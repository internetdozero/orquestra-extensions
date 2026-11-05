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


def validate_skill(target: str) -> dict[str, Any]:
    """Validate directory structure, SKILL.md frontmatter, ID safety, and security limits."""
    raw = (target or "").strip()
    if not raw:
        raise ValueError("target must not be empty")

    path = (
        Path(raw).expanduser().resolve()
        if Path(raw).exists()
        else paths.skills_library() / raw
    )
    if not path.is_dir():
        raise ValueError(f"skill directory not found at {path}")

    skill_id = path.name
    if (
        skill_id.startswith(".")
        or ".." in skill_id
        or "/" in skill_id
        or "\\" in skill_id
    ):
        raise ValueError(f"invalid skill id or directory name '{skill_id}'")

    manifest = path / "SKILL.md"
    if not manifest.is_file():
        raise ValueError(f"missing SKILL.md manifest at {path}")

    text = manifest.read_text(encoding="utf-8", errors="replace")
    fields = skills._frontmatter(text)
    name = fields.get("name")
    description = fields.get("description")
    errors: list[str] = []
    if not name:
        errors.append("frontmatter missing required field 'name'")
    if not description:
        errors.append("frontmatter missing required field 'description'")

    file_count = 0
    max_depth = 0
    for root, dirs, files in os.walk(path):
        rel = Path(root).relative_to(path)
        depth = len(rel.parts)
        if depth > max_depth:
            max_depth = depth
        if max_depth >= 4:
            errors.append(
                f"directory depth exceeds maximum limit of 4 (found depth {max_depth})"
            )
            break
        file_count += len(files)
        if file_count >= 500:
            errors.append(
                f"file count exceeds maximum limit of 500 (found >= {file_count})"
            )
            break

    if errors:
        raise ValueError(
            f"skill validation failed for '{skill_id}': " + "; ".join(errors)
        )

    return {
        "id": skill_id,
        "valid": True,
        "name": name,
        "description": description,
        "path": str(path),
        "file_count": file_count,
        "max_depth": max_depth,
        "tokens": skills.estimate_tokens(text),
    }


def import_skill(
    source: str,
    subpath: str | None = None,
    scope: str = paths.GLOBAL_SCOPE,
    enable: bool = False,
) -> dict[str, Any]:
    """Import a skill from a local directory or remote git repo (with url#subpath support)."""
    clean_src = (source or "").strip()
    if not clean_src:
        raise ValueError("source must not be empty")

    if "#" in clean_src and not subpath:
        clean_src, subpath = clean_src.split("#", 1)

    is_git = (
        clean_src.startswith("http://")
        or clean_src.startswith("https://")
        or clean_src.startswith("git@")
        or clean_src.endswith(".git")
    )

    temp_clone_dir = None
    try:
        if is_git:
            import subprocess
            import uuid

            temp_clone_dir = (
                Path("/var/tmp/testing") / f"skill-import-{uuid.uuid4().hex}"
            )
            temp_clone_dir.parent.mkdir(parents=True, exist_ok=True)
            res = subprocess.run(
                ["git", "clone", "--depth", "1", clean_src, str(temp_clone_dir)],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode != 0:
                raise ValueError(
                    f"git clone failed: {res.stderr.strip() or res.stdout.strip()}"
                )
            src_dir = (
                temp_clone_dir / subpath if subpath else temp_clone_dir
            )
        else:
            local_path = Path(clean_src).expanduser().resolve()
            src_dir = local_path / subpath if subpath else local_path

        val = validate_skill(str(src_dir))
        skill_id = _validate_id(val["id"])
        dest = paths.skills_library() / skill_id
        if dest.exists():
            raise ValueError(f"skill '{skill_id}' already exists in library")

        shutil.copytree(str(src_dir), str(dest))
        skills.clear_cache()

        enabled_report = None
        if enable:
            enabled_report = skills.enable_skill(skill_id, scope=scope)

        return {
            "id": skill_id,
            "imported": True,
            "source": source,
            "path": str(dest / "SKILL.md"),
            "enabled": enable,
            "scope": scope if enable else None,
            "activation": enabled_report,
        }
    finally:
        if temp_clone_dir and temp_clone_dir.exists():
            shutil.rmtree(str(temp_clone_dir), ignore_errors=True)
