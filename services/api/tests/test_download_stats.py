"""Integration tests for download stats behavior."""

from datetime import UTC, datetime

import pytest

from app.service import files as files_service
from app.types import FileMetadata


@pytest.mark.asyncio
async def test_downloads_increment_stats(client, monkeypatch):
    monkeypatch.setattr(files_service, "_download_count", 0)
    monkeypatch.setattr(
        files_service,
        "get_upload_stats",
        lambda: {
            "total_files": 2,
            "total_size_bytes": 2048,
            "total_size_human": "2.0 KB",
            "uploads_today": 2,
        },
    )

    def fake_metadata(key: str) -> FileMetadata:
        return FileMetadata(
            key=key,
            filename="test.txt",
            folder="uploads/",
            size_bytes=1024,
            size_human="1.0 KB",
            content_type="text/plain",
            uploaded_at=datetime.now(UTC),
            url=None,
        )

    monkeypatch.setattr(files_service, "get_file_metadata", fake_metadata)
    monkeypatch.setattr(
        files_service,
        "get_presigned_url",
        lambda key, filename=None: "https://example.com/file",
    )

    response = await client.get("/files/stats")
    assert response.status_code == 200
    assert response.json()["total_downloads"] == 0

    await client.get("/files/uploads/test.txt/download")
    await client.get("/files/uploads/test.txt/download")

    response = await client.get("/files/stats")
    assert response.status_code == 200
    assert response.json()["total_downloads"] == 2


@pytest.mark.asyncio
async def test_preview_does_not_increment_downloads(client, monkeypatch):
    """Preview returns a presigned URL without bumping the download counter."""
    monkeypatch.setattr(files_service, "_download_count", 0)

    def fake_metadata(key: str) -> FileMetadata:
        return FileMetadata(
            key=key,
            filename="test.png",
            folder="uploads/",
            size_bytes=1024,
            size_human="1.0 KB",
            content_type="image/png",
            uploaded_at=datetime.now(UTC),
            url=None,
        )

    monkeypatch.setattr(files_service, "get_file_metadata", fake_metadata)
    monkeypatch.setattr(
        files_service,
        "get_presigned_url",
        lambda key, filename=None: "https://example.com/preview",
    )

    for _ in range(3):
        response = await client.get("/files/uploads/test.png/preview")
        assert response.status_code == 200
        assert response.json()["url"] == "https://example.com/preview"

    assert files_service.get_download_count() == 0
