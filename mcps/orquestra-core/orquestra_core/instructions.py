"""Master `AGENTS.md`: reads, section-scoped mission rules, backups, atomic writes."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import fsutil, paths

HEADING = re.compile(r"^##[ \t]+(.+?)[ \t]*$", re.M)
_BULLET = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+")


def read_instructions() -> str:
    """Return the master instruction file verbatim."""
    path = paths.instructions_path()
    if not path.is_file():
        raise ValueError(f"master instructions not found at {path}")
    return path.read_text(encoding="utf-8")


def _clean_title(title: str) -> str:
    name = (title or "").strip().lstrip("#").strip()
    if not name:
        raise ValueError("section_title must not be empty")
    if "\n" in name:
        raise ValueError("section_title must be a single line")
    return name


def _rule_lines(content: str) -> list[str]:
    """Normalize a directive into bullets so it renders like the rest of the file."""
    lines = [line.rstrip() for line in (content or "").strip().splitlines()]
    lines = [line for line in lines if line.strip()]
    if not lines:
        raise ValueError("rule_content must not be empty")
    return [line if _BULLET.match(line) or line.startswith((" ", "\t")) else f"- {line}" for line in lines]


def _insert(text: str, title: str, block: list[str]) -> str:
    """Place the block at the end of the named section, or append a new one."""
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        match = HEADING.match(line)
        if match and match.group(1).strip().lower() == title.lower():
            start = index + 1
            break

    if start is None:
        body = text.rstrip("\n")
        merged = ([body, ""] if body else []) + [f"## {title}", *block]
        return "\n".join(merged) + "\n"

    end = len(lines)
    for index in range(start, len(lines)):
        if HEADING.match(lines[index]):
            end = index
            break

    # Keep the section's own content, then append after a blank separator.
    content_end = end
    while content_end > start and not lines[content_end - 1].strip():
        content_end -= 1
    head = lines[:content_end]
    tail = lines[end:]
    merged = head + ([""] if head else []) + block
    if tail:
        merged += ["", *tail]
    return "\n".join(merged) + "\n"


def _backup(path: Path) -> Path | None:
    """Keep a timestamped copy of the file about to change."""
    return fsutil.backup_file(path, paths.backups_dir(), "AGENTS", ".md")


def append_mission_rule(section_title: str, rule_content: str) -> dict[str, Any]:
    """Append one directive to a section, backing up and replacing atomically."""
    title = _clean_title(section_title)
    block = _rule_lines(rule_content)
    path = paths.instructions_path()
    before = path.read_text(encoding="utf-8") if path.is_file() else "# Global Agent Instructions\n"
    after = _insert(before, title, block)
    if after == before:
        return {"section": title, "path": str(path), "changed": False, "backup": None}
    backup = _backup(path)
    fsutil.atomic_write_text(path, after)
    return {
        "section": title,
        "path": str(path),
        "changed": True,
        "lines_added": len(block),
        "bytes": len(after.encode("utf-8")),
        "backup": str(backup) if backup else None,
    }
