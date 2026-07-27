import functools
import mimetypes
import time
from threading import Lock
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import APP_VERSION, settings
from app.repo.b2_listing import invalidate_list_cache, list_all_objects
from app.types import FileMetadata
from app.types.formatting import humanize_bytes


def _guess_content_type(key: str) -> str:
    mime, _ = mimetypes.guess_type(key)
    return mime or "application/octet-stream"


def _split_key(key: str) -> tuple[str, str]:
    """Return (folder, filename) from an object key."""
    parts = key.rsplit("/", 1)
    if len(parts) == 2:
        return parts[0] + "/", parts[1]
    return "", parts[0]


def _public_url(key: str) -> str | None:
    """Build a public URL for an object key, percent-encoding the path."""
    if not settings.b2_public_url_base:
        return None
    return f"{settings.b2_public_url_base}/{quote(key, safe='/')}"


@functools.lru_cache(maxsize=1)
def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.b2_endpoint,
        region_name=settings.b2_region,
        aws_access_key_id=settings.b2_application_key_id,
        aws_secret_access_key=settings.b2_application_key,
        # Bound every B2 call (timeouts + capped retries) so a hung endpoint can't
        # tie up a threadpool thread and starve file I/O / the health check. Pool
        # sized to the request threadpool (40) so concurrent ops don't queue.
        config=Config(
            signature_version="s3v4",
            user_agent_extra=f"b2ai-ai-saas-starter-kit/{APP_VERSION} (backblaze-b2-samples)",
            connect_timeout=5,
            read_timeout=30,
            retries={"max_attempts": 3, "mode": "standard"},
            max_pool_connections=40,
        ),
    )


# Cache the B2 connectivity result briefly so uptime monitors polling /health
# every few seconds don't issue a B2 head_bucket on every call.
_HEALTH_TTL_SECONDS = 5.0
_health_cache: tuple[float, bool] | None = None
_health_lock = Lock()


def check_connectivity() -> bool:
    global _health_cache
    now = time.monotonic()
    with _health_lock:
        if _health_cache is not None and now - _health_cache[0] < _HEALTH_TTL_SECONDS:
            return _health_cache[1]
    try:
        client = get_s3_client()
        client.head_bucket(Bucket=settings.b2_bucket_name)
        ok = True
    except Exception:
        ok = False
    with _health_lock:
        _health_cache = (time.monotonic(), ok)
    return ok


def list_files(prefix: str = "") -> list[FileMetadata]:
    """List all files under `prefix`.

    Paginates the whole prefix so callers see every object, not just the first
    1000. Order is unspecified — callers that need newest-first sort themselves
    (see `service.files.get_files`). Raises RuntimeError on S3 failure.
    """
    files: list[FileMetadata] = []
    for obj in list_all_objects(prefix):
        folder, filename = _split_key(obj["Key"])
        files.append(
            FileMetadata(
                key=obj["Key"],
                filename=filename,
                folder=folder,
                size_bytes=obj["Size"],
                size_human=humanize_bytes(obj["Size"]),
                content_type=_guess_content_type(obj["Key"]),
                uploaded_at=obj["LastModified"],
                url=_public_url(obj["Key"]),
            )
        )
    return files


def get_file_metadata(key: str) -> FileMetadata | None:
    client = get_s3_client()
    try:
        response = client.head_object(
            Bucket=settings.b2_bucket_name, Key=key
        )
    except ClientError as e:
        # Only treat 404/NoSuchKey as "not found"; re-raise other errors
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey"):
            return None
        raise

    folder, filename = _split_key(key)
    return FileMetadata(
        key=key,
        filename=filename,
        folder=folder,
        size_bytes=response["ContentLength"],
        size_human=humanize_bytes(response["ContentLength"]),
        content_type=response.get("ContentType", _guess_content_type(key)),
        uploaded_at=response["LastModified"],
        url=_public_url(key),
    )


def delete_file(key: str) -> None:
    """Delete an object from B2. Raises RuntimeError on failure."""
    client = get_s3_client()
    try:
        client.delete_object(Bucket=settings.b2_bucket_name, Key=key)
    except ClientError as e:
        raise RuntimeError(f"B2 delete failed for '{key}': {e}") from e
    invalidate_list_cache()  # deleted object must disappear from listings/stats


def get_presigned_url(
    key: str,
    filename: str | None = None,
    expires_in: int = 600,
    disposition: str = "attachment",
) -> str:
    """Generate a presigned download URL. Raises RuntimeError on failure.

    `disposition`: "attachment" (default) forces a save on real downloads;
    "inline" lets the preview modal render an image/PDF in-browser. Inline is
    safe — the URL is on the isolated B2 origin and SVG/HTML are excluded from
    the upload allow-list, so no allowed type executes script in the app context.
    """
    client = get_s3_client()
    params: dict = {"Bucket": settings.b2_bucket_name, "Key": key}
    if filename:
        # RFC 5987 encoding for non-ASCII filenames
        encoded = quote(filename, safe="")
        params["ResponseContentDisposition"] = (
            f"{disposition}; filename=\"{encoded}\"; filename*=UTF-8''{encoded}"
        )
    else:
        params["ResponseContentDisposition"] = disposition
    try:
        return client.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=expires_in,
        )
    except ClientError as e:
        raise RuntimeError(f"B2 presign failed for '{key}': {e}") from e


def get_presigned_upload_url(
    key: str, content_type: str, expires_in: int = 900
) -> str:
    """Generate a presigned PUT URL for a direct browser→B2 upload.

    The signature binds both the exact object ``key`` and the ``Content-Type``:
    the browser must PUT with a matching ``Content-Type`` header or B2 rejects
    the request, so a caller can't sign for one declared type and store another.

    Bytes travel straight from the browser to B2 — they never transit the API —
    which is what lets uploads exceed a serverless platform's request-body cap
    (e.g. Vercel's hard 4.5 MB limit). Presigning is a local HMAC computation,
    so this makes no network call. Raises RuntimeError on failure.
    """
    client = get_s3_client()
    try:
        return client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.b2_bucket_name,
                "Key": key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in,
        )
    except ClientError as e:
        raise RuntimeError(f"B2 presign(put) failed for '{key}': {e}") from e


def get_object_head_bytes(key: str, length: int = 32) -> bytes:
    """Fetch the first ``length`` bytes of an object via a Range GET.

    Used to sniff magic-byte signatures during upload finalization: with direct
    browser→B2 uploads the API never sees the payload, so it re-reads just the
    header from B2 to confirm the stored bytes match the declared type. Returns
    at most ``length`` bytes (fewer for a tiny object). Raises RuntimeError on
    S3 failure; the caller checks existence separately via ``get_file_metadata``.
    """
    client = get_s3_client()
    try:
        response = client.get_object(
            Bucket=settings.b2_bucket_name,
            Key=key,
            Range=f"bytes=0-{length - 1}",
        )
        return response["Body"].read()
    except ClientError as e:
        raise RuntimeError(f"B2 range-get failed for '{key}': {e}") from e
