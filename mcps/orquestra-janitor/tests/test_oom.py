"""OOM score inspection shape and runner detection."""

from __future__ import annotations

import subprocess
import time

import pytest

from janitor import oom


def test_report_shape_and_score_ranges() -> None:
    report = oom.oom_inspect()
    assert set(report) == {"scale", "count", "processes", "note"}
    assert report["count"] == len(report["processes"])
    scores = [row["oom_score"] for row in report["processes"]]
    assert scores == sorted(scores, reverse=True)
    for row in report["processes"]:
        assert 0 <= row["oom_score"] <= 1000
        assert -1000 <= row["oom_score_adj"] <= 1000
        assert row["pid"] > 0 and row["name"]
        assert row["recommendation"]


def test_active_agent_runner_is_reported() -> None:
    proc = subprocess.Popen(["bash", "-c", "exec -a codex-app-server sleep 600"])
    try:
        deadline = time.time() + 5
        while time.time() < deadline:
            report = oom.oom_inspect()
            match = [r for r in report["processes"] if r["pid"] == proc.pid]
            if match:
                break
            time.sleep(0.1)
        else:
            raise AssertionError("codex-app-server runner never appeared")
        row = match[0]
        assert "codex-app-server" in row["command"]
        assert 0 <= row["oom_score"] <= 1000
        assert row["oom_score_adj"] in range(-1000, 1001)
        assert "adj" in row["recommendation"].lower() or "oom_score" in row["recommendation"]
    finally:
        proc.kill()
        proc.wait(timeout=10)


def test_unrelated_processes_are_not_listed() -> None:
    proc = subprocess.Popen(["sleep", "600"])
    try:
        pids = {row["pid"] for row in oom.oom_inspect()["processes"]}
        assert proc.pid not in pids, "plain daemons are not agent runners"
    finally:
        proc.kill()
        proc.wait(timeout=10)