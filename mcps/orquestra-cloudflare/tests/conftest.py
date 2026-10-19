"""Shared fixtures for the cloudflare-mcp suite.

Every fixture is hermetic: no network, no real token, and all scratch paths live
under pytest's basetemp (`--basetemp=/var/tmp/testing/cfmcp-pytest`), never
`/tmp`.
"""

from __future__ import annotations

import httpx
import pytest

from cloudflare_mcp import docs
from cloudflare_mcp import server as server_module
from cloudflare_mcp.client import CloudflareClient
from cloudflare_mcp.config import Settings

from fake_cloudflare import FakeCloudflare

API_BASE = "https://api.test"
ACCOUNT = "acct-123"
TOKEN = "token-abc1234"
ZONE = "example.com"
ZONE_ID = "zone-1"

ENV_VARS = (
    "CLOUDFLARE_API_TOKEN",
    "CLOUDFLARE_ACCOUNT_ID",
    "CLOUDFLARE_ZONE_MAP",
    "CLOUDFLARE_API_BASE",
    "CLOUDFLARE_MCP_TIMEOUT",
    "CLOUDFLARE_MCP_RETRIES",
    "CLOUDFLARE_MCP_WRANGLER_FALLBACK",
    "CLOUDFLARE_MCP_DOCS_DIRS",
)


def make_settings(**overrides) -> Settings:
    """Settings pointed at the fake API with a deterministic account."""

    values: dict = {
        "api_token": TOKEN,
        "account_id": ACCOUNT,
        "base_url": API_BASE,
        "zone_map": {ZONE: ZONE_ID},
        "max_retries": 0,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture(autouse=True)
def _clear_caches():
    """Docs reads are cached per directory tuple; isolate every test."""
    docs.load_corpus.cache_clear()
    yield
    docs.load_corpus.cache_clear()


@pytest.fixture
def fake() -> FakeCloudflare:
    return FakeCloudflare()


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def anonymous_settings() -> Settings:
    return make_settings(api_token=None, account_id=None, zone_map={})


@pytest.fixture
def fake_client(fake: FakeCloudflare, settings: Settings):
    """A credentialed client on the fake transport, injected into the server."""
    client = CloudflareClient(settings, transport=httpx.MockTransport(fake.handler))
    server_module.set_client(client)
    try:
        yield client
    finally:
        server_module.set_client(None)
        client.close()


@pytest.fixture
def anonymous_client(fake: FakeCloudflare, anonymous_settings: Settings):
    """A client with no token: only docs and local wrangler paths can work."""
    client = CloudflareClient(anonymous_settings, transport=httpx.MockTransport(fake.handler))
    server_module.set_client(client)
    try:
        yield client
    finally:
        server_module.set_client(None)
        client.close()


@pytest.fixture
def clean_env(monkeypatch):
    """No Cloudflare variables at all, whatever the developer's shell holds."""
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("CLOUDFLARE_MCP_NO_AUTO_WRANGLER", "1")
    return monkeypatch


@pytest.fixture
def cf_env(monkeypatch):
    """Credentials in the process environment for tools that re-read settings."""
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)

    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", TOKEN)
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", ACCOUNT)
    monkeypatch.setenv("CLOUDFLARE_ZONE_MAP", f"{ZONE}={ZONE_ID}")
    return monkeypatch
