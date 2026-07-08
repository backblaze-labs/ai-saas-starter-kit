"""Auth routes + the reusable get_current_user dependency.

Other routers can depend on `get_current_user` to require a valid Supabase
session, or `require_admin` to gate admin-only endpoints (used from the admin
slice onward).
"""

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.service import auth as auth_service
from app.types.auth import AuthUser

router = APIRouter()


async def get_current_user(authorization: str | None = Header(default=None)) -> AuthUser:
    """FastAPI dependency: resolve the bearer token to an AuthUser or raise 401."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    token = authorization.split(" ", 1)[1].strip()
    user = await auth_service.user_from_token(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return user


async def require_admin(current_user: AuthUser = Depends(get_current_user)) -> AuthUser:
    """FastAPI dependency: require an authenticated admin."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user


@router.get("/me", response_model=AuthUser)
async def read_me(current_user: AuthUser = Depends(get_current_user)) -> AuthUser:
    """Return the authenticated identity — proves the backend accepts the token."""
    return current_user
