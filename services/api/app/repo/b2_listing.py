"""Full-bucket object listing with a short-TTL, single-flight cache.

Extracted from ``b2_client`` to keep each module focused (and under the file-size
limit). The dashboard and stats endpoints scan the whole bucket repeatedly; this
collapses concurrent/duplicate scans into one and caches the empty-prefix result
briefly. ``get_s3_client`` is imported lazily inside the fetch to avoid a circular
import with ``b2_client`` (which imports the listing helpers back).
"""

import time
from threading import Lock

from botocore.exceptions import ClientError

from app.config import settings

# Only the empty prefix is cached — caching client-supplied `?prefix=` values
# would grow unbounded. Thread-safe: the B2 handlers run in Starlette's
# threadpool.
_LIST_CACHE_TTL_SECONDS = 30.0
_list_cache: dict[str, tuple[float, list[dict]]] = {}
_list_cache_lock = Lock()  # guards _list_cache and _list_generation
_list_scan_lock = Lock()  # single-flight: one bucket scan at a time
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


def list_all_objects(prefix: str = "") -> list[dict]:
    """Paginate through every object under `prefix`, with single-flight caching.

    S3 caps each list_objects_v2 response at 1000 keys, so follow the
    continuation token to collect the full set. The returned list is shared and
    cached — callers must treat it as read-only (never sort/mutate in place).
    Raises RuntimeError on S3 failure.
    """
    # Non-empty prefixes are neither cached nor deduplicated; routing them
    # through the single-flight lock would serialize unrelated scans for no
    # benefit. Scan directly (bounded by rate limiting).
    if prefix != "":
        return _fetch_all_objects(prefix)

    hit = _cached_listing(prefix)
    if hit is not None:
        return hit

    # Single-flight: serialize the (empty-prefix) dashboard scans so a
    # cold/expired/invalidated entry can't trigger a thundering herd. Waiters
    # re-check the cache and reuse the winner's result.
    with _list_scan_lock:
        with _list_cache_lock:
            cached = _list_cache.get(prefix)
            if cached is not None and time.monotonic() - cached[0] < _LIST_CACHE_TTL_SECONDS:
                return cached[1]
            generation = _list_generation

        contents = _fetch_all_objects(prefix)  # scan under the single-flight lock

        with _list_cache_lock:
            # Only store if nothing invalidated the cache mid-scan, else we'd
            # cache a pre-mutation snapshot.
            if generation == _list_generation:
                _list_cache[prefix] = (time.monotonic(), contents)
        return contents


def _fetch_all_objects(prefix: str) -> list[dict]:
    """Paginate B2 for every object under `prefix`. Raises RuntimeError on failure."""
    from app.repo.b2_client import get_s3_client  # lazy: breaks import cycle

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
