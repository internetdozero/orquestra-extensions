"""Age-gated cleanup of stale sockets, staging dirs and testing scratch."""

from __future__ import annotations

import os
import shutil
import socket
import stat
import time
from pathlib import Path
from typing import Any

# Overridable so tests own their fixtures; production values are the real paths.
SOCKET_DIR = Path.home() / ".orquestra"
STAGING_DIR = Path.home() / ".codex" / ".tmp" / "marketplaces" / ".staging"
TESTING_DIR = Path("/var/tmp/testing")

DEFAULT_TARGETS = ("sockets", "staging", "testing_scratch")
DEFAULT_OLDER_THAN_HOURS = 6


def _age_hours(path: Path, now: float | None = None) -> float:
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return -1.0
    return ((now or time.time()) - mtime) / 3600


def _size_bytes(path: Path) -> int:
    if path.is_symlink() or path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total


def _is_socket(path: Path) -> bool:
    try:
        return stat.S_ISSOCK(path.stat().st_mode)
    except OSError:
        return False


def socket_alive(path: Path) -> bool:
    """True when something still answers on this Unix domain socket."""
    if not _is_socket(path):
        return False
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(0.25)
    try:
        client.connect(str(path))
        return True
    except (FileNotFoundError, ConnectionRefusedError, OSError):
        return False
    finally:
        client.close()


def _collect(directory: Path | None) -> list[Path]:
    if directory is None or not directory.is_dir():
        return []
    return sorted(p for p in directory.iterdir() if p.name != ".")


def _remove(path: Path) -> str | None:
    try:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
        return None
    except OSError as error:
        return str(error)


def _entries_for(target: str, now: float) -> list[dict[str, Any]]:
    """Resolve one target class into candidate entries with liveness checks."""
    if target == "sockets":
        rows = []
        for path in _collect(SOCKET_DIR):
            if not path.name.endswith(".sock"):
                continue
            reason = "socket still connected" if socket_alive(path) else "dead socket"
            rows.append(
                {"target": target, **_as_row(path, not reason.startswith("dead"), reason, now)}
            )
        return rows
    if target == "staging":
        return [
            {"target": target, **_as_row(p, False, "stale staging entry", now)}
            for p in _collect(STAGING_DIR)
        ]
    if target == "testing_scratch":
        return [
            {"target": target, **_as_row(p, False, "aged testing scratch", now)}
            for p in _collect(TESTING_DIR)
        ]
    raise ValueError(f"unknown target '{target}'; expected one of {DEFAULT_TARGETS}")


def _as_row(path: Path, alive: bool, reason: str, now: float) -> dict[str, Any]:
    return {
        "path": str(path),
        "size_mb": round(_size_bytes(path) / 2**20, 2),
        "age_hours": round(_age_hours(path, now), 1),
        "alive": alive,
        "reason": reason,
    }


def clean_caches(
    dry_run: bool = True,
    targets: list[str] | None = None,
    older_than_hours: int = DEFAULT_OLDER_THAN_HOURS,
) -> dict[str, Any]:
    """Remove stale sockets, staging dirs and scratch older than the cutoff."""
    if older_than_hours < 0:
        raise ValueError("older_than_hours must be >= 0")
    chosen = list(targets) if targets else list(DEFAULT_TARGETS)
    unknown = [t for t in chosen if t not in DEFAULT_TARGETS]
    if unknown:
        raise ValueError(f"unknown targets {unknown}; expected one of {DEFAULT_TARGETS}")
    now = time.time()
    items: list[dict[str, Any]] = []
    for target in chosen:
        for row in _entries_for(target, now):
            path = Path(row["path"])
            action, reason = "skipped", row["reason"]
            if row["age_hours"] < 0:
                reason = "vanished during scan"
            elif row["alive"]:
                reason = "socket still connected; left alone"
            elif row["age_hours"] < older_than_hours:
                reason = (
                    f"only {row['age_hours']}h old; threshold is {older_than_hours}h"
                )
            elif dry_run:
                action = "would_remove"
            else:
                error = _remove(path)
                action, reason = ("removed", row["reason"]) if error is None else ("failed", error)
            items.append({**row, "action": action, "reason": reason})
    freed = sum(
        i["size_mb"] for i in items if i["action"] in {"removed", "would_remove"}
    )
    counts: dict[str, int] = {}
    for item in items:
        counts[item["action"]] = counts.get(item["action"], 0) + 1
    return {
        "dry_run": dry_run,
        "older_than_hours": older_than_hours,
        "targets": chosen,
        "items": items,
        "summary": {**counts, "reclaimable_mb": round(freed, 2)},
    }