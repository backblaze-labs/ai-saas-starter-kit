"""Tests for the optional allowed_key_prefix confinement (off by default)."""

from datetime import UTC, datetime

import pytest

from app.config import settings
from app.service import files as files_service
from app.types import FileMetadata


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
async def test_key_outside_allowed_prefix_rejected(client, monkeypatch):
    monkeypatch.setattr(settings, "allowed_key_prefix", "uploads/")
    monkeypatch.setattr(files_service, "get_file_metadata", _fake_metadata)

    resp = await client.get(
        "/files-by-key/metadata", params={"key": "other/secret.txt"}
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_key_inside_allowed_prefix_allowed(client, monkeypatch):
    monkeypatch.setattr(settings, "allowed_key_prefix", "uploads/")
    monkeypatch.setattr(files_service, "get_file_metadata", _fake_metadata)

    resp = await client.get(
        "/files-by-key/metadata", params={"key": "uploads/a.txt"}
    )
    assert resp.status_code == 200
    assert resp.json()["key"] == "uploads/a.txt"


@pytest.mark.asyncio
async def test_arbitrary_key_allowed_by_default(client, monkeypatch):
    # Default (empty prefix) preserves the by-key routes' arbitrary-key support.
    monkeypatch.setattr(files_service, "get_file_metadata", _fake_metadata)

    resp = await client.get(
        "/files-by-key/metadata", params={"key": "tenant-a/reports/q1.txt"}
    )
    assert resp.status_code == 200
