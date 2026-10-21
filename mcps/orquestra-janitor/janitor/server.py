"""MCP entrypoint: system health, orphan scan/sweep, cache hygiene, OOM view."""

from __future__ import annotations

import argparse
import sys
from typing import Annotated, Any, Callable

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from . import caches, health, oom, orphans, sweep
from .errors import actionable
from .schema import CacheTarget, SweepTarget

INSTRUCTIONS = """Linux housekeeping for agentic workspaces, local-only and read-mostly.

janitor_system_health reports RAM/swap/tmpfs use, CPU load, cpu.temperature_c,
the top-5 RSS processes, alert=true past 85% RAM or 80% /tmp, and
thermal_alert=true past 82°C.

janitor_scan_orphans lists this user's suspected orphaned dev workers
(headless browsers, dead agent runners, detached compilers) with reasons.

janitor_sweep_processes terminates them safely: denylisted/system processes
are always refused, SIGTERM gets 3s, SIGKILL only with force=true, and
dry_run=true (the default) only reports.

janitor_clean_caches removes dead ~/.orquestra/*.sock, stale .codex staging
dirs and aged /var/tmp/testing/ scratch, gated by older_than_hours (default 6),
dry_run=true by default.

janitor_oom_inspect shows oom_score/oom_score_adj for active runners plus
sacrifice-priority recommendations.

Nothing is ever written to /tmp/: scratch belongs under /var/tmp/testing/."""

server = MCPServer(
    name="janitor",
    title="Janitor (System & Memory Guard)",
    version="0.1.0",
    instructions=INSTRUCTIONS,
)


def tool(*, description: str) -> Callable[[Callable[..., Any]], Any]:
    """Register a tool whose anticipated failures reach the caller verbatim."""
    return lambda fn: server.tool(description=description)(actionable(fn))


AgeHours = Annotated[
    int,
    Field(ge=0, description="Only remove entries older than this many hours."),
]


@tool(
    description=(
        "RAM/swap/tmpfs health: used/free RAM and swap, /tmp tmpfs utilization, "
        "CPU load, cpu.temperature_c from the hottest thermal zone, and the "
        "top-5 processes by resident memory. alert=true past 85% RAM or 80% "
        "/tmp. thermal_alert=true when cpu.temperature_c exceeds 82°C."
    )
)
def janitor_system_health() -> dict[str, Any]:
    """Snapshot of memory, tmpfs, CPU and the heaviest processes."""
    return health.system_health()


@tool(
    description=(
        "Scan this user's processes for suspected orphaned development workers "
        "(PPID=1, dead parent, zombie): headless browsers, agent runners, "
        "detached compilers and python sub-workers."
    )
)
def janitor_scan_orphans() -> list[dict[str, Any]]:
    """Read-only list: pid, name, memory_mb, cpu_percent, command, ppid, reason."""
    return orphans.scan_orphans()


@tool(
    description=(
        "Terminate processes safely. Provide explicit pids and/or "
        "target_type='orphans'|'browsers'|'compilers'. dry_run=true (default) "
        "only reports; force=true allows SIGKILL after a 3s SIGTERM grace. "
        "systemd, compositors, sshd, shells and OrquestraAI are always refused."
    )
)
def janitor_sweep_processes(
    pids: list[int] | None = None,
    target_type: SweepTarget | None = None,
    dry_run: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    """Denylist-checked termination plan or execution."""
    return sweep.sweep(pids, target_type, dry_run, force)


@tool(
    description=(
        "Clean transient caches. targets: sockets (dead ~/.orquestra/*.sock), "
        "staging (.codex marketplace staging), testing_scratch "
        "(/var/tmp/testing). older_than_hours=6 gates every removal; "
        "dry_run=true (default) only reports."
    )
)
def janitor_clean_caches(
    dry_run: bool = True,
    targets: list[CacheTarget] | None = None,
    older_than_hours: AgeHours = caches.DEFAULT_OLDER_THAN_HOURS,
) -> dict[str, Any]:
    """Age-gated removal report with per-item actions and reclaimable MB."""
    return caches.clean_caches(dry_run, targets, older_than_hours)


@tool(
    description=(
        "Inspect oom_score and oom_score_adj for active agent runners to show "
        "kernel sacrifice priority under memory pressure, with recommendations."
    )
)
def janitor_oom_inspect() -> dict[str, Any]:
    """Sorted OOM priority of this user's runners plus advisory notes."""
    return oom.oom_inspect()


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and serve MCP over the chosen transport (stdio default)."""
    parser = argparse.ArgumentParser(prog="janitor", description=__doc__)
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=("stdio", "sse", "streamable-http"),
        help="MCP transport (default: stdio)",
    )
    args = parser.parse_args(argv)
    print(f"janitor: serving over {args.transport}", file=sys.stderr)
    server.run(args.transport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())