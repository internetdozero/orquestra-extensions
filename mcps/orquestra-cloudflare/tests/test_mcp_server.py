"""MCP surface: registry, typed output schemas and end-to-end tool calls.

Every tool is exercised through ``server.call_tool`` against the fake API, which
is what an MCP client does: arguments are validated by the SDK, the tool runs,
and the result comes back as a structured envelope.
"""

from __future__ import annotations

import asyncio
import json

import httpx

from cloudflare_mcp.server import mcp

from conftest import ACCOUNT, TOKEN, ZONE, ZONE_ID

TOOLS = [
    "cf_system_status",
    "cf_d1_query",
    "cf_d1_list_databases",
    "cf_d1_schema",
    "cf_list_workers",
    "cf_kv_get",
    "cf_kv_set",
    "cf_r2_list_buckets",
    "cf_dns_list",
    "cf_dns_upsert",
    "cf_search_docs",
    "cf_email_routing_rules",
    "cf_email_destinations",
    "cf_ai_models",
    "cf_vectorize_list_indexes",
    "cf_tunnels_list",
    "cf_access_apps_list",
]

KV_NS = "0123456789abcdef0123456789abcdef"
DB_ID = "aaaaaaaa-1111-2222-3333-444444444444"
SCRIPTS = f"/accounts/{ACCOUNT}/workers/scripts"
KV = f"/accounts/{ACCOUNT}/storage/kv/namespaces"
BUCKETS = f"/accounts/{ACCOUNT}/r2/buckets"
RECORDS = f"/zones/{ZONE_ID}/dns_records"

CALLS: list[tuple[str, dict]] = [
    ("cf_system_status", {}),
    ("cf_d1_list_databases", {}),
    ("cf_d1_query", {"database": "orquestra", "sql": "SELECT 1"}),
    ("cf_d1_schema", {"database": "orquestra", "table": "users"}),
    ("cf_list_workers", {}),
    ("cf_kv_get", {"key": "greeting", "namespace": KV_NS}),
    ("cf_kv_set", {"key": "greeting", "value": "hi", "namespace": KV_NS}),
    ("cf_r2_list_buckets", {}),
    ("cf_dns_list", {"zone": ZONE}),
    ("cf_dns_upsert", {"zone": ZONE, "name": "www", "type": "A", "content": "1.2.3.4"}),
    ("cf_search_docs", {"query": "d1 migrations"}),
    ("cf_email_routing_rules", {"zone": ZONE}),
    ("cf_email_destinations", {}),
    ("cf_ai_models", {"search": "llama"}),
    ("cf_vectorize_list_indexes", {}),
    ("cf_tunnels_list", {}),
    ("cf_access_apps_list", {}),
]


def _call(name: str, arguments: dict | None = None):
    return asyncio.run(mcp.call_tool(name, arguments or {}))


def _register_every_route(fake) -> None:
    """Routes covering every endpoint the eleven tools touch."""
    fake.add("GET", "/user/tokens/verify", {"status": "active"})
    fake.add("GET", f"/accounts/{ACCOUNT}", {"id": ACCOUNT, "name": "Orquestra"})
    fake.add("GET", f"/accounts/{ACCOUNT}/d1/database",
             [{"uuid": DB_ID, "name": "orquestra", "created_at": "2026-01-01T00:00:00Z"}])
    fake.add("POST", f"/accounts/{ACCOUNT}/d1/database/{DB_ID}/query",
             [{"results": [{"id": 1}], "success": True,
               "meta": {"duration": 1, "changes": 0, "rows_read": 1}}])
    fake.add("GET", SCRIPTS, [{"id": "api", "handlers": ["fetch"]}])
    fake.add("GET", f"/accounts/{ACCOUNT}/workers/routes", [])
    fake.add("GET", f"{SCRIPTS}/api/subdomain", {"environment": "production"})
    fake.add("GET", f"{SCRIPTS}/api/deployments", [])
    fake.add("GET", KV, [{"id": KV_NS, "title": "CACHE"}])
    fake.add_raw("GET", f"{KV}/{KV_NS}/values/greeting", httpx.Response(200, text="hello"))
    fake.add("GET", f"{KV}/{KV_NS}/metadata/greeting", {})
    fake.add("PUT", f"{KV}/{KV_NS}/values/greeting", None)
    fake.add("GET", BUCKETS, [{"name": "assets"}])
    fake.add("GET", "/zones", [{"id": ZONE_ID, "name": ZONE, "status": "active"}])
    fake.add("GET", RECORDS, [])
    fake.add("POST", RECORDS,
             {"id": "rec-1", "type": "A", "name": "www.example.com", "content": "1.2.3.4",
              "ttl": 1, "proxied": True})
    fake.add("GET", f"/zones/{ZONE_ID}/email/routing/rules", [{"id": "rule-1", "enabled": True}])
    fake.add("GET", f"/accounts/{ACCOUNT}/email/routing/addresses", [{"id": "addr-1", "email": "me@example.com"}])
    fake.add("GET", f"/accounts/{ACCOUNT}/ai/models/search", [{"name": "@cf/meta/llama-3"}])
    fake.add("GET", f"/accounts/{ACCOUNT}/vectorize/v2/indexes", [{"name": "idx-1"}])
    fake.add("GET", f"/accounts/{ACCOUNT}/cfd_tunnel", [{"id": "tun-1", "name": "prod-tunnel"}])
    fake.add("GET", f"/accounts/{ACCOUNT}/access/apps", [{"id": "app-1", "name": "wiki"}])


def test_every_tool_is_registered_in_order():
    tools = asyncio.run(mcp.list_tools())
    assert [tool.name for tool in tools] == TOOLS


def test_every_tool_publishes_a_typed_envelope_schema():
    for tool in asyncio.run(mcp.list_tools()):
        schema = tool.output_schema
        assert schema is not None, f"{tool.name} has no output schema"
        assert schema.get("type") == "object", f"{tool.name} must return an object envelope"
        properties = schema.get("properties", {})
        assert "ok" in properties, f"{tool.name} envelope lacks ok"
        assert "result" in properties, f"{tool.name} envelope lacks result"


def test_every_tool_executes_cleanly_against_the_fake_api(fake, fake_client, cf_env):
    _register_every_route(fake)

    for name, arguments in CALLS:
        result = _call(name, arguments)
        envelope = result.structured_content
        assert envelope is not None, f"{name} returned no structured content"
        assert envelope["ok"] is True, f"{name} -> {envelope.get('error')}"
        assert "result" in envelope


def test_d1_query_tool_returns_rows(fake, fake_client, cf_env):
    _register_every_route(fake)
    envelope = _call("cf_d1_query", {"database": "orquestra", "sql": "SELECT 1"}).structured_content
    assert envelope["result"]["rows"] == [{"id": 1}]
    assert envelope["result"]["columns"] == ["id"]


def test_kv_get_tool_returns_the_value(fake, fake_client, cf_env):
    _register_every_route(fake)
    envelope = _call("cf_kv_get", {"key": "greeting", "namespace": KV_NS}).structured_content
    assert envelope["result"]["value"] == "hello"
    assert envelope["result"]["found"] is True


def test_search_docs_tool_returns_snippets(fake, fake_client, cf_env):
    _register_every_route(fake)
    envelope = _call("cf_search_docs", {"query": "kv ttl"}).structured_content
    assert envelope["result"]["count"] >= 1
    assert envelope["result"]["matches"][0]["snippet"]


def test_tools_fail_with_a_configuration_envelope_without_credentials(
    fake, anonymous_client, clean_env
):
    envelope = _call("cf_d1_list_databases").structured_content
    assert envelope["ok"] is False
    assert envelope["error"]["type"] == "configuration"
    assert "CLOUDFLARE_API_TOKEN" in envelope["error"]["message"]


def test_api_errors_become_cloudflare_api_envelopes(fake, fake_client, cf_env):
    fake.add("GET", f"/accounts/{ACCOUNT}/d1/database", success=False, status=403,
             errors=[{"code": 7403, "message": "not authorized"}])

    error = _call("cf_d1_list_databases").structured_content["error"]
    assert error["type"] == "cloudflare_api"
    assert error["status"] == 403
    assert "not authorized" in error["message"]


def test_dns_upsert_rejects_a_bad_type_with_a_configuration_envelope(fake, fake_client, cf_env):
    envelope = _call(
        "cf_dns_upsert",
        {"zone": ZONE, "name": "x", "type": "BOGUS", "content": "1.2.3.4"},
    ).structured_content
    assert envelope["ok"] is False
    assert envelope["error"]["type"] == "configuration"


def test_system_status_probes_capabilities_and_masks_the_token(fake, fake_client, cf_env):
    _register_every_route(fake)
    status = _call("cf_system_status").structured_content["result"]

    assert status["authenticated"] is True
    assert status["account_id"] == ACCOUNT
    assert status["token"] == "****1234"
    assert TOKEN not in json.dumps(status)
    assert status["capabilities"]["d1"]["available"] is True
    assert status["capabilities"]["workers"]["available"] is True
    assert status["zones"] == [ZONE]
    assert status["wrangler"]["fallback_enabled"] is True


def test_system_status_without_credentials_reports_a_warning(
    fake, anonymous_client, clean_env
):
    status = _call("cf_system_status").structured_content["result"]

    assert status["authenticated"] is False
    assert status["token"] == "<not set>"
    assert status["account_id"] is None
    assert status["capabilities"] == {}
    assert "warning" in status
