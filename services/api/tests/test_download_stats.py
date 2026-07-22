"""Integration tests for download stats behavior (per-user scoped, authed)."""

from datetime import UTC, datetime

import pytest

from app.repo import counter
from app.service import files as files_service
from app.types import FileMetadata

from .conftest import TEST_USER_ID

OWNED_KEY = f"uploads/{TEST_USER_ID}/test.txt"


def _fake_metadata(key: str) -> FileMetadata:
    return FileMetadata(
        key=key,
        filename=key.rsplit("/", 1)[-1],
        folder="uploads/",
        size_bytes=1024,
        size_human="1.0 KB",
        content_type="text/plain",
        uploaded_at=datetime.now(UTC),
        url=None,
    )


@pytest.mark.asyncio
async def test_downloads_increment_stats(auth_client, monkeypatch):
    monkeypatch.setattr(counter, "_count", 0)
    # get_stats derives file counts from the caller's own listings; the
    # download counter is a separate app-wide value under test here.
    monkeypatch.setattr(files_service, "list_files", lambda prefix="": [])
    monkeypatch.setattr(files_service, "get_file_metadata", _fake_metadata)
    monkeypatch.setattr(
        files_service,
        "get_presigned_url",
        lambda key, filename=None, disposition="attachment": "https://example.com/file",
    )

    response = await auth_client.get("/files/stats")
    assert response.status_code == 200
    assert response.json()["total_downloads"] == 0

    await auth_client.get(f"/files/{OWNED_KEY}/download")
    await auth_client.get(f"/files/{OWNED_KEY}/download")

    response = await auth_client.get("/files/stats")
    assert response.status_code == 200
    assert response.json()["total_downloads"] == 2


@pytest.mark.asyncio
async def test_preview_does_not_increment_downloads(auth_client, monkeypatch):
    """Preview returns a presigned URL without bumping the download counter."""
    monkeypatch.setattr(counter, "_count", 0)
    monkeypatch.setattr(files_service, "get_file_metadata", _fake_metadata)
    monkeypatch.setattr(
        files_service,
        "get_presigned_url",
        lambda key, filename=None, disposition="attachment": "https://example.com/preview",
    )

    for _ in range(3):
        response = await auth_client.get(f"/files/{OWNED_KEY}/preview")
        assert response.status_code == 200
        assert response.json()["url"] == "https://example.com/preview"

    assert files_service.get_download_count() == 0


@pytest.mark.asyncio
async def test_stats_requires_auth(client):
    assert (await client.get("/files/stats")).status_code == 401
