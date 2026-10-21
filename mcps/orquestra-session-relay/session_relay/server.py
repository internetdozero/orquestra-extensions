"""MCP entrypoint: cross-harness session inspection and handoff tools."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from . import audit, discovery, handoff, policy, watch
from .adapters.base import clamp_limit
from .compact import compact_row, compact_session
from .errors import actionable
from .lookup import resolve
from .schema import Harness

INSTRUCTIONS = """Read-only session relay for AI coding harnesses on this machine.

Use list_recent_sessions to see what Codex, Claude Code, Antigravity, OpenCode,
Kilo, Copilot, Hermes and Freebuff were doing, inspect_session for the ordered
conversation and tool events, search_sessions_history to find earlier work by
keyword, handoff_context to produce a Goal / Files / State / Blocker /
Next-steps brief, pin_session / unpin_session / list_pinned_sessions to protect
sessions in ~/.orquestra/sessions_policy.json, watch_active_agent to track live
agent state and touched files in real time, and tail_agent_activity to tail
concise summaries of the latest events.

Every harness parameter publishes its accepted ids in the tool schema (canonical
ids plus aliases such as claude-code, gemini and xai); a rejected id comes back
as a tool error listing them, not as a generic execution failure.

Every store is opened read-only. Missing harnesses return friendly empty states.
"""

server = MCPServer(
    name="session-relay",
    title="Session Relay",
    version="0.1.0",
    instructions=INSTRUCTIONS,
)


@server.tool(
    description="List recent sessions across all 9 harnesses (newest first); pinned sessions show is_pinned."
)
@actionable
def list_recent_sessions(
    harness: Harness | None = None, limit: int = 5, compact: bool = False
) -> dict[str, Any]:
    """Discover recent sessions; omit harness to merge every supported store."""
    sessions, warnings = discovery.recent_sessions(
        harness, clamp_limit(limit, 5, 50)
    )
    sessions = policy.decorate(sessions)
    if compact:
        return {
            "count": len(sessions),
            "sessions": [compact_row(session) for session in sessions],
            "warnings": warnings,
            "compact": True,
        }
    return {
        "count": len(sessions),
        "sessions": [session.as_dict() for session in sessions],
        "warnings": warnings,
    }


@server.tool(description="Pin a session so purges skip it (stored in ~/.orquestra).")
@actionable
def pin_session(
    harness: Harness, session_id: str, label: str | None = None
) -> dict[str, Any]:
    """Protect one session; re-pinning only updates the label."""
    return policy.pin_session(harness, session_id, label)


@server.tool(description="Remove a session pin; missing pins report pinned False.")
@actionable
def unpin_session(harness: Harness, session_id: str) -> dict[str, Any]:
    """Lift protection from one session."""
    return policy.unpin_session(harness, session_id)


@server.tool(description="List every pinned session from ~/.orquestra.")
@actionable
def list_pinned_sessions() -> dict[str, Any]:
    """Return pins in file order with harness, sessionId and label."""
    pins = policy.list_pins()
    return {"count": len(pins), "pins": pins}


@server.tool(
    description="Read a session's ordered conversation and tool events. session_id defaults to the newest one; harness is inferred from desktop:/claude:/codex: prefixes or searched across harnesses when omitted."
)
@actionable
def inspect_session(
    harness: Harness | None = None,
    session_id: str = "latest",
    max_turns: int = 10,
    compact: bool = False,
) -> dict[str, Any]:
    """Inspect one session; max_turns keeps only the most recent user turns."""
    resolution = resolve(harness, session_id, max_turns)
    if resolution.error is not None:
        return resolution.as_error_payload()
    if compact:
        payload = compact_session(resolution.detail)
        payload["compact"] = True
        return payload
    payload = resolution.detail.as_dict(max_text=2000)
    payload["harness"] = resolution.adapter.id
    return payload


@server.tool(
    description="Generate an executive handoff brief (goal, files, blocker, next steps) for a session."
)
@actionable
def handoff_context(source_harness: Harness, session_id: str = "latest") -> str:
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
@actionable
def search_sessions_history(
    query: str, harness: Harness | None = None, limit: int = 10
) -> dict[str, Any]:
    """Find prior work by case-insensitive substring across session texts."""
    if not query.strip():
        raise ToolError("query must not be empty")
    adapters = discovery.adapters_for(harness)
    hits = []
    warnings: list[str] = []
    for adapter in adapters:
        if not adapter.available():
            warnings.append(f"{adapter.id}: no session store found")
            continue
        try:
            hits.extend(adapter.search(query, clamp_limit(limit, 10, 50)))
        except Exception as error:  # a broken store must not hide the others
            warnings.append(f"{adapter.id}: {type(error).__name__}: {error}")
    hits.sort(key=lambda hit: hit.updated_at or "", reverse=True)
    hits = hits[: clamp_limit(limit, 10, 50)]
    return {
        "query": query,
        "count": len(hits),
        "hits": [hit.as_dict() for hit in hits],
        "warnings": warnings,
    }


@server.tool(
    description="Watch the active coding agent session, status (running/idle), last turn, and touched files."
)
@actionable
def watch_active_agent(
    project_path: str | None = None,
    harness: Harness | None = None,
    exclude_harness: Harness | None = None,
) -> dict[str, Any]:
    """Observe live agent activity and whether an agent is actively running."""
    return watch.watch_active_agent(project_path, harness, exclude_harness)


@server.tool(
    description="Tail the last few events or turns of an agent session with concise summary text."
)
@actionable
def tail_agent_activity(
    harness: Harness | None = None, session_id: str | None = None, limit: int = 5
) -> dict[str, Any]:
    """Get the latest events of a session without loading megabytes of payload."""
    return watch.tail_agent_activity(harness, session_id, limit)


@server.tool(
    description="Lean orchestrator telemetry: liveness, current turn, git worktree state."
)
@actionable
def audit_agent(harness: Harness, session_id: str | None = None) -> dict[str, Any]:
    """Audit one agent thread without loading its full transcript."""
    return audit.audit_agent(harness, session_id)


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
