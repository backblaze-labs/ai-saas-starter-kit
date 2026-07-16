"""Tests for the listing: newest-first ordering, per-user union, and auth.

`get_files` unions the caller's own `uploads/{me}/` and `generated/{me}/`
prefixes, so the repo `list_files` fake here is prefix-aware.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.service import files as files_service
from app.types import FileMetadata

from .conftest import TEST_USER_ID


def _make_file(key: str, hours_ago: int) -> FileMetadata:
    return FileMetadata(
        key=key,
        filename=key.split("/")[-1],
        folder=key.rsplit("/", 1)[0] + "/",
        size_bytes=100,
        size_human="100 B",
        content_type="text/plain",
        uploaded_at=datetime.now(UTC) - timedelta(hours=hours_ago),
        url=None,
    )


def _prefix_aware(files: list[FileMetadata]):
    return lambda prefix="": [f for f in files if f.key.startswith(prefix)]


@pytest.mark.asyncio
async def test_recent_uploads_sorted_newest_first(auth_client, monkeypatch):
    """Files are returned newest-first, not alphabetically."""
    fake_files = [
        _make_file(f"uploads/{TEST_USER_ID}/alpha.txt", hours_ago=24),  # oldest
        _make_file(f"uploads/{TEST_USER_ID}/zebra.txt", hours_ago=0),  # newest
        _make_file(f"uploads/{TEST_USER_ID}/middle.txt", hours_ago=12),
    ]
    fake_files.sort(key=lambda f: f.key)  # simulate lexicographic S3 order
    monkeypatch.setattr(files_service, "list_files", _prefix_aware(fake_files))

    response = await auth_client.get("/files?limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["filename"] == "zebra.txt"
    assert data[1]["filename"] == "middle.txt"


@pytest.mark.asyncio
async def test_listing_unions_uploads_and_generated(auth_client, monkeypatch):
    """The caller sees both their uploads and their generated media, newest-first."""
    fake_files = [
        _make_file(f"uploads/{TEST_USER_ID}/doc.txt", hours_ago=5),
        _make_file(f"generated/{TEST_USER_ID}/run-1/img.png", hours_ago=1),
        # Another user's objects must never appear.
        _make_file("uploads/other-user/secret.txt", hours_ago=0),
        _make_file("generated/other-user/run-9/img.png", hours_ago=0),
    ]
    monkeypatch.setattr(files_service, "list_files", _prefix_aware(fake_files))

    response = await auth_client.get("/files")
    assert response.status_code == 200
    keys = [row["key"] for row in response.json()]
    assert keys == [
        f"generated/{TEST_USER_ID}/run-1/img.png",
        f"uploads/{TEST_USER_ID}/doc.txt",
    ]


@pytest.mark.asyncio
async def test_limit_applied_after_sort(auth_client, monkeypatch):
    """Limit slices after the date sort, not before the fetch."""
    fake_files = [
        _make_file(f"uploads/{TEST_USER_ID}/file{i:03d}.txt", hours_ago=100 - i)
        for i in range(20)
    ]
    fake_files.sort(key=lambda f: f.key)
    monkeypatch.setattr(files_service, "list_files", _prefix_aware(fake_files))

    response = await auth_client.get("/files?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 5
    assert data[0]["filename"] == "file019.txt"
    assert data[4]["filename"] == "file015.txt"


@pytest.mark.asyncio
async def test_list_requires_auth(client):
    assert (await client.get("/files")).status_code == 401
