"""Worker inventory: deployments, routes and live tail via local wrangler."""

from __future__ import annotations

import json
from typing import Any

from .client import CloudflareAPIError, CloudflareClient
from .wrangler import WranglerError, find_wrangler_config, run_wrangler


def list_workers(client: CloudflareClient, *, include_routes: bool = True) -> list[dict[str, Any]]:
    """List deployed Workers with environments, routes and modified dates."""
    scripts = client.get(client.account_path("/workers/scripts")) or []
    routes_by_script: dict[str, list[dict[str, Any]]] = {}
    if include_routes:
        routes_by_script = _routes_by_script(client)
    workers: list[dict[str, Any]] = []
    for script in scripts:
        script_id = str(script.get("id") or script.get("name") or "")
        workers.append(
            {
                "id": script_id,
                "name": script_id,
                "created_on": script.get("created_on"),
                "modified_on": script.get("modified_on"),
                "etag": script.get("etag"),
                "handlers": script.get("handlers") or [],
                "environments": deploy_environments(client, script_id),
                "routes": routes_by_script.get(script_id, []),
                "deployments": deployments(client, script_id),
            }
        )
    return workers


def _routes_by_script(client: CloudflareClient) -> dict[str, list[dict[str, Any]]]:
    """Map worker id -> zone routes (account-wide route list is pre-v4 only)."""
    mapping: dict[str, list[dict[str, Any]]] = {}
    try:
        routes = client.get(client.account_path("/workers/routes")) or []
    except CloudflareAPIError:
        return mapping
    for route in routes:
        script = str(route.get("script") or "")
        mapping.setdefault(script, []).append(
            {
                "pattern": route.get("pattern"),
                "zone_id": route.get("zone_id"),
                "zone_name": route.get("zone_name"),
            }
        )
    return mapping


def deploy_environments(client: CloudflareClient, worker_id: str) -> list[str]:
    """Return the environments a worker is deployed to (production/preview)."""
    try:
        subdomain = client.get(client.account_path(f"/workers/scripts/{worker_id}/subdomain"))
    except CloudflareAPIError:
        return []
    if not isinstance(subdomain, dict):
        return []
    return [str(subdomain.get("environment") or "production")]


def deployments(client: CloudflareClient, worker_id: str) -> list[dict[str, Any]]:
    """Return deployment records (versioned rollout history) for a worker."""
    try:
        result = client.get(client.account_path(f"/workers/scripts/{worker_id}/deployments"))
    except CloudflareAPIError:
        return []
    if not isinstance(result, list):
        result = [result] if isinstance(result, dict) else []
    records = []
    for item in result:
        records.append(
            {
                "deployment_id": item.get("id"),
                "created_on": item.get("created_on"),
                "versions": [
                    str(v.get("version_id") or v.get("id") or "")
                    for v in (item.get("versions") or [])
                    if isinstance(v, dict)
                ],
            }
        )
    return records


def worker_detail(client: CloudflareClient, worker_id: str) -> dict[str, Any]:
    """Metadata for a single worker (settings, compatibility, placements)."""
    result = client.get(client.account_path(f"/workers/scripts/{worker_id}")) or {}
    if not isinstance(result, dict):
        raise CloudflareAPIError(f"worker '{worker_id}' not found")
    return {
        "id": worker_id,
        "modified_on": result.get("modified_on"),
        "usage_model": result.get("usage_model"),
        "compatibility_date": (result.get("compatibility_date") or (result.get("metadata") or {}).get("compatibility_date")),
        "bindings": [
            {"name": b.get("name"), "type": b.get("type")}
            for b in (result.get("bindings") or [])
            if isinstance(b, dict)
        ],
    }


def tail_worker(worker: str, *, seconds: int = 10, filter_expr: str | None = None,
                cwd=None) -> dict[str, Any]:
    """Capture a bounded live log tail for a Worker through ``wrangler tail``.

    Uses the local wrangler CLI (no REST equivalent); returns parsed JSON log
    lines when available plus the raw text.
    """
    if find_wrangler_config(cwd) is None and not worker:
        raise WranglerError("wrangler tail requires a worker name and a local wrangler config.")
    args = ["tail", worker, "--format", "json", "--duration", str(max(1, min(seconds, 60)))]
    if filter_expr:
        args += ["--filter", filter_expr]
    output = run_wrangler(args, cwd=cwd, timeout=max(10, seconds * 3 + 10))
    lines = [line for line in output.splitlines() if line.strip()]
    events: list[Any] = []
    for line in lines:
        try:
            events.append(json.loads(line))
        except ValueError:
            events.append(line)
    return {"worker": worker, "seconds": seconds, "events": events, "raw": output[-8000:]}


def local_worker_names() -> list[str]:
    """Worker names declared in the local wrangler config, if present."""
    path = find_wrangler_config()
    if not path:
        return []
    from .wrangler import read_wrangler_config

    try:
        config = read_wrangler_config(path)
    except (OSError, ValueError):
        return []
    name = config.get("name")
    return [str(name)] if name else []