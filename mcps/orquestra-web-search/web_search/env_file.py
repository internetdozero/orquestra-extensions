"""Find the operator's ``.env`` so the server works without a manual export.

MCP clients start the server from an arbitrary working directory and often pass
no ``env`` block at all, so ``EXA_API_KEY`` has to be discoverable on its own.

An explicit ``WEB_SEARCH_ENV_FILE`` is authoritative: it is the only file read,
so a typo fails loudly instead of silently loading another key. Otherwise the
first ``.env`` found next to the installed package wins, then the first one
found by walking up from the working directory (the case of a wheel install
with a project-local file).

Only the requested keys are copied into ``os.environ``, and a value already in
the environment is never overwritten, so an explicit export always wins.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Iterator

ENV_OVERRIDE = "WEB_SEARCH_ENV_FILE"
FILENAME = ".env"

# Deep enough for a package nested in a monorepo, shallow enough to stay cheap.
_MAX_PARENT_HOPS = 8


def _ancestors(start: Path) -> Iterator[Path]:
    """Yield ``start`` and its parents, stopping at the filesystem root."""
    current = start if start.is_dir() else start.parent
    for _ in range(_MAX_PARENT_HOPS):
        yield current
        if current.parent == current:
            return
        current = current.parent


def candidates() -> list[Path]:
    """Files to try, most authoritative first, without duplicates."""
    override = os.environ.get(ENV_OVERRIDE, "").strip()
    if override:
        return [Path(override).expanduser()]

    found: list[Path] = []
    seen: set[Path] = set()

    for root in (Path(__file__).resolve().parent, Path.cwd()):
        for directory in _ancestors(root.resolve()):
            candidate = directory / FILENAME
            if candidate not in seen:
                seen.add(candidate)
                found.append(candidate)
            if candidate.is_file():
                break
    return found


def parse(text: str) -> dict[str, str]:
    """Read ``KEY=value`` lines, tolerating ``export``, quotes and comments."""
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].rstrip()
        values[key] = value
    return values


def load(names: Iterable[str]) -> Path | None:
    """Copy ``names`` from the first matching env file into ``os.environ``.

    Returns the file that supplied a value, or ``None`` when no candidate
    defines any of them. Unreadable candidates are skipped rather than raised:
    the caller reports the missing key with its own actionable message.
    """
    wanted = list(names)
    for path in candidates():
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        values = parse(text)
        supplied = False
        for name in wanted:
            value = values.get(name, "").strip()
            if value and not os.environ.get(name, "").strip():
                os.environ[name] = value
                supplied = True
        if supplied:
            return path
    return None
