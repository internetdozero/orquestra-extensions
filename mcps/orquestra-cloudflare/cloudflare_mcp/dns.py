"""DNS zone listing and record CRUD (create / update) operations."""

from __future__ import annotations

from typing import Any

from .client import CloudflareClient, CloudflareAPIError
from .config import ConfigError

ALLOWED_TYPES = {
    "A", "AAAA", "CNAME", "TXT", "MX", "NS", "SRV", "CAA", "PTR", "HTTPS", "SVCB",
    "DS", "DNSKEY", "NAPTR", "SSHFP", "TLSA", "URI",
}


def list_zones(client: CloudflareClient) -> list[dict[str, Any]]:
    """List zones on the account with activation status."""
    raw = client.paginate("/zones")
    zones = []
    for zone in raw:
        zones.append(
            {
                "id": zone.get("id"),
                "name": zone.get("name"),
                "status": zone.get("status"),
                "plan": (zone.get("plan") or {}).get("name"),
                "name_servers": zone.get("name_servers") or [],
            }
        )
    return zones


def resolve_zone(client: CloudflareClient, zone: str, *, allow_default: bool = False) -> str:
    """Resolve a zone name to its zone id.

    Uses ``CLOUDFLARE_ZONE_MAP`` first (no API round trip), then a name lookup.
    """
    zone = zone.strip().rstrip(".").lower()
    if not zone:
        if allow_default:
            if len(client.settings.zone_map) == 1:
                return next(iter(client.settings.zone_map.values()))
            if client.settings.has_credentials:
                try:
                    account_zones = client.get("/zones", {"per_page": 2})
                    if account_zones and len(account_zones) == 1:
                        first = account_zones[0]
                        return str(first["id"] if isinstance(first, dict) else first)
                except Exception:
                    pass
        raise ConfigError("A zone (domain) name is required.")
    mapped = client.settings.zone_map.get(zone)
    if mapped:
        return mapped
    # Support agents passing subdomains directly (e.g. sub.example.com)
    for candidate_zone, zone_id in client.settings.zone_map.items():
        if zone.endswith(f".{candidate_zone}"):
            return zone_id
    if len(zone) == 32 and all(c in "0123456789abcdef" for c in zone.lower()):
        return zone
    if not client.settings.has_credentials:
        client.settings.zone_id(zone)  # raises ConfigError with guidance
        raise ConfigError(f"Zone '{zone}' is only resolvable with CLOUDFLARE_API_TOKEN.")
    try:
        result = client.get("/zones", {"name": zone, "per_page": 5})
        if not result and "." in zone:
            parts = zone.split(".")
            for i in range(1, len(parts) - 1):
                parent = ".".join(parts[i:])
                parent_res = client.get("/zones", {"name": parent, "per_page": 5})
                if parent_res:
                    result = parent_res
                    break
    except CloudflareAPIError:
        raise ConfigError(
            f"Zone '{zone}' could not be resolved. Add it to CLOUDFLARE_ZONE_MAP "
            "or verify the account has the zone."
        )
    if not result:
        client.settings.zone_id(zone)  # raises with guidance
    first = result[0]
    return str(first["id"] if isinstance(first, dict) else first)


def list_records(client: CloudflareClient, zone: str = "", *, type: str | None = None,
                 name: str | None = None, limit: int = 200) -> dict[str, Any]:
    """List DNS records for a zone with optional type/name filtering."""
    if not zone and name and "." in name:
        zone = name
    zone_id = resolve_zone(client, zone, allow_default=True)
    params: dict[str, Any] = {}
    if type:
        params["type"] = type.upper()
    if name:
        params["name"] = name.rstrip(".").lower()
    records = client.paginate(
        f"/zones/{zone_id}/dns_records", params or None, max_pages=5, per_page=min(limit, 100)
    )
    return {
        "zone": zone,
        "zone_id": zone_id,
        "count": len(records),
        "records": [_public(r) for r in records],
    }


def _public(record: Any) -> dict[str, Any]:
    return {
        "id": record.get("id"),
        "type": record.get("type"),
        "name": record.get("name"),
        "content": record.get("content"),
        "ttl": record.get("ttl"),
        "proxied": record.get("proxied"),
        "proxiable": record.get("proxiable"),
        "comment": record.get("comment"),
    }


def find_record(client: CloudflareClient, zone_id: str, name: str,
                record_type: str) -> dict[str, Any] | None:
    """Find the single record matching type + name inside a zone."""
    params = {"type": record_type.upper(), "name": name.rstrip(".").lower()}
    result = client.get(f"/zones/{zone_id}/dns_records", params)
    if not result:
        return None
    return result[0]


def upsert_record(client: CloudflareClient, zone: str = "", *, name: str,
                  type: str, content: str, ttl: int = 1,
                  proxied: bool = False, comment: str | None = None,
                  priority: int | None = None) -> dict[str, Any]:
    """Create or update a DNS record (safe, idempotent by type + name).

    ``ttl=1`` means "automatic" in Cloudflare terms. ``proxied`` controls the
    orange-cloud CDN proxy status where the record type supports it.
    """
    record_type = type.strip().upper()
    if record_type not in ALLOWED_TYPES:
        raise ConfigError(
            f"Unsupported DNS record type '{type}'. Allowed: {', '.join(sorted(ALLOWED_TYPES))}"
        )
    if not content or not content.strip():
        raise ConfigError("DNS record content/value must not be empty.")
    if ttl != 1 and (ttl < 60 or ttl > 86400):
        raise ConfigError("ttl must be 1 (automatic) or between 60 and 86400 seconds.")

    if not zone and name and "." in name:
        zone = name
    zone_id = resolve_zone(client, zone, allow_default=True)
    zone_clean = zone.strip().rstrip(".").lower()
    canonical_zone = zone_clean
    for candidate_zone, zid in client.settings.zone_map.items():
        if zid == zone_id:
            canonical_zone = candidate_zone
            break

    fqdn = name.rstrip(".").lower()
    if fqdn in {"@", zone_clean, canonical_zone}:
        fqdn = canonical_zone
    elif not fqdn.endswith(f".{canonical_zone}"):
        fqdn = f"{fqdn}.{canonical_zone}"

    body: dict[str, Any] = {
        "type": record_type,
        "name": fqdn,
        "content": content.strip(),
        "ttl": ttl,
    }
    if record_type in {"A", "AAAA", "CNAME"}:
        body["proxied"] = bool(proxied)
    else:
        body["proxied"] = False
    if comment:
        body["comment"] = comment
    if priority is not None:
        body["priority"] = int(priority)

    existing = find_record(client, zone_id, fqdn, record_type)
    if existing:
        result = client.patch(f"/zones/{zone_id}/dns_records/{existing['id']}", body)
        action = "updated"
    else:
        result = client.post(f"/zones/{zone_id}/dns_records", body)
        action = "created"

    record = _public(result if isinstance(result, dict) else {"id": result, **body})
    record["action"] = action
    record["zone_id"] = zone_id
    return record


def delete_record(client: CloudflareClient, zone: str, *, name: str, type: str) -> dict[str, Any]:
    """Delete the record matching type + name (explicit destructive helper)."""
    zone_id = resolve_zone(client, zone)
    existing = find_record(client, zone_id, name, type.upper())
    if not existing:
        raise ConfigError(f"No {type.upper()} record named '{name}' in zone '{zone}'.")
    client.delete(f"/zones/{zone_id}/dns_records/{existing['id']}")
    return {"action": "deleted", "id": existing["id"], "name": existing.get("name"),
            "type": existing.get("type")}