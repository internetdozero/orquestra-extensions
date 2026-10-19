"""Classification helpers plus detection of a real reparented dev worker."""

from __future__ import annotations

from janitor import orphans


REQUIRED_FIELDS = {"pid", "name", "memory_mb", "cpu_percent", "command", "ppid", "reason"}


def test_categorize_browser_and_compiler_classes() -> None:
    assert orphans.categorize("chromedriver", "chromedriver --port=4444") == "browsers"
    assert orphans.categorize("sleep", "chrome --headless --dump-dom") == "browsers"
    assert orphans.categorize("puppeteer-worker", "puppeteer run.js") == "browsers"
    assert orphans.categorize("rustc", "rustc src/main.rs") == "compilers"
    assert orphans.categorize("node", "node build.js") == "compilers"
    assert orphans.categorize("plasmashell", "plasmashell") is None


def test_proc_info_reads_a_live_process() -> None:
    import os

    info = orphans.proc_info(os.getpid())
    assert info is not None
    assert info["pid"] == os.getpid()
    assert info["ppid"] > 0
    assert info["uid"] == os.getuid()
    assert info["state"] in {"R", "S", "D", "t"}
    assert info["cpu_percent"] >= 0
    assert orphans.proc_info(999_999_999) is None


def test_scan_finds_reparented_agent_runner(orphan_pid: int) -> None:
    rows = orphans.scan_orphans()
    by_pid = {row["pid"]: row for row in rows}
    assert orphan_pid in by_pid, f"expected orphan {orphan_pid} in {sorted(by_pid)}"
    row = by_pid[orphan_pid]
    assert set(row) == REQUIRED_FIELDS
    assert row["ppid"] >= 1
    assert "codex-app-server" in row["command"]
    assert "suspected orphaned agent runner" in row["reason"]
    # Whatever adopted it (init or a subreaper), the cause must be named.
    assert any(
        marker in row["reason"]
        for marker in ("reparented to init", "adopted from another session", "no longer exists", "zombie")
    )
    assert 0 <= row["cpu_percent"] < 100 * 60


def _fake(pid: int, ppid: int, state: str = "S", pgrp: int | None = None, session: int = 500):
    return {
        "pid": pid,
        "ppid": ppid,
        "pgrp": pgrp if pgrp is not None else pid,
        "session": session,
        "name": "sleep",
        "state": state,
        "uid": 1000,
        "command": "sleep 10",
        "rss_mb": 1.0,
        "cpu_percent": 0.0,
    }


def test_orphan_cause_covers_init_and_missing_parents() -> None:
    assert (
        "reparented to init"
        in orphans._orphan_cause(_fake(10, 1), known={1, 10})  # type: ignore[arg-type]
    )
    assert (
        "no longer exists"
        in orphans._orphan_cause(_fake(10, 9999), known={10})  # type: ignore[arg-type]
    )
    zombie = _fake(10, 10, state="Z")
    assert "zombie" in orphans._orphan_cause(zombie, known={10})  # type: ignore[arg-type]


def test_adoption_cause_detects_subreaper_and_spares_setsid() -> None:
    child = _fake(100, ppid=200, pgrp=90, session=1000)
    parent = _fake(200, ppid=1, pgrp=200, session=200)
    assert "adopted from another session" in orphans._adoption_cause(child, parent)  # type: ignore[arg-type]
    # Same session: freshly spawned child, not an orphan.
    sibling = _fake(101, ppid=200, pgrp=91, session=200)
    assert orphans._adoption_cause(sibling, parent) is None  # type: ignore[arg-type]
    # setsid() daemons own their group: not called an orphan by adoption.
    self_grouped = _fake(102, ppid=200, pgrp=102, session=1500)
    assert orphans._adoption_cause(self_grouped, parent) is None  # type: ignore[arg-type]


def test_scan_returns_sorted_well_formed_rows(orphan_pid: int) -> None:
    rows = orphans.scan_orphans()
    memory = [row["memory_mb"] for row in rows]
    assert memory == sorted(memory, reverse=True)
    for row in rows:
        assert set(row) == REQUIRED_FIELDS
        assert row["pid"] > 0 and row["ppid"] >= 1
        assert row["reason"] and ";" in row["reason"]
        assert len(row["command"]) <= 300