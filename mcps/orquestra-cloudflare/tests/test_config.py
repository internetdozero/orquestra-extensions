"""Configuration parsing: token masking, zone maps and env overrides."""

from __future__ import annotations

import pytest

from cloudflare_mcp.config import (
    ConfigError,
    Settings,
    load_settings,
    mask_token,
    parse_zone_map,
)


def test_mask_token_never_leaks_the_secret():
    masked = mask_token("supersecrettoken")
    assert masked == "****oken"
    assert "supersecrettoken" not in masked
    assert mask_token("shrt") == "****shrt"
    assert mask_token("abc") == "****...."
    assert mask_token(None) == "<not set>"


def test_parse_zone_map_accepts_json_and_csv():
    assert parse_zone_map('{"Example.COM.": "zone-1"}') == {"example.com": "zone-1"}
    assert parse_zone_map("example.com=zone-1, api.example.com = zone-2") == {
        "example.com": "zone-1",
        "api.example.com": "zone-2",
    }
    assert parse_zone_map(None) == {}
    assert parse_zone_map("   ") == {}


def test_parse_zone_map_rejects_malformed_input():
    with pytest.raises(ConfigError):
        parse_zone_map("{not json}")
    with pytest.raises(ConfigError):
        parse_zone_map('["example.com"]')
    with pytest.raises(ConfigError):
        parse_zone_map('{"example.com": ""}')
    with pytest.raises(ConfigError):
        parse_zone_map("example.com")


def test_zone_id_resolution_and_single_entry_wildcard():
    settings = Settings(zone_map={"example.com": "zone-1"})
    assert settings.zone_id("Example.com.") == "zone-1"
    assert settings.zone_id("") == "zone-1"
    assert settings.zone_id("*") == "zone-1"

    with pytest.raises(ConfigError) as error:
        settings.zone_id("other.com")
    assert "CLOUDFLARE_ZONE_MAP" in str(error.value)

    two_zones = Settings(zone_map={"a.com": "1", "b.com": "2"})
    with pytest.raises(ConfigError):
        two_zones.zone_id("*")


def test_require_credentials_names_the_missing_variable():
    with pytest.raises(ConfigError) as error:
        Settings().require_credentials()
    assert "CLOUDFLARE_API_TOKEN" in str(error.value)

    with pytest.raises(ConfigError) as error:
        Settings(api_token="token").require_credentials()
    assert "CLOUDFLARE_ACCOUNT_ID" in str(error.value)

    assert Settings(api_token="token", account_id="acct").has_credentials


def test_load_settings_reads_env_with_defaults_and_overrides():
    defaults = load_settings({})
    assert defaults.api_token is None
    assert defaults.account_id is None
    assert defaults.base_url == "https://api.cloudflare.com/client/v4"
    assert defaults.timeout == 30.0
    assert defaults.max_retries == 2
    assert defaults.wrangler_fallback is True
    assert defaults.docs_dirs == ()

    loaded = load_settings(
        {
            "CLOUDFLARE_API_TOKEN": "  token  ",
            "CLOUDFLARE_ACCOUNT_ID": "acct",
            "CLOUDFLARE_API_BASE": "https://api.test/",
            "CLOUDFLARE_ZONE_MAP": "example.com=zone-1",
            "CLOUDFLARE_MCP_TIMEOUT": "5.5",
            "CLOUDFLARE_MCP_RETRIES": "7",
            "CLOUDFLARE_MCP_WRANGLER_FALLBACK": "off",
            "CLOUDFLARE_MCP_DOCS_DIRS": "/a:/b:",
        }
    )
    assert loaded.api_token == "token"
    assert loaded.account_id == "acct"
    assert loaded.base_url == "https://api.test"
    assert loaded.zone_map == {"example.com": "zone-1"}
    assert loaded.timeout == 5.5
    assert loaded.max_retries == 7
    assert loaded.wrangler_fallback is False
    assert loaded.docs_dirs == ("/a", "/b")


def test_load_settings_rejects_non_numeric_values():
    with pytest.raises(ConfigError):
        load_settings({"CLOUDFLARE_MCP_TIMEOUT": "soon"})
    with pytest.raises(ConfigError):
        load_settings({"CLOUDFLARE_MCP_RETRIES": "many"})


def test_discover_vault_credentials(tmp_path, monkeypatch):
    import json
    from cloudflare_mcp.config import _discover_vault_credentials

    vault_file = tmp_path / "vault.json"
    vault_file.write_text(
        json.dumps({
            "cloudflare": {"keys": ["vault-token-123"], "active_index": 0},
            "cf_account": {"keys": ["vault-acct-456"]},
            "zone_map": {"example.com": "zone-789"}
        }),
        encoding="utf-8"
    )

    monkeypatch.setattr(
        "cloudflare_mcp.config.Path.home",
        lambda: tmp_path
    )
    (tmp_path / ".config" / "api-vault").mkdir(parents=True)
    (tmp_path / ".config" / "api-vault" / "vault.json").write_text(vault_file.read_text(), encoding="utf-8")

    token, acct, zones = _discover_vault_credentials()
    assert token == "vault-token-123"
    assert acct == "vault-acct-456"
    assert zones == {"example.com": "zone-789"}
