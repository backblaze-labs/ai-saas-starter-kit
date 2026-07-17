import re

from app.config import settings
from app.repo import (
    delete_file,
    get_file_metadata,
    get_object_head_bytes,
    get_presigned_upload_url,
)
from app.service.keys import has_path_traversal
from app.types import FileUploadResponse, PresignedUpload
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


def upload_key_for(user_id: str, safe_name: str) -> str:
    """The B2 object key a user's upload lands under.

    Scoped to the caller (``uploads/{user_id}/``) so one user's uploads never
    collide with or shadow another's, matching the file browser's per-user
    scoping. B2 buckets are always versioned, so re-uploading the same name just
    creates a new version — no duplicate rejection needed.
    """
    return f"uploads/{user_id}/{safe_name}"


def prepare_upload(
    filename: str,
    content_type: str,
    size_bytes: int,
    *,
    user_id: str,
) -> PresignedUpload:
    """Validate an upload intent and mint a scoped, type-bound presigned PUT URL.

    The browser then uploads the bytes **straight to B2** with this URL, so the
    payload never transits the API — that's what sidesteps a serverless
    request-body cap (Vercel's 4.5 MB). Everything checkable without the bytes is
    enforced here (type allow-list, extension/type consistency, declared size);
    the magic-byte signature and true stored size are re-checked in
    :func:`finalize_upload` once the object exists. Raises UploadError on
    failure.
    """
    if not filename:
        raise UploadError("No filename provided")

    if size_bytes <= 0:
        raise UploadError("Empty file")

    if size_bytes > settings.max_file_size:
        raise UploadError(
            f"File too large. Max size: {humanize_bytes(settings.max_file_size)}",
            status_code=413,
        )

    if content_type not in ALLOWED_TYPES:
        raise UploadError(f"File type '{content_type}' not allowed", status_code=415)

    safe_name = sanitize_filename(filename)

    if not validate_extension_matches_type(safe_name, content_type):
        raise UploadError(
            "File extension does not match declared content type",
            status_code=415,
        )

    key = upload_key_for(user_id, safe_name)
    upload_url = get_presigned_upload_url(key, content_type)
    return PresignedUpload(
        upload_url=upload_url,
        key=key,
        headers={"Content-Type": content_type},
    )


def _require_owned_upload(user_id: str, key: str) -> None:
    """Reject an empty/traversing key, or one outside the caller's upload prefix.

    Finalize only ever confirms objects the app itself wrote under
    ``uploads/{user_id}/`` (generated media is created server-side, never
    finalized by a client), so this is a single-prefix ownership gate.
    """
    if not key or has_path_traversal(key):
        raise UploadError("Invalid file key")
    if not key.startswith(upload_key_for(user_id, "")):
        raise UploadError("Invalid file key", status_code=403)


def finalize_upload(key: str, *, user_id: str) -> FileUploadResponse:
    """Confirm a direct upload landed and passes the checks the sign step couldn't.

    Called after the browser's PUT to B2 succeeds. Re-establishes the guarantees
    the in-transit path used to provide, now that the bytes only ever lived in
    B2:

    * **Ownership** — the key must be under the caller's own ``uploads/`` prefix,
      so a client can't finalize (and thereby surface) an object it doesn't own.
    * **Existence** — a missing object means the PUT never completed (404).
    * **True size** — re-check the stored size against the limit, in case the
      client under-declared it at sign time.
    * **Content signature** — Range-GET the header bytes and reject a payload
      whose magic bytes don't match its declared type, deleting the bad object.

    Raises UploadError on any failure.
    """
    _require_owned_upload(user_id, key)

    metadata = get_file_metadata(key)
    if metadata is None:
        raise UploadError("Upload did not complete — object not found", status_code=404)

    if metadata.size_bytes == 0:
        delete_file(key)
        raise UploadError("Empty file")

    if metadata.size_bytes > settings.max_file_size:
        delete_file(key)
        raise UploadError(
            f"File too large. Max size: {humanize_bytes(settings.max_file_size)}",
            status_code=413,
        )

    if metadata.content_type not in ALLOWED_TYPES:
        delete_file(key)
        raise UploadError(
            f"File type '{metadata.content_type}' not allowed", status_code=415
        )

    header = get_object_head_bytes(key)
    if not matches_content_signature(header, metadata.content_type):
        # The stored bytes lied about their type — drop the object so a spoofed
        # payload never lingers in the bucket, then reject.
        delete_file(key)
        raise UploadError(
            "File contents do not match the declared type", status_code=415
        )

    return FileUploadResponse(
        key=metadata.key,
        filename=metadata.filename,
        size_bytes=metadata.size_bytes,
        size_human=metadata.size_human,
        content_type=metadata.content_type,
        uploaded_at=metadata.uploaded_at,
        url=metadata.url,
    )
