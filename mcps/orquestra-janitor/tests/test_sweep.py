"""Denylist refusals, dry-run reporting and real SIGTERM termination."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from janitor import orphans, sweep


def _alive(pid: int) -> bool:
    """Zombies count as dead: only a live process is alive."""
    try:
        raw = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return False
    close = raw.rfind(")")
    return close >= 0 and raw[close + 2 : close + 3] != "Z"


@pytest.fixture
def stray_sleep() -> subprocess.Popen[bytes]:
    """A live, unprotected child process of the test suite."""
    proc = subprocess.Popen(["sleep", "600"])
    yield proc
    if proc.poll() is None:
        proc.kill()
        proc.wait(timeout=10)


def test_denylist_refuses_pid_one_and_self() -> None:
    result = sweep.sweep(pids=[1, os.getpid()], dry_run=True)
    by_pid = {row["pid"]: row for row in result["results"]}
    assert by_pid[1]["action"] == "refused"
    assert "never terminated" in by_pid[1]["reason"]
    assert by_pid[os.getpid()]["action"] == "refused"
    assert "ancestors" in by_pid[os.getpid()]["reason"]
    assert result["summary"]["refused"] == 2


def test_denylist_refuses_shells_and_missing_pids() -> None:
    shell = subprocess.Popen(["bash", "--norc"], stdin=subprocess.PIPE)
    try:
        result = sweep.sweep(pids=[shell.pid, 999_999_999], dry_run=True)
        by_pid = {row["pid"]: row for row in result["results"]}
        assert by_pid[shell.pid]["action"] == "refused"
        assert "denylist" in by_pid[shell.pid]["reason"]
        assert by_pid[999_999_999]["action"] == "refused"
    finally:
        shell.kill()
        shell.wait(timeout=10)


def test_denylist_refuses_orquestra_and_ancestors() -> None:
    fake = subprocess.Popen(["bash", "-c", "exec -a orquestra-ai sleep 600"])
    try:
        deadline = time.time() + 5
        while time.time() < deadline:
            info = orphans.proc_info(fake.pid)
            if info and info["command"].startswith("orquestra-ai"):
                break
            time.sleep(0.05)
        result = sweep.sweep(pids=[fake.pid], dry_run=True)
        row = result["results"][0]
        assert row["action"] == "refused"
        assert "protected token 'orquestra'" in row["reason"]
    finally:
        fake.kill()
        fake.wait(timeout=10)
    myself = sweep.sweep(pids=[os.getpid()], dry_run=True)
    assert "ancestors" in myself["results"][0]["reason"]


def test_dry_run_reports_without_killing(stray_sleep: subprocess.Popen[bytes]) -> None:
    result = sweep.sweep(pids=[stray_sleep.pid], dry_run=True, force=True)
    row = result["results"][0]
    assert row["action"] == "would_terminate"
    assert "SIGKILL" in row["reason"] and row["name"] == "sleep"
    assert stray_sleep.poll() is None, "dry_run must not kill anything"


def test_real_sweep_sigterms_a_stray_process(stray_sleep: subprocess.Popen[bytes]) -> None:
    pid = stray_sleep.pid
    result = sweep.sweep(pids=[pid], dry_run=False)
    assert result["results"][0]["action"] == "terminated"
    assert result["summary"]["terminated"] == 1
    assert stray_sleep.wait(timeout=5) == -signal.SIGTERM
    assert not _alive(pid)


def test_missing_arguments_and_bad_target_type_raise() -> None:
    with pytest.raises(ValueError, match="provide"):
        sweep.sweep()
    with pytest.raises(ValueError, match="target_type"):
        sweep.sweep(target_type="everything")


def test_target_type_orphans_dry_run(orphan_pid: int) -> None:
    result = sweep.sweep(target_type="orphans", dry_run=True)
    by_pid = {row["pid"]: row for row in result["results"]}
    assert orphan_pid in by_pid
    assert by_pid[orphan_pid]["action"] == "would_terminate"
    assert result["dry_run"] is True and result["selected"] >= 1


def test_target_type_browsers_only_matches_browser_class(stray_orphan_pid: int) -> None:
    result = sweep.sweep(target_type="browsers", dry_run=True)
    names = {row["name"] for row in result["results"]}
    assert stray_orphan_pid in {row["pid"] for row in result["results"]}
    assert names <= {"sleep"}  # argv0 headless_shell, comm stays sleep


def test_real_class_sweep_terminates_only_flagged_pids(
    stray_orphan_pid: int, orphan_pid: int
) -> None:
    result = sweep.sweep(target_type="browsers", dry_run=False)
    assert result["results"], "expected the browser-shaped orphan in scope"
    killed = {row["pid"] for row in result["results"] if row["action"] == "terminated"}
    assert stray_orphan_pid in killed
    assert orphan_pid not in killed, "class filter must not touch other orphans"
    assert not _alive(stray_orphan_pid)
    assert _alive(orphan_pid)


def test_survivor_without_force_is_reported_not_killed() -> None:
    # SIGTERM-ignoring process; bash would hit the shell denylist, so use python.
    proc = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(300)",
        ],
        start_new_session=True,
    )
    try:
        time.sleep(0.2)  # let it install the handler before we signal it
        result = sweep.sweep(pids=[proc.pid], dry_run=False, force=False)
        row = result["results"][0]
        assert row["action"] == "survived", row
        assert "force=true" in row["reason"]
        assert proc.poll() is None, "no force means no SIGKILL"

        once = sweep.sweep(pids=[proc.pid], dry_run=False, force=True)
        assert once["results"][0]["action"] == "killed"
        proc.wait(timeout=10)
        assert proc.poll() is not None
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=10)


def test_scan_and_select_agree_on_public_surface() -> None:
    rows = orphans.scan_orphans()
    assert isinstance(rows, list)
    assert all(set(r) >= {"pid", "reason"} for r in rows)