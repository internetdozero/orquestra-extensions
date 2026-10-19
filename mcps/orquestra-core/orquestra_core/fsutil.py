"""Atomic writes, timestamped backups and collision-free names."""

from __future__ import annotations

import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def timestamp() -> str:
    """UTC stamp used in backup names: 20261017T141500Z."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def atomic_write_text(path: Path, text: str, mode: int | None = None) -> None:
    """Replace a text file through a temporary sibling, keeping its mode."""
    path.parent.mkdir(parents=True, exist_ok=True)
    effective = mode if mode is not None else (path.stat().st_mode & 0o777 if path.exists() else 0o644)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.tmp-", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, effective)
        os.replace(temporary, path)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise


def backup_file(path: Path, directory: Path, prefix: str, suffix: str = "") -> Path | None:
    """Copy an existing file into `directory` under a unique stamped name."""
    if not path.is_file():
        return None
    directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / f"{prefix}-{timestamp()}{suffix}"
    attempt = 1
    while candidate.exists():
        candidate = directory / f"{prefix}-{timestamp()}-{attempt}{suffix}"
        attempt += 1
    shutil.copy2(path, candidate)
    os.chmod(candidate, path.stat().st_mode & 0o777)
    return candidate


def unique_directory(parent: Path, stem: str) -> Path:
    """Create a fresh directory `parent/stem`, suffixing on a name clash."""
    candidate = parent / stem
    attempt = 1
    while True:
        try:
            candidate.mkdir(parents=True)
            return candidate
        except FileExistsError:
            candidate = parent / f"{stem}-{attempt}"
            attempt += 1
