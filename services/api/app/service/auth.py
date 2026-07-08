"""Auth business logic: turn a raw access token into a validated AuthUser."""

from app.repo import supabase_auth
from app.types.auth import AuthUser


async def user_from_token(access_token: str) -> AuthUser | None:
    """Validate the token with Supabase and enrich it with the app role.

    Returns None when the token is missing/invalid so callers can raise 401.
    """
    user = await supabase_auth.fetch_user(access_token)
    if not user or not user.get("id"):
        return None
    role = await supabase_auth.fetch_profile_role(access_token, user["id"]) or "user"
    return AuthUser(id=user["id"], email=user.get("email"), role=role)
