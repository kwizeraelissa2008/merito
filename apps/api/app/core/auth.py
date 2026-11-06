"""Authentication & authorization dependencies for FastAPI.

The frontend passes the Supabase access token as a Bearer credential. We verify
the signature, then resolve the caller's school memberships from the database.

Token verification supports both Supabase token styles:

* **Asymmetric (hosted default)** — the project signs tokens with a private key
  and publishes the public keys at ``/auth/v1/.well-known/jwks.json`` (RS256 /
  ES256). We verify against the JWKS, cached per process.
* **Legacy HS256** — projects that still use the shared JWT secret are verified
  against ``SUPABASE_JWT_SECRET`` (this is also what local development uses).

If both are configured, JWKS is tried first.

Authorization is deny-by-default: a request must name a school and the caller
must hold a required role in that school. Client-supplied role claims are never
trusted.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Annotated, Any, Iterable

import httpx
from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from jose.constants import ALGORITHMS
from jose.exceptions import JWKError

from app.core.config import settings
from app.core.supabase import PostgrestClient, service_client, user_client

# Algorithms we are willing to verify. Never accept "none".
_ASYMMETRIC_ALGS = (ALGORITHMS.RS256, ALGORITHMS.ES256, ALGORITHMS.RS384, ALGORITHMS.RS512)


@dataclass(frozen=True)
class CurrentUser:
    id: uuid.UUID
    email: str
    token: str


class _JwksCache:
    """Small in-process cache for the project's JWKS document."""

    def __init__(self, ttl_seconds: int = 600) -> None:
        self._ttl = ttl_seconds
        self._fetched_at: float = 0.0
        self._document: dict[str, Any] | None = None

    async def get(self) -> dict[str, Any]:
        now = time.monotonic()
        if self._document is not None and now - self._fetched_at < self._ttl:
            return self._document
        url = settings.supabase_jwks_url
        if not url:
            raise JWTError("No JWKS URL configured")
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            self._document = resp.json()
        self._fetched_at = now
        return self._document


_jwks = _JwksCache()


def _key_candidates(jwks: dict[str, Any]) -> list[dict[str, Any]]:
    keys = jwks.get("keys") if isinstance(jwks, dict) else None
    if not isinstance(keys, list):
        raise JWTError("Malformed JWKS document")
    return [k for k in keys if isinstance(k, dict)]


async def _decode_with_jwks(token: str) -> dict[str, Any]:
    jwks = await _jwks.get()
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    candidates = _key_candidates(jwks)

    last_error: Exception | None = None
    for key in candidates:
        if kid and key.get("kid") != kid:
            continue
        try:
            return jwt.decode(
                token,
                key,
                algorithms=list(_ASYMMETRIC_ALGS),
                audience="authenticated",
            )
        except (JWTError, JWKError) as exc:  # try the next key
            last_error = exc
    raise last_error or JWTError("No matching signing key found for token")


async def _decode_token(token: str) -> dict[str, Any]:
    """Verify a Supabase access token. Fail closed when no verifier is set."""
    if settings.supabase_jwks_url:
        try:
            return await _decode_with_jwks(token)
        except (JWTError, JWKError, httpx.HTTPError) as exc:
            if not settings.supabase_jwt_secret:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token",
                ) from exc

    if not settings.supabase_jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server authentication is not configured",
        )

    try:
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=[ALGORITHMS.HS256],
            audience="authenticated",
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> CurrentUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    token = authorization.split(" ", 1)[1].strip()

    claims = await _decode_token(token)

    sub = claims.get("sub")
    email = claims.get("email", "")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )

    return CurrentUser(id=uuid.UUID(sub), email=str(email), token=token)


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def client_for(user: CurrentUser) -> PostgrestClient:
    """RLS-scoped client for the current user."""
    return user_client(user.token)


async def active_roles(user: CurrentUser, school_id: uuid.UUID) -> set[str]:
    """Return the caller's active membership roles in the given school.

    Uses the service client for a deterministic read of memberships; the result
    is still the caller's real membership, not a client-supplied claim.
    """
    rows = await service_client().select(
        "school_memberships",
        params={
            "select": "role,status",
            "school_id": f"eq.{school_id}",
            "user_id": f"eq.{user.id}",
            "status": "eq.active",
        },
    )
    return {row["role"] for row in rows}


async def require_school_role(
    user: CurrentUser,
    school_id: uuid.UUID,
    allowed: Iterable[str],
) -> set[str]:
    roles = await active_roles(user, school_id)
    if not roles.intersection(set(allowed)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action in this school",
        )
    return roles


def parse_school_id(school_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(school_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid school id",
        ) from exc
