"""Server instructions and metadata strings for orquestra-core MCP."""

from __future__ import annotations

INSTRUCTIONS = """Control plane for the OrquestraAI harness fleet on this machine.

Skills: orquestra_list_skills shows the vault and which scopes project each
skill (with optional filter_text, official_only, and has_scripts_only),
orquestra_enable_skill / orquestra_disable_skill flip the symlinks the
harnesses read (a global change fans out to every harness scope).
Granular skills: orquestra_inspect_skill inspects metadata, scripts, and projection matrix,
orquestra_validate_skill audits SKILL.md frontmatter and directory security limits,
orquestra_get_skill_content / orquestra_set_skill_content read and write SKILL.md manifests atomically,
orquestra_skills_summary reports fleet-wide active/total skills per scope,
orquestra_batch_skills bulk enables or disables all skills for a scope, and
orquestra_import_skill imports skills from local directories or git repositories.

MCP servers: orquestra_list_mcps reads the catalog, orquestra_toggle_mcp flips
one server and recompiles every harness config through the native binary.
Granular MCP management: orquestra_mcp_status summarizes catalog and targets sync,
orquestra_inspect_mcp inspects detailed server config and environment,
orquestra_test_mcp_connection validates transport and protocol handshake,
orquestra_list_mcp_tools introspects tool schemas dynamically,
orquestra_call_mcp_tool dynamically executes a tool over stdio transport, and
orquestra_list_harness_targets lists supported AI agent targets and configs.

Lifecycle: orquestra_create_skill / orquestra_delete_skill manage the vault,
orquestra_create_mcp / orquestra_delete_mcp register or retire a server and
deploy the catalog.

Instructions: orquestra_read_instructions returns the master AGENTS.md and
orquestra_append_mission_rule appends a scoped directive with a backup.

Vault: orquestra_vault_list shows credential services with masked keys,
orquestra_vault_inspect displays full metadata, tags and pool health,
orquestra_vault_rotate advances key pointers or rotates specific keys,
orquestra_vault_test pings provider verification endpoints measuring latency,
orquestra_vault_presets lists provider credential templates,
orquestra_vault_audit checks at-rest encryption and permission security,
orquestra_vault_http / orquestra_vault_exec spend a stored key blind (with optional
key_number or key_tag), and orquestra_vault_set_enabled flips the kill-switch.
Before a credentialed request, ask whether the operator prefers a specific
key number or the active default when no preference is already stated. Reuse
that choice for the task; never request or expose the secret itself.

Fleet: orquestra_fleet_status reports the link state of every harness.
orquestra_deploy_bridge runs headless bridge fusion: backs up and symlinks
every installed harness into the fleet projection.

Presets: orquestra_list_presets lists all built-in and custom mission presets;
orquestra_apply_preset activates a named preset (full-power or a custom
id) across all harnesses via the native binary;
orquestra_save_preset creates or updates a custom preset in presets.json and
orquestra_delete_preset removes one (built-ins are protected).
"""
