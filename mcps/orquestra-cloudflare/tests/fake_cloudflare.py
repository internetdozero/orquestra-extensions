"""In-process fake for the Cloudflare v4 REST API.

Every test routes its HTTP through :class:`FakeCloudflare`, so the suite never
touches the network and never needs a real token. Routes are registered per
(method, path); an unregistered route fails loudly with a Cloudflare-shaped 404
so a typo in a path cannot silently pass.
"""

from __future__ import annotations

from typing import Any, Iterable

import httpx


def envelope(
    result: Any = None,
    *,
    success: bool = True,
    errors: list[dict[str, Any]] | None = None,
    result_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """A Cloudflare response body with the real envelope shape."""
    payload: dict[str, Any] = {
        "success": success,
        "result": result,
        "errors": errors or [],
        "messages": [],
    }
    if result_info is not None:
        payload["result_info"] = result_info
    return payload


class FakeCloudflare:
    """Registers canned responses and records every request it receives."""

    def __init__(self) -> None:
        self.calls: list[httpx.Request] = []
        self._routes: dict[tuple[str, str], list[httpx.Response]] = {}

    # ------------------------------------------------------------- registering
    def add(
        self,
        method: str,
        path: str,
        result: Any = None,
        *,
        success: bool = True,
        status: int = 200,
        errors: list[dict[str, Any]] | None = None,
        result_info: dict[str, Any] | None = None,
    ) -> "FakeCloudflare":
        body = envelope(result, success=success, errors=errors, result_info=result_info)
        return self.add_raw(method, path, httpx.Response(status, json=body))

    def add_raw(self, method: str, path: str, response: httpx.Response) -> "FakeCloudflare":
        self._routes[(method.upper(), path)] = [response]
        return self

    def add_sequence(
        self, method: str, path: str, responses: Iterable[httpx.Response]
    ) -> "FakeCloudflare":
        """Queue responses; the last one repeats once the queue is exhausted."""
        queued = list(responses)
        if not queued:
            raise ValueError("add_sequence needs at least one response")
        self._routes[(method.upper(), path)] = queued
        return self

    # --------------------------------------------------------------- transport
    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        queued = self._routes.get((request.method, request.url.path))
        if not queued:
            return httpx.Response(
                404,
                json=envelope(
                    success=False,
                    errors=[
                        {
                            "code": 1000,
                            "message": f"no fake route for {request.method} {request.url.path}",
                        }
                    ],
                ),
            )
        if len(queued) > 1:
            return queued.pop(0)
        return queued[0]

    # ------------------------------------------------------------------ helpers
    @property
    def paths(self) -> list[tuple[str, str]]:
        return [(call.method, call.url.path) for call in self.calls]

    def requests_for(self, method: str, path: str) -> list[httpx.Request]:
        return [
            call
            for call in self.calls
            if call.method == method.upper() and call.url.path == path
        ]

    def last_request(self) -> httpx.Request:
        return self.calls[-1]
