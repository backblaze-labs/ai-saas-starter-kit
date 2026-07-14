"""Admin routes — cross-resource visibility + one state-changing action.

Every endpoint is gated by `require_admin`, so a signed-out caller gets 401 and a
non-admin gets 403. Reads are service-role (they span all users' rows); the role
change is issued with the caller's own token inside the repo so the profiles
escalation trigger permits it.

Endpoints (all under /admin):
  GET  /overview                aggregate counts + storage for the console cards
  GET  /users                   every profile (users grid)
  GET  /subscriptions           every subscription (subscriptions grid)
  GET  /jobs                    every generation job (jobs grid)
  GET  /files                   every generated file (files grid)
  GET  /provider-runs           every provider invocation (provider-usage grid)
  GET  /audit                   the admin audit log (admin-only)
  POST /users/{user_id}/role    change a user's role (audited)
"""

from fastapi import APIRouter, Depends, Header, HTTPException

from app.runtime.auth import require_admin
from app.service import admin as admin_service
from app.service.admin import AdminError
from app.types.admin import (
    AdminAuditEvent,
    AdminFile,
    AdminOverview,
    AdminProviderRun,
    AdminUser,
    RoleUpdateRequest,
)
from app.types.auth import AuthUser
from app.types.billing import Subscription
from app.types.generation import GenerationJob

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview", response_model=AdminOverview)
async def get_overview(_admin: AuthUser = Depends(require_admin)) -> AdminOverview:
    return await admin_service.overview()


@router.get("/users", response_model=list[AdminUser])
async def get_users(_admin: AuthUser = Depends(require_admin)) -> list[AdminUser]:
    return await admin_service.list_users()


@router.get("/subscriptions", response_model=list[Subscription])
async def get_subscriptions(_admin: AuthUser = Depends(require_admin)) -> list[Subscription]:
    return await admin_service.list_subscriptions()


@router.get("/jobs", response_model=list[GenerationJob])
async def get_jobs(_admin: AuthUser = Depends(require_admin)) -> list[GenerationJob]:
    return await admin_service.list_jobs()


@router.get("/files", response_model=list[AdminFile])
async def get_files(_admin: AuthUser = Depends(require_admin)) -> list[AdminFile]:
    return await admin_service.list_files()


@router.get("/provider-runs", response_model=list[AdminProviderRun])
async def get_provider_runs(
    _admin: AuthUser = Depends(require_admin),
) -> list[AdminProviderRun]:
    return await admin_service.list_provider_runs()


@router.get("/audit", response_model=list[AdminAuditEvent])
async def get_audit(_admin: AuthUser = Depends(require_admin)) -> list[AdminAuditEvent]:
    return await admin_service.list_audit_events()


@router.post("/users/{user_id}/role", response_model=AdminUser)
async def set_user_role(
    user_id: str,
    body: RoleUpdateRequest,
    admin: AuthUser = Depends(require_admin),
    authorization: str | None = Header(default=None),
) -> AdminUser:
    # Defense-in-depth against self-lockout: an admin cannot change their own
    # role via the API (the UI also disables the self row). Demoting the last
    # admin would otherwise strand the workspace with no admin surface.
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot change your own role.")
    # require_admin already validated the token; re-extract the raw bearer so the
    # PATCH runs as the admin (the profiles escalation trigger checks auth.uid()).
    token = authorization.split(" ", 1)[1].strip() if authorization else ""
    try:
        return await admin_service.set_user_role(
            actor=admin, access_token=token, target_user_id=user_id, role=body.role
        )
    except AdminError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None
