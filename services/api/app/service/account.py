"""Business-logic layer for user account settings.

Delegates straight to the repo layer — the service boundary exists so callers
in the runtime layer never import from repo directly (architectural invariant).
"""

from app.repo import supabase_account
from app.types.account import UpdateSettingsRequest, UserSettings


async def get_settings(access_token: str, user_id: str) -> UserSettings:
    """Return the caller's persisted settings, falling back to defaults."""
    return await supabase_account.get_settings(access_token, user_id)


async def update_settings(
    access_token: str, user_id: str, patch: UpdateSettingsRequest
) -> UserSettings:
    """Apply a partial patch to the caller's settings and return the result."""
    return await supabase_account.update_settings(access_token, user_id, patch)
