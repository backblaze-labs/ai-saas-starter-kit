import functools
import io
import mimetypes
import time
from datetime import UTC, datetime
from threading import Lock
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import APP_VERSION, settings
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


def upload_file(
    file_data: bytes, key: str, content_type: str
) -> FileMetadata:
    """Upload file to B2. Raises RuntimeError on S3 failure."""
    client = get_s3_client()
    try:
        client.put_object(
            Bucket=settings.b2_bucket_name,
            Key=key,
            Body=io.BytesIO(file_data),
            ContentType=content_type,
        )
    except ClientError as e:
        raise RuntimeError(f"B2 upload failed for '{key}': {e}") from e
    _invalidate_list_cache()  # new object must show up in listings/stats now
    folder, filename = _split_key(key)
    size = len(file_data)
    return FileMetadata(
        key=key,
        filename=filename,
        folder=folder,
        size_bytes=size,
        size_human=humanize_bytes(size),
        content_type=content_type,
        uploaded_at=datetime.now(UTC),
        url=_public_url(key),
    )


# Short-TTL cache for object listings, keyed by prefix. Caching ALL prefixes (not
# just the empty one) is what collapses the dashboard's per-user scans (files +
# stats + activity all hit uploads/{uid}/ + generated/{uid}/) into one B2 round-
# trip. Bounded by _LIST_CACHE_MAX. Invalidation is global (any upload/delete
# clears every prefix) — coarse but correct; per-user invalidation is future work
# (tech-debt-tracker). Thread-safe: B2 handlers run in Starlette's threadpool.
_LIST_CACHE_TTL_SECONDS = 30.0
_LIST_CACHE_MAX = 1000  # cap distinct cached prefixes (bounds memory)
_list_cache: dict[str, tuple[float, list[dict]]] = {}
_list_cache_lock = Lock()  # guards _list_cache and _list_generation
_list_scan_lock = Lock()  # single-flight: one cold-cache scan at a time
_list_generation = 0  # bumped on invalidation to void in-flight scans


def _invalidate_list_cache() -> None:
    """Drop cached listings and void any scan already in flight (call after any
    upload/delete). Bumping the generation stops a scan that started *before*
    the mutation from writing its stale snapshot back after this clears it.
    """
    global _list_generation
    with _list_cache_lock:
        _list_cache.clear()
        _list_generation += 1


def _cached_listing(prefix: str) -> list[dict] | None:
    """Return a fresh cached listing for `prefix`, or None. Caller holds no lock."""
    with _list_cache_lock:
        cached = _list_cache.get(prefix)
        if cached is not None and time.monotonic() - cached[0] < _LIST_CACHE_TTL_SECONDS:
            return cached[1]
    return None


def _store_listing(prefix: str, contents: list[dict]) -> None:
    """Cache `contents` for `prefix`, evicting the oldest entry when at capacity."""
    with _list_cache_lock:
        if prefix not in _list_cache and len(_list_cache) >= _LIST_CACHE_MAX:
            oldest = min(_list_cache, key=lambda k: _list_cache[k][0])
            del _list_cache[oldest]
        _list_cache[prefix] = (time.monotonic(), contents)


def _list_all_objects(prefix: str = "") -> list[dict]:
    """Paginate through every object under `prefix`, with single-flight caching.
    S3 caps each list_objects_v2 response at 1000 keys, so follow the
    continuation token to collect the full set. The returned list is shared and
    cached — callers must treat it as read-only (never sort/mutate in place).
    Raises RuntimeError on S3 failure.
    """
    hit = _cached_listing(prefix)
    if hit is not None:
        return hit

    # Single-flight: serialize cold-cache scans so an expired/invalidated entry
    # can't trigger a thundering herd (the dashboard fires three endpoints that
    # scan the same prefix at once). Waiters re-check the cache and reuse it.
    with _list_scan_lock:
        hit = _cached_listing(prefix)
        if hit is not None:
            return hit
        with _list_cache_lock:
            generation = _list_generation

        contents = _fetch_all_objects(prefix)  # scan under the single-flight lock

        # Only store if nothing invalidated the cache mid-scan, else we'd cache a
        # pre-mutation snapshot.
        with _list_cache_lock:
            stale = generation != _list_generation
        if not stale:
            _store_listing(prefix, contents)
        return contents


def _fetch_all_objects(prefix: str) -> list[dict]:
    """Paginate B2 for every object under `prefix`. Raises RuntimeError on failure."""
    client = get_s3_client()
    contents: list[dict] = []
    kwargs: dict = {
        "Bucket": settings.b2_bucket_name,
        "Prefix": prefix,
        "MaxKeys": 1000,
    }
    try:
        while True:
            response = client.list_objects_v2(**kwargs)
            contents.extend(response.get("Contents", []))
            if not response.get("IsTruncated"):
                break
            kwargs["ContinuationToken"] = response["NextContinuationToken"]
    except ClientError as e:
        raise RuntimeError(f"B2 list failed: {e}") from e
    return contents


def list_files(prefix: str = "") -> list[FileMetadata]:
    """List all files under `prefix`.

    Paginates the whole prefix so callers see every object, not just the first
    1000. Order is unspecified — callers that need newest-first sort themselves
    (see `service.files.get_files`). Raises RuntimeError on S3 failure.
    """
    files: list[FileMetadata] = []
    for obj in _list_all_objects(prefix):
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
    _invalidate_list_cache()  # deleted object must disappear from listings/stats


def get_presigned_url(
    key: str,
    filename: str | None = None,
    expires_in: int = 600,
    disposition: str = "attachment",
) -> str:
    """Generate a presigned URL. Raises RuntimeError on failure.

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
