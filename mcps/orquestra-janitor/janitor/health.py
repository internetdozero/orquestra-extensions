"""RAM/swap, `/tmp` tmpfs utilization, CPU load and the heaviest processes."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

ALERT_RAM_PCT = 85.0
ALERT_TMP_PCT = 80.0
MEMINFO = "/proc/meminfo"
MOUNTS = "/proc/mounts"
PROC = "/proc"
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


def _cpu() -> dict[str, Any]:
    """Load averages normalized against the core count."""
    load1, load5, load15 = os.getloadavg()
    cores = os.cpu_count() or 1
    return {
        "cores": cores,
        "load1": round(load1, 2),
        "load5": round(load5, 2),
        "load15": round(load15, 2),
        "load_percent": round(load1 * 100 / cores, 1),
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
    reasons: list[str] = []
    if ram["used_percent"] > ALERT_RAM_PCT:
        reasons.append(f"RAM usage {ram['used_percent']}% exceeds {ALERT_RAM_PCT:.0f}%")
    if tmp["used_percent"] > ALERT_TMP_PCT:
        reasons.append(f"/tmp usage {tmp['used_percent']}% exceeds {ALERT_TMP_PCT:.0f}%")
    return {
        "ram": ram,
        "swap": swap,
        "tmp": tmp,
        "cpu": _cpu(),
        "top_processes": top_rss(),
        "alert": bool(reasons),
        "alert_reasons": reasons,
    }