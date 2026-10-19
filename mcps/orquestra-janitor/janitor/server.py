"""MCP entrypoint: system health, orphan scan/sweep, cache hygiene, OOM view."""

from __future__ import annotations

import argparse
import sys
from typing import Any, Callable

from mcp.server.mcpserver import MCPServer

from . import caches, health, oom, orphans, sweep

INSTRUCTIONS = """Linux housekeeping for agentic workspaces, local-only and read-mostly.

janitor_system_health reports RAM/swap/tmpfs use, CPU load, the top-5 RSS
processes, and alert=true past 85% RAM or 80% /tmp.

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


def _guarded(action: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Run an action, turning readable failures into a structured error."""
    try:
        return action(*args, **kwargs)
    except (ValueError, OSError) as error:
        return {"error": str(error)}


@server.tool(
    description=(
        "RAM/swap/tmpfs health: used/free RAM and swap, /tmp tmpfs utilization, "
        "CPU load and the top-5 processes by resident memory. alert=true past "
        "85% RAM or 80% /tmp."
    )
)
def janitor_system_health() -> dict[str, Any]:
    """Snapshot of memory, tmpfs, CPU and the heaviest processes."""
    return _guarded(health.system_health)


@server.tool(
    description=(
        "Scan this user's processes for suspected orphaned development workers "
        "(PPID=1, dead parent, zombie): headless browsers, agent runners, "
        "detached compilers and python sub-workers."
    )
)
def janitor_scan_orphans() -> list[dict[str, Any]]:
    """Read-only list: pid, name, memory_mb, cpu_percent, command, ppid, reason."""
    try:
        return orphans.scan_orphans()
    except OSError as error:
        return [{"error": str(error)}]


@server.tool(
    description=(
        "Terminate processes safely. Provide explicit pids and/or "
        "target_type='orphans'|'browsers'|'compilers'. dry_run=true (default) "
        "only reports; force=true allows SIGKILL after a 3s SIGTERM grace. "
        "systemd, compositors, sshd, shells and OrquestraAI are always refused."
    )
)
def janitor_sweep_processes(
    pids: list[int] | None = None,
    target_type: str | None = None,
    dry_run: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    """Denylist-checked termination plan or execution."""
    return _guarded(sweep.sweep, pids, target_type, dry_run, force)


@server.tool(
    description=(
        "Clean transient caches. targets: sockets (dead ~/.orquestra/*.sock), "
        "staging (.codex marketplace staging), testing_scratch "
        "(/var/tmp/testing). older_than_hours=6 gates every removal; "
        "dry_run=true (default) only reports."
    )
)
def janitor_clean_caches(
    dry_run: bool = True,
    targets: list[str] | None = None,
    older_than_hours: int = caches.DEFAULT_OLDER_THAN_HOURS,
) -> dict[str, Any]:
    """Age-gated removal report with per-item actions and reclaimable MB."""
    return _guarded(caches.clean_caches, dry_run, targets, older_than_hours)


@server.tool(
    description=(
        "Inspect oom_score and oom_score_adj for active agent runners to show "
        "kernel sacrifice priority under memory pressure, with recommendations."
    )
)
def janitor_oom_inspect() -> dict[str, Any]:
    """Sorted OOM priority of this user's runners plus advisory notes."""
    return _guarded(oom.oom_inspect)


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