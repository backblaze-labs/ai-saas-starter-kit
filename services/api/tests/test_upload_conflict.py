"""Unit tests for upload filename handling and per-user key scoping."""

from app.service import upload as upload_service
from app.types import FileUploadResponse

from .conftest import TEST_USER_ID


def _fake_upload(monkeypatch):
    monkeypatch.setattr(
        upload_service,
        "upload_file",
        lambda file_data, key, content_type: FileUploadResponse(
            key=key,
            filename="report.txt",
            size_bytes=len(file_data),
            size_human="5 B",
            content_type=content_type,
            uploaded_at="2026-02-14T00:00:00Z",
            url=None,
            metadata=None,
        ),
    )
    monkeypatch.setattr(
        upload_service,
        "extract_metadata",
        lambda file_data, filename, content_type: None,
    )


def test_upload_allows_duplicate_filename(monkeypatch):
    """B2 is always versioned — re-uploading the same name creates a new version."""
    _fake_upload(monkeypatch)

    result = upload_service.process_upload(
        file_data=b"hello",
        filename="report.txt",
        content_type="text/plain",
        content_length=5,
        user_id=TEST_USER_ID,
    )

    assert result.key == f"uploads/{TEST_USER_ID}/report.txt"


def test_upload_scopes_key_to_user(monkeypatch):
    """The uploaded object is keyed under the caller's own prefix."""
    _fake_upload(monkeypatch)

    result = upload_service.process_upload(
        file_data=b"hello",
        filename="report.txt",
        content_type="text/plain",
        content_length=5,
        user_id="another-user",
    )

    assert result.key == "uploads/another-user/report.txt"
