"""Tests for extended modular tools: email, ai, tunnels, and docs discovery."""

from __future__ import annotations

import httpx

from cloudflare_mcp.ai import list_ai_models, list_vectorize_indexes
from cloudflare_mcp.client import CloudflareClient
from cloudflare_mcp.config import load_settings
from cloudflare_mcp.email import list_destination_addresses, list_routing_rules
from cloudflare_mcp.tunnels import list_access_apps, list_tunnels

from conftest import ACCOUNT, ZONE, ZONE_ID, make_settings


def test_email_functions(fake):
    fake.add("GET", f"/zones/{ZONE_ID}/email/routing/rules", [{"id": "r1", "enabled": True}])
    fake.add("GET", f"/accounts/{ACCOUNT}/email/routing/addresses", [{"id": "a1", "email": "dev@test.com"}])

    client = CloudflareClient(make_settings(), transport=httpx.MockTransport(fake.handler))
    rules = list_routing_rules(client, ZONE)
    assert rules["count"] == 1
    assert rules["rules"][0]["id"] == "r1"

    dests = list_destination_addresses(client)
    assert dests["count"] == 1
    assert dests["addresses"][0]["email"] == "dev@test.com"


def test_ai_functions(fake):
    fake.add("GET", f"/accounts/{ACCOUNT}/ai/models/search", [{"name": "@cf/meta/llama-3"}])
    fake.add("GET", f"/accounts/{ACCOUNT}/vectorize/v2/indexes", [{"name": "idx-main"}])

    client = CloudflareClient(make_settings(), transport=httpx.MockTransport(fake.handler))
    models = list_ai_models(client, search="llama")
    assert models["count"] == 1
    assert models["models"][0]["name"] == "@cf/meta/llama-3"

    indexes = list_vectorize_indexes(client)
    assert indexes["count"] == 1
    assert indexes["indexes"][0]["name"] == "idx-main"


def test_tunnel_functions(fake):
    fake.add("GET", f"/accounts/{ACCOUNT}/cfd_tunnel", [{"id": "t1", "name": "office"}])
    fake.add("GET", f"/accounts/{ACCOUNT}/access/apps", [{"id": "ap1", "name": "dashboard"}])

    client = CloudflareClient(make_settings(), transport=httpx.MockTransport(fake.handler))
    tunnels = list_tunnels(client)
    assert tunnels["count"] == 1
    assert tunnels["tunnels"][0]["name"] == "office"

    apps = list_access_apps(client)
    assert apps["count"] == 1
    assert apps["apps"][0]["name"] == "dashboard"


def test_docs_discovery_finds_local_skills_library():
    settings = load_settings()
    # When running on host without overrides, docs_dirs should discover local skill folders
    assert any("cloudflare" in d for d in settings.docs_dirs)
