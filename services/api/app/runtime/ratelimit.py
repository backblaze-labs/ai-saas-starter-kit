"""Per-IP fixed-window rate limiting.

The file endpoints (list/stats/upload/download/delete) are authenticated and
per-user scoped, but a single authenticated client can still hammer the
expensive list/stats endpoints or loop delete/download calls — a DoS and a
Backblaze transaction/egress cost-amplification vector. This is a small,
dependency-free fixed-window limiter (per client IP, ahead of auth).

Scope: in-process, per replica. That's acceptable for a starter kit; horizontal
scaling (multiple Railway replicas) needs a shared store like Redis. Documented
in docs/RELIABILITY.md.
"""

import time
from threading import Lock

from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.types import ErrorResponse

_WINDOW_SECONDS = 60.0
# Sweep stale entries only once the map grows past this, to bound memory
# without paying an O(n) prune on every request.
_MAX_TRACKED = 10_000

_lock = Lock()
# (ip, tier) -> (window_start_monotonic, count)
_state: dict[tuple[str, str], tuple[float, int]] = {}


def _client_ip(request: Request) -> str:
    """Best-effort client IP.

    Trust only the RIGHTMOST `X-Forwarded-For` entry — the address the trusted
    edge proxy (Railway) appended. The leftmost entries are client-supplied and
    trivially spoofable; keying on them would let a caller mint a fresh limiter
    bucket per request (bypassing the limit and ballooning `_state`). Behind
    multiple proxies, adjust the trusted-hop selection accordingly.
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        hop = xff.split(",")[-1].strip()
        if hop:
            return hop
    return request.client.host if request.client else "unknown"


def _tier_and_limit(request: Request) -> tuple[str, int]:
    """Expensive/mutating requests get the tighter 'write' cap."""
    path = request.url.path
    if request.method in ("POST", "DELETE") or path.endswith(
        ("/download", "/preview")
    ):
        return "write", settings.rate_limit_write_per_minute
    return "read", settings.rate_limit_per_minute


def _reset_state() -> None:
    """Clear all counters. Used by tests to stay hermetic."""
    with _lock:
        _state.clear()


async def rate_limit_middleware(request: Request, call_next):
    ip = _client_ip(request)
    tier, limit = _tier_and_limit(request)
    now = time.monotonic()
    key = (ip, tier)

    with _lock:
        if len(_state) >= _MAX_TRACKED:
            # Drop expired windows; if a genuine flood of distinct IPs still
            # keeps the map full, reset it wholesale. Bounds memory in a single
            # O(n) pass, and only runs at the cap so the common path is O(1).
            for k in [k for k, (s, _) in _state.items() if now - s >= _WINDOW_SECONDS]:
                del _state[k]
            if len(_state) >= _MAX_TRACKED:
                _state.clear()

        start, count = _state.get(key, (now, 0))
        if now - start >= _WINDOW_SECONDS:
            start, count = now, 0
        count += 1
        _state[key] = (start, count)
        over_limit = count > limit

    if over_limit:
        return JSONResponse(
            status_code=429,
            content=ErrorResponse(
                detail="Rate limit exceeded. Try again shortly."
            ).model_dump(),
            headers={"Retry-After": str(int(_WINDOW_SECONDS))},
        )
    return await call_next(request)
