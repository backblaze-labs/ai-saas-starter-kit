import contextlib
import json
import logging
import os
import re
import tempfile
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock

from app.config import settings
from app.repo import (
    delete_file,
    get_file_metadata,
    get_presigned_url,
    get_upload_stats,
    list_files,
)
from app.types import FileMetadata, UploadStats
from app.types.stats import DailyUploadCount

logger = logging.getLogger(__name__)

_DANGEROUS_KEY_RE = re.compile(r"(\.\./|/\.\.|\\|%2e%2e|%00|\x00)")
_download_lock = Lock()


def _counter_path() -> Path:
    """Resolve the counter file path relative to the api service root."""
    p = Path(settings.download_count_file)
    if not p.is_absolute():
        # Anchor at services/api/ (three levels up from this file)
        p = Path(__file__).resolve().parents[2] / p
    return p


def _load_download_count() -> int:
    """Read persisted counter; return 0 if the file is missing or unreadable."""
    try:
        with open(_counter_path()) as f:
            return int(json.load(f).get("count", 0))
    except (FileNotFoundError, json.JSONDecodeError, ValueError, TypeError):
        return 0


def _save_download_count(count: int) -> None:
    """Atomically persist the counter. Caller must hold the download lock."""
    path = _counter_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: tmp file in the same dir, then rename.
        fd, tmp = tempfile.mkstemp(
            dir=path.parent, prefix=path.name + ".", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump({"count": count}, f)
            os.replace(tmp, path)
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise
    except OSError as e:
        # Counter persistence failing shouldn't break downloads — log and move on.
        logger.warning("Failed to persist download counter: %s", e)


_download_count = _load_download_count()


def _record_download() -> None:
    global _download_count
    with _download_lock:
        _download_count += 1
        _save_download_count(_download_count)


def get_download_count() -> int:
    with _download_lock:
        return _download_count


class FileKeyError(Exception):
    """Raised when a file key is invalid."""

    def __init__(self, detail: str = "Invalid file key"):
        self.detail = detail
        super().__init__(detail)


class FileNotFoundError(Exception):
    """Raised when a file is not found."""

    def __init__(self, detail: str = "File not found"):
        self.detail = detail
        super().__init__(detail)


def validate_key(key: str) -> None:
    """Reject empty keys and keys that contain path-traversal patterns."""
    if not key:
        raise FileKeyError()
    if _DANGEROUS_KEY_RE.search(key.lower()):
        raise FileKeyError()


def get_files(prefix: str = "", limit: int = 100) -> list[FileMetadata]:
    if limit < 1 or limit > 1000:
        raise ValueError("Limit must be between 1 and 1000")
    # S3 list_objects_v2 returns objects in lexicographic order, not by date.
    # Fetch a full batch, sort newest-first, then slice to the requested limit.
    files = list_files(prefix=prefix, max_keys=1000)
    files.sort(key=lambda f: f.uploaded_at, reverse=True)
    return files[:limit]


def get_stats() -> UploadStats:
    data = get_upload_stats()
    data["total_downloads"] = get_download_count()
    return UploadStats(**data)


def get_file(key: str) -> FileMetadata:
    validate_key(key)
    metadata = get_file_metadata(key)
    if not metadata:
        raise FileNotFoundError()
    return metadata


def get_preview_url(key: str) -> str:
    """Return a presigned URL without recording a download.

    Used by the preview modal for rendering images / PDFs inline — opening
    a preview is not a user-initiated download and shouldn't inflate the
    download counter.
    """
    validate_key(key)
    metadata = get_file_metadata(key)
    if not metadata:
        raise FileNotFoundError()
    return get_presigned_url(key, filename=metadata.filename)


def get_download_url(key: str) -> str:
    """Return a presigned URL and record the event as a download."""
    url = get_preview_url(key)
    _record_download()
    return url


def remove_file(key: str) -> None:
    """Validate key and delete the file. Raises RuntimeError on B2 failure."""
    validate_key(key)
    delete_file(key)


def get_upload_activity(days: int = 7) -> list[DailyUploadCount]:
    """Return daily upload counts for the last N days."""
    files = list_files(prefix="", max_keys=1000)
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
