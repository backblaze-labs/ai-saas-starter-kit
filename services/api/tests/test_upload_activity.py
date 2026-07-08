"""Tests for the upload activity endpoint."""

from datetime import UTC, datetime, timedelta

import pytest

from app.service import files as files_service
from app.types import FileMetadata


def _make_file(key: str, uploaded_at: datetime) -> FileMetadata:
    return FileMetadata(
        key=key,
        filename=key.split("/")[-1],
        folder="uploads/",
        size_bytes=100,
        size_human="100 B",
        content_type="text/plain",
        uploaded_at=uploaded_at,
        url=None,
    )


@pytest.mark.asyncio
async def test_upload_activity_returns_daily_counts(client, monkeypatch):
    now = datetime.now(UTC)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)

    fake_files = [
        _make_file("uploads/a.txt", today),
        _make_file("uploads/b.txt", today),
        _make_file("uploads/c.txt", yesterday),
    ]
    monkeypatch.setattr(files_service, "list_files", lambda prefix, max_keys: fake_files)

    response = await client.get("/files/stats/activity?days=7")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 7

    # Last two entries should match today and yesterday
    date_map = {entry["date"]: entry["uploads"] for entry in data}
    assert date_map[today.date().isoformat()] == 2
    assert date_map[yesterday.date().isoformat()] == 1


@pytest.mark.asyncio
async def test_upload_activity_rejects_invalid_days(client):
    response = await client.get("/files/stats/activity?days=0")
    assert response.status_code == 400

    response = await client.get("/files/stats/activity?days=91")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_upload_activity_fills_missing_days(client, monkeypatch):
    monkeypatch.setattr(files_service, "list_files", lambda prefix, max_keys: [])

    response = await client.get("/files/stats/activity?days=3")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 3
    assert all(entry["uploads"] == 0 for entry in data)
