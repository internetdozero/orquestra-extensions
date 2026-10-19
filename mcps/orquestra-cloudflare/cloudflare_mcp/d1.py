"""D1 serverless SQL: database listing, query execution and schema inspection."""

from __future__ import annotations

import json
import re
import time
from typing import Any

from .client import CloudflareAPIError, CloudflareClient
from .config import ConfigError
from .wrangler import find_wrangler_config, read_wrangler_config, run_wrangler

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)
SQLITE_MASTER_SQL = (
    "SELECT name, type, sql FROM sqlite_master "
    "WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' {where} ORDER BY name"
)


def looks_like_uuid(value: str) -> bool:
    return bool(UUID_RE.match(value.strip()))


def local_d1_bindings() -> dict[str, str]:
    """Return ``binding name -> database name/id`` from a local wrangler config."""
    path = find_wrangler_config()
    if not path:
        return {}
    try:
        config = read_wrangler_config(path)
    except (OSError, ValueError):
        return {}
    bindings: dict[str, str] = {}
    for entry in config.get("d1_databases") or []:
        if isinstance(entry, dict) and entry.get("database_name"):
            bindings[str(entry.get("binding", entry["database_name"]))] = str(
                entry.get("database_id") or entry["database_name"]
            )
    return bindings


def list_databases(client: CloudflareClient) -> list[dict[str, Any]]:
    """List all D1 databases in the account with ids and creation timestamps."""
    result = client.get(client.account_path("/d1/database")) or []
    databases = []
    for item in result:
        databases.append(
            {
                "uuid": item.get("uuid"),
                "name": item.get("name"),
                "created_at": item.get("created_at"),
                "version": item.get("version"),
                "file_size_bytes": (item.get("file_size") or 0),
            }
        )
    bindings = local_d1_bindings()
    if bindings:
        known = {db["name"] for db in databases if db.get("name")}
        for name, identifier in bindings.items():
            if name not in known:
                databases.append(
                    {"uuid": None, "name": name, "created_at": None,
                     "version": None, "file_size_bytes": 0, "local_binding": identifier}
                )
    return databases


def resolve_database_id(client: CloudflareClient, reference: str) -> str:
    """Resolve a database name (or binding) to its UUID.

    Falls back to local wrangler bindings when the account has no matching
    database, then to executing through the local wrangler CLI.
    """
    ref = reference.strip()
    if looks_like_uuid(ref):
        return ref
    databases = client.settings.has_credentials and list_databases(client) or []
    for item in databases:
        if item.get("name") == ref and item.get("uuid"):
            return str(item["uuid"])
    bindings = local_d1_bindings()
    if ref in bindings and looks_like_uuid(bindings[ref]):
        return bindings[ref]
    if ref in bindings:
        # Binding without a usable database id: run through wrangler instead.
        return ref
    raise ConfigError(
        f"D1 database '{ref}' not found in this account and no local wrangler "
        "binding matches. Use cf_d1_list_databases to see available names."
    )


def query(client: CloudflareClient, database: str, sql: str,
          params: list[Any] | None = None, *, timeout_ms: int = 30_000) -> dict[str, Any]:
    """Execute a SQL statement and return rows, changes and duration."""
    if not sql or not sql.strip():
        raise ConfigError("SQL must not be empty.")
    started = time.perf_counter()
    if client.settings.has_credentials:
        db_id = resolve_database_id(client, database)
        body: dict[str, Any] = {"sql": sql, "params": params or [], "timeout": timeout_ms}
        try:
            result = _api_query(client, db_id, body)
        except CloudflareAPIError:
            if not _binds_locally(client, database) or not client.settings.wrangler_fallback:
                raise
            result = _wrangler_query(database, sql, params)
    else:
        if not client.settings.wrangler_fallback:
            client.settings.require_credentials()
        result = _wrangler_query(database, sql, params)
    elapsed_ms = (time.perf_counter() - started) * 1000
    result["duration_ms_api"] = round(elapsed_ms, 2)
    return result


def _api_query(client: CloudflareClient, db_id: str, body: dict[str, Any]) -> dict[str, Any]:
    batch = client.post(client.account_path(f"/d1/database/{db_id}/query"), body)
    return _batch_to_payload(batch)


def _batch_to_payload(batch: Any) -> dict[str, Any]:
    """Normalize one or many statement results into a single payload."""
    if not isinstance(batch, list):
        batch = [batch]
    if not batch:
        return {"columns": [], "rows": [], "rows_affected": 0, "rows_read": 0,
                "duration_ms": 0, "success": True}
    first = batch[0]
    meta = first.get("meta") or {}
    rows = first.get("results") or []
    columns = list(rows[0].keys()) if rows else []
    return {
        "columns": columns,
        "rows": rows,
        "statements": len(batch),
        "rows_affected": int(first.get("changes") or meta.get("changes") or 0),
        "rows_read": int(meta.get("rows_read") or 0),
        "duration_ms": float(meta.get("duration") or 0),
        "last_row_id": meta.get("last_row_id"),
        "success": bool(first.get("success", True)),
    }


def _binds_locally(client: CloudflareClient, reference: str) -> bool:
    return reference in local_d1_bindings() or bool(find_wrangler_config())


def _wrangler_query(reference: str, sql: str, params: list[Any] | None) -> dict[str, Any]:
    """Fallback: execute through the local wrangler CLI (``--json`` output)."""
    if params:
        raise ConfigError(
            "Positional parameters are only available through the REST API path; "
            "the local wrangler fallback cannot bind them. Inline the values or "
            "configure CLOUDFLARE_API_TOKEN."
        )
    started = time.perf_counter()
    output = run_wrangler(
        ["d1", "execute", reference, "--json", "--command", sql], timeout=90.0
    )
    duration = (time.perf_counter() - started) * 1000
    parsed = json.loads(output or "[]")
    if isinstance(parsed, dict):
        parsed = [parsed]
    payload = _batch_to_payload(parsed[0] if parsed else {})
    payload["duration_ms"] = round(payload.get("duration_ms") or duration, 2)
    payload["source"] = "wrangler"
    return payload


def describe_schema(client: CloudflareClient, database: str,
                    table: str | None = None) -> dict[str, Any]:
    """Inspect table/view DDL for a database (optionally a single table)."""
    if table:
        sql = SQLITE_MASTER_SQL.format(where="AND name = ?")
        result = query(client, database, sql, [table])
    else:
        sql = SQLITE_MASTER_SQL.format(where="")
        result = query(client, database, sql)
    objects = [
        {"name": row.get("name"), "type": row.get("type"), "sql": row.get("sql")}
        for row in result.get("rows", [])
    ]
    return {"database": database, "table": table, "objects": objects}