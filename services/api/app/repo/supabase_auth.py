"""Adapter for the Supabase Auth + PostgREST HTTP APIs.

Token validation is done by asking Supabase who a token belongs to
(`GET /auth/v1/user`) rather than verifying a signature locally. That keeps the
backend agnostic to how the project signs JWTs (local HS256 shared secret vs.
hosted asymmetric signing keys), so pointing at a hosted project is config-only.
"""

import httpx

from app.config import settings
from app.repo import http_client

_TIMEOUT = httpx.Timeout(10.0)


class TokenRejected(Exception):
    """Raised when Supabase rejects the bearer token (401/403) on the live role
    call — distinct from an empty result. On a warm identity-cache hit this is
    the ONLY signal that the token is expired/revoked, so the caller must reject
    the request rather than default to a role (see service.user_from_token)."""


async def fetch_user(access_token: str) -> dict | None:
    """Return the Supabase user for a bearer token, or None if it is invalid."""
    resp = await http_client.get_client().get(
        f"{settings.supabase_url}/auth/v1/user",
        headers={
            "Authorization": f"Bearer {access_token}",
            "apikey": settings.supabase_anon_key,
        },
        timeout=_TIMEOUT,
    )
    if resp.status_code != httpx.codes.OK:
        return None
    return resp.json()


async def fetch_profile_role(access_token: str, user_id: str) -> str | None:
    """Read the caller's role from public.profiles via PostgREST (RLS-scoped)."""
    resp = await http_client.get_client().get(
        f"{settings.supabase_url}/rest/v1/profiles",
        params={"id": f"eq.{user_id}", "select": "role"},
        headers={
            "Authorization": f"Bearer {access_token}",
            "apikey": settings.supabase_anon_key,
            "Accept": "application/json",
        },
        timeout=_TIMEOUT,
    )
    if resp.status_code in (httpx.codes.UNAUTHORIZED, httpx.codes.FORBIDDEN):
        # Token is invalid/expired/revoked. Surface it distinctly so a warm
        # identity-cache hit still rejects, rather than collapsing to None (which
        # would default to role "user" and authenticate an invalid token).
        raise TokenRejected()
    if resp.status_code != httpx.codes.OK:
        # A transient 5xx / other non-200 can't confirm the role; degrade to the
        # default role (fail-safe, least-privilege) rather than logging the user
        # out — do NOT treat it as a rejected token.
        return None
    rows = resp.json()
    return rows[0]["role"] if rows else None
