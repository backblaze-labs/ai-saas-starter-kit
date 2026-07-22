"""Tests for file deletion: error propagation, auth, and ownership scoping."""

import pytest

from app.service import files as files_service

from .conftest import TEST_USER_ID

OWNED_KEY = f"uploads/{TEST_USER_ID}/test.txt"


@pytest.mark.asyncio
async def test_delete_propagates_error(auth_client, monkeypatch):
    monkeypatch.setattr(
        files_service,
        "delete_file",
        lambda key: (_ for _ in ()).throw(RuntimeError("B2 delete failed")),
    )

    response = await auth_client.delete("/files-by-key", params={"key": OWNED_KEY})
    assert response.status_code == 500
    assert "Failed to delete file" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_success(auth_client, monkeypatch):
    monkeypatch.setattr(files_service, "delete_file", lambda key: None)

    response = await auth_client.delete("/files-by-key", params={"key": OWNED_KEY})
    assert response.status_code == 200
    assert response.json()["deleted"] is True


@pytest.mark.asyncio
async def test_delete_foreign_key_404s_without_touching_b2(auth_client, monkeypatch):
    """Deleting another tenant's key returns 404 and never calls the bucket."""
    calls: list[str] = []
    monkeypatch.setattr(files_service, "delete_file", lambda key: calls.append(key))

    response = await auth_client.delete(
        "/files-by-key", params={"key": "uploads/other-user/test.txt"}
    )
    assert response.status_code == 404
    assert calls == []


@pytest.mark.asyncio
async def test_delete_requires_auth(client):
    response = await client.delete("/files-by-key", params={"key": OWNED_KEY})
    assert response.status_code == 401
