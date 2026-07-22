"""Tests for the auth dependency and the /me endpoint.

Supabase validation itself is an external call (repo layer); here we stub it at
the service boundary so the dependency/route behavior is covered hermetically.
"""

import pytest
from fastapi import HTTPException

from app.config import settings
from app.runtime.auth import require_admin
from app.types.auth import AuthUser


@pytest.mark.asyncio
async def test_me_requires_bearer(client):
    resp = await client.get("/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_rejects_non_bearer_scheme(client):
    resp = await client.get("/me", headers={"Authorization": "Basic Zm9v"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_identity_for_valid_token(client, monkeypatch):
    async def fake_user_from_token(token: str):
        assert token == "good-token"
        return AuthUser(id="u-1", email="user@example.com", role="admin")

    from app.service import auth as auth_service

    monkeypatch.setattr(auth_service, "user_from_token", fake_user_from_token)

    resp = await client.get("/me", headers={"Authorization": "Bearer good-token"})
    assert resp.status_code == 200
    assert resp.json() == {"id": "u-1", "email": "user@example.com", "role": "admin"}


@pytest.mark.asyncio
async def test_me_rejects_invalid_token(client, monkeypatch):
    async def fake_user_from_token(token: str):
        return None

    from app.service import auth as auth_service

    monkeypatch.setattr(auth_service, "user_from_token", fake_user_from_token)

    resp = await client.get("/me", headers={"Authorization": "Bearer nope"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_require_admin_rejects_non_admin():
    with pytest.raises(HTTPException) as exc:
        await require_admin(AuthUser(id="u", email=None, role="user"))
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_require_admin_allows_admin():
    admin = AuthUser(id="u", email=None, role="admin")
    assert await require_admin(admin) is admin


# --- Identity cache (service layer) -------------------------------------------
#
# These exercise user_from_token directly, stubbing the repo round-trips with
# call counters. The contract under test: identity (GET /auth/v1/user) is cached
# for a short TTL, but the role (GET /rest/v1/profiles) is fetched live EVERY
# request so an authorization decision is never stale.


def _counting_repo_stubs(monkeypatch, *, user=None, role="user"):
    """Stub the two Supabase repo calls with [user_calls, role_calls] counters."""
    from app.repo import supabase_auth

    counts = {"user": 0, "role": 0}

    async def fake_fetch_user(_token):
        counts["user"] += 1
        return user

    async def fake_fetch_profile_role(_token, _user_id):
        counts["role"] += 1
        return role

    monkeypatch.setattr(supabase_auth, "fetch_user", fake_fetch_user)
    monkeypatch.setattr(supabase_auth, "fetch_profile_role", fake_fetch_profile_role)
    return counts


@pytest.fixture
def auth_service():
    """The auth service module with its identity cache cleared before/after."""
    from app.service import auth as auth_service

    auth_service._reset_cache()
    try:
        yield auth_service
    finally:
        auth_service._reset_cache()


@pytest.mark.asyncio
async def test_identity_cached_but_role_fetched_live(auth_service, monkeypatch):
    """Within TTL the identity endpoint is hit ONCE; the role is re-fetched."""
    monkeypatch.setattr(settings, "auth_cache_ttl_seconds", 30)
    counts = _counting_repo_stubs(monkeypatch, user={"id": "u-1", "email": "a@b.co"})

    first = await auth_service.user_from_token("tok")
    second = await auth_service.user_from_token("tok")

    assert first == second == AuthUser(id="u-1", email="a@b.co", role="user")
    assert counts["user"] == 1  # identity served from cache on the 2nd call
    assert counts["role"] == 2  # role always fetched live


@pytest.mark.asyncio
async def test_identity_cache_expiry_rehits_identity(auth_service, monkeypatch):
    """After the TTL lapses, the identity endpoint is hit again."""
    monkeypatch.setattr(settings, "auth_cache_ttl_seconds", 30)
    counts = _counting_repo_stubs(monkeypatch, user={"id": "u-1", "email": None})

    clock = {"t": 1000.0}
    monkeypatch.setattr(auth_service.time, "monotonic", lambda: clock["t"])

    await auth_service.user_from_token("tok")
    clock["t"] += 31  # advance past the 30s TTL
    await auth_service.user_from_token("tok")

    assert counts["user"] == 2  # entry expired, identity re-fetched
    assert counts["role"] == 2


@pytest.mark.asyncio
async def test_invalid_token_not_cached_as_valid(auth_service, monkeypatch):
    """A bad token returns None every time — never cached, role never reached."""
    monkeypatch.setattr(settings, "auth_cache_ttl_seconds", 30)
    counts = _counting_repo_stubs(monkeypatch, user=None)

    assert await auth_service.user_from_token("bad") is None
    assert await auth_service.user_from_token("bad") is None

    assert counts["user"] == 2  # re-validated each call (not cached as valid)
    assert counts["role"] == 0  # never reached for an invalid token
    assert auth_service._identity_cache == {}


@pytest.mark.asyncio
async def test_ttl_zero_disables_cache(auth_service, monkeypatch):
    """TTL=0 disables caching: identity is hit on every request."""
    monkeypatch.setattr(settings, "auth_cache_ttl_seconds", 0)
    counts = _counting_repo_stubs(monkeypatch, user={"id": "u-1", "email": "a@b.co"})

    await auth_service.user_from_token("tok")
    await auth_service.user_from_token("tok")

    assert counts["user"] == 2  # no caching — identity fetched every time
    assert counts["role"] == 2
    assert auth_service._identity_cache == {}  # nothing stored


def test_cache_is_bounded_and_purges_expired_first(auth_service, monkeypatch):
    """The store caps the cache: expired entries are purged first, and if still
    at capacity the soonest-to-expire live entry is evicted — so token churn
    can't grow the dict unboundedly."""
    clock = {"t": 1000.0}
    monkeypatch.setattr(auth_service.time, "monotonic", lambda: clock["t"])
    monkeypatch.setattr(auth_service, "_IDENTITY_CACHE_MAX", 3)

    # Fill to capacity with live entries (ttl 100 → expire at 1100).
    for i in range(3):
        auth_service._store_identity(f"k{i}", (f"u-{i}", None), ttl=100)
    assert len(auth_service._identity_cache) == 3

    # A new key at capacity with everything live evicts the soonest-to-expire
    # (k0, stored first) — never exceeding the cap.
    auth_service._store_identity("k-new", ("u-new", None), ttl=100)
    assert len(auth_service._identity_cache) == 3
    assert "k0" not in auth_service._identity_cache
    assert "k-new" in auth_service._identity_cache

    # Advance past the live entries' expiry; a further store purges the expired
    # ones instead of evicting a live entry, and stays bounded.
    clock["t"] = 1200.0
    auth_service._store_identity("k-fresh", ("u-fresh", None), ttl=100)
    assert len(auth_service._identity_cache) == 1
    assert "k-fresh" in auth_service._identity_cache
