"""Full-bucket object listing with a short-TTL, single-flight cache.

Extracted from ``b2_client`` to keep each module under the file-size limit once
the direct-to-B2 upload helpers landed. The dashboard and stats endpoints scan
the same per-user prefixes repeatedly; this collapses concurrent/duplicate scans
into one and caches each prefix's result briefly. ``get_s3_client`` is imported
lazily inside the fetch to avoid an import cycle with ``b2_client`` (which imports
these helpers back).
"""

import time
from threading import Lock

from botocore.exceptions import ClientError

from app.config import settings

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


def invalidate_list_cache() -> None:
    """Drop cached listings and void any scan already in flight (call after any
    upload/delete/finalize). Bumping the generation stops a scan that started
    *before* the mutation from writing its stale snapshot back after this clears
    it. Public because the finalize path (service/upload) must invalidate too —
    the browser writes the object straight to B2, so the repo has no other hook.
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


def list_all_objects(prefix: str = "") -> list[dict]:
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
