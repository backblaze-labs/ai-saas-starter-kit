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


@pytest.mark.asyncio
async def test_revoked_token_on_warm_cache_is_rejected(auth_service, monkeypatch):
    """A1: on a warm identity-cache hit the token isn't re-validated by fetch_user,
    so the live role call is the only place an expired/revoked token surfaces. A
    401/403 there (TokenRejected) must REJECT the request (not default to role
    'user') and evict the cached identity so the stale token can't re-authorize."""
    from app.repo import supabase_auth

    monkeypatch.setattr(settings, "auth_cache_ttl_seconds", 30)
    state = {"reject": False, "user_calls": 0}

    async def fake_fetch_user(_token):
        state["user_calls"] += 1
        return {"id": "u-1", "email": "a@b.co"}

    async def fake_fetch_profile_role(_token, _uid):
        if state["reject"]:
            raise supabase_auth.TokenRejected()
        return "user"

    monkeypatch.setattr(supabase_auth, "fetch_user", fake_fetch_user)
    monkeypatch.setattr(supabase_auth, "fetch_profile_role", fake_fetch_profile_role)

    # 1. Warm the cache with a valid request.
    assert (await auth_service.user_from_token("tok")).id == "u-1"
    assert state["user_calls"] == 1

    # 2. Token now revoked/expired → live role call 401s → reject + evict.
    state["reject"] = True
    assert await auth_service.user_from_token("tok") is None
    assert auth_service._identity_cache == {}, "cached identity not evicted on reject"

    # 3. After eviction the next attempt goes cold (re-validates via fetch_user).
    state["reject"] = False
    assert (await auth_service.user_from_token("tok")).id == "u-1"
    assert state["user_calls"] == 2


@pytest.mark.asyncio
async def test_transient_role_fetch_failure_does_not_log_out(auth_service, monkeypatch):
    """A transient 5xx on the role call (repo returns None, NOT TokenRejected)
    must degrade to the default role — never evict the identity or 401 the user.
    This is the regression guard against a PostgREST blip mass-logging users out."""
    monkeypatch.setattr(settings, "auth_cache_ttl_seconds", 30)
    # role=None models a 5xx/empty result (the repo maps both to None).
    counts = _counting_repo_stubs(monkeypatch, user={"id": "u-1", "email": None}, role=None)

    result = await auth_service.user_from_token("tok")
    assert result == AuthUser(id="u-1", email=None, role="user")
    assert counts["role"] == 1
    # Identity stays cached — a transient failure is not a rejection.
    assert auth_service._identity_cache != {}


def test_effective_ttl_is_clamped_to_ceiling(auth_service, monkeypatch):
    """A2: a misconfigured large AUTH_CACHE_TTL_SECONDS is capped so identity
    staleness stays bounded (token validity is enforced live regardless)."""
    monkeypatch.setattr(settings, "auth_cache_ttl_seconds", 100_000)
    assert auth_service._effective_ttl() == auth_service._AUTH_CACHE_TTL_CEILING
    monkeypatch.setattr(settings, "auth_cache_ttl_seconds", 30)
    assert auth_service._effective_ttl() == 30
    monkeypatch.setattr(settings, "auth_cache_ttl_seconds", 0)
    assert auth_service._effective_ttl() == 0  # 0 still disables the cache


@pytest.mark.asyncio
async def test_fetch_profile_role_maps_status_codes(monkeypatch):
    """The load-bearing 401/403-vs-5xx split the cache-eviction fix hinges on,
    tested against real HTTP responses (not stubbed at the service boundary):
    a rejected token raises TokenRejected; a transient 5xx (or an empty result)
    returns None so the caller degrades to the default role rather than logging
    the user out."""
    import httpx

    from app.repo import http_client, supabase_auth

    monkeypatch.setattr(supabase_auth.settings, "supabase_url", "https://db.example")
    monkeypatch.setattr(supabase_auth.settings, "supabase_anon_key", "anon")

    def use_response(status: int, body) -> httpx.AsyncClient:
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _req: httpx.Response(status, json=body))
        )
        monkeypatch.setattr(http_client, "get_client", lambda: client)
        return client

    async def role_for(status: int, body):
        client = use_response(status, body)
        try:
            return await supabase_auth.fetch_profile_role("tok", "u-1")
        finally:
            await client.aclose()

    assert await role_for(200, [{"role": "admin"}]) == "admin"
    assert await role_for(200, []) is None  # no profile row
    assert await role_for(500, {}) is None  # transient — degrade, don't reject
    assert await role_for(503, {}) is None

    for code in (401, 403):
        client = use_response(code, {})
        try:
            with pytest.raises(supabase_auth.TokenRejected):
                await supabase_auth.fetch_profile_role("tok", "u-1")
        finally:
            await client.aclose()


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
