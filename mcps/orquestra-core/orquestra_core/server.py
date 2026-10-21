"""MCP entrypoint: OrquestraAI skills, MCP servers, bridge state and master rules."""

from __future__ import annotations

import argparse
import sys
from typing import Any, Callable

from mcp.server.mcpserver import MCPServer

from . import catalog, catalog_admin, fleet, instructions, paths, presets, skill_admin, skills, vault
from .errors import actionable
from .schema import HttpMethod

INSTRUCTIONS = """Control plane for the OrquestraAI harness fleet on this machine.

Skills: orquestra_list_skills shows the vault and which scopes project each
skill, orquestra_enable_skill / orquestra_disable_skill flip the symlinks the
harnesses read (a global change fans out to every harness scope).

MCP servers: orquestra_list_mcps reads the catalog, orquestra_toggle_mcp flips
one server and recompiles every harness config through the native binary.

Lifecycle: orquestra_create_skill / orquestra_delete_skill manage the vault,
orquestra_create_mcp / orquestra_delete_mcp register or retire a server and
deploy the catalog.

Instructions: orquestra_read_instructions returns the master AGENTS.md and
orquestra_append_mission_rule appends a scoped directive with a backup.

Fleet: orquestra_fleet_status reports the link state of every harness.
orquestra_deploy_bridge runs headless bridge fusion: backs up and symlinks
every installed harness into the fleet projection.

Presets: orquestra_list_presets lists all built-in and custom mission presets;
orquestra_apply_preset activates a named preset (stealth, rust-dev,
web-fullstack, full-power) across all harnesses via the native binary;
orquestra_save_preset creates or updates a custom preset in presets.json and
orquestra_delete_preset removes one (built-ins are protected).
"""

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
    description="List every skill in the vault with token weight and whether a scope projects it."
)
def orquestra_list_skills(scope: str = "global") -> list[dict[str, Any]]:
    """scope: 'global' or a harness id such as codex, claude, grok."""
    return skills.list_skills(scope)


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
    """Returns built-ins (stealth, rust-dev, web-fullstack, full-power) merged with any
    custom presets defined in ~/.orquestra/presets.json."""
    return presets.list_presets()


@tool(
    description=(
        "Apply a curated mission preset (e.g. stealth, rust-dev, web-fullstack, full-power) "
        "across all harnesses."
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
    description="List all credential services in Orquestra Vault with health and masked keys. Zero secrets returned."
)
def orquestra_vault_list() -> list[dict[str, Any]]:
    """Inspect configured API services and key pools without exposing any secret."""
    return vault.list_services()


@tool(
    description="Execute blind HTTP request using a stored service credential. The secret is injected in memory and scrubbed from responses."
)
def orquestra_vault_http(
    service_id: str,
    endpoint: str,
    method: HttpMethod = "GET",
    headers: dict[str, str] | None = None,
    body: Any | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """service_id: e.g. 'inception-labs', 'openai', 'github'. Returns status, scrubbed headers, and scrubbed body."""
    return vault.execute_http(service_id, endpoint, method, headers, body, timeout)


@tool(
    description="Execute CLI command with stored service credentials injected into environment in memory. Output is scrubbed."
)
def orquestra_vault_exec(
    service_id: str,
    command: list[str] | str,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """service_id: e.g. 'github', 'cloudflare', 'inception-labs'. Command runs with secret in env, output scrubbed."""
    return vault.execute_exec(service_id, command, timeout)


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
