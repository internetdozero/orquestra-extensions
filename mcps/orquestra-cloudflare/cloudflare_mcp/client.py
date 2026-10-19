"""High performance HTTP client for the Cloudflare v4 REST API.

The local ``wrangler`` fallback lives in :mod:`cloudflare_mcp.wrangler` so this
module stays a pure transport layer.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from .config import Settings, load_settings

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class CloudflareAPIError(RuntimeError):
    """Structured error returned by the Cloudflare API."""

    def __init__(self, message: str, *, status: int | None = None,
                 errors: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.errors = errors or []

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"message": str(self)}
        if self.status is not None:
            payload["status"] = self.status
        if self.errors:
            payload["details"] = self.errors[:5]
        return payload


class CloudflareClient:
    """Thin, dependency-light client around the Cloudflare v4 REST API."""

    def __init__(self, settings: Settings | None = None,
                 transport: httpx.BaseTransport | None = None) -> None:
        self.settings = settings or load_settings()
        self._client = httpx.Client(
            base_url=self.settings.base_url,
            timeout=self.settings.timeout,
            transport=transport,
            headers={"Accept": "application/json"},
        )

    # ------------------------------------------------------------------ http
    def _auth_headers(self, content_type: bool = True) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.settings.api_token}"}
        if content_type:
            headers["Content-Type"] = "application/json"
        return headers

    def get_raw(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        """Unvalidated GET used for binary/plain payloads (e.g. KV values)."""
        self.settings.require_credentials()
        return self._client.get(path, params=params,
                                headers=self._auth_headers(content_type=False))

    def request(self, method: str, path: str, *, params: dict[str, Any] | None = None,
                json_body: dict[str, Any] | None = None, content: str | bytes | None = None,
                content_type: str | None = None, raw: bool = False) -> Any:
        """Perform an authenticated request and return the ``result`` payload.

        ``content_type`` labels a raw ``content`` body (KV values are stored
        with the type the caller declares). With ``raw=True`` the complete
        payload is returned, including ``result_info`` pagination metadata.
        """
        self.settings.require_credentials()
        headers = self._auth_headers(content_type=json_body is not None)
        if content_type:
            headers["Content-Type"] = content_type
        attempts = self.settings.max_retries + 1
        last_error: CloudflareAPIError | None = None
        for attempt in range(attempts):
            try:
                response = self._client.request(
                    method, path, params=params, json=json_body,
                    content=None if json_body is not None else content, headers=headers,
                )
            except httpx.HTTPError as exc:
                last_error = CloudflareAPIError(f"transport error: {exc}")
            else:
                if response.status_code in RETRYABLE_STATUS:
                    last_error = CloudflareAPIError(
                        f"HTTP {response.status_code} from {path}",
                        status=response.status_code,
                    )
                    delay = _retry_delay(response, attempt)
                    if attempt + 1 < attempts:
                        time.sleep(delay)
                        continue
                    raise last_error
                payload = self._validate(response)
                return payload if raw else payload.get("result")
            if attempt + 1 < attempts:
                time.sleep(min(2.0 * (attempt + 1), 5.0))
        raise last_error or CloudflareAPIError("request failed")

    @staticmethod
    def _validate(response: httpx.Response) -> dict[str, Any]:
        """Validate a Cloudflare envelope and return the full JSON payload."""
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if payload is None or not isinstance(payload, dict):
            if response.is_success:
                return {"success": True, "result": None, "raw": response.text}
            raise CloudflareAPIError(
                f"HTTP {response.status_code}: {response.text[:300]}", status=response.status_code
            )
        if payload.get("success", response.is_success) and response.is_success:
            return payload
        errors = payload.get("errors") or []
        message = "; ".join(
            str(err.get("message", err)) for err in errors
        ) or f"Cloudflare API call failed with status {response.status_code}"
        raise CloudflareAPIError(message, status=response.status_code, errors=errors)

    def get_full(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET returning the complete response envelope (incl. result_info)."""
        return self.request("GET", path, params=params, raw=True)

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self.request("GET", path, params=params)

    def post(self, path: str, body: dict[str, Any] | None = None,
             params: dict[str, Any] | None = None) -> Any:
        return self.request("POST", path, json_body=body, params=params)

    def put(self, path: str, body: dict[str, Any] | None = None) -> Any:
        return self.request("PUT", path, json_body=body)

    def patch(self, path: str, body: dict[str, Any] | None = None) -> Any:
        return self.request("PATCH", path, json_body=body)

    def delete(self, path: str) -> Any:
        return self.request("DELETE", path)

    # ------------------------------------------------------------ account id
    @property
    def account_id(self) -> str:
        if self.settings.account_id:
            return self.settings.account_id
        if not self.settings.api_token:
            self.settings.require_credentials()
        discovered = getattr(self, "_discovered_account_id", None)
        if discovered:
            return discovered
        try:
            accounts = self.get("/accounts")
            if accounts and isinstance(accounts, list) and isinstance(accounts[0], dict) and accounts[0].get("id"):
                self._discovered_account_id = str(accounts[0]["id"])
                return self._discovered_account_id
        except Exception:
            pass
        self.settings.require_credentials()
        assert self.settings.account_id
        return self.settings.account_id

    def account_path(self, suffix: str) -> str:
        return f"/accounts/{self.account_id}{suffix}"

    # -------------------------------------------------------------- pagination
    def paginate(self, path: str, params: dict[str, Any] | None = None,
                 *, max_pages: int = 10, per_page: int = 50) -> list[Any]:
        """Collect all items across ``result_info`` pages (bounded)."""
        collected: list[Any] = []
        query = dict(params or {})
        query.setdefault("per_page", per_page)
        for page in range(1, max_pages + 1):
            query["page"] = page
            payload = self.get_full(path, query)
            result = payload.get("result")
            if isinstance(result, list):
                collected.extend(result)
            info = payload.get("result_info") or {}
            if not info.get("has_more"):
                break
        return collected

    # --------------------------------------------------------------- close
    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "CloudflareClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("retry-after")
    if retry_after:
        try:
            return min(float(retry_after), 10.0)
        except ValueError:
            pass
    return min(1.0 * (attempt + 1), 5.0)
