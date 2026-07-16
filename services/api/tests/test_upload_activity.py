"""Tests for the upload activity endpoint (per-user scoped, authed)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.service import files as files_service
from app.types import FileMetadata

from .conftest import TEST_USER_ID


def _make_file(key: str, uploaded_at: datetime) -> FileMetadata:
    return FileMetadata(
        key=key,
        filename=key.split("/")[-1],
        folder=key.rsplit("/", 1)[0] + "/",
        size_bytes=100,
        size_human="100 B",
        content_type="text/plain",
        uploaded_at=uploaded_at,
        url=None,
    )


def _prefix_aware(files: list[FileMetadata]):
    return lambda prefix="": [f for f in files if f.key.startswith(prefix)]


@pytest.mark.asyncio
async def test_upload_activity_returns_daily_counts(auth_client, monkeypatch):
    now = datetime.now(UTC)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)

    fake_files = [
        _make_file(f"uploads/{TEST_USER_ID}/a.txt", today),
        _make_file(f"generated/{TEST_USER_ID}/run-1/b.png", today),
        _make_file(f"uploads/{TEST_USER_ID}/c.txt", yesterday),
        # Another user's upload must not be counted.
        _make_file("uploads/other-user/z.txt", today),
    ]
    monkeypatch.setattr(files_service, "list_files", _prefix_aware(fake_files))

    response = await auth_client.get("/files/stats/activity?days=7")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 7

    date_map = {entry["date"]: entry["uploads"] for entry in data}
    assert date_map[today.date().isoformat()] == 2
    assert date_map[yesterday.date().isoformat()] == 1


@pytest.mark.asyncio
async def test_upload_activity_rejects_invalid_days(auth_client):
    response = await auth_client.get("/files/stats/activity?days=0")
    assert response.status_code == 400

    response = await auth_client.get("/files/stats/activity?days=91")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_upload_activity_fills_missing_days(auth_client, monkeypatch):
    monkeypatch.setattr(files_service, "list_files", lambda prefix="": [])

    response = await auth_client.get("/files/stats/activity?days=3")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 3
    assert all(entry["uploads"] == 0 for entry in data)


@pytest.mark.asyncio
async def test_upload_activity_requires_auth(client):
    assert (await client.get("/files/stats/activity")).status_code == 401
