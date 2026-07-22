"""Auth business logic: turn a raw access token into a validated AuthUser.

Identity (who a token belongs to) is served from a short-TTL cache to drop one
of the two Supabase round-trips an authenticated request otherwise makes. The
role/authorization decision is NEVER cached — it is fetched live on every
request, so a demoted admin loses access immediately (no privilege-escalation
window). See docs/SECURITY.md (Authentication & Authorization).
"""

import hashlib
import time

from app.config import settings
from app.repo import supabase_auth
from app.types.auth import AuthUser

# Short-TTL identity cache: sha256(token) hex -> (expiry_monotonic, (id, email)).
# Keyed by a hash, never the raw token, so bearer tokens aren't held in memory
# in plaintext. Requests share one event loop and there is no `await` between
# reading and using an entry, so a plain dict is safe without a lock; the size
# cap bounds memory under token churn.
_IDENTITY_CACHE_MAX = 10_000  # cap distinct cached tokens (bounds memory)
_identity_cache: dict[str, tuple[float, tuple[str, str | None]]] = {}


def _reset_cache() -> None:
    """Drop all cached identities (test hook)."""
    _identity_cache.clear()


def _token_key(access_token: str) -> str:
    """Hash the token so the raw bearer value never lands in the cache keyspace."""
    return hashlib.sha256(access_token.encode("utf-8")).hexdigest()


def _cached_identity(key: str) -> tuple[str, str | None] | None:
    """Return a still-fresh cached identity for `key`, or None on miss/expiry."""
    entry = _identity_cache.get(key)
    if entry is not None and time.monotonic() < entry[0]:
        return entry[1]
    return None


def _store_identity(key: str, identity: tuple[str, str | None], ttl: float) -> None:
    """Cache `identity` under `key`, purging expired entries then capping size."""
    now = time.monotonic()
    if key not in _identity_cache and len(_identity_cache) >= _IDENTITY_CACHE_MAX:
        # Purge anything already expired first; only if still at capacity do we
        # evict the soonest-to-expire entry, so churn can't grow the dict.
        for expired in [k for k, (exp, _) in _identity_cache.items() if exp <= now]:
            del _identity_cache[expired]
        if len(_identity_cache) >= _IDENTITY_CACHE_MAX:
            del _identity_cache[min(_identity_cache, key=lambda k: _identity_cache[k][0])]
    _identity_cache[key] = (now + ttl, identity)


async def user_from_token(access_token: str) -> AuthUser | None:
    """Validate the token with Supabase and enrich it with the app role.

    The identity lookup (GET /auth/v1/user) is served from a short-TTL cache when
    warm; the role (GET /rest/v1/profiles) is ALWAYS fetched live so an
    authorization decision is never stale. Returns None when the token is
    missing/invalid so callers can raise 401.
    """
    ttl = settings.auth_cache_ttl_seconds
    key = _token_key(access_token) if ttl > 0 else None

    identity = _cached_identity(key) if key is not None else None
    if identity is None:
        user = await supabase_auth.fetch_user(access_token)
        if not user or not user.get("id"):
            return None  # invalid token — never cached as valid
        identity = (user["id"], user.get("email"))
        if key is not None:
            _store_identity(key, identity, ttl)

    user_id, email = identity
    # Role/authorization is fetched live on EVERY request — see module docstring.
    role = await supabase_auth.fetch_profile_role(access_token, user_id) or "user"
    return AuthUser(id=user_id, email=email, role=role)
