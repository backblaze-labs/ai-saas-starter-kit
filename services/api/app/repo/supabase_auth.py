"""Adapter for the Supabase Auth + PostgREST HTTP APIs.

Token validation is done by asking Supabase who a token belongs to
(`GET /auth/v1/user`) rather than verifying a signature locally. That keeps the
backend agnostic to how the project signs JWTs (local HS256 shared secret vs.
hosted asymmetric signing keys), so pointing at a hosted project is config-only.
"""

import httpx

from app.config import settings

_TIMEOUT = httpx.Timeout(10.0)


async def fetch_user(access_token: str) -> dict | None:
    """Return the Supabase user for a bearer token, or None if it is invalid."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{settings.supabase_url}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "apikey": settings.supabase_anon_key,
            },
        )
    if resp.status_code != httpx.codes.OK:
        return None
    return resp.json()


async def fetch_profile_role(access_token: str, user_id: str) -> str | None:
    """Read the caller's role from public.profiles via PostgREST (RLS-scoped)."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/profiles",
            params={"id": f"eq.{user_id}", "select": "role"},
            headers={
                "Authorization": f"Bearer {access_token}",
                "apikey": settings.supabase_anon_key,
                "Accept": "application/json",
            },
        )
    if resp.status_code != httpx.codes.OK:
        return None
    rows = resp.json()
    return rows[0]["role"] if rows else None
