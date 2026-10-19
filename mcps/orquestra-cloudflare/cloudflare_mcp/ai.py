"""Cloudflare Workers AI catalog and Vectorize index inspection.

Enables agents to query available Workers AI models and vector database indexes
without leaving the unified MCP interface.
"""

from __future__ import annotations

from typing import Any, Callable

from mcp.server.mcpserver import MCPServer

from .client import CloudflareClient
from .result import ToolResult, safe


def list_ai_models(client: CloudflareClient, search: str | None = None) -> dict[str, Any]:
    """List or search available Cloudflare Workers AI models."""
    client.settings.require_credentials()
    acct = client.settings.account_id
    params = {"search": search.strip()} if search and search.strip() else None
    models = client.get(f"/accounts/{acct}/ai/models/search", params=params)
    items = models if isinstance(models, list) else []
    return {
        "account_id": acct,
        "search": search or "",
        "count": len(items),
        "models": items[:50],
    }


def list_vectorize_indexes(client: CloudflareClient) -> dict[str, Any]:
    """List Vectorize vector database indexes under the active account."""
    client.settings.require_credentials()
    acct = client.settings.account_id
    indexes = client.get(f"/accounts/{acct}/vectorize/v2/indexes")
    items = indexes if isinstance(indexes, list) else []
    return {
        "account_id": acct,
        "count": len(items),
        "indexes": items,
    }


def register_ai_tools(mcp: MCPServer, get_client: Callable[[], CloudflareClient]) -> None:
    """Register AI and Vectorize tools onto the MCP server instance."""

    @mcp.tool(
        description=(
            "List or search Cloudflare Workers AI models (e.g. '@cf/meta/llama-3', "
            "embeddings, text generation, vision). Returns model metadata and capabilities."
        )
    )
    @safe
    def cf_ai_models(search: str = "") -> ToolResult:
        client = get_client()
        return list_ai_models(client, search=search)

    @mcp.tool(
        description=(
            "List Cloudflare Vectorize vector database indexes (dimensions, metric, "
            "creation timestamp, description)."
        )
    )
    @safe
    def cf_vectorize_list_indexes() -> ToolResult:
        client = get_client()
        return list_vectorize_indexes(client)
