"""Cloudflare Zero Trust: Tunnels and Access applications.

Provides inspection of Cloudflare Tunnels (cloudflared connectors) and
Cloudflare Access protected applications.
"""

from __future__ import annotations

from typing import Any, Callable

from mcp.server.mcpserver import MCPServer

from .client import CloudflareClient
from .result import ToolResult, safe


def list_tunnels(client: CloudflareClient, is_deleted: bool = False) -> dict[str, Any]:
    """List Cloudflare Tunnels (Zero Trust connectors) in the active account."""
    client.settings.require_credentials()
    acct = client.settings.account_id
    params = {"is_deleted": "true" if is_deleted else "false"}
    tunnels = client.get(f"/accounts/{acct}/cfd_tunnel", params=params)
    items = tunnels if isinstance(tunnels, list) else []
    return {
        "account_id": acct,
        "count": len(items),
        "tunnels": items,
    }


def list_access_apps(client: CloudflareClient) -> dict[str, Any]:
    """List Cloudflare Access applications configured in the active account."""
    client.settings.require_credentials()
    acct = client.settings.account_id
    apps = client.get(f"/accounts/{acct}/access/apps")
    items = apps if isinstance(apps, list) else []
    return {
        "account_id": acct,
        "count": len(items),
        "apps": items,
    }


def register_tunnel_tools(mcp: MCPServer, get_client: Callable[[], CloudflareClient]) -> None:
    """Register Zero Trust Tunnel and Access tools onto the MCP server instance."""

    @mcp.tool(
        description=(
            "List Cloudflare Zero Trust Tunnels (cloudflared connectors), their active "
            "status, tunnel id, connectors and configuration."
        )
    )
    @safe
    def cf_tunnels_list(is_deleted: bool = False) -> ToolResult:
        client = get_client()
        return list_tunnels(client, is_deleted=is_deleted)

    @mcp.tool(
        description=(
            "List Cloudflare Access protected applications (domains, session durations, "
            "identity provider bindings)."
        )
    )
    @safe
    def cf_access_apps_list() -> ToolResult:
        client = get_client()
        return list_access_apps(client)
