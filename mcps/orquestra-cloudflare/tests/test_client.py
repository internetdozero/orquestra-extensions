"""REST transport behaviour: envelopes, retries and pagination."""

from __future__ import annotations

import json
import subprocess

import httpx
import pytest

from cloudflare_mcp.client import CloudflareAPIError, CloudflareClient
from cloudflare_mcp.config import ConfigError

from conftest import ACCOUNT, make_settings


def _client(fake, **overrides) -> CloudflareClient:
    settings = make_settings(**overrides)
    return CloudflareClient(settings, transport=httpx.MockTransport(fake.handler))


def test_get_returns_result_and_get_full_returns_envelope(fake):
    fake.add("GET", f"/accounts/{ACCOUNT}/thing", {"value": 1})
    client = _client(fake)
    try:
        assert client.get(f"/accounts/{ACCOUNT}/thing") == {"value": 1}
        full = client.get_full(f"/accounts/{ACCOUNT}/thing")
        assert full["success"] is True
        assert full["result"] == {"value": 1}
        assert fake.last_request().headers["authorization"].startswith("Bearer ")
    finally:
        client.close()


def test_api_error_envelope_becomes_a_structured_error(fake):
    fake.add(
        "GET",
        "/zones",
        success=False,
        status=403,
        errors=[{"code": 9109, "message": "Invalid access token"}],
    )
    client = _client(fake)
    try:
        with pytest.raises(CloudflareAPIError) as error:
            client.get("/zones")
        assert error.value.status == 403
        assert "Invalid access token" in str(error.value)
        assert error.value.to_dict()["details"][0]["code"] == 9109
    finally:
        client.close()


def test_retryable_status_is_retried_then_succeeds(fake):
    fake.add_sequence(
        "GET",
        "/zones",
        [
            httpx.Response(429, headers={"retry-after": "0"}, json={"success": False}),
            httpx.Response(200, json={"success": True, "result": [1], "errors": []}),
        ],
    )
    client = _client(fake, max_retries=1)
    try:
        assert client.get("/zones") == [1]
        assert len(fake.requests_for("GET", "/zones")) == 2
    finally:
        client.close()


def test_retryable_status_exhausting_retries_raises(fake):
    fake.add("GET", "/zones", success=False, status=503)
    client = _client(fake, max_retries=1)
    try:
        with pytest.raises(CloudflareAPIError) as error:
            client.get("/zones")
        assert error.value.status == 503
    finally:
        client.close()


def test_transport_error_is_reported_as_an_api_error(fake):
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = CloudflareClient(make_settings(), transport=httpx.MockTransport(boom))
    try:
        with pytest.raises(CloudflareAPIError):
            client.get("/zones")
    finally:
        client.close()


def test_non_json_success_keeps_the_raw_text(fake):
    fake.add_raw("GET", "/raw", httpx.Response(200, text="hello"))
    client = _client(fake)
    try:
        payload = client.get_full("/raw")
        assert payload["success"] is True
        assert payload["raw"] == "hello"
    finally:
        client.close()


def test_anonymous_client_refuses_authenticated_requests(fake, anonymous_settings):
    client = CloudflareClient(anonymous_settings, transport=httpx.MockTransport(fake.handler))
    try:
        with pytest.raises(ConfigError) as error:
            client.get("/zones")
        assert "CLOUDFLARE_API_TOKEN" in str(error.value)
        assert fake.calls == []
    finally:
        client.close()


def test_pagination_collects_pages_until_has_more_is_false(fake):
    fake.add_sequence(
        "GET",
        "/zones",
        [
            httpx.Response(
                200,
                json={
                    "success": True,
                    "result": [1, 2],
                    "errors": [],
                    "result_info": {"has_more": True, "page": 1},
                },
            ),
            httpx.Response(
                200,
                json={
                    "success": True,
                    "result": [3],
                    "errors": [],
                    "result_info": {"has_more": False, "page": 2},
                },
            ),
        ],
    )
    client = _client(fake)
    try:
        assert client.paginate("/zones", per_page=2) == [1, 2, 3]
    finally:
        client.close()


def test_client_is_a_context_manager():
    settings = make_settings()
    with CloudflareClient(settings, transport=httpx.MockTransport(lambda request: httpx.Response(200))) as client:
        assert client.account_id == ACCOUNT
