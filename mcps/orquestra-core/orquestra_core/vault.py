"""Blind Credential Vault integration for OrquestraAI MCP control plane.

Allows autonomous agents to perform HTTP API calls and CLI execution with
stored secrets WITHOUT exposing the raw secret to prompt or context.
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from . import paths
from .errors import UnknownVaultService, VaultRequestError

SENSITIVE_HEADERS = {
    "authorization",
    "proxy-authenticate",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "x-goog-api-key",
    "api-key",
    "apikey",
}

PRESET_SPECS: dict[str, dict[str, Any]] = {
    "openai": {
        "header": "authorization",
        "prefix": "Bearer ",
        "env": "OPENAI_API_KEY",
        "extra": {},
    },
    "anthropic": {
        "header": "x-api-key",
        "prefix": "",
        "env": "ANTHROPIC_API_KEY",
        "extra": {"anthropic-version": "2023-06-01"},
    },
    "gemini": {
        "header": "x-goog-api-key",
        "prefix": "",
        "env": "GEMINI_API_KEY",
        "extra": {},
    },
    "openrouter": {
        "header": "authorization",
        "prefix": "Bearer ",
        "env": "OPENROUTER_API_KEY",
        "extra": {},
    },
    "groq": {
        "header": "authorization",
        "prefix": "Bearer ",
        "env": "GROQ_API_KEY",
        "extra": {},
    },
    "mistral": {
        "header": "authorization",
        "prefix": "Bearer ",
        "env": "MISTRAL_API_KEY",
        "extra": {},
    },
    "deepseek": {
        "header": "authorization",
        "prefix": "Bearer ",
        "env": "DEEPSEEK_API_KEY",
        "extra": {},
    },
    "cloudflare": {
        "header": "authorization",
        "prefix": "Bearer ",
        "env": "CLOUDFLARE_API_TOKEN",
        "extra": {},
    },
    "github": {
        "header": "authorization",
        "prefix": "Bearer ",
        "env": "GITHUB_TOKEN",
        "extra": {"user-agent": "OrquestraAI"},
    },
    "supabase": {
        "header": "apikey",
        "prefix": "",
        "env": "SUPABASE_KEY",
        "extra": {},
    },
    "custom": {
        "header": "authorization",
        "prefix": "Bearer ",
        "env": "CUSTOM_API_KEY",
        "extra": {},
    },
}


def vault_path() -> Path:
    return paths.home() / "vault.json"


def load_vault() -> dict[str, Any]:
    path = vault_path()
    if not path.exists():
        return {"services": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"services": {}}


def save_vault(data: dict[str, Any]) -> None:
    path = vault_path()
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def mask_key(secret: str) -> str:
    if not secret:
        return ""
    if len(secret) <= 8:
        return "********"
    return f"****{secret[-4:]}"


def scrub_text(text: str, secrets: list[str]) -> str:
    out = text
    for secret in secrets:
        if len(secret) >= 4:
            out = out.replace(secret, "[REDACTED]")
    return out


def strip_headers(headers: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in headers.items() if k.lower() not in SENSITIVE_HEADERS}


def get_service(vault_data: dict[str, Any], service_id: str) -> dict[str, Any]:
    services = vault_data.get("services", {})
    if service_id not in services:
        available = ", ".join(services.keys()) or "none"
        raise UnknownVaultService(f"unknown vault service '{service_id}'; available: {available}")
    return services[service_id]


def build_headers_for_service(service: dict[str, Any], secret: str, custom_extra: dict[str, str] | None = None) -> dict[str, str]:
    preset_id = service.get("preset", "custom")
    preset = PRESET_SPECS.get(preset_id, PRESET_SPECS["custom"])

    header_name = service.get("customHeader") or service.get("custom_header") or preset["header"]
    prefix = service.get("customPrefix") if service.get("customPrefix") is not None else service.get("custom_prefix")
    if prefix in ("none", "-", ""):
        prefix = ""
    elif prefix is None:
        prefix = preset["prefix"]

    out = {header_name: f"{prefix}{secret}"}
    out.update(preset["extra"])

    if custom_extra:
        for k, v in custom_extra.items():
            if k.lower() not in SENSITIVE_HEADERS:
                out[k] = v
    return out


def build_env_for_service(service: dict[str, Any], secret: str) -> dict[str, str]:
    preset_id = service.get("preset", "custom")
    preset = PRESET_SPECS.get(preset_id, PRESET_SPECS["custom"])

    env_var = service.get("customEnv") or service.get("custom_env") or preset["env"]
    child_env = os.environ.copy()
    child_env[env_var] = secret
    child_env["API_KEY"] = secret
    child_env["API_TOKEN"] = secret

    # Add meta fields into env if available
    meta = service.get("meta", {})
    if isinstance(meta, dict):
        for k, v in meta.items():
            child_env[k] = str(v)

    return child_env


def list_services() -> list[dict[str, Any]]:
    vault = load_vault()
    result = []
    for s_id, s in vault.get("services", {}).items():
        keys = s.get("keys", [])
        active_idx = s.get("active", 0)
        masked = [mask_key(k.get("secret", "")) if isinstance(k, dict) else mask_key(str(k)) for k in keys]
        result.append({
            "id": s_id,
            "label": s.get("label", s_id),
            "preset": s.get("preset", "custom"),
            "health": s.get("health", "Healthy"),
            "totalKeys": len(keys),
            "activeKeyIndex": active_idx,
            "maskedKeys": masked,
            "meta": s.get("meta", {}),
        })
    return result


def execute_http(
    service_id: str,
    endpoint: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: str | dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    if not endpoint.startswith(("http://", "https://")):
        raise ValueError("endpoint must start with http:// or https://")

    vault = load_vault()
    service = get_service(vault, service_id)
    keys = service.get("keys", [])
    if not keys:
        raise ValueError(f"vault service '{service_id}' has no keys configured")

    active_idx = service.get("active", 0)
    attempts = len(keys)
    last_err: Exception | None = None

    for attempt in range(attempts):
        idx = (active_idx + attempt) % len(keys)
        key_obj = keys[idx]
        secret = key_obj.get("secret", "") if isinstance(key_obj, dict) else str(key_obj)

        req_headers = build_headers_for_service(service, secret, headers)
        data = None
        if body is not None:
            if isinstance(body, dict):
                data = json.dumps(body).encode("utf-8")
                req_headers.setdefault("Content-Type", "application/json")
            elif isinstance(body, str):
                data = body.encode("utf-8")

        req = urllib.request.Request(endpoint, data=data, headers=req_headers, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_status = resp.status
                resp_body = resp.read().decode("utf-8", errors="replace")
                resp_headers = dict(resp.headers.items())

                all_secrets = [k.get("secret", "") if isinstance(k, dict) else str(k) for k in keys]
                scrubbed_body = scrub_text(resp_body, all_secrets)
                safe_headers = strip_headers(resp_headers)

                # If rotated successfully, save new active index
                if idx != active_idx:
                    service["active"] = idx
                    save_vault(vault)

                return {
                    "status": resp_status,
                    "headers": safe_headers,
                    "body": scrubbed_body,
                    "usedKeyIndex": idx,
                    "rotated": idx != active_idx,
                }
        except urllib.error.HTTPError as e:
            if e.code in (401, 402, 403, 429) and attempt < attempts - 1:
                # Fail over to next key
                last_err = e
                continue

            err_body = e.read().decode("utf-8", errors="replace")
            all_secrets = [k.get("secret", "") if isinstance(k, dict) else str(k) for k in keys]
            return {
                "status": e.code,
                "headers": strip_headers(dict(e.headers.items())),
                "body": scrub_text(err_body, all_secrets),
                "usedKeyIndex": idx,
                "rotated": idx != active_idx,
                "error": f"HTTP {e.code}",
            }
        except Exception as e:
            last_err = e
            if attempt < attempts - 1:
                continue
            raise VaultRequestError(f"vault HTTP request failed: {e}") from e

    raise VaultRequestError(f"all keys failed for service '{service_id}': {last_err}")


def execute_exec(service_id: str, command: str | list[str], timeout: float = 60.0) -> dict[str, Any]:
    vault = load_vault()
    service = get_service(vault, service_id)
    keys = service.get("keys", [])
    if not keys:
        raise ValueError(f"vault service '{service_id}' has no keys configured")

    active_idx = service.get("active", 0)
    key_obj = keys[active_idx % len(keys)]
    secret = key_obj.get("secret", "") if isinstance(key_obj, dict) else str(key_obj)

    child_env = build_env_for_service(service, secret)

    if isinstance(command, list):
        args = command
        shell = False
    else:
        args = command
        shell = True

    proc = subprocess.run(
        args,
        shell=shell,
        env=child_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )

    all_secrets = [k.get("secret", "") if isinstance(k, dict) else str(k) for k in keys]
    return {
        "code": proc.returncode,
        "stdout": scrub_text(proc.stdout, all_secrets),
        "stderr": scrub_text(proc.stderr, all_secrets),
        "usedKeyIndex": active_idx,
    }
