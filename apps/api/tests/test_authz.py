"""Authorization boundary tests for FastAPI configuration routes.

Verifies deny-by-default behaviour: requests without a token are rejected, and
tokens are never trusted without verification. No live database is required.
"""

import pytest
from fastapi import HTTPException

from app.core.auth import get_current_user


@pytest.mark.asyncio
async def test_missing_authorization_header_is_unauthorized():
    with pytest.raises(HTTPException) as exc:
        await get_current_user(None)
    assert exc.value.status_code == 401
    assert "bearer" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_non_bearer_scheme_is_unauthorized():
    with pytest.raises(HTTPException) as exc:
        await get_current_user("Basic abc123")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_garbage_bearer_token_is_unauthorized_hs256(monkeypatch):
    # HS256 mode: no JWKS URL, a shared secret is set, token is invalid.
    from app.core import auth

    monkeypatch.setattr(auth.settings, "supabase_jwt_secret", "test-secret")
    monkeypatch.setattr(auth.settings, "supabase_jwks_url", "")
    with pytest.raises(HTTPException) as exc:
        await get_current_user("Bearer not.a.valid.jwt")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_missing_all_verifiers_fails_closed(monkeypatch):
    # No JWKS and no shared secret → server misconfiguration, 500 (fail closed).
    from app.core import auth

    monkeypatch.setattr(auth.settings, "supabase_jwt_secret", "")
    monkeypatch.setattr(auth.settings, "supabase_jwks_url", "")
    with pytest.raises(HTTPException) as exc:
        await get_current_user("Bearer something")
    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_jwks_mode_rejects_garbage(monkeypatch):
    # JWKS configured but token malformed → 401 (no HS256 fallback configured).
    from app.core import auth

    monkeypatch.setattr(auth.settings, "supabase_jwt_secret", "")
    monkeypatch.setattr(auth.settings, "supabase_jwks_url", "https://example.test/jwks.json")
    with pytest.raises(HTTPException) as exc:
        await get_current_user("Bearer not.a.valid.jwt")
    assert exc.value.status_code == 401
