"""Fake-vs-real contract: the mock binary must accept the bridge's argv shapes.

The roundtrip tests prove the Python bridge against the fake binary. This
module pins the other seam: the same argv run against the REAL `orquestra`
binary must exit the same way with the same error vocabulary. Only
read-only shapes and unknown-service refusals run against the real binary,
with HOME pointed at an empty scratch dir, so no operator state is touched.

Skipped when no vault-capable binary is installed (old binaries exit 0
with no output for `vault list`, which fails the JSON probe below).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from orquestra_core import paths

GHOST = "__nope__"


def _real_binary() -> Path | None:
    """Installed native binary, or None when it cannot prove vault support."""
    seen: set[str] = set()
    candidates: list[str] = []
    found = shutil.which("orquestra")
    if found:
        candidates.append(found)
    fallback = str(Path.home() / ".local" / "bin" / "orquestra")
    candidates.append(fallback)
    for raw in candidates:
        if not raw or raw in seen:
            continue
        seen.add(raw)
        candidate = Path(raw)
        if not (candidate.is_file() and os.access(candidate, os.X_OK)):
            continue
        try:
            if candidate.read_bytes().startswith(b"#!/usr/bin/env python3"):
                continue  # a test double, not the native binary
        except OSError:
            continue
        probe = subprocess.run(
            [str(candidate), "vault", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=60,
            env={**os.environ, "HOME": tempfile.gettempdir()},
        )
        try:
            if probe.returncode == 0 and isinstance(json.loads(probe.stdout), list):
                return candidate
        except (json.JSONDecodeError, ValueError):
            continue
    return None


def _run(binary: str, argv: list[str], home: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [binary, *argv],
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "HOME": str(home), "ORQUESTRA_HOME": str(home)},
    )


@pytest.fixture()
def real_binary() -> Path:
    binary = _real_binary()
    if binary is None:
        pytest.skip("no vault-capable orquestra binary installed")
    assert binary is not None
    return binary


@pytest.fixture()
def scratch_home() -> Path:
    home = Path(tempfile.mkdtemp(prefix="cli-contract-", dir="/var/tmp/testing"))
    yield home
    shutil.rmtree(home, ignore_errors=True)


def _assert_same_exit(label: str, fake: subprocess.CompletedProcess[str], real: subprocess.CompletedProcess[str]) -> None:
    assert fake.returncode == real.returncode, (
        f"{label}: fake exit {fake.returncode} != real exit {real.returncode}\n"
        f"fake stderr: {fake.stderr.strip()[-200:]}\n"
        f"real stderr: {real.stderr.strip()[-200:]}"
    )


def test_list_shape_matches(mock_home: Path, real_binary: Path, scratch_home: Path) -> None:
    fake = _run(paths.binary(), ["vault", "list", "--json"], mock_home)
    real = _run(str(real_binary), ["vault", "list", "--json"], scratch_home)
    _assert_same_exit("list", fake, real)
    assert real.returncode == 0
    assert isinstance(json.loads(real.stdout), list)
    assert [row["id"] for row in json.loads(fake.stdout)] == ["svc-a"]


def test_set_enabled_unknown_matches(mock_home: Path, real_binary: Path, scratch_home: Path) -> None:
    argv = ["vault", "set-enabled", GHOST, "on", "--json"]
    fake = _run(paths.binary(), argv, mock_home)
    real = _run(str(real_binary), argv, scratch_home)
    _assert_same_exit("set-enabled", fake, real)
    assert real.returncode == 1
    assert f"unknown vault service: {GHOST}" in real.stderr


def test_exec_unknown_matches(mock_home: Path, real_binary: Path, scratch_home: Path) -> None:
    argv = ["vault", "exec", GHOST, "--", "echo", "hi"]
    fake = _run(paths.binary(), argv, mock_home)
    real = _run(str(real_binary), argv, scratch_home)
    _assert_same_exit("exec", fake, real)
    assert real.returncode == 1
    assert f"unknown vault service: {GHOST}" in real.stderr


def test_http_unknown_matches(mock_home: Path, real_binary: Path, scratch_home: Path) -> None:
    argv = ["vault", "http", "--service", GHOST, "--endpoint", "https://api.example.com/x", "--json"]
    fake = _run(paths.binary(), argv, mock_home)
    real = _run(str(real_binary), argv, scratch_home)
    _assert_same_exit("http", fake, real)
    assert real.returncode == 1
    assert f"unknown vault service: {GHOST}" in real.stderr
