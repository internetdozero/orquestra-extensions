"""Zones and DNS record CRUD against the fake API."""

from __future__ import annotations

import json

import pytest

from cloudflare_mcp import dns
from cloudflare_mcp.config import ConfigError

from conftest import ZONE, ZONE_ID

ZONES = "/zones"
RECORDS = f"/zones/{ZONE_ID}/dns_records"
HEX_ZONE = "ab" * 16


def test_list_zones_flattens_the_plan(fake, fake_client):
    fake.add(
        "GET",
        ZONES,
        [
            {
                "id": ZONE_ID,
                "name": ZONE,
                "status": "active",
                "plan": {"name": "Free"},
                "name_servers": ["ns1.example.com"],
            }
        ],
    )

    assert dns.list_zones(fake_client) == [
        {
            "id": ZONE_ID,
            "name": ZONE,
            "status": "active",
            "plan": "Free",
            "name_servers": ["ns1.example.com"],
        }
    ]


def test_resolve_zone_prefers_the_map_then_the_api(fake, fake_client):
    assert dns.resolve_zone(fake_client, ZONE) == ZONE_ID
    assert dns.resolve_zone(fake_client, f"{ZONE}.") == ZONE_ID
    assert dns.resolve_zone(fake_client, f"sub.{ZONE}") == ZONE_ID
    assert dns.resolve_zone(fake_client, HEX_ZONE) == HEX_ZONE

    fake.add("GET", ZONES, [{"id": "zone-2", "name": "other.com"}])
    assert dns.resolve_zone(fake_client, "other.com") == "zone-2"


def test_resolve_zone_reports_unknown_zones(fake, fake_client):
    fake.add("GET", ZONES, [])
    with pytest.raises(ConfigError) as error:
        dns.resolve_zone(fake_client, "missing.com")
    assert "CLOUDFLARE_ZONE_MAP" in str(error.value)

    with pytest.raises(ConfigError):
        dns.resolve_zone(fake_client, "   ")


def test_resolve_zone_needs_credentials_for_api_lookup(anonymous_client):
    with pytest.raises(ConfigError):
        dns.resolve_zone(anonymous_client, "unmapped.com")


def test_list_records_filters_and_redacts(fake, fake_client):
    fake.add(
        "GET",
        RECORDS,
        [
            {
                "id": "rec-1",
                "type": "A",
                "name": "www.example.com",
                "content": "1.2.3.4",
                "ttl": 1,
                "proxied": True,
                "proxiable": True,
                "comment": None,
                "private_field": "drop me",
            }
        ],
    )

    payload = dns.list_records(fake_client, ZONE, type="a", name="WWW.example.com.")
    assert payload["zone"] == ZONE
    assert payload["zone_id"] == ZONE_ID
    assert payload["count"] == 1
    assert payload["records"][0] == {
        "id": "rec-1",
        "type": "A",
        "name": "www.example.com",
        "content": "1.2.3.4",
        "ttl": 1,
        "proxied": True,
        "proxiable": True,
        "comment": None,
    }

    params = fake.requests_for("GET", RECORDS)[0].url.params
    assert params["type"] == "A"
    assert params["name"] == "www.example.com"


def test_upsert_creates_when_no_record_exists(fake, fake_client):
    fake.add("GET", RECORDS, [])
    fake.add(
        "POST",
        RECORDS,
        {
            "id": "rec-9",
            "type": "A",
            "name": "www.example.com",
            "content": "1.2.3.4",
            "ttl": 300,
            "proxied": True,
        },
    )

    record = dns.upsert_record(
        fake_client, ZONE, name="www.example.com", type="a", content="1.2.3.4",
        ttl=300, proxied=True, comment="hi",
    )
    assert record["action"] == "created"
    assert record["zone_id"] == ZONE_ID
    assert record["type"] == "A"

    body = json.loads(fake.requests_for("POST", RECORDS)[0].content)
    assert body == {
        "type": "A",
        "name": "www.example.com",
        "content": "1.2.3.4",
        "ttl": 300,
        "proxied": True,
        "comment": "hi",
    }


def test_upsert_normalizes_relative_subdomain_name(fake, fake_client):
    fake.add("GET", RECORDS, [])
    fake.add(
        "POST",
        RECORDS,
        {"id": "rec-rel", "type": "CNAME", "name": f"app.{ZONE}", "content": "target.pages.dev", "ttl": 1},
    )
    record = dns.upsert_record(fake_client, ZONE, name="app", type="CNAME", content="target.pages.dev")
    assert record["action"] == "created"
    body = json.loads(fake.requests_for("POST", RECORDS)[0].content)
    assert body["name"] == f"app.{ZONE}"


def test_upsert_updates_an_existing_record_and_forces_no_proxy_for_txt(fake, fake_client):
    fake.add("GET", RECORDS, [{"id": "rec-1", "name": "example.com", "type": "TXT"}])
    fake.add(
        "PATCH",
        f"{RECORDS}/rec-1",
        {"id": "rec-1", "type": "TXT", "name": "example.com", "content": "v=1", "ttl": 1},
    )

    record = dns.upsert_record(fake_client, ZONE, name="@", type="TXT", content="v=1",
                               proxied=True)
    assert record["action"] == "updated"

    body = json.loads(fake.requests_for("PATCH", f"{RECORDS}/rec-1")[0].content)
    assert body["name"] == ZONE
    assert body["proxied"] is False


def test_upsert_validates_type_ttl_and_content(fake_client):
    with pytest.raises(ConfigError):
        dns.upsert_record(fake_client, ZONE, name="x", type="BOGUS", content="1.1.1.1")
    with pytest.raises(ConfigError):
        dns.upsert_record(fake_client, ZONE, name="x", type="A", content="1.1.1.1", ttl=5)
    with pytest.raises(ConfigError):
        dns.upsert_record(fake_client, ZONE, name="x", type="A", content="   ")


def test_delete_record_requires_an_existing_record(fake, fake_client):
    fake.add("GET", RECORDS, [])
    with pytest.raises(ConfigError):
        dns.delete_record(fake_client, ZONE, name="www.example.com", type="A")


def test_delete_record_removes_it(fake, fake_client):
    fake.add("GET", RECORDS, [{"id": "rec-1", "name": "www.example.com", "type": "A"}])
    fake.add("DELETE", f"{RECORDS}/rec-1", {"id": "rec-1"})

    payload = dns.delete_record(fake_client, ZONE, name="www.example.com", type="A")
    assert payload == {
        "action": "deleted",
        "id": "rec-1",
        "name": "www.example.com",
        "type": "A",
    }


def test_find_record_returns_none_when_absent(fake, fake_client):
    fake.add("GET", RECORDS, [])
    assert dns.find_record(fake_client, ZONE_ID, "www.example.com", "A") is None
