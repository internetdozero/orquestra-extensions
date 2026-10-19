"""Shared fixtures. Every scratch path lives under /var/tmp/testing, never /tmp."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
import uuid
from pathlib import Path
from typing import Iterator

import pytest

from janitor import orphans

SCRATCH_ROOT = Path("/var/tmp/testing/janitor-tests")


@pytest.fixture
def scratch(request: pytest.FixtureRequest) -> Iterator[Path]:
    """An isolated directory for one test, removed afterwards."""
    path = SCRATCH_ROOT / f"{request.node.name.replace('/', '_')}-{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    yield path
    shutil.rmtree(path, ignore_errors=True)


def _spawn_orphan(argv0: str) -> int:
    """Fork a process whose parent exits at once, so it reparents to init."""
    out = subprocess.check_output(
        ["bash", "-c", f"exec -a {argv0} sleep 600 >/dev/null 2>&1 & echo $!"],
        text=True,
    )
    pid = int(out.strip().splitlines()[-1])
    deadline = time.time() + 10
    while time.time() < deadline:
        if any(row["pid"] == pid for row in orphans.scan_orphans()):
            return pid
        time.sleep(0.1)
    info = orphans.proc_info(pid)
    raise AssertionError(f"engineered orphan {pid} never detected: {info}")


def _kill(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


@pytest.fixture
def orphan_pid() -> Iterator[int]:
    """A genuine PPID=1 'codex app-server' orphan, reaped when the test ends."""
    pid = _spawn_orphan("codex-app-server")
    yield pid
    _kill(pid)


@pytest.fixture
def stray_orphan_pid() -> Iterator[int]:
    """A genuine PPID=1 headless-browser-shaped orphan for sweep-class tests."""
    pid = _spawn_orphan("headless_shell")
    yield pid
    _kill(pid)