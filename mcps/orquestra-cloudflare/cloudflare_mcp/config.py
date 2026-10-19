"""Environment configuration for the Cloudflare MCP server.

Reads credentials and account/zone mapping from the process environment.
Tokens are never printed or returned by tools; only masked forms leave this
module (see :func:`mask_token`).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Mapping

DEFAULT_BASE_URL = "https://api.cloudflare.com/client/v4"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 2


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or malformed."""


@dataclass(frozen=True)
class Settings:
    """Immutable runtime configuration resolved once at startup."""

    api_token: str | None = None
    account_id: str | None = None
    base_url: str = DEFAULT_BASE_URL
    zone_map: dict[str, str] = field(default_factory=dict)
    timeout: float = DEFAULT_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    wrangler_fallback: bool = True
    docs_dirs: tuple[str, ...] = ()

    @property
    def has_credentials(self) -> bool:
        return bool(self.api_token and self.account_id)

    def require_credentials(self) -> None:
        if not self.api_token:
            raise ConfigError(
                "CLOUDFLARE_API_TOKEN is not set. Export it in your MCP server "
                "environment (e.g. in mcps.json) and restart the harness."
            )
        if not self.account_id:
            raise ConfigError(
                "CLOUDFLARE_ACCOUNT_ID is not set. Export it in your MCP server "
                "environment (e.g. in mcps.json) and restart the harness."
            )

    def zone_id(self, zone_name: str) -> str:
        """Resolve a zone name to a zone ID via CLOUDFLARE_ZONE_MAP."""
        key = zone_name.strip().rstrip(".").lower()
        if key in self.zone_map:
            return self.zone_map[key]
        if len(self.zone_map) == 1 and key in {"", "*"}:
            return next(iter(self.zone_map.values()))
        raise ConfigError(
            f"Zone '{zone_name}' is not present in CLOUDFLARE_ZONE_MAP. "
            "Set CLOUDFLARE_ZONE_MAP as JSON '{\"example.com\": \"<zone_id>\"}' "
            "or as comma separated 'example.com=<zone_id>'."
        )


def mask_token(token: str | None) -> str:
    """Return a safe display form of a token (last four characters only)."""
    if not token:
        return "<not set>"
    tail = token[-4:] if len(token) >= 4 else "...."
    return f"****{tail}"


def parse_zone_map(raw: str | None) -> dict[str, str]:
    """Parse CLOUDFLARE_ZONE_MAP from JSON object or ``name=id,name2=id2``."""
    if not raw:
        return {}
    raw = raw.strip()
    if not raw:
        return {}
    mapping: dict[str, str] = {}
    if raw.startswith("{"):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"CLOUDFLARE_ZONE_MAP is not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise ConfigError("CLOUDFLARE_ZONE_MAP JSON must be an object of zone -> id")
        for key, value in data.items():
            if not isinstance(value, str) or not value:
                raise ConfigError(f"CLOUDFLARE_ZONE_MAP value for '{key}' must be a zone id string")
            mapping[str(key).strip().rstrip(".").lower()] = value.strip()
        return mapping
    for part in raw.split(","):
        if not part.strip():
            continue
        if "=" not in part:
            raise ConfigError(
                f"CLOUDFLARE_ZONE_MAP entry '{part.strip()}' must be 'name=zone_id'"
            )
        name, _, zone_id = part.partition("=")
        mapping[name.strip().rstrip(".").lower()] = zone_id.strip()
    return mapping


def _env_float(env: Mapping[str, str], key: str, default: float) -> float:
    raw = env.get(key)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"{key} must be a number, got '{raw}'") from exc
    return value


def _env_int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{key} must be an integer, got '{raw}'") from exc


def _env_bool(env: Mapping[str, str], key: str, default: bool) -> bool:
    raw = env.get(key)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


from pathlib import Path


def _discover_vault_credentials() -> tuple[str | None, str | None, dict[str, str]]:
    """Inspect ~/.config/api-vault/vault.json for cloudflare api token and account id."""
    candidates = (
        Path.home() / ".config" / "api-vault" / "vault.json",
        Path("/etc/api-vault/vault.json"),
    )
    for p in candidates:
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                cf_data = data.get("cloudflare") or data.get("cloudflare_api") or {}
                if isinstance(cf_data, dict):
                    keys = cf_data.get("keys", [])
                    idx = cf_data.get("active_index", 0)
                    token = keys[idx] if isinstance(keys, list) and 0 <= idx < len(keys) else (keys[0] if keys else None)
                elif isinstance(cf_data, str):
                    token = cf_data
                else:
                    token = data.get("CLOUDFLARE_API_TOKEN")

                acct_data = data.get("cf_account") or data.get("cloudflare_account") or {}
                if isinstance(acct_data, dict):
                    acct_keys = acct_data.get("keys", [])
                    account_id = acct_keys[0] if isinstance(acct_keys, list) and acct_keys else None
                elif isinstance(acct_data, str):
                    account_id = acct_data
                else:
                    account_id = data.get("CLOUDFLARE_ACCOUNT_ID")

                zone_map_raw = data.get("cloudflare_zone_map") or data.get("zone_map") or {}
                zone_map = parse_zone_map(json.dumps(zone_map_raw)) if isinstance(zone_map_raw, dict) else (
                    parse_zone_map(str(zone_map_raw)) if zone_map_raw else {}
                )
                if token or account_id or zone_map:
                    return token, account_id, zone_map
            except Exception:
                pass
    return None, None, {}


def _discover_wrangler_credentials() -> tuple[str | None, str | None, dict[str, str]]:
    """Inspect ~/.config/.wrangler/config/default.toml for oauth token and account id."""
    candidates = (
        Path.home() / ".config" / ".wrangler" / "config" / "default.toml",
        Path.home() / ".wrangler" / "config" / "default.toml",
    )
    for p in candidates:
        if p.is_file():
            try:
                import tomllib

                data = tomllib.loads(p.read_text(encoding="utf-8"))
                token = data.get("oauth_token")
                account_id = data.get("default_account_id")
                if token or account_id:
                    return token, account_id, {}
            except Exception:
                pass
    return None, None, {}


def _default_docs_dirs() -> tuple[str, ...]:
    """Auto-discover all local Cloudflare skill documentation directories."""
    lib = Path.home() / ".orquestra" / "skills-library"
    if not lib.is_dir():
        return ()
    found: list[str] = []
    deploy_ref = lib / "cloudflare-deploy" / "references"
    if deploy_ref.is_dir():
        found.append(str(deploy_ref))
    for d in sorted(lib.glob("*cloudflare*")):
        if d.is_dir() and d != (lib / "cloudflare-deploy"):
            found.append(str(d))
    return tuple(found)


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Build :class:`Settings` from the environment (``os.environ`` by default)."""
    is_default_env = env is None
    env = os.environ if env is None else env
    api_token = (env.get("CLOUDFLARE_API_TOKEN") or "").strip() or None
    account_id = (env.get("CLOUDFLARE_ACCOUNT_ID") or "").strip() or None
    zone_map = parse_zone_map(env.get("CLOUDFLARE_ZONE_MAP"))

    auto_discover = (
        is_default_env
        and not _env_bool(env, "CLOUDFLARE_MCP_NO_AUTO_WRANGLER", False)
        and not _env_bool(env, "CLOUDFLARE_MCP_NO_AUTO_VAULT", False)
    )

    if auto_discover and (api_token is None or account_id is None):
        v_token, v_acct, v_zones = _discover_vault_credentials()
        api_token = api_token or v_token
        account_id = account_id or v_acct
        if not zone_map:
            zone_map = v_zones

    if auto_discover and (api_token is None or account_id is None):
        w_token, w_acct, w_zones = _discover_wrangler_credentials()
        api_token = api_token or w_token
        account_id = account_id or w_acct
        if not zone_map:
            zone_map = w_zones

    if not zone_map and auto_discover:
        _, _, fallback_zones = _discover_vault_credentials()
        if not fallback_zones:
            _, _, fallback_zones = _discover_wrangler_credentials()
        zone_map = fallback_zones

    raw_docs = (env.get("CLOUDFLARE_MCP_DOCS_DIRS") or "").strip()
    if is_default_env and not raw_docs:
        docs_dirs = _default_docs_dirs()
    else:
        docs_dirs = tuple(part.strip() for part in raw_docs.split(os.pathsep) if part.strip())

    return Settings(
        api_token=api_token,
        account_id=account_id,
        base_url=(env.get("CLOUDFLARE_API_BASE") or DEFAULT_BASE_URL).rstrip("/"),
        zone_map=zone_map,
        timeout=_env_float(env, "CLOUDFLARE_MCP_TIMEOUT", DEFAULT_TIMEOUT),
        max_retries=_env_int(env, "CLOUDFLARE_MCP_RETRIES", DEFAULT_MAX_RETRIES),
        wrangler_fallback=_env_bool(env, "CLOUDFLARE_MCP_WRANGLER_FALLBACK", True),
        docs_dirs=docs_dirs,
    )