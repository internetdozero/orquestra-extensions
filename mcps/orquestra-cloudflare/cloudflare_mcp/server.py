"""MCP tool definitions and stdio entry point for cloudflare-mcp.

Every tool returns a stable envelope: ``{"ok": true, "result": ...}`` on
success or ``{"ok": false, "error": {...}}`` on failure, so harnesses always
receive structured JSON instead of opaque tool crashes.
"""

from __future__ import annotations

import json
import platform
import shutil
from typing import Any

from mcp.server.mcpserver import MCPServer

from . import __version__, d1, dns, docs, storage, workers
from .ai import register_ai_tools
from .client import CloudflareAPIError, CloudflareClient
from .config import ConfigError, mask_token, load_settings
from .email import register_email_tools
from .result import ToolResult, safe
from .tunnels import register_tunnel_tools
from .wrangler import find_wrangler_config

mcp = MCPServer(
    "cloudflare-mcp",
    version=__version__,
    instructions=(
        "Unified Cloudflare control plane. Use cf_system_status first when "
        "configuration is unclear, cf_d1_* for SQL, cf_list_workers for "
        "deployments/routes, cf_kv_* and cf_r2_list_buckets for storage, "
        "cf_dns_* for records, cf_email_* for routing/addresses, "
        "cf_ai_* for Workers AI/Vectorize, cf_tunnels_* for Zero Trust, and "
        "cf_search_docs for guidance across all Cloudflare products."
    ),
)

_client: CloudflareClient | None = None


def get_client() -> CloudflareClient:
    global _client
    if _client is None:
        _client = CloudflareClient(load_settings())
    return _client


def set_client(client: CloudflareClient | None) -> None:
    """Test seam: inject a client backed by a mock transport."""
    global _client
    _client = client


def _probe(client: CloudflareClient, path: str) -> dict[str, Any]:
    try:
        client.get(path)
        return {"available": True}
    except (CloudflareAPIError, ConfigError) as exc:
        return {"available": False, "detail": str(exc)[:160]}


@mcp.tool(
    description=(
        "Verify Cloudflare API authentication, the active account id, masked "
        "token state, zone mapping and which product capabilities are reachable."
    )
)
@safe
def cf_system_status() -> ToolResult:
    settings = load_settings()
    client = get_client()
    status: dict[str, Any] = {
        "server": "cloudflare-mcp",
        "version": __version__,
        "python": platform.python_version(),
        "authenticated": settings.has_credentials,
        "token": mask_token(settings.api_token),
        "account_id": settings.account_id,
        "zones": sorted(settings.zone_map),
        "api_base": settings.base_url,
        "wrangler": {
            "binary": shutil.which("wrangler"),
            "local_config": str(find_wrangler_config() or ""),
            "fallback_enabled": settings.wrangler_fallback,
        },
        "docs_dirs": list(settings.docs_dirs),
        "capabilities": {},
    }
    if not settings.has_credentials:
        status["warning"] = (
            "CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID are not set - only "
            "cf_search_docs and local wrangler fallback will work."
        )
        return status
    a = f"/accounts/{settings.account_id}"
    status["token_verify"] = _probe(client, "/user/tokens/verify")
    status["account"] = _probe(client, a)
    status["capabilities"] = {
        "d1": _probe(client, f"{a}/d1/database"), "workers": _probe(client, f"{a}/workers/scripts"),
        "kv": _probe(client, f"{a}/storage/kv/namespaces"), "r2": _probe(client, f"{a}/r2/buckets"),
        "zones": _probe(client, "/zones"),
    }
    return status


@mcp.tool(
    description=(
        "Execute a SQL statement (SELECT/INSERT/UPDATE/DDL) against a named D1 "
        "database or database id. Returns columns, rows, rows_affected and "
        "duration. Supports positional parameter binding on the REST path."
    )
)
@safe
def cf_d1_query(database: str, sql: str, params: list[Any] | None = None) -> ToolResult:
    return d1.query(get_client(), database, sql, params)


@mcp.tool(
    description=(
        "List all D1 (serverless SQLite) databases in the account with ids, "
        "creation timestamps and local wrangler bindings."
    )
)
@safe
def cf_d1_list_databases() -> ToolResult:
    return d1.list_databases(get_client())


@mcp.tool(
    description=(
        "Inspect the table and view DDL of a D1 database (optionally a single "
        "table), so an agent can write valid SQL without a full schema dump."
    )
)
@safe
def cf_d1_schema(database: str, table: str | None = None) -> ToolResult:
    return d1.describe_schema(get_client(), database, table)


@mcp.tool(
    description=(
        "List deployed Cloudflare Workers with environments, routes, "
        "deployment history and modified dates."
    )
)
@safe
def cf_list_workers(include_routes: bool = True) -> ToolResult:
    return workers.list_workers(get_client(), include_routes=include_routes)


@mcp.tool(
    description=(
        "Read one key (value + metadata + expiration) from a Workers KV "
        "namespace by namespace id or namespace title."
    )
)
@safe
def cf_kv_get(key: str, namespace: str) -> ToolResult:
    return storage.kv_get(get_client(), key, namespace)


@mcp.tool(
    description=(
        "Write one key/value pair into a Workers KV namespace. Optional ttl in "
        "seconds (max 604800) and JSON metadata; set is_json when the value is "
        "a JSON document that should be validated before write."
    )
)
@safe
def cf_kv_set(
    key: str,
    value: str,
    namespace: str,
    ttl: int | None = None,
    metadata_json: str | None = None,
    is_json: bool = False,
) -> ToolResult:
    metadata: dict[str, Any] | None = None
    if metadata_json:
        parsed = json.loads(metadata_json)
        if not isinstance(parsed, dict):
            raise ConfigError("metadata_json must be a JSON object.")
        metadata = parsed
    return storage.kv_set(get_client(), key, value, namespace, ttl=ttl,
                          metadata=metadata, is_json=is_json)


@mcp.tool(
    description=(
        "List R2 buckets in the account with creation time, location and "
        "storage class. Pass cursor for the next page."
    )
)
@safe
def cf_r2_list_buckets(limit: int = 100, cursor: str | None = None) -> ToolResult:
    return storage.list_buckets(get_client(), cursor=cursor, limit=limit)


@mcp.tool(
    description=(
        "List DNS records of a zone (optional type/name filter) with content, "
        "TTL and proxy status. Zone defaults to the account's primary domain if omitted."
    )
)
@safe
def cf_dns_list(zone: str = "", type: str | None = None, name: str | None = None,
                limit: int = 100) -> ToolResult:
    return dns.list_records(get_client(), zone, type=type, name=name, limit=limit)


@mcp.tool(
    description=(
        "Create or update a DNS record in a zone (idempotent by type + name). "
        "Set type/name/content plus optional ttl (1=automatic), proxied flag "
        "and comment. Zone defaults to the account's primary domain if omitted."
    )
)
@safe
def cf_dns_upsert(name: str, type: str, content: str, zone: str = "",
                  ttl: int = 1, proxied: bool = False, comment: str | None = None) -> ToolResult:
    return dns.upsert_record(get_client(), zone, name=name, type=type, content=content,
                             ttl=ttl, proxied=proxied, comment=comment)


@mcp.tool(
    description=(
        "On-demand search over Cloudflare configuration/architecture guidance. "
        "Returns targeted snippets and code samples only - use this instead of "
        "loading manuals or guessing wrangler/wrangler-free API syntax."
    )
)
@safe
def cf_search_docs(query: str, limit: int = 5) -> ToolResult:
    return docs.search(query, limit=limit, extra_dirs=load_settings().docs_dirs)


register_email_tools(mcp, get_client)
register_ai_tools(mcp, get_client)
register_tunnel_tools(mcp, get_client)


def main() -> None:
    """Console entry point: serve MCP over stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":  # pragma: no cover
    main()