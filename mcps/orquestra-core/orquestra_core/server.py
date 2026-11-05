"""MCP entrypoint: OrquestraAI skills, MCP servers, bridge state and master rules."""

from __future__ import annotations

import argparse
import sys
from typing import Any, Callable

from mcp.server.mcpserver import MCPServer

from . import catalog, catalog_admin, fleet, instructions, mcp_control, paths, presets, skill_admin, skill_tools, skills, vault
from .errors import actionable
from .meta import INSTRUCTIONS
from .schema import HttpMethod

server = MCPServer(
    name="orquestra-core",
    title="Orquestra Core",
    version="0.1.0",
    instructions=INSTRUCTIONS,
)


def tool(*, description: str) -> Callable[[Callable[..., Any]], Any]:
    """Register a tool whose anticipated failures reach the caller verbatim."""
    return lambda fn: server.tool(description=description)(actionable(fn))


@tool(
    description="List skills in the vault with token weight, projection status, and optional filtering."
)
def orquestra_list_skills(
    scope: str = "global",
    filter_text: str | None = None,
    official_only: bool = False,
    has_scripts_only: bool = False,
) -> list[dict[str, Any]]:
    """scope: 'global' or a harness id such as codex, claude, grok."""
    return skills.list_skills(scope, filter_text, official_only, has_scripts_only)


@tool(
    description="Activate a skill in a scope; 'global' propagates the symlink to every harness."
)
def orquestra_enable_skill(skill_id: str, scope: str = "global") -> dict[str, Any]:
    """Create the active/<scope>/<skill> symlink atomically and report the scopes changed."""
    return skills.enable_skill(skill_id, scope)


@tool(
    description="Deactivate a skill; 'global' removes its symlink from every harness projection."
)
def orquestra_disable_skill(skill_id: str, scope: str = "global") -> dict[str, Any]:
    """Remove the projection and report the approximate tokens freed."""
    return skills.disable_skill(skill_id, scope)


@tool(description="List registered MCP servers with their global and per-harness state.")
def orquestra_list_mcps() -> list[dict[str, Any]]:
    """Reads ~/.orquestra/mcps.json, the catalog OrquestraAI compiles outward."""
    return catalog.list_mcps()


@tool(
    description="Enable or disable one MCP server, then redeploy the catalog to every harness."
)
def orquestra_toggle_mcp(
    mcp_id: str, scope: str = "global", enabled: bool = True
) -> dict[str, Any]:
    """scope: 'global' or a harness id. Returns the config files that changed."""
    return catalog.toggle_mcp(mcp_id, scope, enabled)


@tool(
    description="Get fleet-wide MCP catalog status, total servers, and per-harness projection summary."
)
def orquestra_mcp_status() -> dict[str, Any]:
    """Returns counts of official/custom servers, active states, and target sync status."""
    return mcp_control.get_mcp_status()


@tool(
    description="Inspect full configuration, environment variables, headers, and projection of an MCP server."
)
def orquestra_inspect_mcp(mcp_id: str, reveal: bool = False) -> dict[str, Any]:
    """mcp_id: Server identifier (e.g. 'cloudflare'). reveal: whether to reveal raw environment values."""
    return mcp_control.inspect_mcp(mcp_id, reveal=reveal)


@tool(
    description="Test connection and protocol handshake for an MCP server (measures latency and handshake health)."
)
def orquestra_test_mcp_connection(mcp_id: str, timeout_ms: int = 5000) -> dict[str, Any]:
    """mcp_id: Server identifier. timeout_ms: Handshake timeout in milliseconds."""
    return mcp_control.test_mcp_connection(mcp_id, timeout_ms=timeout_ms)


@tool(
    description="List all available tools and schema definitions exposed by an MCP server without mounting it."
)
def orquestra_list_mcp_tools(mcp_id: str, timeout_ms: int = 5000) -> dict[str, Any]:
    """mcp_id: Server identifier. Returns list of tools with their descriptions and parameters."""
    return mcp_control.list_mcp_tools(mcp_id, timeout_ms=timeout_ms)


@tool(
    description="Dynamically execute a tool on an MCP server over stdio transport without mounting it into session context."
)
def orquestra_call_mcp_tool(
    mcp_id: str,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    timeout_ms: int = 15000,
) -> dict[str, Any]:
    """Execute on-demand tool calls against any catalog server cleanly."""
    return mcp_control.call_mcp_tool(mcp_id, tool_name, arguments=arguments, timeout_ms=timeout_ms)


@tool(
    description="List all supported AI agent harness targets (Claude, Codex, OpenCode, Cursor) and sync status."
)
def orquestra_list_harness_targets() -> list[dict[str, Any]]:
    """Returns harness targets with their install and config paths."""
    return mcp_control.list_harness_targets()


@tool(description="Return the master ~/.orquestra/AGENTS.md that every harness inherits.")
def orquestra_read_instructions() -> str:
    """The single source of truth symlinked into each harness."""
    return instructions.read_instructions()


@tool(
    description="Append a mission directive to a section of the master AGENTS.md, with a backup."
)
def orquestra_append_mission_rule(section_title: str, rule_content: str) -> dict[str, Any]:
    """Creates the section when missing; never rewrites unrelated sections."""
    return instructions.append_mission_rule(section_title, rule_content)


@tool(description="Report link state for every harness in the OrquestraAI fleet.")
def orquestra_fleet_status() -> dict[str, Any]:
    """Runs orquestra --bridge-status and condenses the per-harness report."""
    return fleet.fleet_status()


@tool(
    description=(
        "List all built-in and custom mission presets with their active status "
        "and member skills/MCPs."
    )
)
def orquestra_list_presets() -> list[dict[str, Any]]:
    """Returns the built-in full-power preset merged with any custom presets
    defined in ~/.orquestra/presets.json."""
    return presets.list_presets()


@tool(
    description=(
        "Apply a mission preset (full-power or a custom id) across all harnesses."
    )
)
def orquestra_apply_preset(preset_id: str) -> dict[str, Any]:
    """Validates the id, then delegates to orquestra --preset <id> and returns a PresetReport."""
    return presets.apply_preset(preset_id)


@tool(description="Save a new custom mission preset with a selection of skills and MCP servers.")
def orquestra_save_preset(
    name: str,
    description: str = "",
    skills: list[str] | None = None,
    mcps: list[str] | None = None,
    icon: str = "custom",
) -> dict[str, Any]:
    """Creates or updates a custom preset in ~/.orquestra/presets.json."""
    return presets.save_preset(name, description, skills, mcps, icon)


@tool(description="Delete a custom mission preset by its ID. Built-in presets cannot be deleted.")
def orquestra_delete_preset(preset_id: str) -> dict[str, Any]:
    """Removes a custom preset from ~/.orquestra/presets.json."""
    return presets.delete_preset(preset_id)


@tool(
    description=(
        "Deploy harness bridge fusion: back up and symlink every installed harness "
        "into the fleet projection."
    )
)
def orquestra_deploy_bridge() -> dict[str, Any]:
    """Delegates to orquestra --bridge-deploy and returns a BridgeReport."""
    return fleet.deploy_bridge()


@tool(
    description="Create a skill in the vault with frontmatter, markdown body and optional scripts."
)
def orquestra_create_skill(
    skill_id: str,
    name: str,
    description: str,
    instructions_markdown: str,
    scripts: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Writes skills-library/<id>/SKILL.md; scripts land in that skill's scripts/ folder."""
    return skill_admin.create_skill(
        skill_id, name, description, instructions_markdown, scripts
    )


@tool(
    description="Archive a skill: unlink it from every scope, then move its vault folder to backups."
)
def orquestra_delete_skill(skill_id: str) -> dict[str, Any]:
    """Never hard-deletes: the vault folder is moved under backups/deleted-skills-<stamp>/."""
    return skill_admin.delete_skill(skill_id)


@tool(
    description="Register a new MCP server in the catalog, then deploy it to every harness."
)
def orquestra_create_mcp(
    mcp_id: str,
    name: str,
    description: str,
    command: str,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
    global_enabled: bool = True,
) -> dict[str, Any]:
    """Adds the entry to mcps.json and managedIds, then runs --mcp-deploy."""
    return catalog_admin.create_mcp(
        mcp_id, name, description, command, args, env, global_enabled
    )


@tool(description="Remove an MCP server from the catalog and from every harness config.")
def orquestra_delete_mcp(mcp_id: str) -> dict[str, Any]:
    """Backs up the catalog, drops the entry and its managed id, then redeploys."""
    return catalog_admin.delete_mcp(mcp_id)


@tool(
    description=(
        "List credential services, masked keys in 1-based order, the active key "
        "number, and health. Secrets are never returned."
    )
)
def orquestra_vault_list() -> list[dict[str, Any]]:
    """Inspect configured API services and key pools without exposing any secret."""
    return vault.list_services()


@tool(
    description=(
        "Execute a blind HTTP request with a stored credential. Ask whether the "
        "operator prefers a key number or the active default unless already stated. "
        "Pass key_number (1-based) to pin one key; omit it for the default. "
        "A pinned request uses only that key and never changes the default. "
        "Reuse the same choice for related calls. The secret stays in memory and "
        "is scrubbed from responses."
    )
)
def orquestra_vault_http(
    service_id: str,
    endpoint: str,
    method: HttpMethod = "GET",
    headers: dict[str, str] | None = None,
    body: Any | None = None,
    timeout: float = 30.0,
    key_number: int | None = None,
    key_tag: str | None = None,
) -> dict[str, Any]:
    """Returns status and scrubbed response; reports the one-based key number used."""
    return vault.execute_http(
        service_id, endpoint, method, headers, body, timeout, key_number, key_tag
    )


@tool(description="Inspect credential service details, masked keys, health, and key tags.")
def orquestra_vault_inspect(service_id: str) -> dict[str, Any]:
    """Inspect service metadata and key pool without revealing secrets."""
    return vault.inspect_service(service_id)


@tool(description="Advance the active key pointer or rotate a specific key in the pool.")
def orquestra_vault_rotate(
    service_id: str, next_key: bool = True, key_number: int | None = None
) -> dict[str, Any]:
    """Rotate keys in pool or advance active pointer."""
    return vault.rotate_key(service_id, next_key=next_key, key_number=key_number)


@tool(description="Test connection and latency to provider verify endpoint.")
def orquestra_vault_test(
    service_id: str, key_number: int | None = None
) -> dict[str, Any]:
    """Ping provider endpoint and persist updated health."""
    return vault.test_service(service_id, key_number=key_number)


@tool(description="List built-in provider presets (headers, env vars, metadata).")
def orquestra_vault_presets() -> list[dict[str, Any]]:
    """List provider credential templates."""
    return vault.list_vault_presets()


@tool(description="Audit vault at-rest encryption, 0600 file permissions, and backups.")
def orquestra_vault_audit() -> dict[str, Any]:
    """Audit security posture of local vault storage."""
    return vault.audit_vault()


@tool(
    description=(
        "Execute an allowlisted CLI command with a stored credential injected "
        "in memory. Ask whether the operator prefers a key number or the active "
        "default unless already stated. Pass key_number (1-based) to pin one key; "
        "omit it for the default. A pinned command uses only that key and never "
        "changes the default. Reuse the same choice for related calls. Output is scrubbed."
    )
)
def orquestra_vault_exec(
    service_id: str,
    command: list[str] | str,
    timeout: float = 60.0,
    key_number: int | None = None,
) -> dict[str, Any]:
    """Command runs with selected secret in env; returns scrubbed output and key number used."""
    return vault.execute_exec(service_id, command, timeout, key_number)


@tool(
    description="Flip a vault credential service kill-switch. The blind proxy refuses disabled services."
)
def orquestra_vault_set_enabled(service_id: str, enabled: bool) -> dict[str, Any]:
    """service_id: e.g. 'github'. Returns the service with its new enabled state; no secrets."""
    return vault.set_service_enabled(service_id, enabled)


# Register granular skill administration and introspection tools
skill_tools.register_skill_tools(server)


def main(argv: list[str] | None = None) -> int:
    """Serve the control plane over the chosen MCP transport (stdio by default)."""
    parser = argparse.ArgumentParser(prog="orquestra-core", description=__doc__)
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=("stdio", "sse", "streamable-http"),
        help="MCP transport (default: stdio)",
    )
    args = parser.parse_args(argv)
    print(f"orquestra-core: serving {paths.home()} over {args.transport}", file=sys.stderr)
    server.run(args.transport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
