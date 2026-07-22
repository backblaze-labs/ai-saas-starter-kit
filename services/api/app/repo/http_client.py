"""Process-wide pooled httpx.AsyncClient shared by the Supabase HTTP adapters.

Every Supabase repo call used to open and tear down its own
`httpx.AsyncClient`, so the auth hot path (two calls per request via
`get_current_user`) paid full TCP + TLS setup on every hop. This module owns a
single client whose connection pool is reused across all Supabase requests. It
is created on FastAPI startup and closed on shutdown (see `main.lifespan`).

Per-call timeouts are still passed explicitly by each adapter
(`timeout=_TIMEOUT`), so each repo keeps its own timeout semantics — this client
only owns the shared connection pool, not the timeout policy.
"""

import logging

import httpx

logger = logging.getLogger("api")

# Fallback timeout for the shared client. Individual repo calls override this
# per-request with their own `_TIMEOUT`, so this default is rarely hit.
_DEFAULT_TIMEOUT = httpx.Timeout(10.0)

# Make the shared pool's ceiling explicit rather than relying on httpx defaults,
# so the connection budget is visible and tunable. Sized to the API's likely
# concurrency (Supabase does ~2 hops per authed request); httpx queues callers
# beyond the limit rather than erroring.
_LIMITS = httpx.Limits(max_connections=100, max_keepalive_connections=20)

_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    """Return the shared client, lazily creating one if the lifespan never ran.

    The lazy path keeps tests that drive the app via TestClient/ASGITransport
    (no startup event) working without wiring the lifespan into every fixture.
    """
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT, limits=_LIMITS)
        logger.info("Created shared Supabase httpx client")
    return _client


async def init_client() -> None:
    """Eagerly create the shared client on startup (idempotent)."""
    get_client()


async def close_client() -> None:
    """Close the shared client on shutdown. Safe to call more than once."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        logger.info("Closed shared Supabase httpx client")
    _client = None
