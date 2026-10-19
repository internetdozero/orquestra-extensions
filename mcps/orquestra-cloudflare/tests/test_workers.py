"""Workers: inventory, routes, deployment history and the local tail fallback."""

from __future__ import annotations

import json

import pytest

from cloudflare_mcp import workers
from cloudflare_mcp.wrangler import WranglerError

from conftest import ACCOUNT

SCRIPTS = f"/accounts/{ACCOUNT}/workers/scripts"
WORKER = "orquestra-api"


def test_list_workers_combines_scripts_routes_and_deployments(fake, fake_client):
    fake.add(
        "GET",
        SCRIPTS,
        [
            {"id": WORKER, "created_on": "c", "modified_on": "m", "etag": "e",
             "handlers": ["fetch"]},
            {"id": "other", "handlers": []},
        ],
    )
    fake.add(
        "GET",
        f"/accounts/{ACCOUNT}/workers/routes",
        [
            {"pattern": "example.com/*", "script": WORKER, "zone_id": "zone-1",
             "zone_name": "example.com"},
            {"pattern": "other.com/*", "script": "missing"},
        ],
    )
    fake.add("GET", f"{SCRIPTS}/{WORKER}/subdomain", {"environment": "production"})
    fake.add("GET", f"{SCRIPTS}/other/subdomain", {"environment": "preview"})
    fake.add(
        "GET",
        f"{SCRIPTS}/{WORKER}/deployments",
        [{"id": "dep-1", "created_on": "d", "versions": [{"version_id": "v1"}, {"id": "v2"}]}],
    )
    fake.add("GET", f"{SCRIPTS}/other/deployments", [])

    listed = workers.list_workers(fake_client)
    first = listed[0]
    assert first["id"] == WORKER
    assert first["environments"] == ["production"]
    assert first["routes"] == [
        {"pattern": "example.com/*", "zone_id": "zone-1", "zone_name": "example.com"}
    ]
    assert first["deployments"] == [
        {"deployment_id": "dep-1", "created_on": "d", "versions": ["v1", "v2"]}
    ]
    assert listed[1]["environments"] == ["preview"]


def test_route_lookup_can_be_skipped(fake, fake_client):
    fake.add("GET", SCRIPTS, [{"id": WORKER}])
    fake.add("GET", f"{SCRIPTS}/{WORKER}/subdomain", {"environment": "production"})
    fake.add("GET", f"{SCRIPTS}/{WORKER}/deployments", [])

    listed = workers.list_workers(fake_client, include_routes=False)
    assert listed[0]["routes"] == []
    assert ("GET", f"/accounts/{ACCOUNT}/workers/routes") not in fake.paths


def test_route_and_deployment_failures_are_tolerated(fake, fake_client):
    fake.add("GET", SCRIPTS, [{"id": WORKER}])
    fake.add("GET", f"/accounts/{ACCOUNT}/workers/routes", success=False, status=403,
             errors=[{"message": "no access"}])
    fake.add("GET", f"{SCRIPTS}/{WORKER}/subdomain", success=False, status=403,
             errors=[{"message": "no access"}])
    fake.add("GET", f"{SCRIPTS}/{WORKER}/deployments", success=False, status=403,
             errors=[{"message": "no access"}])

    listed = workers.list_workers(fake_client)
    assert listed[0]["routes"] == []
    assert listed[0]["environments"] == []
    assert listed[0]["deployments"] == []


def test_worker_detail_reports_bindings_and_compatibility(fake, fake_client):
    fake.add(
        "GET",
        f"{SCRIPTS}/{WORKER}",
        {
            "modified_on": "m",
            "usage_model": "bundled",
            "metadata": {"compatibility_date": "2026-01-01"},
            "bindings": [{"name": "DB", "type": "d1"}, {"name": "CACHE", "type": "kv_namespace"}],
        },
    )

    detail = workers.worker_detail(fake_client, WORKER)
    assert detail["compatibility_date"] == "2026-01-01"
    assert detail["usage_model"] == "bundled"
    assert detail["bindings"] == [
        {"name": "DB", "type": "d1"},
        {"name": "CACHE", "type": "kv_namespace"},
    ]


def test_tail_worker_parses_json_lines(monkeypatch, tmp_path):
    (tmp_path / "wrangler.toml").write_text('name = "demo"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    output = "\n".join(json.dumps({"event": index}) for index in range(2))
    seen: dict = {}

    def fake_run(args, **kwargs):
        seen["args"] = list(args)
        return output

    monkeypatch.setattr(workers, "run_wrangler", fake_run)
    payload = workers.tail_worker(WORKER, seconds=5, filter_expr="status:error")

    assert payload["events"] == [{"event": 0}, {"event": 1}]
    assert payload["worker"] == WORKER
    assert seen["args"][:3] == ["tail", WORKER, "--format"]
    assert "--duration" in seen["args"]
    assert "status:error" in seen["args"]


def test_tail_worker_clamps_the_duration(monkeypatch, tmp_path):
    (tmp_path / "wrangler.toml").write_text('name = "demo"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    seen: dict = {}

    def fake_run(args, **kwargs):
        seen["args"] = list(args)
        return ""

    monkeypatch.setattr(workers, "run_wrangler", fake_run)
    workers.tail_worker(WORKER, seconds=5_000)

    assert seen["args"][seen["args"].index("--duration") + 1] == "60"


def test_tail_worker_requires_a_worker_and_a_local_config(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(WranglerError):
        workers.tail_worker("", seconds=1)


def test_local_worker_names_reads_the_config(monkeypatch, tmp_path):
    (tmp_path / "wrangler.jsonc").write_text('{\n  "name": "demo-worker"\n}\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert workers.local_worker_names() == ["demo-worker"]


def test_local_worker_names_without_a_config(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert workers.local_worker_names() == []
