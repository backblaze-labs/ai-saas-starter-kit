"""Adapter for user settings stored in public.profiles via PostgREST."""

import logging

import httpx

from app.config import settings
from app.repo import http_client
from app.types.account import UpdateSettingsRequest, UserSettings

logger = logging.getLogger("api")

_TIMEOUT = httpx.Timeout(10.0)

# Settings columns to SELECT — keeps the query narrow and the response stable.
_SETTINGS_COLUMNS = (
    "display_name,bio,theme,default_view,"
    "email_on_upload,warn_near_quota,quota_threshold"
)


async def get_settings(access_token: str, user_id: str) -> UserSettings:
    """Fetch the caller's settings row from public.profiles (RLS-scoped)."""
    resp = await http_client.get_client().get(
        f"{settings.supabase_url}/rest/v1/profiles",
        params={"id": f"eq.{user_id}", "select": _SETTINGS_COLUMNS},
        headers={
            "Authorization": f"Bearer {access_token}",
            "apikey": settings.supabase_anon_key,
            "Accept": "application/json",
        },
        timeout=_TIMEOUT,
    )
    if resp.status_code != httpx.codes.OK:
        logger.warning(
            "Failed to fetch settings",
            extra={"user_id": user_id, "status": resp.status_code},
        )
        return UserSettings()

    rows = resp.json()
    if not rows:
        return UserSettings()
    return UserSettings(**rows[0])


async def update_settings(
    access_token: str, user_id: str, patch: UpdateSettingsRequest
) -> UserSettings:
    """Patch the caller's settings row and return the updated values."""
    # Only send fields that were explicitly set — omit None values so we do a
    # true partial update (unset fields keep their DB value).
    payload = patch.model_dump(exclude_none=True)

    resp = await http_client.get_client().patch(
        f"{settings.supabase_url}/rest/v1/profiles",
        params={"id": f"eq.{user_id}"},
        headers={
            "Authorization": f"Bearer {access_token}",
            "apikey": settings.supabase_anon_key,
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        json=payload,
        timeout=_TIMEOUT,
    )
    if resp.status_code not in (httpx.codes.OK, httpx.codes.NO_CONTENT):
        logger.warning(
            "Failed to update settings",
            extra={"user_id": user_id, "status": resp.status_code},
        )
        # Fall back to a fresh read so the caller still gets a consistent response.
        return await get_settings(access_token, user_id)

    rows = resp.json()
    if not rows:
        return await get_settings(access_token, user_id)
    return UserSettings(**{k: rows[0][k] for k in UserSettings.model_fields if k in rows[0]})
