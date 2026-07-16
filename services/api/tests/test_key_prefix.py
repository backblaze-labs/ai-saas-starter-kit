"""Tests for key confinement on the by-key routes.

Two independent layers apply:
  1. Per-user ownership (always on): a key must sit under the caller's own
     prefix or the route 404s.
  2. The optional global `allowed_key_prefix` confinement (off by default),
     enforced in `validate_key` as a 400 before ownership is even considered.
"""

from datetime import UTC, datetime

import pytest

from app.config import settings
from app.service import files as files_service
from app.types import FileMetadata

from .conftest import TEST_USER_ID


def _fake_metadata(key: str) -> FileMetadata:
    return FileMetadata(
        key=key,
        filename=key.rsplit("/", 1)[-1],
        folder="uploads/",
        size_bytes=1,
        size_human="1 B",
        content_type="text/plain",
        uploaded_at=datetime.now(UTC),
        url=None,
    )


@pytest.mark.asyncio
async def test_key_outside_allowed_prefix_rejected(auth_client, monkeypatch):
    monkeypatch.setattr(settings, "allowed_key_prefix", "uploads/")
    monkeypatch.setattr(files_service, "get_file_metadata", _fake_metadata)

    resp = await auth_client.get(
        "/files-by-key/metadata", params={"key": "other/secret.txt"}
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_owned_key_inside_allowed_prefix_allowed(auth_client, monkeypatch):
    monkeypatch.setattr(settings, "allowed_key_prefix", "uploads/")
    monkeypatch.setattr(files_service, "get_file_metadata", _fake_metadata)

    key = f"uploads/{TEST_USER_ID}/a.txt"
    resp = await auth_client.get("/files-by-key/metadata", params={"key": key})
    assert resp.status_code == 200
    assert resp.json()["key"] == key


@pytest.mark.asyncio
async def test_unowned_key_404s_by_default(auth_client, monkeypatch):
    """With no global prefix set, ownership still gates by-key access: an
    arbitrary key the caller doesn't own 404s rather than resolving."""
    monkeypatch.setattr(files_service, "get_file_metadata", _fake_metadata)

    resp = await auth_client.get(
        "/files-by-key/metadata", params={"key": "tenant-a/reports/q1.txt"}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_owned_key_allowed_by_default(auth_client, monkeypatch):
    monkeypatch.setattr(files_service, "get_file_metadata", _fake_metadata)

    key = f"generated/{TEST_USER_ID}/2026-07-16/run-1/img.png"
    resp = await auth_client.get("/files-by-key/metadata", params={"key": key})
    assert resp.status_code == 200
    assert resp.json()["key"] == key
