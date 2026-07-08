"""Tests for file deletion error propagation."""

from datetime import UTC, datetime

import pytest

from app.service import files as files_service
from app.types import FileMetadata


def _fake_metadata(key: str) -> FileMetadata:
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


@pytest.mark.asyncio
async def test_delete_propagates_error(client, monkeypatch):
    monkeypatch.setattr(files_service, "get_file_metadata", _fake_metadata)
    monkeypatch.setattr(
        files_service,
        "delete_file",
        lambda key: (_ for _ in ()).throw(RuntimeError("B2 delete failed")),
    )

    response = await client.delete("/files/uploads/test.txt")
    assert response.status_code == 500
    assert "Failed to delete file" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_success(client, monkeypatch):
    monkeypatch.setattr(files_service, "get_file_metadata", _fake_metadata)
    monkeypatch.setattr(files_service, "delete_file", lambda key: None)

    response = await client.delete("/files/uploads/test.txt")
    assert response.status_code == 200
    assert response.json()["deleted"] is True
