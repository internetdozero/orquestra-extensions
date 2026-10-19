"""MCP entrypoint: cross-harness session inspection and handoff tools."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from mcp.server.mcpserver import MCPServer

from . import discovery, handoff, watch

INSTRUCTIONS = """Read-only session relay for AI coding harnesses on this machine.

Use list_recent_sessions to see what Codex, Claude Code, Antigravity, OpenCode
and Freebuff were doing, inspect_session for the ordered conversation and tool
events, search_sessions_history to find earlier work by keyword,
handoff_context to produce a Goal / Files / State / Blocker / Next-steps brief,
watch_active_agent to track live agent state and touched files in real time, and
tail_agent_activity to tail concise summaries of the latest events.

Every store is opened read-only. Missing harnesses return friendly empty states.
"""

server = MCPServer(
    name="session-relay",
    title="Session Relay",
    version="0.1.0",
    instructions=INSTRUCTIONS,
)


def _bounds(value: int, default: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(1, min(number, maximum))


@server.tool(
    description="List recent sessions across harnesses (codex, claude, antigravity, opencode, freebuff), newest first."
)
def list_recent_sessions(
    harness: str | None = None, limit: int = 5
) -> dict[str, Any]:
    """Discover recent sessions; omit harness to merge every supported store."""
    try:
        sessions, warnings = discovery.recent_sessions(harness, _bounds(limit, 5, 50))
    except ValueError as error:
        return {"count": 0, "sessions": [], "warnings": [], "error": str(error)}
    return {
        "count": len(sessions),
        "sessions": [session.as_dict() for session in sessions],
        "warnings": warnings,
    }


@server.tool(
    description="Read a session's ordered conversation and tool events. session_id defaults to the newest one."
)
def inspect_session(
    harness: str, session_id: str = "latest", max_turns: int = 10
) -> dict[str, Any]:
    """Inspect one session; max_turns keeps only the most recent user turns."""
    try:
        adapter = discovery.get_adapter(harness)
    except ValueError as error:
        return {"error": str(error)}
    if not adapter.available():
        return {
            "error": f"no {adapter.label} session store was found on this machine",
            "harness": adapter.id,
            "events": [],
        }
    detail = adapter.load_session(session_id, _bounds(max_turns, 10, 50))
    if detail is None:
        return {
            "error": f"session '{session_id}' was not found for {adapter.id}",
            "harness": adapter.id,
            "hint": "Call list_recent_sessions(harness='%s') for valid ids." % adapter.id,
            "events": [],
        }
    payload = detail.as_dict(max_text=2000)
    payload["harness"] = adapter.id
    return payload


@server.tool(
    description="Generate an executive handoff brief (goal, files, blocker, next steps) for a session."
)
def handoff_context(source_harness: str, session_id: str = "latest") -> str:
    """Return markdown another agent can resume from without copying context."""
    try:
        adapter = discovery.get_adapter(source_harness)
    except ValueError as error:
        return f"# Handoff unavailable\n\n{error}\n"
    if not adapter.available():
        return (
            f"# Handoff unavailable\n\nNo {adapter.label} session store was found. "
            "Run list_recent_sessions to see which harnesses have history.\n"
        )
    detail = adapter.load_session(session_id, max_turns=0)  # full history for the original goal
    if detail is None:
        return (
            f"# Handoff unavailable\n\nSession `{session_id}` was not found for "
            f"{adapter.id}. Try `list_recent_sessions(harness='{adapter.id}')`.\n"
        )
    return handoff.synthesize(detail)


@server.tool(
    description="Keyword search across session message texts in one or every harness."
)
def search_sessions_history(
    query: str, harness: str | None = None, limit: int = 10
) -> dict[str, Any]:
    """Find prior work by case-insensitive substring across session texts."""
    if not query.strip():
        return {"query": query, "count": 0, "hits": [], "error": "query must not be empty"}
    try:
        adapters = discovery.adapters_for(harness)
    except ValueError as error:
        return {"query": query, "count": 0, "hits": [], "error": str(error)}
    hits = []
    warnings: list[str] = []
    for adapter in adapters:
        if not adapter.available():
            warnings.append(f"{adapter.id}: no session store found")
            continue
        try:
            hits.extend(adapter.search(query, _bounds(limit, 10, 50)))
        except Exception as error:  # a broken store must not hide the others
            warnings.append(f"{adapter.id}: {type(error).__name__}: {error}")
    hits.sort(key=lambda hit: hit.updated_at or "", reverse=True)
    hits = hits[: _bounds(limit, 10, 50)]
    return {
        "query": query,
        "count": len(hits),
        "hits": [hit.as_dict() for hit in hits],
        "warnings": warnings,
    }


@server.tool(
    description="Watch the active coding agent session, status (running/idle), last turn, and touched files."
)
def watch_active_agent(project_path: str | None = None) -> dict[str, Any]:
    """Observe live agent activity and whether an agent is actively running."""
    return watch.watch_active_agent(project_path)


@server.tool(
    description="Tail the last few events or turns of an agent session with concise summary text."
)
def tail_agent_activity(
    harness: str | None = None, session_id: str | None = None, limit: int = 5
) -> dict[str, Any]:
    """Get the latest events of a session without loading megabytes of payload."""
    return watch.tail_agent_activity(harness, session_id, limit)


def main(argv: list[str] | None = None) -> int:
    """Serve the relay over the chosen MCP transport (stdio by default)."""
    parser = argparse.ArgumentParser(prog="session-relay", description=__doc__)
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=("stdio", "sse", "streamable-http"),
        help="MCP transport (default: stdio)",
    )
    args = parser.parse_args(argv)
    print(f"session-relay: serving over {args.transport}", file=sys.stderr)
    server.run(args.transport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
