"""RAM/swap/tmpfs report structure, top-5 ordering and the alert flag."""

from __future__ import annotations

from janitor import health


def test_report_contains_all_sections() -> None:
    report = health.system_health()
    assert set(report) == {
        "ram",
        "swap",
        "tmp",
        "cpu",
        "top_processes",
        "alert",
        "alert_reasons",
    }
    for section in ("ram", "swap"):
        assert set(report[section]) == {
            "total_mb",
            "used_mb",
            "free_mb",
            "used_percent",
        }
        assert 0.0 <= report[section]["used_percent"] <= 100.0
    assert report["swap"]["total_mb"] >= report["swap"]["used_mb"]
    assert isinstance(report["alert"], bool)
    if report["alert"]:
        assert report["alert_reasons"]


def test_tmp_is_reported_as_tmpfs_with_utilization() -> None:
    tmp = health.system_health()["tmp"]
    assert tmp["path"] == "/tmp"
    assert tmp["fs_type"] == "tmpfs" and tmp["is_tmpfs"] is True
    assert tmp["total_mb"] > 0
    assert 0.0 <= tmp["used_percent"] <= 100.0
    assert tmp["total_mb"] >= tmp["used_mb"]


def test_top_processes_are_five_and_sorted_by_rss() -> None:
    top = health.system_health()["top_processes"]
    assert 0 < len(top) <= 5
    rss = [row["rss_mb"] for row in top]
    assert rss == sorted(rss, reverse=True)
    assert all(row["pid"] > 0 and row["name"] for row in top)


def test_cpu_load_shape() -> None:
    cpu = health.system_health()["cpu"]
    assert cpu["cores"] >= 1
    assert cpu["load1"] >= 0 and cpu["load5"] >= 0 and cpu["load15"] >= 0
    assert cpu["load_percent"] >= 0


def test_alert_thresholds_are_85_ram_and_80_tmp(monkeypatch) -> None:
    """Deterministic: feed 90% RAM and 90% /tmp past the 85/80 thresholds."""
    assert (health.ALERT_RAM_PCT, health.ALERT_TMP_PCT) == (85.0, 80.0)
    fake_mem = health._meminfo()
    fake_mem["MemTotal"] = 1000 * 1024
    fake_mem["MemAvailable"] = 100 * 1024  # 900/1000 used -> 90%
    fake_tmp = {**health._tmp_usage(), "used_percent": 90.0}
    monkeypatch.setattr(health, "_meminfo", lambda: fake_mem)
    monkeypatch.setattr(health, "_tmp_usage", lambda: fake_tmp)

    report = health.system_health()
    assert report["alert"] is True
    assert report["ram"]["used_percent"] == 90.0
    assert any("RAM usage 90.0% exceeds 85%" in r for r in report["alert_reasons"])
    assert any("/tmp usage 90.0% exceeds 80%" in r for r in report["alert_reasons"])

    fake_tmp["used_percent"] = 10.0
    fake_mem["MemAvailable"] = 500 * 1024  # 50% used
    assert health.system_health()["alert"] is False