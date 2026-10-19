"""Termination behind an immutable denylist: SIGTERM, 3s grace, opt-in SIGKILL."""

from __future__ import annotations

import os
import signal
import time
from pathlib import Path
from typing import Any

from . import orphans

GRACE_SECONDS = 3.0
POLL_SECONDS = 0.1
TARGET_TYPES = ("orphans", "browsers", "compilers")

# Immutable denylist: session, desktop and harness-critical processes.
PROTECTED_NAMES = frozenset(
    {
        "systemd", "init", "plasmashell", "kwin", "kwin_x11", "kwin_wayland",
        "kwin_wayland_wrapper", "Xorg", "Xwayland", "weston", "sway", "hyprland",
        "gnome-shell", "xwayland", "sshd", "dbus-daemon",
        "bash", "zsh", "fish", "sh", "dash", "ksh", "tmux", "screen",
        "orquestra", "orquestra-ai",
    }
)
PROTECTED_SUBSTRINGS = (
    "orquestra", "plasmashell", "kwin", "xwayland", "systemd", "hyprland",
    "gnome-shell", "wayland",
)
# Streamed-in commands that must never be killed no matter the argv[0].
PROTECTED_COMMAND_TOKENS = ("ssh ", "sudo ", "systemd-run")


def _ancestors() -> set[int]:
    """Self, our whole parent chain, and pid 1 — never selection material."""
    chain: set[int] = set()
    pid = os.getpid()
    while pid > 1 and pid not in chain:
        chain.add(pid)
        info = orphans.proc_info(pid)
        pid = info["ppid"] if info else 0
    chain.add(1)
    return chain


def _protection(
    pid: int, info: dict[str, Any] | None, ancestors: set[int]
) -> str | None:
    """Reason this pid must not be touched, or None when it is sweepable."""
    if pid <= 1:
        return "pid <= 1 (init) is never terminated"
    if info is None:
        return "process not found (already gone)"
    if info["uid"] != os.getuid():
        return "process is not owned by this user"
    if pid in ancestors:
        return "the janitor process or one of its ancestors (active shell/pipeline)"
    name = info["name"].lower()
    if name in PROTECTED_NAMES:
        return f"'{name}' is on the protected denylist"
    command = info["command"].lower()
    for token in PROTECTED_SUBSTRINGS:
        if token in name or token in command:
            return f"'{name}' matches protected token '{token}'"
    for token in PROTECTED_COMMAND_TOKENS:
        if command.startswith(token):
            return f"'{name}' runs a protected command starting with '{token.strip()}'"
    return None


def _alive(pid: int) -> bool:
    """A zombie is dead: only a live or runnable process counts as alive."""
    try:
        raw = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return False
    close = raw.rfind(")")
    if close < 0:
        return False
    return raw[close + 2 : close + 3] != "Z"


def _wait_gone(pid: int, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not _alive(pid):
            return True
        time.sleep(POLL_SECONDS)
    return not _alive(pid)


def _terminate(pid: int, force: bool) -> dict[str, Any]:
    """SIGTERM, wait up to 3s, then SIGKILL only when `force` allows it."""
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return {"action": "already_exited", "signal": None}
    except PermissionError:
        return {"action": "refused", "signal": None, "reason": "permission denied"}
    if _wait_gone(pid, GRACE_SECONDS):
        return {"action": "terminated", "signal": "SIGTERM"}
    if not force:
        return {
            "action": "survived",
            "signal": "SIGTERM",
            "reason": f"still alive after {GRACE_SECONDS}s; rerun with force=true to SIGKILL",
        }
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return {"action": "terminated", "signal": "SIGKILL"}
    except PermissionError:
        return {"action": "refused", "signal": "SIGKILL", "reason": "permission denied"}
    if _wait_gone(pid, 1.0):
        return {"action": "killed", "signal": "SIGKILL"}
    return {"action": "survived", "signal": "SIGKILL", "reason": "unkillable state (D?)"}


def _select(pids: list[int] | None, target_type: str | None) -> list[int]:
    """Resolve pids and/or a sweep class into the candidate pid list."""
    if not pids and not target_type:
        raise ValueError("provide pids and/or target_type")
    if target_type is not None and target_type not in TARGET_TYPES:
        raise ValueError(f"target_type must be one of {TARGET_TYPES}")
    if pids:
        selected = [int(p) for p in dict.fromkeys(pids)]
        if target_type and target_type != "orphans":
            selected = [
                p
                for p in selected
                if (info := orphans.proc_info(p))
                and orphans.categorize(info["name"], info["command"]) == target_type
            ]
        return selected
    rows = orphans.scan_orphans()
    if target_type == "orphans":
        return [row["pid"] for row in rows]
    return [
        row["pid"]
        for row in rows
        if orphans.categorize(row["name"], row["command"]) == target_type
    ]


def sweep(
    pids: list[int] | None = None,
    target_type: str | None = None,
    dry_run: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    """Report or perform termination, always honouring the denylist first."""
    selected = _select(pids, target_type)
    ancestors = _ancestors()
    results: list[dict[str, Any]] = []
    for pid in selected:
        info = orphans.proc_info(pid)
        base = {
            "pid": pid,
            "name": info["name"] if info else None,
            "memory_mb": info["rss_mb"] if info else 0.0,
            "command": (info["command"][:200] if info else ""),
        }
        blocked = _protection(pid, info, ancestors)
        if blocked:
            results.append({**base, "action": "refused", "reason": blocked})
            continue
        if dry_run:
            results.append(
                {
                    **base,
                    "action": "would_terminate",
                    "reason": f"SIGTERM then {GRACE_SECONDS:.0f}s grace"
                    + (" then SIGKILL" if force else "; SIGKILL needs force=true"),
                }
            )
            continue
        outcome = _terminate(pid, force)
        results.append({**base, **outcome})
    counts: dict[str, int] = {}
    for row in results:
        counts[row["action"]] = counts.get(row["action"], 0) + 1
    return {
        "dry_run": dry_run,
        "force": force,
        "target_type": target_type,
        "grace_seconds": GRACE_SECONDS,
        "selected": len(selected),
        "results": results,
        "summary": counts,
    }