"""Account routes — user settings read/write.

Routes
------
GET  /account/settings  — return the caller's persisted preferences
PATCH /account/settings — partially update the caller's preferences
"""

from fastapi import APIRouter, Depends

from app.runtime.auth import get_current_user
from app.service import account as account_service
from app.types.account import UpdateSettingsRequest, UserSettings
from app.types.auth import AuthUser

router = APIRouter(prefix="/account", tags=["account"])


@router.get("/settings", response_model=UserSettings)
async def read_settings(
    current_user: AuthUser = Depends(get_current_user),
) -> UserSettings:
    """Return the authenticated user's saved preferences."""
    return await account_service.get_settings(
        current_user.token, current_user.id
    )


@router.patch("/settings", response_model=UserSettings)
async def patch_settings(
    body: UpdateSettingsRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> UserSettings:
    """Partially update the authenticated user's preferences.

    Only fields included in the request body are updated; omitted fields
    keep their current stored value.
    """
    return await account_service.update_settings(
        current_user.token, current_user.id, body
    )
