"""KV and R2 storage operations against the fake API."""

from __future__ import annotations

import json

import httpx
import pytest

from cloudflare_mcp import storage
from cloudflare_mcp.config import ConfigError

from conftest import ACCOUNT

NS = "0123456789abcdef0123456789abcdef"
NS_LIST = f"/accounts/{ACCOUNT}/storage/kv/namespaces"
VALUES = f"{NS_LIST}/{NS}/values"
METADATA = f"{NS_LIST}/{NS}/metadata"
BUCKETS = f"/accounts/{ACCOUNT}/r2/buckets"


def test_list_namespaces_maps_fields(fake, fake_client):
    fake.add("GET", NS_LIST, [{"id": NS, "title": "ORQUESTRA_CACHE", "created_on": "c"}])
    assert storage.list_namespaces(fake_client) == [
        {"id": NS, "title": "ORQUESTRA_CACHE", "created_on": "c"}
    ]


def test_resolve_namespace_accepts_id_title_and_rejects_unknown(fake, fake_client):
    assert storage.resolve_namespace(fake_client, NS) == NS

    fake.add("GET", NS_LIST, [{"id": "ns-1", "title": "Orquestra-Cache"}])
    assert storage.resolve_namespace(fake_client, "Orquestra-Cache") == "ns-1"
    assert storage.resolve_namespace(fake_client, "ORQUESTRA_CACHE") == "ns-1"

    with pytest.raises(ConfigError):
        storage.resolve_namespace(fake_client, "nope")
    with pytest.raises(ConfigError):
        storage.resolve_namespace(fake_client, "  ")


def test_kv_get_reads_value_and_metadata(fake, fake_client):
    fake.add_raw("GET", f"{VALUES}/greeting", httpx.Response(200, text="hello"))
    fake.add("GET", f"{METADATA}/greeting", {"ttl": 60})

    payload = storage.kv_get(fake_client, "greeting", NS)
    assert payload == {
        "key": "greeting",
        "namespace": NS,
        "value": "hello",
        "encoding": "utf-8",
        "metadata": {"ttl": 60},
        "found": True,
    }


def test_kv_get_reports_a_missing_key(fake, fake_client):
    fake.add("GET", f"{VALUES}/missing", success=False, status=404,
             errors=[{"code": 10009, "message": "not found"}])

    payload = storage.kv_get(fake_client, "missing", NS)
    assert payload["found"] is False
    assert payload["value"] is None


def test_kv_get_decodes_json_values_and_tolerates_missing_metadata(fake, fake_client):
    fake.add_raw(
        "GET",
        f"{VALUES}/cfg",
        httpx.Response(200, json={"enabled": True},
                       headers={"content-type": "application/json"}),
    )
    fake.add("GET", f"{METADATA}/cfg", success=False, status=404,
             errors=[{"message": "none"}])

    payload = storage.kv_get(fake_client, "cfg", NS)
    assert payload["value"] == {"enabled": True}
    assert payload["encoding"] == "json"
    assert payload["metadata"] is None


def test_kv_get_escapes_the_key_in_the_path(fake, fake_client):
    fake.add_raw("GET", f"{VALUES}/a%2Fb%20c", httpx.Response(200, text="v"))
    fake.add("GET", f"{METADATA}/a%2Fb%20c", {})

    storage.kv_get(fake_client, "a/b c", NS)
    assert "a%2Fb%20c" in str(fake.last_request().url)


def test_kv_set_sends_content_type_ttl_and_metadata(fake, fake_client):
    fake.add("PUT", f"{VALUES}/flag", "ok")
    payload = storage.kv_set(
        fake_client, "flag", '{"on": true}', NS, ttl=60,
        metadata={"owner": "ops"}, is_json=True,
    )

    request = fake.requests_for("PUT", f"{VALUES}/flag")[0]
    assert request.headers["content-type"] == "application/json"
    assert request.content == b'{"on": true}'
    assert request.url.params["expiration_ttl"] == "60"
    assert json.loads(request.url.params["metadata"]) == {"owner": "ops"}

    assert payload["ok"] is True
    assert payload["bytes"] == len('{"on": true}')
    assert payload["ttl"] == 60
    assert payload["metadata"] is True


def test_kv_set_defaults_to_text_plain(fake, fake_client):
    fake.add("PUT", f"{VALUES}/note", "ok")
    storage.kv_set(fake_client, "note", "hi", NS)

    request = fake.requests_for("PUT", f"{VALUES}/note")[0]
    assert request.headers["content-type"] == "text/plain; charset=utf-8"
    assert "expiration_ttl" not in request.url.params


def test_kv_set_validates_ttl_and_json(fake, fake_client):
    with pytest.raises(ConfigError):
        storage.kv_set(fake_client, "key", "value", NS, ttl=0)
    with pytest.raises(ConfigError):
        storage.kv_set(fake_client, "key", "value", NS, ttl=999_999)
    with pytest.raises(ValueError):
        storage.kv_set(fake_client, "key", "{not json}", NS, is_json=True)


def test_list_buckets_reports_pagination(fake, fake_client):
    fake.add(
        "GET",
        BUCKETS,
        [{"name": "b1", "created_on": "c", "location": "WEUR", "storage_class": "Standard"}],
        result_info={"truncated": True, "cursor": "next-page"},
    )

    payload = storage.list_buckets(fake_client)
    assert payload["count"] == 1
    assert payload["buckets"][0] == {
        "name": "b1",
        "created_on": "c",
        "location": "WEUR",
        "storage_class": "Standard",
    }
    assert payload["truncated"] is True
    assert payload["cursor"] == "next-page"
    assert fake.last_request().url.params["per_page"] == "100"


def test_list_buckets_forwards_the_cursor(fake, fake_client):
    fake.add("GET", BUCKETS, [])
    storage.list_buckets(fake_client, cursor="abc", limit=5)
    assert fake.last_request().url.params["cursor"] == "abc"


def test_list_objects_uses_the_data_plane_endpoint(fake, fake_client):
    fake.add(
        "POST",
        f"{BUCKETS}/b1/objects/list",
        {
            "objects": [{"key": "a.txt", "size": 3, "uploaded": "u", "etag": "e"}],
            "truncated": False,
        },
    )

    payload = storage.list_objects(fake_client, "b1", prefix="a")
    assert payload["bucket"] == "b1"
    assert payload["objects"][0]["key"] == "a.txt"
    assert payload["truncated"] is False

    body = json.loads(fake.requests_for("POST", f"{BUCKETS}/b1/objects/list")[0].content)
    assert body == {"prefix": "a", "limit": 50}
