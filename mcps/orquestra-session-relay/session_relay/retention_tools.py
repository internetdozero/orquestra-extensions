"""Export, purge and retention policy tool registration for session-relay."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from . import delete, export, policy, purge
from .errors import actionable
from .schema import Harness


def register_retention_tools(server: MCPServer) -> None:
    """Register export, purge, and retention tools onto the MCP server."""

    @server.tool(
        description="Export complete unabridged transcript of a session to structured Markdown or JSON."
    )
    @actionable
    def export_session(
        harness: Harness,
        session_id: str = "latest",
        format: str = "markdown",
        output_path: str | None = None,
    ) -> dict[str, Any]:
        """Export complete session turns with YAML frontmatter or unabridged JSON."""
        return export.export_session(
            harness=harness,
            session_id=session_id,
            format=format,
            output_path=output_path,
        )

    @server.tool(
        description="Estimate candidates and disk space to reclaim in a retention purge (dry-run)."
    )
    @actionable
    def estimate_purge(
        older_than_days: int | None = None,
        harness: Harness | None = None,
        session_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Calculate purge candidates without deleting anything; protects pinned and active sessions."""
        return purge.estimate_purge(
            older_than_days=older_than_days,
            harness=harness,
            session_ids=session_ids,
        )

    @server.tool(
        description="Batch purge expired or specified sessions, respecting pin and active protection."
    )
    @actionable
    def purge_sessions(
        older_than_days: int | None = None,
        harness: Harness | None = None,
        session_ids: list[str] | None = None,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Purge sessions. dry_run defaults to True for safety; pass dry_run=False to delete."""
        return purge.purge_sessions(
            older_than_days=older_than_days,
            harness=harness,
            session_ids=session_ids,
            dry_run=dry_run,
        )

    @server.tool(
        description="Surgically delete an individual session from a harness store, with safety guards."
    )
    @actionable
    def delete_session(
        harness: Harness, session_id: str, force: bool = False
    ) -> dict[str, Any]:
        """Refuses deletion if active or pinned (unless force=True). Reclaims disk storage."""
        return delete.delete_session(
            harness=harness, session_id=session_id, force=force
        )

    @server.tool(
        description="Get current retention policy settings from ~/.orquestra/sessions_policy.json."
    )
    @actionable
    def get_retention_policy() -> dict[str, Any]:
        """Returns default TTL, auto-purge flag, interval, and per-harness overrides."""
        return policy.get_retention_policy()

    @server.tool(
        description="Update retention policy configuration in ~/.orquestra/sessions_policy.json."
    )
    @actionable
    def set_retention_policy(
        default_ttl_days: int | None = None,
        auto_purge_enabled: bool | None = None,
        interval_hours: int | None = None,
        harness_overrides: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        """Atomically configure retention TTLs, auto-purge switch, and intervals."""
        return policy.set_retention_policy(
            default_ttl_days=default_ttl_days,
            auto_purge_enabled=auto_purge_enabled,
            interval_hours=interval_hours,
            harness_overrides=harness_overrides,
        )
