"""Tests for error handling across the API."""

import pytest

from app.service import files as files_service

from .conftest import TEST_USER_ID


@pytest.mark.asyncio
async def test_unhandled_exception_returns_500(auth_client, monkeypatch):
    """Global handler catches unhandled exceptions and returns 500 JSON."""

    def explode(*args, **kwargs):
        raise RuntimeError("B2 exploded")

    monkeypatch.setattr(files_service, "list_files", explode)

    response = await auth_client.get("/files")
    assert response.status_code == 500
    body = response.json()
    assert body["detail"] == "Internal server error"
    # Ensure raw error message is NOT leaked to the client
    assert "B2 exploded" not in body["detail"]


@pytest.mark.asyncio
async def test_unhandled_exception_500_carries_cors_headers(auth_client, monkeypatch):
    """An uncaught-exception 500 must still carry CORS headers.

    Regression guard for the structural bug where the catch-all middleware sat
    OUTSIDE CORSMiddleware: its 500 shipped without `Access-Control-Allow-Origin`,
    so browsers blocked it and the frontend saw an opaque "network error" instead
    of the real server failure. CORS must be the outermost middleware (main.py)
    so the 500 produced by the inner catch-all flows back out through it.
    """

    def explode(*args, **kwargs):
        raise RuntimeError("B2 exploded")

    monkeypatch.setattr(files_service, "list_files", explode)

    origin = "http://localhost:3000"
    response = await auth_client.get("/files", headers={"Origin": origin})

    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error"
    # The whole point: the error response is readable cross-origin.
    assert response.headers.get("access-control-allow-origin") == origin


@pytest.mark.asyncio
async def test_stats_b2_failure_returns_500(auth_client, monkeypatch):
    """Stats endpoint returns 500 when B2 is unreachable."""

    def explode(*args, **kwargs):
        raise RuntimeError("B2 stats query failed")

    monkeypatch.setattr(files_service, "list_files", explode)

    response = await auth_client.get("/files/stats")
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error"


@pytest.mark.asyncio
async def test_download_not_found_returns_404(auth_client, monkeypatch):
    """Download for a missing (but owned) file returns 404 with detail."""
    monkeypatch.setattr(files_service, "get_file_metadata", lambda key: None)

    response = await auth_client.get(
        "/files-by-key/download",
        params={"key": f"uploads/{TEST_USER_ID}/missing.txt"},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_traversal_keys_are_rejected():
    """validate_key blocks empty keys and path-traversal patterns."""
    from app.service.files import FileKeyError, validate_key

    bad_keys = [
        "",
        "uploads/../secret.txt",
        "../etc/passwd",
        "uploads\\secret.txt",
        "uploads/%2e%2e/secret",
        "uploads/\x00null",
    ]
    for bad in bad_keys:
        with pytest.raises(FileKeyError):
            validate_key(bad)

    # Sanity: ordinary keys (including those outside uploads/) pass.
    validate_key("uploads/file.txt")
    validate_key("photos/2026/vacation.jpg")
    validate_key("readme.md")


@pytest.mark.asyncio
async def test_upload_empty_file_returns_400(auth_client):
    """Uploading an empty file returns 400 with explanation."""
    from io import BytesIO

    response = await auth_client.post(
        "/upload",
        files={"file": ("empty.txt", BytesIO(b""), "text/plain")},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()
