"""Heuristics that spot orphaned development workers in this user's /proc."""

from __future__ import annotations

import os
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

PROC = "/proc"
HZ = os.sysconf("SC_CLK_TCK")
PAGE = os.sysconf("SC_PAGE_SIZE")

BROWSER_NAMES = frozenset(
    {"chrome", "chromium", "chromium-browser", "google-chrome", "headless_shell", "chromedriver"}
)
BROWSER_CMD_TOKENS = ("--headless", "headless_shell", "puppeteer", "playwright", "chromedriver")
COMPILER_NAMES = frozenset(
    {
        "cargo", "rustc", "cc1", "cc1plus", "gcc", "g++", "clang", "clang++",
        "ld", "ld.lld", "make", "cmake", "ninja", "node", "deno", "esbuild",
    }
)
RUNNER_TOKENS = (
    "codex", "claude", "opencode", "antigravity", "freebuff", "aider",
    "copilot", "cursor-agent", "grok-cli", "app-server",
)
PYTHON_WORKER_TOKENS = ("multiprocessing", "spawn_main", "resource_tracker", "forkserver")


@lru_cache(maxsize=1)
def _boot_time() -> float:
    try:
        for line in open(f"{PROC}/stat"):
            if line.startswith("btime"):
                return float(line.split()[1])
    except OSError:
        pass
    return 0.0


def proc_info(pid: int) -> dict[str, Any] | None:
    """The /proc fields every heuristic needs, or None if the pid is gone."""
    try:
        raw = Path(f"{PROC}/{pid}/stat").read_text()
    except OSError:
        return None
    close = raw.rfind(")")
    if close < 0:
        return None
    name = raw[raw.find("(") + 1 : close]
    fields = raw[close + 2 :].split()
    if len(fields) < 20:
        return None
    state = fields[0]
    ppid = int(fields[1])
    pgrp = int(fields[2])
    session = int(fields[3])
    cpu_ticks = int(fields[11]) + int(fields[12])
    start_ticks = int(fields[19])
    try:
        uid = int(
            next(
                line.split()[1]
                for line in Path(f"{PROC}/{pid}/status").read_text().splitlines()
                if line.startswith("Uid:")
            )
        )
    except (OSError, StopIteration, IndexError, ValueError):
        return None
    try:
        command = Path(f"{PROC}/{pid}/cmdline").read_bytes().decode(
            "utf-8", "replace"
        ).replace("\0", " ").strip()
    except OSError:
        command = ""
    rss_mb = 0.0
    try:
        rss_mb = round(int(Path(f"{PROC}/{pid}/statm").read_text().split()[1]) * PAGE / 2**20, 1)
    except (OSError, IndexError, ValueError):
        pass
    start_epoch = _boot_time() + start_ticks / HZ
    elapsed = max(time.time() - start_epoch, 0.01)
    return {
        "pid": pid,
        "ppid": ppid,
        "pgrp": pgrp,
        "session": session,
        "name": name,
        "state": state,
        "uid": uid,
        "command": command or name,
        "rss_mb": rss_mb,
        "cpu_percent": round(100 * (cpu_ticks / HZ) / elapsed, 1),
    }


def categorize(name: str, command: str) -> str | None:
    """Map a process to a sweep class: 'browsers', 'compilers', or None."""
    low_name, low_cmd = name.lower(), command.lower()
    if low_name in BROWSER_NAMES or any(t in low_cmd for t in BROWSER_CMD_TOKENS):
        return "browsers"
    if low_name in COMPILER_NAMES:
        return "compilers"
    return None


def _dev_kind(info: dict[str, Any]) -> str | None:
    """What kind of development worker this is, or None for ordinary daemons."""
    cls = categorize(info["name"], info["command"])
    if cls == "browsers":
        return "headless browser worker"
    if cls == "compilers":
        return "compiler/build runner"
    low_cmd = info["command"].lower()
    if any(t in low_cmd for t in RUNNER_TOKENS):
        return "agent runner"
    if info["name"].lower().startswith("python") and any(
        t in low_cmd for t in PYTHON_WORKER_TOKENS
    ):
        return "detached python sub-worker"
    return None


def _all_pids() -> set[int]:
    return {int(e) for e in os.listdir(PROC) if e.isdigit()}


def _adoption_cause(child: dict[str, Any], parent: dict[str, Any]) -> str | None:
    """Subreaper adoption: child sits outside its parent's session and group.

    A process that called setsid() itself owns its group (pgrp == pid) and is
    skipped; genuinely spawned children share their parent's session.
    """
    if child["session"] == parent["session"]:
        return None
    if child["pgrp"] == child["pid"]:
        return None
    return (
        f"adopted from another session: parent pid {parent['pid']} "
        f"lives in session {parent['session']} (subreaper adoption) while this "
        f"process stays in orphaned group {child['pgrp']}"
    )


def _orphan_cause(info: dict[str, Any], known: set[int]) -> str | None:
    """Why this pid looks orphaned: dead parent, init reparenting, or zombie."""
    if info["state"] == "Z":
        return "zombie (state Z) never reaped by its parent"
    if info["ppid"] == 1:
        return "reparented to init: original parent exited (PPID=1)"
    if info["ppid"] not in known:
        return f"parent pid {info['ppid']} no longer exists"
    parent = proc_info(info["ppid"])
    if parent is None:
        return f"parent pid {info['ppid']} no longer exists"
    if parent["state"] == "Z":
        return f"parent pid {info['ppid']} is a zombie"
    return _adoption_cause(info, parent)


def scan_orphans() -> list[dict[str, Any]]:
    """Suspected orphaned dev workers of the current user, heaviest first."""
    my_uid, my_pid = os.getuid(), os.getpid()
    known = _all_pids()
    results: list[dict[str, Any]] = []
    for pid in sorted(known):
        if pid == my_pid:
            continue
        info = proc_info(pid)
        if info is None or info["uid"] != my_uid:
            continue
        cause = _orphan_cause(info, known)
        if cause is None:
            continue
        kind = _dev_kind(info)
        if kind is None:
            continue
        results.append(
            {
                "pid": pid,
                "name": info["name"],
                "memory_mb": info["rss_mb"],
                "cpu_percent": info["cpu_percent"],
                "command": info["command"][:300],
                "ppid": info["ppid"],
                "reason": f"{cause}; suspected orphaned {kind}",
            }
        )
    results.sort(key=lambda row: row["memory_mb"], reverse=True)
    return results