"""Supabase access helpers.

Two access paths:

* ``user_client(token)``  — talks to PostgREST *as the signed-in user* using their
  JWT, so Row-Level Security applies. This is the default for request handling.
* ``service_client()``    — uses the service-role key for privileged, audited,
  multi-step transactions only. Never expose this to a browser.

Both use PostgREST over HTTP; no heavy SDK dependency is required.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings


class SupabaseConfigError(RuntimeError):
    """Raised when required Supabase environment configuration is missing."""


def _require(value: str, name: str) -> str:
    if not value:
        raise SupabaseConfigError(f"Missing required setting: {name}")
    return value


class PostgrestClient:
    """Thin async PostgREST client bound to a single access token."""

    def __init__(self, base_url: str, api_key: str, token: str | None = None) -> None:
        self._base = base_url.rstrip("/")
        self._api_key = api_key
        self._token = token or api_key

    def _headers(self, *, prefer: str | None = None) -> dict[str, str]:
        headers = {
            "apikey": self._api_key,
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        return headers

    async def select(
        self,
        table: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        url = f"{self._base}/rest/v1/{table}"
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url, headers=self._headers(), params=params or {})
            resp.raise_for_status()
            return resp.json()

    async def insert(
        self,
        table: str,
        payload: dict[str, Any] | list[dict[str, Any]],
        *,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        url = f"{self._base}/rest/v1/{table}"
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                url,
                headers=self._headers(prefer="return=representation"),
                params=params or {},
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    async def update(
        self,
        table: str,
        payload: dict[str, Any],
        *,
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        url = f"{self._base}/rest/v1/{table}"
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.patch(
                url,
                headers=self._headers(prefer="return=representation"),
                params=params,
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    async def rpc(
        self,
        function: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self._base}/rest/v1/rpc/{function}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                url,
                headers=self._headers(),
                json=payload or {},
            )
            resp.raise_for_status()
            if not resp.content:
                return None
            return resp.json()


def user_client(token: str) -> PostgrestClient:
    url = _require(settings.supabase_url, "SUPABASE_URL")
    anon = _require(settings.supabase_anon_key, "SUPABASE_ANON_KEY")
    return PostgrestClient(url, anon, token=token)


def service_client() -> PostgrestClient:
    url = _require(settings.supabase_url, "SUPABASE_URL")
    service = _require(settings.supabase_service_role_key, "SUPABASE_SERVICE_ROLE_KEY")
    return PostgrestClient(url, service)
