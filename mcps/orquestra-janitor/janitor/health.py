"""RAM/swap, `/tmp` tmpfs utilization, CPU load, temperature and the heaviest processes."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

ALERT_RAM_PCT = 85.0
ALERT_TMP_PCT = 80.0
ALERT_CPU_TEMP_C = 82.0
MEMINFO = "/proc/meminfo"
MOUNTS = "/proc/mounts"
PROC = "/proc"
THERMAL_ROOT = "/sys/class/thermal"
CPU_ZONE_TYPES = ("x86_pkg_temp", "coretemp", "TCPU", "cpu-thermal", "k10temp")
TOP_N = 5


def _meminfo() -> dict[str, int]:
    """Parse /proc/meminfo into {field: kB}."""
    values: dict[str, int] = {}
    try:
        handle = open(MEMINFO)
    except OSError:
        return values
    with handle:
        for line in handle:
            key, _, rest = line.partition(":")
            parts = rest.split()
            if len(parts) == 2 and parts[0].isdigit():
                values[key] = int(parts[0])
    return values


def _ram_swap(mem: dict[str, int]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Used = total - available for RAM, total - free for swap (all MB)."""
    total = mem.get("MemTotal", 0) // 1024
    free = mem.get("MemAvailable", mem.get("MemFree", 0)) // 1024
    used = max(total - free, 0)
    ram = {
        "total_mb": total,
        "used_mb": used,
        "free_mb": free,
        "used_percent": round(used * 100 / total, 1) if total else 0.0,
    }
    swap_total = mem.get("SwapTotal", 0) // 1024
    swap_free = mem.get("SwapFree", 0) // 1024
    swap_used = max(swap_total - swap_free, 0)
    swap = {
        "total_mb": swap_total,
        "used_mb": swap_used,
        "free_mb": swap_free,
        "used_percent": round(swap_used * 100 / swap_total, 1) if swap_total else 0.0,
    }
    return ram, swap


def _mount_for(target: str) -> tuple[str, str] | None:
    """Longest mount covering `target`, as (mountpoint, filesystem type)."""
    try:
        lines = Path(MOUNTS).read_text().splitlines()
    except OSError:
        return None
    resolved = str(Path(target))
    best: tuple[str, str] | None = None
    for line in lines:
        parts = line.split()
        if len(parts) < 3:
            continue
        mountpoint, fs_type = parts[1], parts[2]
        inside = resolved == mountpoint or resolved.startswith(mountpoint.rstrip("/") + "/")
        if inside and (best is None or len(mountpoint) > len(best[0])):
            best = (mountpoint, fs_type)
    return best


def _tmp_usage() -> dict[str, Any]:
    """Capacity of the filesystem mounted at /tmp (tmpfs on this machine)."""
    stat = os.statvfs("/tmp")
    total = stat.f_blocks * stat.f_frsize
    free = stat.f_bavail * stat.f_frsize
    used = max(stat.f_blocks - stat.f_bfree, 0) * stat.f_frsize
    mount = _mount_for("/tmp")
    fs_type = mount[1] if mount else "unknown"
    return {
        "path": "/tmp",
        "fs_type": fs_type,
        "is_tmpfs": fs_type == "tmpfs",
        "total_mb": total // 2**20,
        "used_mb": used // 2**20,
        "free_mb": free // 2**20,
        "used_percent": round(used * 100 / total, 1) if total else 0.0,
    }


def _celsius(milli: int) -> float:
    """Millidegrees to °C at 1 decimal, half away from zero (70050 -> 70.1)."""
    sign = -1 if milli < 0 else 1
    return sign * ((abs(milli) + 50) // 100) / 10


def _zone_reading(zone: Path) -> tuple[float, str] | None:
    """One thermal zone as (°C, type), or None when the sysfs files are unusable."""
    try:
        zone_type = (zone / "type").read_text().strip()
        milli = int((zone / "temp").read_text().strip())
    except (OSError, ValueError):
        return None
    if not zone_type:
        return None
    return _celsius(milli), zone_type


def _cpu_temperature() -> tuple[float | None, str | None]:
    """Hottest CPU zone, else the hottest zone, as (°C, type)."""
    try:
        zones = list(Path(THERMAL_ROOT).glob("thermal_zone*"))
    except OSError:
        return None, None
    readings = [item for zone in zones if (item := _zone_reading(zone)) is not None]
    if not readings:
        return None, None
    preferred = [item for item in readings if item[1] in CPU_ZONE_TYPES]
    temp_c, zone_type = max(preferred or readings, key=lambda item: item[0])
    return temp_c, zone_type


def _cpu() -> dict[str, Any]:
    """Load averages normalized against the core count, plus package temperature."""
    load1, load5, load15 = os.getloadavg()
    cores = os.cpu_count() or 1
    temp_c, zone_type = _cpu_temperature()
    return {
        "cores": cores,
        "load1": round(load1, 2),
        "load5": round(load5, 2),
        "load15": round(load15, 2),
        "load_percent": round(load1 * 100 / cores, 1),
        "temperature_c": temp_c,
        "thermal_zone": zone_type,
    }


def top_rss(limit: int = TOP_N) -> list[dict[str, Any]]:
    """The `limit` processes holding the most resident memory."""
    page = os.sysconf("SC_PAGE_SIZE")
    rows: list[dict[str, Any]] = []
    try:
        entries = os.listdir(PROC)
    except OSError:
        return rows
    for entry in entries:
        if not entry.isdigit():
            continue
        try:
            with open(f"{PROC}/{entry}/statm") as handle:
                resident = int(handle.read().split()[1])
            name = Path(f"{PROC}/{entry}/comm").read_text().strip()
        except (OSError, ValueError, IndexError):
            continue
        rows.append(
            {
                "pid": int(entry),
                "name": name,
                "rss_mb": round(resident * page / 2**20, 1),
            }
        )
    rows.sort(key=lambda row: row["rss_mb"], reverse=True)
    return rows[:limit]


def system_health() -> dict[str, Any]:
    """Everything the health tool reports, plus the alert flag and reasons."""
    ram, swap = _ram_swap(_meminfo())
    tmp = _tmp_usage()
    cpu = _cpu()
    temp_c = cpu["temperature_c"]
    reasons: list[str] = []
    if ram["used_percent"] > ALERT_RAM_PCT:
        reasons.append(f"RAM usage {ram['used_percent']}% exceeds {ALERT_RAM_PCT:.0f}%")
    if tmp["used_percent"] > ALERT_TMP_PCT:
        reasons.append(f"/tmp usage {tmp['used_percent']}% exceeds {ALERT_TMP_PCT:.0f}%")
    thermal_alert = bool(temp_c and temp_c > ALERT_CPU_TEMP_C)
    if thermal_alert:
        reasons.append(
            f"CPU temperature {temp_c}°C exceeds {ALERT_CPU_TEMP_C:.0f}°C threshold"
        )
    return {
        "ram": ram,
        "swap": swap,
        "tmp": tmp,
        "cpu": cpu,
        "top_processes": top_rss(),
        "thermal_alert": thermal_alert,
        "alert": bool(reasons),
        "alert_reasons": reasons,
    }