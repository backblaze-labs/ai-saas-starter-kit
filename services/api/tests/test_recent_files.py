"""Tests for recent files ordering — most recent first, regardless of key name."""

from datetime import UTC, datetime, timedelta

import pytest

from app.service import files as files_service
from app.types import FileMetadata


def _make_file(key: str, hours_ago: int) -> FileMetadata:
    return FileMetadata(
        key=key,
        filename=key.split("/")[-1],
        folder="uploads/",
        size_bytes=100,
        size_human="100 B",
        content_type="text/plain",
        uploaded_at=datetime.now(UTC) - timedelta(hours=hours_ago),
        url=None,
    )


@pytest.mark.asyncio
async def test_recent_uploads_sorted_newest_first(client, monkeypatch):
    """Files are returned newest-first, not alphabetically."""
    fake_files = [
        _make_file("uploads/alpha.txt", hours_ago=24),  # oldest
        _make_file("uploads/zebra.txt", hours_ago=0),  # newest
        _make_file("uploads/middle.txt", hours_ago=12),
    ]
    # Simulate S3 returning in lexicographic order (alpha, middle, zebra)
    fake_files.sort(key=lambda f: f.key)
    monkeypatch.setattr(
        files_service, "list_files", lambda prefix, max_keys: fake_files
    )

    response = await client.get("/files?limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # Newest file should be first even though it's last alphabetically
    assert data[0]["filename"] == "zebra.txt"
    assert data[1]["filename"] == "middle.txt"


@pytest.mark.asyncio
async def test_limit_applied_after_sort(client, monkeypatch):
    """Limit slices after date sort, not before S3 fetch."""
    fake_files = [
        _make_file(f"uploads/file{i:03d}.txt", hours_ago=100 - i)
        for i in range(20)
    ]
    # S3 returns lexicographic order
    fake_files.sort(key=lambda f: f.key)
    monkeypatch.setattr(
        files_service, "list_files", lambda prefix, max_keys: fake_files
    )

    response = await client.get("/files?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 5
    # The 5 most recent by upload time (file019, file018, file017, ...)
    assert data[0]["filename"] == "file019.txt"
    assert data[4]["filename"] == "file015.txt"
