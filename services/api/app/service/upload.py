import re

from app.config import settings
from app.repo import upload_file
from app.service.metadata import extract_metadata
from app.types import FileUploadResponse
from app.types.formatting import humanize_bytes

# Note: image/svg+xml is deliberately excluded. SVGs can embed <script>, so a
# file stored and later served from a public bucket URL would execute in the
# browser (stored XSS). Re-add only with server-side SVG sanitization.
ALLOWED_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "application/pdf",
    "text/plain",
    "text/csv",
    "application/json",
    "application/zip",
    "video/mp4",
    "audio/mpeg",
    "audio/wav",
}

MIME_EXTENSION_MAP: dict[str, set[str]] = {
    "image/jpeg": {"jpg", "jpeg", "jfif"},
    "image/png": {"png"},
    "image/gif": {"gif"},
    "image/webp": {"webp"},
    "application/pdf": {"pdf"},
    "text/plain": {"txt", "text", "log", "md"},
    "text/csv": {"csv"},
    "application/json": {"json"},
    "application/zip": {"zip"},
    "video/mp4": {"mp4"},
    "audio/mpeg": {"mp3", "mpeg"},
    "audio/wav": {"wav"},
}


# Magic-byte signatures for the binary types we accept. The client-declared
# content_type is untrusted, so we sniff the leading bytes and reject obvious
# mismatches (e.g. an HTML/script payload uploaded as image/png). Text-like
# types (text/plain, text/csv, application/json) have no reliable signature and
# are intentionally omitted — they skip this check but remain constrained by
# the extension/type consistency check.
def matches_content_signature(data: bytes, content_type: str) -> bool:
    """Return True if `data`'s leading bytes are consistent with `content_type`.

    Types without a known signature return True (nothing to verify).
    """
    if content_type == "image/jpeg":
        return data[:3] == b"\xff\xd8\xff"
    if content_type == "image/png":
        return data[:8] == b"\x89PNG\r\n\x1a\n"
    if content_type == "image/gif":
        return data[:6] in (b"GIF87a", b"GIF89a")
    if content_type == "image/webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    if content_type == "application/pdf":
        return data[:5] == b"%PDF-"
    if content_type == "application/zip":
        return data[:4] in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
    if content_type == "video/mp4":
        return data[4:8] == b"ftyp"  # ISO base media 'ftyp' box
    if content_type == "audio/mpeg":
        # ID3 tag, or an MPEG audio frame sync (11 set bits).
        return data[:3] == b"ID3" or (
            len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0
        )
    if content_type == "audio/wav":
        return data[:4] == b"RIFF" and data[8:12] == b"WAVE"
    return True


_SAFE_FILENAME_RE = re.compile(r"[^\w\-.]")


def sanitize_filename(filename: str) -> str:
    """Sanitize filename: strip path components, remove unsafe chars, limit length."""
    name = filename.replace("\\", "/").split("/")[-1]
    name = name.replace("\x00", "")
    name = _SAFE_FILENAME_RE.sub("_", name)
    name = re.sub(r"[_.]{2,}", "_", name)
    name = name.lstrip(".").strip()
    if len(name) > 200:
        base, sep, ext = name.rpartition(".")
        # Preserve the extension only when there is one that still fits;
        # otherwise (no dot, or an absurdly long "extension") hard-truncate.
        # `rpartition` returns ("", "", name) when there is no dot, so guard on
        # `sep`, not `ext` — else an extensionless name keeps its whole body.
        name = (
            base[: 200 - len(ext) - 1] + "." + ext
            if sep and len(ext) < 200
            else name[:200]
        )
    return name or "unnamed"


def validate_extension_matches_type(filename: str, content_type: str) -> bool:
    """Verify the file extension is consistent with the declared MIME type."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed_exts = MIME_EXTENSION_MAP.get(content_type)
    if allowed_exts is None:
        return False
    if not ext:
        return True
    return ext in allowed_exts


class UploadError(Exception):
    """Raised when upload validation fails."""

    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def check_upload_type(filename: str, content_type: str) -> None:
    """Validate the declared MIME type and its extension. Raises UploadError(415).

    These checks depend only on headers/filename — not the body — so the runtime
    layer can call this to reject a disallowed upload BEFORE buffering the body
    into memory. `process_upload` reuses it so the rule lives in exactly one
    place (the body-dependent checks — signature, size, emptiness — stay there).
    """
    if content_type not in ALLOWED_TYPES:
        raise UploadError(f"File type '{content_type}' not allowed", status_code=415)

    if not validate_extension_matches_type(sanitize_filename(filename), content_type):
        raise UploadError(
            "File extension does not match declared content type",
            status_code=415,
        )


def process_upload(
    file_data: bytes,
    filename: str,
    content_type: str,
    content_length: int | None = None,
    *,
    user_id: str,
) -> FileUploadResponse:
    """Validate and process a file upload. Raises UploadError on failure.

    The object is keyed under the caller's own prefix (``uploads/{user_id}/``)
    so uploads are per-user isolated, matching the file browser's scoping.
    """
    if not filename:
        raise UploadError("No filename provided")

    if content_length and content_length > settings.max_file_size:
        raise UploadError(
            f"File too large. Max size: {humanize_bytes(settings.max_file_size)}",
            status_code=413,
        )

    # Type/extension gate — the runtime layer runs this pre-buffer too, so a
    # disallowed type never reaches here; kept here for direct callers (tests,
    # future entry points) and to keep the rule in one place.
    check_upload_type(filename, content_type)

    safe_name = sanitize_filename(filename)

    if len(file_data) == 0:
        raise UploadError("Empty file")

    if not matches_content_signature(file_data, content_type):
        raise UploadError(
            "File contents do not match the declared type", status_code=415
        )

    if len(file_data) > settings.max_file_size:
        raise UploadError(
            f"File too large. Max size: {humanize_bytes(settings.max_file_size)}",
            status_code=413,
        )

    # B2 buckets are always versioned — uploading the same key creates a new
    # version automatically.  No duplicate rejection needed. The key is scoped
    # to the caller so one user's uploads never collide with or shadow another's.
    key = f"uploads/{user_id}/{safe_name}"
    result = upload_file(file_data, key, content_type)
    metadata = extract_metadata(file_data, safe_name, content_type)

    return FileUploadResponse(
        key=result.key,
        filename=result.filename,
        size_bytes=result.size_bytes,
        size_human=result.size_human,
        content_type=content_type,
        uploaded_at=result.uploaded_at,
        url=result.url,
        metadata=metadata,
    )
