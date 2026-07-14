"""Admin models: the aggregate overview, the admin-specific resource rows, and
the role-change request.

Resources already modelled elsewhere are reused by the admin routes rather than
re-declared: subscriptions -> app.types.billing.Subscription, generation jobs ->
app.types.generation.GenerationJob. Only shapes with no existing model live here.
"""

from pydantic import BaseModel, Field


class AdminOverview(BaseModel):
    """Aggregate counts + storage for the admin console landing cards."""

    users: int = 0
    admins: int = 0
    active_subscriptions: int = 0
    generation_jobs: int = 0
    failed_jobs: int = 0
    files: int = 0
    storage_bytes: int = 0
    provider_runs: int = 0
    webhook_events: int = 0


class AdminUser(BaseModel):
    """A public.profiles row for the admin users grid."""

    id: str
    email: str | None = None
    full_name: str | None = None
    role: str = "user"
    created_at: str | None = None


class AdminFile(BaseModel):
    """A public.files row (a generated asset) for the admin files grid."""

    id: str
    user_id: str
    job_id: str | None = None
    b2_key: str
    url: str | None = None
    media_type: str | None = None
    size_bytes: int | None = None
    created_at: str | None = None


class AdminProviderRun(BaseModel):
    """A public.provider_runs row for the admin provider-usage grid."""

    id: str
    job_id: str
    provider: str
    model: str
    run_id: str | None = None
    status: str
    cost_usd: float | None = None
    assets_count: int = 0
    created_at: str | None = None


class AdminAuditEvent(BaseModel):
    """A public.admin_audit_events row for the admin audit grid."""

    id: str
    actor_id: str | None = None
    actor_email: str | None = None
    action: str
    resource: str
    target_id: str | None = None
    detail: dict = Field(default_factory=dict)
    created_at: str | None = None


class RoleUpdateRequest(BaseModel):
    """Body for POST /admin/users/{user_id}/role. Only the two catalog roles."""

    role: str = Field(pattern="^(user|admin)$")
