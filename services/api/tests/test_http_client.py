"""Tests for the shared, pooled Supabase httpx client.

These prove the pooling contract that replaced the per-call
`async with httpx.AsyncClient(...)`: one client instance is reused across repo
calls, it is closed idempotently on shutdown, it is lazily recreated when the
lifespan never ran (the test-drive path), and auth still 401s on a bad token
end-to-end through the pooled client.
"""

import httpx
import pytest

from app.config import settings
from app.repo import http_client, supabase_billing


@pytest.fixture(autouse=True)
async def _reset_shared_client():
    """Start and end each test with no shared client so instances never leak
    across event loops (pytest gives each async test its own loop)."""
    await http_client.close_client()
    yield
    await http_client.close_client()


async def test_get_client_returns_same_instance():
    c1 = http_client.get_client()
    c2 = http_client.get_client()
    assert c1 is c2
    assert not c1.is_closed


async def test_close_client_is_idempotent():
    client = http_client.get_client()
    await http_client.close_client()
    assert client.is_closed
    # A second close (e.g. shutdown after a lazy-close) must not raise.
    await http_client.close_client()


async def test_get_client_recreates_after_close():
    first = http_client.get_client()
    await http_client.close_client()
    second = http_client.get_client()
    assert second is not first
    assert not second.is_closed


async def test_shared_client_reused_across_repo_calls(monkeypatch):
    """Two different Supabase repo calls go through the one pooled client."""
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=[])

    shared = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(http_client, "_client", shared)
    monkeypatch.setattr(settings, "supabase_url", "http://sb.test")
    monkeypatch.setattr(settings, "supabase_service_role_key", "svc-key")

    await supabase_billing.list_plans()
    await supabase_billing.get_subscription("u-1")

    # Both hops resolved to the same pooled client, and both were sent.
    assert http_client.get_client() is shared
    assert len(requests) == 2
    await http_client.close_client()


async def test_auth_returns_401_on_bad_token(client, monkeypatch):
    """A bad bearer token still 401s through the real repo/service path when it
    rides the pooled client (error propagation preserved by the refactor)."""

    async def handler(request: httpx.Request) -> httpx.Response:
        # Supabase answers GET /auth/v1/user with 401 for an invalid token.
        return httpx.Response(401, json={"msg": "invalid token"})

    shared = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(http_client, "_client", shared)
    monkeypatch.setattr(settings, "supabase_url", "http://sb.test")

    resp = await client.get("/me", headers={"Authorization": "Bearer bad"})
    assert resp.status_code == 401
    await http_client.close_client()


async def test_auth_returns_401_on_absent_token(client):
    """No Authorization header short-circuits to 401 before any client call."""
    resp = await client.get("/me")
    assert resp.status_code == 401
