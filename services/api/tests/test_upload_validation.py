"""Unit + integration tests for upload validation and content sniffing."""

import asyncio

import pytest

from app.service import upload as upload_service
from app.service.upload import (
    UploadError,
    check_upload_type,
    matches_content_signature,
    sanitize_filename,
    validate_extension_matches_type,
)
from app.types import FileUploadResponse

from .conftest import TEST_USER_ID


def process_upload(*args, **kwargs):
    """process_upload now requires a caller id; default it for the rejection
    matrix, which fails before the key is ever built."""
    kwargs.setdefault("user_id", TEST_USER_ID)
    return upload_service.process_upload(*args, **kwargs)

# --- sanitize_filename ------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("../../etc/passwd", "passwd"),  # path components stripped
        ("a\x00b.txt", "ab.txt"),  # null byte removed
        ("my file.txt", "my_file.txt"),  # unsafe char substituted
        ("...hidden", "_hidden"),  # dot run collapses to _ before dot-strip
        ("", "unnamed"),  # empty → placeholder
        ("/", "unnamed"),  # only a path separator → placeholder
    ],
)
def test_sanitize_filename(raw, expected):
    assert sanitize_filename(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "a" * 300 + ".txt",  # long name with extension
        "a" * 300,  # long name, NO extension (regression: was 301 chars + ".")
        "a" * 300 + "." + "b" * 250,  # absurdly long extension
    ],
)
def test_sanitize_filename_truncates_long_names(raw):
    result = sanitize_filename(raw)
    assert len(result) <= 200
    assert not result.startswith(".")


# --- validate_extension_matches_type ----------------------------------------


@pytest.mark.parametrize(
    ("filename", "content_type", "expected"),
    [
        ("photo.jpg", "image/jpeg", True),
        ("photo.jpeg", "image/jpeg", True),
        ("photo.png", "image/jpeg", False),  # extension/type mismatch
        ("noext", "image/jpeg", True),  # no extension → not enforced
        ("x.exe", "image/jpeg", False),
        ("x.pdf", "application/octet-stream", False),  # type not in map
    ],
)
def test_validate_extension_matches_type(filename, content_type, expected):
    assert validate_extension_matches_type(filename, content_type) is expected


# --- matches_content_signature ----------------------------------------------

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 8
_PDF = b"%PDF-1.7\n"
_ZIP = b"PK\x03\x04" + b"\x00" * 8


@pytest.mark.parametrize(
    ("data", "content_type", "expected"),
    [
        (_PNG, "image/png", True),
        (b"<html>not a png", "image/png", False),  # spoofed image
        (_JPEG, "image/jpeg", True),
        (_PDF, "application/pdf", True),
        (b"nope", "application/pdf", False),
        (_ZIP, "application/zip", True),
        (b"any text at all", "text/plain", True),  # text has no signature
        (b"{}", "application/json", True),  # json has no signature
    ],
)
def test_matches_content_signature(data, content_type, expected):
    assert matches_content_signature(data, content_type) is expected


# --- process_upload rejection matrix ----------------------------------------


def test_rejects_oversized_content_length(monkeypatch):
    monkeypatch.setattr(upload_service.settings, "max_file_size", 10)
    with pytest.raises(UploadError) as exc:
        process_upload(b"x", "a.txt", "text/plain", content_length=999)
    assert exc.value.status_code == 413


def test_rejects_oversized_body(monkeypatch):
    monkeypatch.setattr(upload_service.settings, "max_file_size", 5)
    with pytest.raises(UploadError) as exc:
        process_upload(b"way too big", "a.txt", "text/plain", content_length=None)
    assert exc.value.status_code == 413


def test_rejects_disallowed_type():
    with pytest.raises(UploadError) as exc:
        process_upload(b"data", "a.exe", "application/x-msdownload", content_length=4)
    assert exc.value.status_code == 415


def test_rejects_extension_mismatch():
    with pytest.raises(UploadError) as exc:
        process_upload(b"data", "a.png", "text/plain", content_length=4)
    assert exc.value.status_code == 415


def test_rejects_content_signature_mismatch():
    # A .png name and declared image/png, but the bytes aren't a PNG.
    with pytest.raises(UploadError) as exc:
        process_upload(b"not a real png", "a.png", "image/png", content_length=14)
    assert exc.value.status_code == 415


def test_rejects_empty_file():
    with pytest.raises(UploadError):
        process_upload(b"", "a.txt", "text/plain", content_length=0)


# --- check_upload_type (pre-buffer gate) ------------------------------------


def test_check_upload_type_allows_matching_type():
    # Allowed type + consistent extension → no raise.
    assert check_upload_type("photo.jpg", "image/jpeg") is None


def test_check_upload_type_rejects_disallowed_type():
    with pytest.raises(UploadError) as exc:
        check_upload_type("a.exe", "application/x-msdownload")
    assert exc.value.status_code == 415


def test_check_upload_type_rejects_extension_mismatch():
    with pytest.raises(UploadError) as exc:
        check_upload_type("a.png", "text/plain")
    assert exc.value.status_code == 415


@pytest.mark.asyncio
async def test_disallowed_type_rejected_before_buffering(auth_client, monkeypatch):
    """A disallowed content-type returns 415 without the body ever being
    buffered or processed — the pre-check short-circuits before the read loop
    and the concurrency slot."""
    from app.runtime import upload as upload_route

    processed = False

    async def fail_if_processed(*args, **kwargs):
        nonlocal processed
        processed = True
        raise AssertionError("process_upload must not run for a disallowed type")

    # Spy on the runtime-bound symbol the handler actually calls.
    monkeypatch.setattr(upload_route, "run_in_threadpool", fail_if_processed)

    resp = await auth_client.post(
        "/upload",
        files={"file": ("evil.exe", b"MZ" + b"\x00" * 4096, "application/x-msdownload")},
    )
    assert resp.status_code == 415
    assert processed is False


# --- concurrency gate --------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_waits_when_concurrency_slots_exhausted(auth_client, monkeypatch):
    """The semaphore actually bounds concurrency: with every slot held, a new
    upload blocks at the gate (doesn't process) until a slot frees."""
    from app.runtime import upload as upload_route

    # Single-slot gate, fully occupied so the next upload must wait.
    gate = asyncio.Semaphore(1)
    monkeypatch.setattr(upload_route, "_upload_semaphore", gate)
    await gate.acquire()

    def fake_upload_file(file_data, key, content_type):
        return FileUploadResponse(
            key=key,
            filename="a.txt",
            size_bytes=len(file_data),
            size_human="5 B",
            content_type=content_type,
            uploaded_at="2026-02-14T00:00:00Z",
            url=None,
            metadata=None,
        )

    monkeypatch.setattr(upload_service, "upload_file", fake_upload_file)
    monkeypatch.setattr(upload_service, "extract_metadata", lambda *a, **k: None)

    task = asyncio.create_task(
        auth_client.post("/upload", files={"file": ("a.txt", b"hello", "text/plain")})
    )
    # While the only slot is held, the request must not complete.
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(asyncio.shield(task), timeout=0.2)

    # Freeing the slot lets the waiting upload proceed to completion.
    gate.release()
    resp = await asyncio.wait_for(task, timeout=2.0)
    assert resp.status_code == 200


# --- uploads_total metric increments ----------------------------------------


@pytest.mark.asyncio
async def test_successful_upload_increments_uploads_metric(auth_client, monkeypatch):
    from app.runtime import metrics

    monkeypatch.setattr(metrics, "_upload_count", 0)
    captured: dict = {}

    def fake_upload_file(file_data, key, content_type):
        captured["key"] = key
        return FileUploadResponse(
            key=key,
            filename="a.txt",
            size_bytes=len(file_data),
            size_human="5 B",
            content_type=content_type,
            uploaded_at="2026-02-14T00:00:00Z",
            url=None,
            metadata=None,
        )

    monkeypatch.setattr(upload_service, "upload_file", fake_upload_file)
    monkeypatch.setattr(
        upload_service, "extract_metadata", lambda file_data, filename, content_type: None
    )

    resp = await auth_client.post(
        "/upload", files={"file": ("a.txt", b"hello", "text/plain")}
    )
    assert resp.status_code == 200
    # The write landed under the caller's own prefix, not a flat uploads/.
    assert captured["key"] == f"uploads/{TEST_USER_ID}/a.txt"

    metrics_resp = await auth_client.get("/metrics")
    assert "uploads_total 1" in metrics_resp.text


@pytest.mark.asyncio
async def test_upload_requires_auth(client):
    resp = await client.post(
        "/upload", files={"file": ("a.txt", b"hello", "text/plain")}
    )
    assert resp.status_code == 401
