"""RAM/swap/tmpfs report structure, top-5 ordering and the alert flag."""

from __future__ import annotations

from pathlib import Path

from janitor import health


def test_report_contains_all_sections() -> None:
    report = health.system_health()
    assert set(report) == {
        "ram",
        "swap",
        "tmp",
        "cpu",
        "top_processes",
        "thermal_alert",
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
    assert cpu["temperature_c"] is None or isinstance(cpu["temperature_c"], float)
    assert cpu["thermal_zone"] is None or isinstance(cpu["thermal_zone"], str)


def test_alert_thresholds_are_85_ram_and_80_tmp(monkeypatch) -> None:
    """Deterministic: feed 90% RAM and 90% /tmp past the 85/80 thresholds."""
    assert (health.ALERT_RAM_PCT, health.ALERT_TMP_PCT) == (85.0, 80.0)
    monkeypatch.setattr(health, "_cpu_temperature", lambda: (40.0, "x86_pkg_temp"))
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
    calm = health.system_health()
    assert calm["alert"] is False
    assert calm["thermal_alert"] is False


def _write_zone(root: Path, name: str, zone_type: str, milli: str) -> None:
    zone = root / name
    zone.mkdir()
    (zone / "type").write_text(zone_type + "\n")
    (zone / "temp").write_text(milli + "\n")


def test_cpu_temperature_converts_millidegrees(monkeypatch, tmp_path: Path) -> None:
    """70050 millidegrees is 70.1°C, not a truncated 70.0."""
    _write_zone(tmp_path, "thermal_zone0", "x86_pkg_temp", "70050")
    monkeypatch.setattr(health, "THERMAL_ROOT", str(tmp_path))
    assert health._cpu_temperature() == (70.1, "x86_pkg_temp")


def test_cpu_temperature_prefers_cpu_zones_and_takes_the_max(monkeypatch, tmp_path: Path) -> None:
    """x86_pkg_temp / TCPU beat a hotter ambient sensor; the hotter CPU zone wins."""
    _write_zone(tmp_path, "thermal_zone0", "acpitz", "90000")
    _write_zone(tmp_path, "thermal_zone1", "x86_pkg_temp", "61000")
    _write_zone(tmp_path, "thermal_zone2", "TCPU", "64500")
    monkeypatch.setattr(health, "THERMAL_ROOT", str(tmp_path))
    assert health._cpu_temperature() == (64.5, "TCPU")


def test_cpu_temperature_falls_back_when_no_cpu_zone(monkeypatch, tmp_path: Path) -> None:
    _write_zone(tmp_path, "thermal_zone0", "acpitz", "41000")
    _write_zone(tmp_path, "thermal_zone1", "iwlwifi_1", "48000")
    monkeypatch.setattr(health, "THERMAL_ROOT", str(tmp_path))
    assert health._cpu_temperature() == (48.0, "iwlwifi_1")


def test_cpu_temperature_missing_or_empty_sysfs_returns_none(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(health, "THERMAL_ROOT", str(tmp_path / "absent"))
    assert health._cpu_temperature() == (None, None)
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setattr(health, "THERMAL_ROOT", str(empty))
    assert health._cpu_temperature() == (None, None)


def test_thermal_alert_triggers_past_82c(monkeypatch) -> None:
    """82.0°C stays quiet; 82.1°C sets thermal_alert and a reason."""
    assert health.ALERT_CPU_TEMP_C == 82.0
    monkeypatch.setattr(health, "_cpu_temperature", lambda: (82.0, "x86_pkg_temp"))
    warm = health.system_health()
    assert warm["cpu"]["temperature_c"] == 82.0
    assert warm["cpu"]["thermal_zone"] == "x86_pkg_temp"
    assert warm["thermal_alert"] is False
    assert not any("temperature" in reason for reason in warm["alert_reasons"])

    monkeypatch.setattr(health, "_cpu_temperature", lambda: (82.1, "coretemp"))
    hot = health.system_health()
    assert hot["thermal_alert"] is True
    assert hot["cpu"]["temperature_c"] == 82.1
    assert any(
        "CPU temperature 82.1°C exceeds 82°C threshold" == reason
        for reason in hot["alert_reasons"]
    )