"""Unit + integration tests for the presigned direct-to-B2 upload flow.

Uploads are two steps: ``prepare_upload`` validates the intent and mints a
presigned PUT URL (bytes then go browser→B2, never through the API), and
``finalize_upload`` confirms the object landed and re-checks what the sign step
couldn't (true size + magic-byte signature).
"""

from datetime import UTC, datetime

import pytest

from app.service import upload as upload_service
from app.service.upload import (
    UploadError,
    finalize_upload,
    matches_content_signature,
    prepare_upload,
    sanitize_filename,
    validate_extension_matches_type,
)
from app.types import FileMetadata

from .conftest import TEST_USER_ID

FAKE_PRESIGNED_URL = "https://s3.example.backblazeb2.com/bucket/key?X-Amz-Signature=abc"


@pytest.fixture
def mock_presign(monkeypatch):
    """Stub the B2 presign so prepare_upload never builds a real S3 client."""
    monkeypatch.setattr(
        upload_service,
        "get_presigned_upload_url",
        lambda key, content_type, **kw: FAKE_PRESIGNED_URL,
    )


def _stored(
    key: str,
    *,
    content_type: str = "text/plain",
    size_bytes: int = 5,
) -> FileMetadata:
    """Build a FileMetadata as get_file_metadata would return it after a PUT."""
    return FileMetadata(
        key=key,
        filename=key.rsplit("/", 1)[-1],
        folder=key.rsplit("/", 1)[0] + "/",
        size_bytes=size_bytes,
        size_human=f"{size_bytes} B",
        content_type=content_type,
        uploaded_at=datetime.now(UTC),
        url=None,
    )


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


# --- prepare_upload rejection matrix (bytes-free validation) -----------------


def test_prepare_rejects_missing_filename():
    with pytest.raises(UploadError):
        prepare_upload("", "text/plain", 5, user_id=TEST_USER_ID)


def test_prepare_rejects_empty_declared_size():
    with pytest.raises(UploadError) as exc:
        prepare_upload("a.txt", "text/plain", 0, user_id=TEST_USER_ID)
    assert "empty" in exc.value.detail.lower()


def test_prepare_rejects_oversized_declared_size(monkeypatch):
    monkeypatch.setattr(upload_service.settings, "max_file_size", 10)
    with pytest.raises(UploadError) as exc:
        prepare_upload("a.txt", "text/plain", 999, user_id=TEST_USER_ID)
    assert exc.value.status_code == 413


def test_prepare_rejects_disallowed_type():
    with pytest.raises(UploadError) as exc:
        prepare_upload("a.exe", "application/x-msdownload", 4, user_id=TEST_USER_ID)
    assert exc.value.status_code == 415


def test_prepare_rejects_extension_mismatch():
    with pytest.raises(UploadError) as exc:
        prepare_upload("a.png", "text/plain", 4, user_id=TEST_USER_ID)
    assert exc.value.status_code == 415


def test_prepare_returns_scoped_type_bound_presign(mock_presign):
    result = prepare_upload("photo.png", "image/png", 1234, user_id=TEST_USER_ID)
    assert result.key == f"uploads/{TEST_USER_ID}/photo.png"
    assert result.upload_url == FAKE_PRESIGNED_URL
    assert result.method == "PUT"
    # The Content-Type is handed back so the browser replays exactly what was
    # signed — anything else and B2 rejects the PUT.
    assert result.headers == {"Content-Type": "image/png"}


# --- finalize_upload --------------------------------------------------------


def test_finalize_happy_path_returns_basic_metadata(monkeypatch):
    key = f"uploads/{TEST_USER_ID}/report.txt"
    monkeypatch.setattr(upload_service, "get_file_metadata", lambda k: _stored(k))
    monkeypatch.setattr(upload_service, "get_object_head_bytes", lambda k, **kw: b"hello")

    result = finalize_upload(key, user_id=TEST_USER_ID)
    assert result.key == key
    assert result.filename == "report.txt"
    assert result.size_bytes == 5
    # Rich metadata (md5/exif/…) is gone — direct upload never sees the bytes.
    assert not hasattr(result, "metadata")


def test_finalize_rejects_key_outside_caller_prefix(monkeypatch):
    called = {"head": False}
    monkeypatch.setattr(
        upload_service,
        "get_file_metadata",
        lambda k: called.__setitem__("head", True) or _stored(k),
    )
    with pytest.raises(UploadError) as exc:
        finalize_upload("uploads/someone-else/report.txt", user_id=TEST_USER_ID)
    assert exc.value.status_code == 403
    # Ownership is checked before any B2 round-trip.
    assert called["head"] is False


@pytest.mark.parametrize("bad_key", ["", "uploads/../secret", f"uploads/{TEST_USER_ID}/\x00"])
def test_finalize_rejects_traversal_key(bad_key):
    with pytest.raises(UploadError):
        finalize_upload(bad_key, user_id=TEST_USER_ID)


def test_finalize_missing_object_returns_404(monkeypatch):
    monkeypatch.setattr(upload_service, "get_file_metadata", lambda k: None)
    with pytest.raises(UploadError) as exc:
        finalize_upload(f"uploads/{TEST_USER_ID}/gone.txt", user_id=TEST_USER_ID)
    assert exc.value.status_code == 404


def test_finalize_deletes_and_rejects_signature_mismatch(monkeypatch):
    key = f"uploads/{TEST_USER_ID}/a.png"
    deleted: list[str] = []
    monkeypatch.setattr(
        upload_service, "get_file_metadata", lambda k: _stored(k, content_type="image/png")
    )
    # Declared image/png but the stored header bytes are HTML — a spoof.
    monkeypatch.setattr(
        upload_service, "get_object_head_bytes", lambda k, **kw: b"<html>nope"
    )
    monkeypatch.setattr(upload_service, "delete_file", lambda k: deleted.append(k))

    with pytest.raises(UploadError) as exc:
        finalize_upload(key, user_id=TEST_USER_ID)
    assert exc.value.status_code == 415
    assert deleted == [key]  # the bad object was removed, not left lingering


def test_finalize_deletes_and_rejects_oversized_stored_file(monkeypatch):
    key = f"uploads/{TEST_USER_ID}/big.txt"
    deleted: list[str] = []
    monkeypatch.setattr(upload_service.settings, "max_file_size", 10)
    monkeypatch.setattr(
        upload_service, "get_file_metadata", lambda k: _stored(k, size_bytes=999)
    )
    monkeypatch.setattr(upload_service, "delete_file", lambda k: deleted.append(k))

    with pytest.raises(UploadError) as exc:
        finalize_upload(key, user_id=TEST_USER_ID)
    assert exc.value.status_code == 413
    assert deleted == [key]


# --- endpoints --------------------------------------------------------------


@pytest.mark.asyncio
async def test_presign_requires_auth(client):
    resp = await client.post(
        "/upload/presign",
        json={"filename": "a.txt", "content_type": "text/plain", "size_bytes": 5},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_complete_requires_auth(client):
    resp = await client.post("/upload/complete", json={"key": "uploads/x/a.txt"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_presign_endpoint_returns_scoped_url(auth_client, monkeypatch):
    monkeypatch.setattr(
        upload_service,
        "get_presigned_upload_url",
        lambda key, content_type, **kw: FAKE_PRESIGNED_URL,
    )
    resp = await auth_client.post(
        "/upload/presign",
        json={"filename": "a.txt", "content_type": "text/plain", "size_bytes": 5},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["key"] == f"uploads/{TEST_USER_ID}/a.txt"
    assert body["upload_url"] == FAKE_PRESIGNED_URL
    assert body["headers"]["Content-Type"] == "text/plain"


@pytest.mark.asyncio
async def test_complete_endpoint_increments_uploads_metric(auth_client, monkeypatch):
    from app.runtime import metrics

    monkeypatch.setattr(metrics, "_upload_count", 0)
    key = f"uploads/{TEST_USER_ID}/a.txt"
    monkeypatch.setattr(upload_service, "get_file_metadata", lambda k: _stored(k))
    monkeypatch.setattr(upload_service, "get_object_head_bytes", lambda k, **kw: b"hello")

    resp = await auth_client.post("/upload/complete", json={"key": key})
    assert resp.status_code == 200
    assert resp.json()["key"] == key

    metrics_resp = await auth_client.get("/metrics")
    assert "uploads_total 1" in metrics_resp.text
