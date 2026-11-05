"""MCP tool registrations for granular skill management."""

from __future__ import annotations

from typing import Any, Callable

from mcp.server.mcpserver import MCPServer

from . import skill_admin, skills
from .errors import actionable


def _tool(server: MCPServer, description: str) -> Callable[[Callable[..., Any]], Any]:
    return lambda fn: server.tool(description=description)(actionable(fn))


def register_skill_tools(server: MCPServer) -> None:
    """Register granular skill inspection, validation, content, batch, and import tools."""

    @_tool(
        server,
        description="Inspect a skill in depth: metadata, token count, script files, and projection matrix across all scopes.",
    )
    def orquestra_inspect_skill(skill_id: str, scope: str = "global") -> dict[str, Any]:
        """skill_id: identifier in ~/.orquestra/skills/library; scope: default perspective."""
        return skills.inspect_skill(skill_id, scope)

    @_tool(
        server,
        description="Validate a skill's directory structure, frontmatter (name/description), ID safety, and limits.",
    )
    def orquestra_validate_skill(target: str) -> dict[str, Any]:
        """target: skill_id in library or an arbitrary directory path to validate before import."""
        return skill_admin.validate_skill(target)

    @_tool(
        server,
        description="Read the raw SKILL.md markdown content from the skill vault.",
    )
    def orquestra_get_skill_content(skill_id: str) -> dict[str, Any]:
        """skill_id: identifier of the skill to read."""
        return skills.get_skill_content(skill_id)

    @_tool(
        server,
        description="Update or rewrite the SKILL.md manifest of an existing skill in the vault atomically.",
    )
    def orquestra_set_skill_content(skill_id: str, content: str) -> dict[str, Any]:
        """skill_id: identifier of the skill; content: new SKILL.md markdown with YAML frontmatter."""
        return skills.set_skill_content(skill_id, content)

    @_tool(
        server,
        description="Get fleet-wide summary of active vs total skill projections across global and all harnesses.",
    )
    def orquestra_skills_summary() -> dict[str, Any]:
        """Returns total skills count and per-scope breakdown of active skills."""
        return skills.skills_summary()

    @_tool(
        server,
        description="Bulk enable or disable all vault skills for a specific scope or globally.",
    )
    def orquestra_batch_skills(action: str, scope: str = "global") -> dict[str, Any]:
        """action: 'enable' or 'disable'; scope: 'global' or harness name."""
        return skills.batch_skills(action, scope)

    @_tool(
        server,
        description="Import a skill from a local directory or remote git repository with validation and optional activation.",
    )
    def orquestra_import_skill(
        source: str,
        subpath: str | None = None,
        scope: str = "global",
        enable: bool = False,
    ) -> dict[str, Any]:
        """source: directory path or git URL; subpath: directory inside git repo; scope: target scope if enable=True."""
        return skill_admin.import_skill(source, subpath, scope, enable)
