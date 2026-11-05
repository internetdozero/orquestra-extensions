"""Server instructions and metadata strings for session-relay MCP."""

from __future__ import annotations

INSTRUCTIONS = """Read-only session relay and retention management for AI coding harnesses on this machine.

Use list_recent_sessions to inspect sessions, inspect_session for turns,
search_sessions_history to find earlier work by keyword/metadata,
handoff_context to produce a structured brief, export_session to export
transcripts to Markdown/JSON, pin_session / unpin_session / list_pinned_sessions
to manage protected sessions in ~/.orquestra/sessions_policy.json,
estimate_purge and purge_sessions for retention cleanup, delete_session for
surgical deletion, get_retention_policy / set_retention_policy for TTLs,
watch_active_agent to track live agent activity, and tail_agent_activity /
audit_agent for streamable telemetry.

Every harness parameter publishes its accepted ids in the tool schema (canonical
ids plus aliases such as claude-code, gemini and xai); a rejected id comes back
as a tool error listing them, not as a generic execution failure.
"""
