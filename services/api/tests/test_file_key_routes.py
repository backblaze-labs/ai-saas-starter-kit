"""Tests for the key-addressed file routes under per-user ownership scoping.

Every route is authenticated (401 without a token) and confined to the caller's
own prefixes: a key under `uploads/{me}/` or `generated/{me}/` resolves; any
other well-formed key 404s (existence is never leaked); traversal/empty keys
400. The `auth_client` fixture authenticates as `TEST_USER_ID`.
"""

from datetime import UTC, datetime

import pytest

from app.service import files as files_service
from app.types import FileMetadata

from .conftest import TEST_USER_ID

# Keys the test user owns — including reserved-word/special-char filenames that
# live *inside* the caller's own prefix.
OWNED_KEYS = [
    f"uploads/{TEST_USER_ID}/file.txt",
    f"uploads/{TEST_USER_ID}/file #1?.txt",
    f"uploads/{TEST_USER_ID}/100% complete.txt",
    f"generated/{TEST_USER_ID}/2026-07-16/run-1/img.png",
]

# Well-formed keys the caller does NOT own — another tenant's objects and
# bucket-level keys outside any user prefix. All must 404, not leak existence.
FOREIGN_KEYS = [
    "uploads/other-user/secret.txt",
    "generated/other-user/2026-07-16/run-1/img.png",
    "folder/file.txt",
    "stats",
    "readme.md",
]

# Malformed keys — rejected up front as 400 regardless of ownership.
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


# --- owned keys resolve ----------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("key", OWNED_KEYS)
async def test_metadata_route_serves_owned_key(auth_client, monkeypatch, key):
    calls: list[str] = []

    def fake_get_file_metadata(requested_key: str) -> FileMetadata:
        calls.append(requested_key)
        return _fake_metadata(requested_key)

    monkeypatch.setattr(files_service, "get_file_metadata", fake_get_file_metadata)

    response = await auth_client.get("/files-by-key/metadata", params={"key": key})

    assert response.status_code == 200
    assert response.json()["key"] == key
    assert calls == [key]


@pytest.mark.asyncio
@pytest.mark.parametrize("key", OWNED_KEYS)
async def test_download_route_serves_owned_key(auth_client, monkeypatch, key):
    presign_calls: list[str] = []
    monkeypatch.setattr(files_service, "get_file_metadata", _fake_metadata)
    monkeypatch.setattr(
        files_service,
        "get_presigned_url",
        lambda requested_key, filename=None, disposition="attachment": presign_calls.append(requested_key)
        or f"https://example.test/download/{len(presign_calls)}",
    )

    response = await auth_client.get("/files-by-key/download", params={"key": key})

    assert response.status_code == 200
    assert response.json()["url"].startswith("https://example.test/download/")
    assert presign_calls == [key]
    assert files_service.get_download_count() == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("key", OWNED_KEYS)
async def test_preview_route_serves_owned_key_without_counting_download(
    auth_client, monkeypatch, key
):
    presign_calls: list[str] = []
    monkeypatch.setattr(files_service, "get_file_metadata", _fake_metadata)
    monkeypatch.setattr(
        files_service,
        "get_presigned_url",
        lambda requested_key, filename=None, disposition="attachment": presign_calls.append(requested_key)
        or f"https://example.test/preview/{len(presign_calls)}",
    )

    response = await auth_client.get("/files-by-key/preview", params={"key": key})

    assert response.status_code == 200
    assert response.json()["url"].startswith("https://example.test/preview/")
    assert presign_calls == [key]
    assert files_service.get_download_count() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("key", OWNED_KEYS)
async def test_delete_route_removes_owned_key(auth_client, monkeypatch, key):
    delete_calls: list[str] = []
    monkeypatch.setattr(
        files_service, "delete_file", lambda k: delete_calls.append(k)
    )

    response = await auth_client.delete("/files-by-key", params={"key": key})

    assert response.status_code == 200
    assert response.json() == {"deleted": True, "key": key}
    assert delete_calls == [key]


# --- foreign keys 404 without touching the bucket --------------------------


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
@pytest.mark.parametrize("key", FOREIGN_KEYS)
async def test_key_routes_404_for_unowned_keys(
    auth_client, monkeypatch, method, path, key
):
    """A key the caller doesn't own returns 404 and never reaches B2 — no user
    can read or delete another tenant's object, even with a guessed key."""
    repo_calls: list[str] = []
    monkeypatch.setattr(
        files_service,
        "get_file_metadata",
        lambda k: repo_calls.append(k) or _fake_metadata(k),
    )
    monkeypatch.setattr(
        files_service,
        "get_presigned_url",
        lambda k, filename=None, disposition="attachment": repo_calls.append(k)
        or "https://example.test/file",
    )
    monkeypatch.setattr(files_service, "delete_file", lambda k: repo_calls.append(k))

    response = await getattr(auth_client, method)(path, params={"key": key})

    assert response.status_code == 404
    assert repo_calls == []


# --- malformed keys 400 ----------------------------------------------------


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
async def test_key_routes_reject_invalid_keys(
    auth_client, monkeypatch, method, path, key
):
    repo_calls: list[str] = []
    monkeypatch.setattr(
        files_service,
        "get_file_metadata",
        lambda k: repo_calls.append(k) or _fake_metadata(k),
    )
    monkeypatch.setattr(
        files_service,
        "get_presigned_url",
        lambda k, filename=None, disposition="attachment": repo_calls.append(k)
        or "https://example.test/file",
    )
    monkeypatch.setattr(files_service, "delete_file", lambda k: repo_calls.append(k))

    response = await getattr(auth_client, method)(path, params={"key": key})

    assert response.status_code == 400
    assert repo_calls == []


# --- authentication required -----------------------------------------------


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
async def test_key_routes_require_auth(client, method, path):
    """No bearer token → 401, before any key handling."""
    response = await getattr(client, method)(
        path, params={"key": f"uploads/{TEST_USER_ID}/file.txt"}
    )
    assert response.status_code == 401
