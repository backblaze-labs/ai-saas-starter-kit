from datetime import UTC, datetime

import pytest

from app.service import files as files_service
from app.types import FileMetadata

VALID_KEYS = [
    "folder/file.txt",
    "folder/file #1?.txt",
    "folder/100% complete.txt",
    "stats",
    "stats/activity",
    "tenant-a/reports/download",
    "tenant-a/reports/preview",
]

INVALID_KEYS = [
    "",
    "../secret.txt",
    "uploads/%2e%2e/secret.txt",
]


def _fake_metadata(key: str) -> FileMetadata:
    filename = key.rsplit("/", 1)[-1]
    folder = key[: -len(filename)] if "/" in key else ""
    return FileMetadata(
        key=key,
        filename=filename,
        folder=folder,
        size_bytes=1024,
        size_human="1.0 KB",
        content_type="text/plain",
        uploaded_at=datetime.now(UTC),
        url=None,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("key", VALID_KEYS)
async def test_query_metadata_route_handles_reserved_key_shapes(
    client, monkeypatch, key
):
    metadata_calls: list[str] = []

    def fake_get_file_metadata(requested_key: str) -> FileMetadata:
        metadata_calls.append(requested_key)
        return _fake_metadata(requested_key)

    monkeypatch.setattr(files_service, "get_file_metadata", fake_get_file_metadata)

    response = await client.get("/files-by-key/metadata", params={"key": key})

    assert response.status_code == 200
    assert response.json()["key"] == key
    assert metadata_calls == [key]


@pytest.mark.asyncio
@pytest.mark.parametrize("key", VALID_KEYS)
async def test_query_download_route_handles_reserved_key_shapes(
    client, monkeypatch, key
):
    presign_calls: list[str] = []
    monkeypatch.setattr(files_service, "get_file_metadata", _fake_metadata)
    monkeypatch.setattr(
        files_service,
        "get_presigned_url",
        lambda requested_key, filename=None: presign_calls.append(requested_key)
        or f"https://example.test/download/{len(presign_calls)}",
    )

    response = await client.get("/files-by-key/download", params={"key": key})

    assert response.status_code == 200
    assert response.json()["url"].startswith("https://example.test/download/")
    assert presign_calls == [key]
    assert files_service.get_download_count() == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("key", VALID_KEYS)
async def test_query_preview_route_handles_reserved_key_shapes(
    client, monkeypatch, key
):
    presign_calls: list[str] = []
    monkeypatch.setattr(files_service, "get_file_metadata", _fake_metadata)
    monkeypatch.setattr(
        files_service,
        "get_presigned_url",
        lambda requested_key, filename=None: presign_calls.append(requested_key)
        or f"https://example.test/preview/{len(presign_calls)}",
    )

    response = await client.get("/files-by-key/preview", params={"key": key})

    assert response.status_code == 200
    assert response.json()["url"].startswith("https://example.test/preview/")
    assert presign_calls == [key]
    assert files_service.get_download_count() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("key", VALID_KEYS)
async def test_query_delete_route_handles_reserved_key_shapes(
    client, monkeypatch, key
):
    delete_calls: list[str] = []
    monkeypatch.setattr(
        files_service, "delete_file", lambda requested_key: delete_calls.append(requested_key)
    )

    response = await client.delete("/files-by-key", params={"key": key})

    assert response.status_code == 200
    assert response.json() == {"deleted": True, "key": key}
    assert delete_calls == [key]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/files-by-key/metadata"),
        ("get", "/files-by-key/download"),
        ("get", "/files-by-key/preview"),
        ("delete", "/files-by-key"),
    ],
)
@pytest.mark.parametrize("key", INVALID_KEYS)
async def test_query_key_routes_reject_invalid_keys(
    client, monkeypatch, method, path, key
):
    repo_calls: list[str] = []
    monkeypatch.setattr(
        files_service,
        "get_file_metadata",
        lambda requested_key: repo_calls.append(requested_key) or _fake_metadata(requested_key),
    )
    monkeypatch.setattr(
        files_service,
        "get_presigned_url",
        lambda requested_key, filename=None: repo_calls.append(requested_key)
        or "https://example.test/file",
    )
    monkeypatch.setattr(
        files_service, "delete_file", lambda requested_key: repo_calls.append(requested_key)
    )

    response = await getattr(client, method)(path, params={"key": key})

    assert response.status_code == 400
    assert repo_calls == []
