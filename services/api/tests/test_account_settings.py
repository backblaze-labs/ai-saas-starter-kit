"""Tests for the account settings routes and persistence."""

import pytest

from app.types.account import UpdateSettingsRequest, UserSettings


@pytest.mark.asyncio
async def test_get_settings_requires_auth(client):
    resp = await client.get("/account/settings")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_patch_settings_requires_auth(client):
    resp = await client.patch("/account/settings", json={"theme": "dark"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_settings_returns_values(auth_client, monkeypatch):
    from app.service import account as account_service

    async def fake_get_settings(access_token, user_id):
        assert user_id == "u-test"
        assert access_token == "tok" # auth_client doesn't send a token, but the Depends override returns one
        return UserSettings(
            display_name="Test User",
            bio="Hello",
            theme="dark",
            default_view="list",
            email_on_upload=True,
            warn_near_quota=False,
            quota_threshold=90,
        )

    monkeypatch.setattr(account_service, "get_settings", fake_get_settings)

    # Note: the auth_client fixture overrides get_current_user to return an
    # AuthUser that doesn't have a token. We need to patch the dependency to return
    # a token for this test.
    from app.runtime.auth import get_current_user
    from app.types.auth import AuthUser
    from main import app

    app.dependency_overrides[get_current_user] = lambda: AuthUser(
        id="u-test", email="test@example.com", role="user", token="tok"
    )

    try:
        resp = await auth_client.get("/account/settings")
        assert resp.status_code == 200
        assert resp.json() == {
            "display_name": "Test User",
            "bio": "Hello",
            "theme": "dark",
            "default_view": "list",
            "email_on_upload": True,
            "warn_near_quota": False,
            "quota_threshold": 90,
        }
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_patch_settings_updates_fields(auth_client, monkeypatch):
    from app.service import account as account_service

    async def fake_update_settings(access_token, user_id, patch):
        assert user_id == "u-test"
        # Validate that the patch only includes the fields sent
        assert patch.theme == "light"
        assert patch.bio is None
        # Return a full settings object (as if updated in the DB)
        return UserSettings(theme="light")

    monkeypatch.setattr(account_service, "update_settings", fake_update_settings)
    
    from app.runtime.auth import get_current_user
    from app.types.auth import AuthUser
    from main import app

    app.dependency_overrides[get_current_user] = lambda: AuthUser(
        id="u-test", email="test@example.com", role="user", token="tok"
    )

    try:
        resp = await auth_client.patch("/account/settings", json={"theme": "light"})
        assert resp.status_code == 200
        assert resp.json()["theme"] == "light"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_patch_settings_rejects_invalid_theme(auth_client):
    # Fails Pydantic validation before reaching the service layer
    resp = await auth_client.patch("/account/settings", json={"theme": "neon"})
    assert resp.status_code == 422
    assert "Input should be 'light', 'dark' or 'system'" in resp.text
