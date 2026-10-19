"""Workers KV and R2 storage operations."""

from __future__ import annotations

import base64
import json
from typing import Any

from .client import CloudflareClient, CloudflareAPIError
from .config import ConfigError


# ---------------------------------------------------------------------- KV
def list_namespaces(client: CloudflareClient) -> list[dict[str, Any]]:
    """List KV namespaces with ids, titles and creation timestamps."""
    result = client.get(client.account_path("/storage/kv/namespaces")) or []
    return [
        {
            "id": item.get("id"),
            "title": item.get("title"),
            "created_on": item.get("created_on"),
        }
        for item in result
    ]


def resolve_namespace(client: CloudflareClient, reference: str) -> str:
    """Accept a namespace UUID as-is; resolve a binding/title name via the API."""
    ref = reference.strip()
    if not ref:
        raise ConfigError("A KV namespace id or title/env binding name is required.")
    if len(ref) == 32 and all(c in "0123456789abcdef" for c in ref.lower()):
        return ref
    for ns in list_namespaces(client):
        title = str(ns.get("title") or "")
        if ref in {title, title.replace("-", "_").upper(), title.upper(), title.lower()}:
            return str(ns["id"])
    raise ConfigError(
        f"KV namespace '{reference}' not found. Use cf docs or the dashboard to "
        "pass the 32-character namespace id, or an exact namespace title."
    )


def kv_get(client: CloudflareClient, key: str, namespace: str) -> dict[str, Any]:
    """Read one key (with metadata and expiration) from a KV namespace."""
    ns_id = resolve_namespace(client, namespace)
    path = client.account_path(f"/storage/kv/namespaces/{ns_id}/values/{_escape(key)}")
    metadata_path = client.account_path(
        f"/storage/kv/namespaces/{ns_id}/metadata/{_escape(key)}"
    )
    response = client.get_raw(path)
    if response.status_code == 404:
        return {"key": key, "namespace": ns_id, "value": None, "encoding": None,
                "metadata": None, "found": False}
    client._validate(response)
    value: Any
    if "json" in response.headers.get("content-type", ""):
        try:
            value = response.json()
        except ValueError:
            value = response.text
    else:
        value = response.text
    decoded, encoding = _decode_value(value)
    metadata: Any = None
    try:
        metadata = client.get(metadata_path)
    except (CloudflareAPIError, ConfigError):
        metadata = None
    return {
        "key": key,
        "namespace": ns_id,
        "value": decoded,
        "encoding": encoding,
        "metadata": metadata,
        "found": True,
    }


def _decode_value(value: Any) -> tuple[Any, str]:
    if isinstance(value, (dict, list)):
        return value, "json"
    if isinstance(value, str):
        return value, "utf-8"
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8"), "utf-8"
        except UnicodeDecodeError:
            return base64.b64encode(value).decode("ascii"), "base64"
    return value, "raw"


def kv_set(client: CloudflareClient, key: str, value: str, namespace: str,
           *, ttl: int | None = None, metadata: dict[str, Any] | None = None,
           is_json: bool = False) -> dict[str, Any]:
    """Write one key to a KV namespace (optional TTL and metadata)."""
    ns_id = resolve_namespace(client, namespace)
    if ttl is not None and (ttl <= 0 or ttl > 604800):
        raise ConfigError("ttl must be in 1..604800 seconds (7 days).")
    body = value
    content_type = "text/plain; charset=utf-8"
    if is_json:
        # Validate before sending so bad payloads fail fast.
        json.loads(value)
        content_type = "application/json"
    path = client.account_path(f"/storage/kv/namespaces/{ns_id}/values/{_escape(key)}")
    params: dict[str, Any] = {}
    if ttl is not None:
        params["expiration_ttl"] = ttl
    if metadata is not None:
        params["metadata"] = json.dumps(metadata)
    client.request("PUT", path, params=params or None, content=body,
                   content_type=content_type)
    return {
        "ok": True,
        "key": key,
        "namespace": ns_id,
        "bytes": len(str(value).encode("utf-8")),
        "ttl": ttl,
        "metadata": metadata is not None,
        "content_type": content_type,
        "encoding": "utf-8",
    }


def _escape(key: str) -> str:
    from urllib.parse import quote

    return quote(key, safe="")


# ---------------------------------------------------------------------- R2
def list_buckets(client: CloudflareClient, *, cursor: str | None = None,
                 limit: int = 100) -> dict[str, Any]:
    """List R2 buckets in the account (cursor pagination supported)."""
    params: dict[str, Any] = {"per_page": max(1, min(limit, 1000))}
    if cursor:
        params["cursor"] = cursor
    payload = client.get_full(client.account_path("/r2/buckets"), params)
    buckets = payload.get("result") or []
    truncated = bool((payload.get("result_info") or {}).get("truncated"))
    return {
        "buckets": [
            {
                "name": b.get("name"),
                "created_on": b.get("created_on"),
                "location": b.get("location"),
                "storage_class": b.get("storage_class"),
            }
            for b in buckets
        ],
        "count": len(buckets),
        "truncated": truncated,
        "cursor": (payload.get("result_info") or {}).get("cursor"),
    }


def list_objects(client: CloudflareClient, bucket: str, *, prefix: str = "",
                 limit: int = 50) -> dict[str, Any]:
    """List object keys inside an R2 bucket (R2 data plane REST endpoint)."""
    payload = client.post(
        client.account_path(f"/r2/buckets/{bucket}/objects/list"),
        {"prefix": prefix, "limit": max(1, min(limit, 1000))},
    )
    objects = (
        payload.get("objects") if isinstance(payload, dict) else payload
    ) or []
    return {
        "bucket": bucket,
        "objects": [
            {
                "key": o.get("key"),
                "size": o.get("size"),
                "uploaded": o.get("uploaded"),
                "etag": o.get("etag"),
            }
            for o in objects
        ],
        "truncated": bool(payload.get("truncated")) if isinstance(payload, dict) else False,
        "cursor": payload.get("cursor") if isinstance(payload, dict) else None,
    }