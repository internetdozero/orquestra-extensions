"""Kernel OOM sacrifice priority for active agent runners and workers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

PROC = "/proc"
RUNNER_TOKENS = (
    "codex", "claude", "opencode", "antigravity", "freebuff", "aider",
    "copilot", "cursor-agent", "grok-cli", "puppeteer", "playwright",
    "headless_shell", "chromium",
)
BACKGROUND_TOKENS = ("headless_shell", "puppeteer", "playwright", "chromedriver", "esbuild")
PROTECT_BELOW = 0     # session-ish runners that should outlive background workers
SACRIFICE_ABOVE = 800  # scores here are killed first under memory pressure


def _read(pid: int, filename: str, default: int | None = None) -> int | None:
    try:
        return int(Path(f"{PROC}/{pid}/{filename}").read_text().strip())
    except (OSError, ValueError):
        return default


def _cmdline(pid: int) -> str:
    try:
        raw = Path(f"{PROC}/{pid}/cmdline").read_bytes()
    except OSError:
        return ""
    return raw.decode("utf-8", "replace").replace("\0", " ").strip()


def _is_runner(command: str) -> bool:
    low = command.lower()
    return any(token in low for token in RUNNER_TOKENS)


def _recommend(pid: int, name: str, command: str, oom_score: int, adj: int) -> str:
    low = f"{name} {command}".lower()
    if any(token in low for token in BACKGROUND_TOKENS) and adj < 200:
        return (
            f"background worker with adj {adj}: raise to 200 so the kernel sheds it "
            f"first (set OOM_SCORE_ADJ=200 at spawn, or write /proc/{pid}/oom_score_adj "
            "with privileges)"
        )
    if oom_score >= SACRIFICE_ABOVE and adj <= 0:
        return (
            f"oom_score {oom_score} means it dies early: consider protection with "
            "adj -200 if this runner must survive pressure"
        )
    if adj > 0:
        return f"adj {adj}: already sacrifices itself before system-critical processes"
    return "adj 0: default priority; no change recommended"


def oom_inspect() -> dict[str, Any]:
    """OOM scores, adjustments and one recommendation per active agent runner."""
    my_uid = os.getuid()
    rows: list[dict[str, Any]] = []
    for entry in sorted(os.listdir(PROC)):
        if not entry.isdigit():
            continue
        command = _cmdline(int(entry))
        if not command or not _is_runner(command):
            continue
        try:
            uid = int(
                next(
                    line.split()[1]
                    for line in Path(f"{PROC}/{entry}/status").read_text().splitlines()
                    if line.startswith("Uid:")
                )
            )
        except (OSError, StopIteration, IndexError, ValueError):
            continue
        if uid != my_uid:
            continue
        pid = int(entry)
        score = _read(pid, "oom_score", -1)
        adj = _read(pid, "oom_score_adj", 0)
        if score < 0 or adj is None:
            continue
        name = Path(f"{PROC}/{entry}/comm").read_text().strip()
        rows.append(
            {
                "pid": pid,
                "name": name,
                "command": command[:200],
                "oom_score": score,
                "oom_score_adj": adj,
                "recommendation": _recommend(pid, name, command, score, adj),
            }
        )
    rows.sort(key=lambda row: row["oom_score"], reverse=True)
    return {
        "scale": "oom_score 0-1000: higher dies sooner; adj -1000..1000 raises/lowers it",
        "count": len(rows),
        "processes": rows,
        "note": (
            "Recommendations are advisory; raising adj above 0 needs CAP_SYS_RESOURCE, "
            "lowering (protecting) is allowed for your own processes at spawn time."
        ),
    }