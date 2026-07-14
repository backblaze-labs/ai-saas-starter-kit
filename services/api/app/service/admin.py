"""Admin business logic: assemble the cross-resource overview, list every
resource for the admin grids, and perform the one state-changing admin action
(a role change) with an audit-log entry.

Row -> model mapping for resources that already have a model is delegated to the
service that owns them (generation.job_from_row, billing.subscription_from_row)
so there is a single mapper per resource.
"""

import logging

from app.repo import supabase_admin
from app.service import billing as billing_service
from app.service import generation as generation_service
from app.types.admin import (
    AdminAuditEvent,
    AdminFile,
    AdminOverview,
    AdminProviderRun,
    AdminUser,
)
from app.types.auth import AuthUser
from app.types.billing import Subscription
from app.types.generation import GenerationJob

logger = logging.getLogger(__name__)


class AdminError(RuntimeError):
    """Raised when an admin action cannot be completed (mapped to 4xx by the route)."""


async def overview() -> AdminOverview:
    """One aggregate snapshot for the admin console landing cards."""
    return AdminOverview(
        users=await supabase_admin.count("profiles"),
        admins=await supabase_admin.count("profiles", {"role": "eq.admin"}),
        active_subscriptions=await supabase_admin.count(
            "subscriptions", {"status": "eq.active"}
        ),
        generation_jobs=await supabase_admin.count("generation_jobs"),
        failed_jobs=await supabase_admin.count("generation_jobs", {"status": "eq.failed"}),
        files=await supabase_admin.count("files"),
        storage_bytes=await supabase_admin.sum_storage_bytes(),
        provider_runs=await supabase_admin.count("provider_runs"),
        webhook_events=await supabase_admin.count("stripe_events"),
    )


async def list_users() -> list[AdminUser]:
    return [AdminUser(**row) for row in await supabase_admin.list_users()]


async def list_subscriptions() -> list[Subscription]:
    return [
        billing_service.subscription_from_row(row)
        for row in await supabase_admin.list_subscriptions()
    ]


async def list_jobs() -> list[GenerationJob]:
    return [generation_service.job_from_row(row) for row in await supabase_admin.list_jobs()]


async def list_files() -> list[AdminFile]:
    return [AdminFile(**row) for row in await supabase_admin.list_files()]


async def list_provider_runs() -> list[AdminProviderRun]:
    return [AdminProviderRun(**row) for row in await supabase_admin.list_provider_runs()]


async def list_audit_events() -> list[AdminAuditEvent]:
    return [AdminAuditEvent(**row) for row in await supabase_admin.list_audit_events()]


async def set_user_role(
    *, actor: AuthUser, access_token: str, target_user_id: str, role: str
) -> AdminUser:
    """Change a user's role and record the action in the audit log.

    The PATCH runs with the actor's token so the profiles escalation trigger
    permits it; the audit insert is service-role. Raises AdminError if no such
    user exists.
    """
    updated = await supabase_admin.update_user_role(
        user_id=target_user_id, role=role, access_token=access_token
    )
    if not updated:
        raise AdminError(f"No user with id {target_user_id}")

    # Best-effort audit: the role change is already committed, so a logging
    # failure must not surface as a 500 that hides a successful change. We log
    # loudly instead — the missing audit row is visible in the API logs.
    try:
        await supabase_admin.record_audit_event(
            {
                "actor_id": actor.id,
                "actor_email": actor.email,
                "action": "update_user_role",
                "resource": "user",
                "target_id": target_user_id,
                "detail": {"role": role},
            }
        )
    except Exception:
        logger.exception("failed to audit role change for user=%s", target_user_id)
    logger.info("admin %s set role=%s for user=%s", actor.id, role, target_user_id)
    return AdminUser(**updated)
