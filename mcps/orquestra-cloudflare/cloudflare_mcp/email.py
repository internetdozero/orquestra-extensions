"""Cloudflare Email Routing and destination management.

Provides visibility into verified destination addresses, active routing rules
and forwarding patterns configured for zones in the account.
"""

from __future__ import annotations

from typing import Any, Callable

from mcp.server.mcpserver import MCPServer

from .client import CloudflareClient
from .result import ToolResult, safe


def list_routing_rules(client: CloudflareClient, zone: str) -> dict[str, Any]:
    """List email routing rules configured for a zone."""
    zone_id = client.settings.zone_id(zone)
    rules = client.get(f"/zones/{zone_id}/email/routing/rules")
    return {
        "zone": zone,
        "zone_id": zone_id,
        "count": len(rules) if isinstance(rules, list) else 0,
        "rules": rules if isinstance(rules, list) else [],
    }


def list_destination_addresses(client: CloudflareClient) -> dict[str, Any]:
    """List verified destination email addresses for the active account."""
    client.settings.require_credentials()
    acct = client.settings.account_id
    addresses = client.get(f"/accounts/{acct}/email/routing/addresses")
    return {
        "account_id": acct,
        "count": len(addresses) if isinstance(addresses, list) else 0,
        "addresses": addresses if isinstance(addresses, list) else [],
    }


def register_email_tools(mcp: MCPServer, get_client: Callable[[], CloudflareClient]) -> None:
    """Register Email service tools onto the MCP server instance."""

    @mcp.tool(
        description=(
            "List Cloudflare Email Routing rules for a zone (matchers, forward actions, "
            "enabled status and priorities). Useful to inspect inbound routing for domains."
        )
    )
    @safe
    def cf_email_routing_rules(zone: str = "") -> ToolResult:
        client = get_client()
        return list_routing_rules(client, zone)

    @mcp.tool(
        description=(
            "List verified destination email addresses for Cloudflare Email Routing "
            "under the active account."
        )
    )
    @safe
    def cf_email_destinations() -> ToolResult:
        client = get_client()
        return list_destination_addresses(client)
