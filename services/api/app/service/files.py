import logging
import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from app.config import settings
from app.repo import (
    delete_file,
    get_download_count,
    get_file_metadata,
    get_presigned_url,
    increment_download_count,
    list_files,
)
from app.types import FileMetadata, UploadStats
from app.types.formatting import humanize_bytes
from app.types.stats import DailyUploadCount

logger = logging.getLogger(__name__)

_DANGEROUS_KEY_RE = re.compile(r"(\.\./|/\.\.|\\|%2e%2e|%00|\x00)")


class FileKeyError(Exception):
    """Raised when a file key is invalid."""

    def __init__(self, detail: str = "Invalid file key"):
        self.detail = detail
        super().__init__(detail)


class FileNotFoundServiceError(Exception):
    """Raised when a file is not found.

    Named distinctly from the built-in ``FileNotFoundError`` so it never
    shadows it at module scope — code here (and in callers) can rely on the
    built-in meaning what it says.
    """

    def __init__(self, detail: str = "File not found"):
        self.detail = detail
        super().__init__(detail)


def validate_key(key: str) -> None:
    """Reject empty keys, path-traversal patterns, and — when configured — keys
    outside the allowed prefix.

    `settings.allowed_key_prefix` is empty by default, so any key shape is
    accepted (the by-key routes deliberately support arbitrary folders and
    reserved-word segments). Set it to confine key ops to a prefix like
    "uploads/" when the bucket also holds non-app data.
    """
    if not key:
        raise FileKeyError()
    if _DANGEROUS_KEY_RE.search(key.lower()):
        raise FileKeyError()
    prefix = settings.allowed_key_prefix
    if prefix and not key.startswith(prefix):
        raise FileKeyError()


def user_prefixes(user_id: str) -> tuple[str, ...]:
    """The B2 key prefixes a user owns.

    Every object the app writes for a user lands under exactly one of these:
    their own uploads (``uploads/{user_id}/``) and their AI-generated media
    (``{generation_prefix}/{user_id}/``). Reads, listings, and key-addressed
    ops are confined to this set so one tenant can never see or touch another's
    objects — even with a guessed key.
    """
    return (f"uploads/{user_id}/", f"{settings.generation_prefix}/{user_id}/")


def _require_owned(user_id: str, key: str) -> None:
    """Validate the key shape, then raise *not found* if it is not under one of
    the caller's prefixes. Answering 404 (rather than 403) avoids leaking the
    existence of another user's object."""
    validate_key(key)
    if not any(key.startswith(prefix) for prefix in user_prefixes(user_id)):
        raise FileNotFoundServiceError()


def _list_owned_files(user_id: str) -> list[FileMetadata]:
    """List every object the caller owns — the union of their upload and
    generated-media prefixes. Scans only those prefixes, never the whole bucket.
    Each prefix scan paginates the full prefix (not just the first 1000 keys)."""
    files: list[FileMetadata] = []
    for prefix in user_prefixes(user_id):
        files.extend(list_files(prefix=prefix))
    return files


def get_files(user_id: str, limit: int = 100) -> list[FileMetadata]:
    if limit < 1 or limit > 1000:
        raise ValueError("Limit must be between 1 and 1000")
    # Union the caller's own prefixes, then sort newest-first so the endpoint's
    # "recent uploads" contract holds regardless of repo ordering, and slice.
    files = _list_owned_files(user_id)
    files.sort(key=lambda f: f.uploaded_at, reverse=True)
    return files[:limit]


def get_stats(user_id: str) -> UploadStats:
    """Aggregate stats over the caller's own objects only.

    ``total_downloads`` stays the app-wide counter — a simple demo metric, not
    per-user object data — while file counts/sizes are scoped to the caller.
    """
    files = _list_owned_files(user_id)
    total_size = sum(f.size_bytes for f in files)
    today = datetime.now(UTC).date()
    uploads_today = sum(1 for f in files if f.uploaded_at.date() == today)
    return UploadStats(
        total_files=len(files),
        total_size_bytes=total_size,
        total_size_human=humanize_bytes(total_size),
        uploads_today=uploads_today,
        total_downloads=get_download_count(),
    )


def get_file(user_id: str, key: str) -> FileMetadata:
    _require_owned(user_id, key)
    metadata = get_file_metadata(key)
    if not metadata:
        raise FileNotFoundServiceError()
    return metadata


def get_preview_url(user_id: str, key: str) -> str:
    """Return a presigned URL without recording a download.

    Used by the preview modal for rendering images / PDFs inline — opening
    a preview is not a user-initiated download and shouldn't inflate the
    download counter.
    """
    _require_owned(user_id, key)
    metadata = get_file_metadata(key)
    if not metadata:
        raise FileNotFoundServiceError()
    return get_presigned_url(key, filename=metadata.filename)


def get_download_url(user_id: str, key: str) -> str:
    """Return a presigned URL and record the event as a download."""
    url = get_preview_url(user_id, key)
    increment_download_count()
    return url


def remove_file(user_id: str, key: str) -> None:
    """Own the key, then delete the file. Raises RuntimeError on B2 failure."""
    _require_owned(user_id, key)
    delete_file(key)


def get_upload_activity(user_id: str, days: int = 7) -> list[DailyUploadCount]:
    """Return daily upload counts for the caller's own files over the last N days."""
    files = _list_owned_files(user_id)
    today = datetime.now(UTC).date()
    cutoff = today - timedelta(days=days - 1)

    counts: dict[str, int] = defaultdict(int)
    for f in files:
        d = f.uploaded_at.date()
        if d >= cutoff:
            counts[d.isoformat()] += 1

    # Fill in missing days with zero
    return [
        DailyUploadCount(
            date=(cutoff + timedelta(days=i)).isoformat(),
            uploads=counts.get((cutoff + timedelta(days=i)).isoformat(), 0),
        )
        for i in range(days)
    ]
