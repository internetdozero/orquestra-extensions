"""D1: database inventory, SQL execution, schema inspection, wrangler fallback."""

from __future__ import annotations

import json

import pytest

from cloudflare_mcp import d1
from cloudflare_mcp.config import ConfigError

from conftest import ACCOUNT

DB_ID = "aaaaaaaa-1111-2222-3333-444444444444"
LIST_PATH = f"/accounts/{ACCOUNT}/d1/database"
QUERY_PATH = f"/accounts/{ACCOUNT}/d1/database/{DB_ID}/query"


def _query_body(fake) -> dict:
    request = fake.requests_for("POST", QUERY_PATH)[0]
    return json.loads(request.content)


def test_looks_like_uuid():
    assert d1.looks_like_uuid(DB_ID)
    assert not d1.looks_like_uuid("orquestra")
    assert not d1.looks_like_uuid("aaaa-1111")


def test_list_databases_maps_fields(fake, fake_client, monkeypatch):
    monkeypatch.setattr(d1, "local_d1_bindings", lambda: {})
    fake.add(
        "GET",
        LIST_PATH,
        [
            {
                "uuid": DB_ID,
                "name": "orquestra",
                "created_at": "2026-01-01T00:00:00Z",
                "version": "v1",
                "file_size": 2048,
            },
            {"uuid": None, "name": "bare"},
        ],
    )

    databases = d1.list_databases(fake_client)
    assert databases[0] == {
        "uuid": DB_ID,
        "name": "orquestra",
        "created_at": "2026-01-01T00:00:00Z",
        "version": "v1",
        "file_size_bytes": 2048,
    }
    assert databases[1]["file_size_bytes"] == 0
    assert databases[1]["created_at"] is None


def test_list_databases_appends_local_wrangler_bindings(fake, fake_client, monkeypatch):
    fake.add("GET", LIST_PATH, [{"uuid": DB_ID, "name": "orquestra"}])
    monkeypatch.setattr(
        d1,
        "local_d1_bindings",
        lambda: {"LOCAL_DB": "bbbbbbbb-1111-2222-3333-444444444444"},
    )

    databases = d1.list_databases(fake_client)
    assert [db["name"] for db in databases] == ["orquestra", "LOCAL_DB"]
    assert databases[-1]["local_binding"] == "bbbbbbbb-1111-2222-3333-444444444444"


def test_resolve_database_id_accepts_uuid_name_and_local_binding(fake, fake_client, monkeypatch):
    monkeypatch.setattr(d1, "local_d1_bindings", lambda: {})
    assert d1.resolve_database_id(fake_client, DB_ID) == DB_ID

    fake.add("GET", LIST_PATH, [{"name": "orquestra", "uuid": DB_ID}])
    assert d1.resolve_database_id(fake_client, "orquestra") == DB_ID

    monkeypatch.setattr(d1, "local_d1_bindings", lambda: {"LOCAL": DB_ID})
    assert d1.resolve_database_id(fake_client, "LOCAL") == DB_ID

    with pytest.raises(ConfigError) as error:
        d1.resolve_database_id(fake_client, "missing")
    assert "cf_d1_list_databases" in str(error.value)


def test_query_maps_rows_changes_and_duration(fake, fake_client, monkeypatch):
    monkeypatch.setattr(d1, "local_d1_bindings", lambda: {})
    fake.add("GET", LIST_PATH, [{"name": "orquestra", "uuid": DB_ID}])
    fake.add(
        "POST",
        QUERY_PATH,
        [
            {
                "results": [{"id": 1, "name": "a"}],
                "success": True,
                "meta": {"duration": 1.25, "changes": 0, "rows_read": 1, "last_row_id": 7},
            }
        ],
    )

    payload = d1.query(fake_client, "orquestra", "SELECT * FROM t")
    assert payload["columns"] == ["id", "name"]
    assert payload["rows"] == [{"id": 1, "name": "a"}]
    assert payload["duration_ms"] == 1.25
    assert payload["rows_read"] == 1
    assert payload["last_row_id"] == 7
    assert payload["statements"] == 1
    assert payload["duration_ms_api"] >= 0

    body = _query_body(fake)
    assert body["sql"] == "SELECT * FROM t"
    assert body["params"] == []
    assert body["timeout"] == 30000


def test_query_passes_bound_parameters(fake, fake_client, monkeypatch):
    monkeypatch.setattr(d1, "local_d1_bindings", lambda: {})
    fake.add("GET", LIST_PATH, [{"name": "orquestra", "uuid": DB_ID}])
    fake.add("POST", QUERY_PATH, [{"results": [], "success": True, "meta": {"changes": 1}}])

    payload = d1.query(fake_client, "orquestra", "INSERT INTO t VALUES (?)", ["x"])
    assert payload["rows_affected"] == 1
    assert _query_body(fake)["params"] == ["x"]


def test_query_rejects_empty_sql(fake_client):
    with pytest.raises(ConfigError):
        d1.query(fake_client, "orquestra", "   ")


def test_query_normalizes_multiple_statements(fake, fake_client, monkeypatch):
    monkeypatch.setattr(d1, "local_d1_bindings", lambda: {})
    fake.add("GET", LIST_PATH, [{"name": "orquestra", "uuid": DB_ID}])
    fake.add(
        "POST",
        QUERY_PATH,
        [
            {"results": [], "success": True, "meta": {"changes": 3, "duration": 2}},
            {"results": [{"x": 1}], "success": True, "meta": {}},
        ],
    )

    payload = d1.query(fake_client, "orquestra", "UPDATE t SET x=1; SELECT 1")
    assert payload["statements"] == 2
    assert payload["rows_affected"] == 3
    assert payload["duration_ms"] == 2


def test_query_falls_back_to_wrangler_when_the_api_fails(fake, fake_client, monkeypatch):
    monkeypatch.setattr(d1, "local_d1_bindings", lambda: {})
    monkeypatch.setattr(d1, "_binds_locally", lambda client, reference: True)
    fake.add("GET", LIST_PATH, [{"name": "orquestra", "uuid": DB_ID}])
    fake.add(
        "POST",
        QUERY_PATH,
        success=False,
        status=403,
        errors=[{"code": 7403, "message": "not authorized"}],
    )

    seen: dict = {}

    def fake_wrangler(reference, sql, params):
        seen["reference"] = reference
        return {"columns": ["x"], "rows": [{"x": 1}], "rows_affected": 0,
                "rows_read": 0, "duration_ms": 4.0, "success": True, "source": "wrangler"}

    monkeypatch.setattr(d1, "_wrangler_query", fake_wrangler)
    payload = d1.query(fake_client, "orquestra", "SELECT 1")
    assert payload["source"] == "wrangler"
    assert seen["reference"] == "orquestra"


def test_query_without_credentials_uses_wrangler(anonymous_client, monkeypatch):
    monkeypatch.setattr(
        d1,
        "_wrangler_query",
        lambda reference, sql, params: {"rows": [{"x": 1}], "columns": ["x"],
                                        "rows_affected": 0, "rows_read": 0,
                                        "duration_ms": 1.0, "success": True,
                                        "source": "wrangler"},
    )
    payload = d1.query(anonymous_client, "local", "SELECT 1")
    assert payload["source"] == "wrangler"


def test_wrangler_query_rejects_bound_parameters():
    with pytest.raises(ConfigError) as error:
        d1._wrangler_query("local", "SELECT ?", [1])
    assert "REST API" in str(error.value)


def test_wrangler_query_parses_json_output(monkeypatch):
    seen: dict = {}

    def fake_run(args, **kwargs):
        seen["args"] = list(args)
        return json.dumps(
            [{"results": [{"x": 1}], "success": True, "meta": {"duration": 3, "changes": 0}}]
        )

    monkeypatch.setattr(d1, "run_wrangler", fake_run)
    payload = d1._wrangler_query("local", "SELECT 1", None)

    assert payload["rows"] == [{"x": 1}]
    assert payload["duration_ms"] == 3
    assert payload["source"] == "wrangler"
    assert seen["args"][:4] == ["d1", "execute", "local", "--json"]


def test_describe_schema_queries_sqlite_master(fake, fake_client, monkeypatch):
    monkeypatch.setattr(d1, "local_d1_bindings", lambda: {})
    fake.add("GET", LIST_PATH, [{"name": "orquestra", "uuid": DB_ID}])
    fake.add(
        "POST",
        QUERY_PATH,
        [
            {
                "results": [
                    {"name": "users", "type": "table", "sql": "CREATE TABLE users(id INTEGER)"}
                ],
                "success": True,
                "meta": {"duration": 1},
            }
        ],
    )

    payload = d1.describe_schema(fake_client, "orquestra")
    assert payload == {
        "database": "orquestra",
        "table": None,
        "objects": [
            {"name": "users", "type": "table", "sql": "CREATE TABLE users(id INTEGER)"}
        ],
    }
    assert "sqlite_master" in _query_body(fake)["sql"]


def test_describe_schema_can_filter_one_table(fake, fake_client, monkeypatch):
    monkeypatch.setattr(d1, "local_d1_bindings", lambda: {})
    fake.add("GET", LIST_PATH, [{"name": "orquestra", "uuid": DB_ID}])
    fake.add("POST", QUERY_PATH, [{"results": [], "success": True, "meta": {}}])

    payload = d1.describe_schema(fake_client, "orquestra", "users")
    assert payload["table"] == "users"
    assert _query_body(fake)["params"] == ["users"]
