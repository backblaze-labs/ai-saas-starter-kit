"""Unit tests for upload filename handling and per-user key scoping.

With the presigned flow the object key is decided at ``prepare_upload`` time
(before any bytes exist), so these assert the key the browser will PUT to.
"""

from app.service import upload as upload_service
from app.service.upload import prepare_upload

from .conftest import TEST_USER_ID


def _mock_presign(monkeypatch):
    monkeypatch.setattr(
        upload_service,
        "get_presigned_upload_url",
        lambda key, content_type, **kw: f"https://s3.example/{key}?sig=x",
    )


def test_upload_allows_duplicate_filename(monkeypatch):
    """B2 is always versioned — re-uploading the same name creates a new version,
    so the same key is handed out again (no conflict rejection)."""
    _mock_presign(monkeypatch)

    result = prepare_upload(
        filename="report.txt",
        content_type="text/plain",
        size_bytes=5,
        user_id=TEST_USER_ID,
    )
    assert result.key == f"uploads/{TEST_USER_ID}/report.txt"


def test_upload_scopes_key_to_user(monkeypatch):
    """The presigned key is scoped under the caller's own prefix."""
    _mock_presign(monkeypatch)

    result = prepare_upload(
        filename="report.txt",
        content_type="text/plain",
        size_bytes=5,
        user_id="another-user",
    )
    assert result.key == "uploads/another-user/report.txt"
