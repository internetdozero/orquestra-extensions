"""Age-gated socket, staging and testing-scratch cleanup in dry and real modes."""

from __future__ import annotations

import os
import socket
import time
from pathlib import Path

import pytest

from janitor import caches

OLD_HOURS = 10


def _age(path: Path, hours: float) -> None:
    stamp = time.time() - hours * 3600
    os.utime(path, (stamp, stamp))


def _bind(path: Path, listen: bool = False) -> socket.socket:
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(path))
    if listen:
        srv.listen(1)
    return srv


@pytest.fixture
def socket_dir(scratch: Path) -> Path:
    d = scratch / "orquestra"
    d.mkdir()
    return d


@pytest.fixture
def staging_dir(scratch: Path) -> Path:
    d = scratch / "staging"
    d.mkdir()
    return d


@pytest.fixture
def testing_dir(scratch: Path) -> Path:
    d = scratch / "testing"
    d.mkdir()
    return d


@pytest.fixture
def paths(monkeypatch, socket_dir, staging_dir, testing_dir):
    monkeypatch.setattr(caches, "SOCKET_DIR", socket_dir)
    monkeypatch.setattr(caches, "STAGING_DIR", staging_dir)
    monkeypatch.setattr(caches, "TESTING_DIR", testing_dir)


def test_production_defaults_never_touch_tmp() -> None:
    for path in (caches.SOCKET_DIR, caches.STAGING_DIR, caches.TESTING_DIR):
        assert not str(path).startswith("/tmp/")


def test_dry_run_reports_dead_and_live_sockets(paths, socket_dir) -> None:
    dead = socket_dir / "dead.sock"
    live = socket_dir / "live.sock"
    stale = _bind(dead, listen=False)
    keeper = _bind(live, listen=True)
    _age(dead, OLD_HOURS)
    _age(live, OLD_HOURS)
    try:
        result = caches.clean_caches(dry_run=True, targets=["sockets"], older_than_hours=6)
        by_path = {Path(i["path"]).name: i for i in result["items"]}
        assert by_path["dead.sock"]["action"] == "would_remove"
        assert by_path["dead.sock"]["reason"] == "dead socket"
        assert by_path["live.sock"]["action"] == "skipped"
        assert "connected" in by_path["live.sock"]["reason"]
        assert dead.exists() and live.exists(), "dry_run must not delete"
        assert result["summary"]["reclaimable_mb"] >= 0
    finally:
        stale.close()
        keeper.close()


def test_older_than_threshold_gates_every_target(paths, staging_dir) -> None:
    old = staging_dir / "pkg-old"
    new = staging_dir / "pkg-new"
    old.mkdir()
    new.mkdir()
    _age(old, OLD_HOURS)
    result = caches.clean_caches(dry_run=False, targets=["staging"], older_than_hours=6)
    assert not old.exists() and new.exists()
    entry = next(i for i in result["items"] if i["path"].endswith("pkg-new"))
    assert entry["action"] == "skipped" and "threshold" in entry["reason"]
    assert result["summary"]["removed"] == 1


def test_testing_scratch_cleanup(paths, testing_dir) -> None:
    aged = testing_dir / "run-abc"
    aged.mkdir()
    (aged / "out.log").write_bytes(b"x" * (3 * 2**20))
    _age(aged, OLD_HOURS)
    fresh = testing_dir / "run-new"
    fresh.mkdir()

    dry = caches.clean_caches(dry_run=True, targets=["testing_scratch"])
    assert len(dry["items"]) == 2
    assert aged.exists(), "dry_run must not delete scratch"

    real = caches.clean_caches(dry_run=False, targets=["testing_scratch"])
    assert not aged.exists() and fresh.exists()
    assert real["summary"]["removed"] == 1
    assert real["summary"]["reclaimable_mb"] > 0


def test_removed_file_with_threshold_zero(paths, socket_dir) -> None:
    dead = socket_dir / "one.sock"
    sock = _bind(dead, listen=False)
    try:
        result = caches.clean_caches(
            dry_run=False, targets=["sockets"], older_than_hours=0
        )
    finally:
        sock.close()
    assert not dead.exists()
    assert result["summary"]["removed"] == 1


def test_validation_errors(paths) -> None:
    with pytest.raises(ValueError, match="older_than_hours"):
        caches.clean_caches(older_than_hours=-1)
    with pytest.raises(ValueError, match="unknown targets"):
        caches.clean_caches(targets=["everything"])