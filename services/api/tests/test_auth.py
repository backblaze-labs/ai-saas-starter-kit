"""Tests for the auth dependency and the /me endpoint.

Supabase validation itself is an external call (repo layer); here we stub it at
the service boundary so the dependency/route behavior is covered hermetically.
"""

import pytest
from fastapi import HTTPException

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
