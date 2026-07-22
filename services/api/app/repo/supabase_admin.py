"""PostgREST adapter for admin reads, counts, and the admin audit log.

All list/count reads use the service-role key (bypasses RLS) and run only behind
the `require_admin` dependency, which has already proven the caller is an admin.

The one write that changes user state — a role change — is issued with the
CALLER'S token, NOT the service role, on purpose: public.profiles has a
`prevent_role_escalation` trigger that calls public.is_admin() against
auth.uid(), so a service-role PATCH (auth.uid() is null) would be rejected. The
audit-log insert is service-role (append-only, no client policy).
"""

import httpx

from app.config import settings
from app.repo import http_client

_TIMEOUT = httpx.Timeout(15.0)


def is_configured() -> bool:
    """Admin reads/writes need the service-role key; report whether it is set."""
    return bool(settings.supabase_service_role_key)


def _service_headers() -> dict[str, str]:
    key = settings.supabase_service_role_key
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


async def _list(table: str, params: dict) -> list[dict]:
    resp = await http_client.get_client().get(
        f"{settings.supabase_url}/rest/v1/{table}",
        params=params,
        headers=_service_headers(),
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


async def count(table: str, filters: dict | None = None) -> int:
    """Exact row count via PostgREST's Content-Range header.

    `Prefer: count=exact` + a 0-0 range returns the total in `Content-Range`
    (e.g. `0-0/123`, or `*/0` when empty) while transferring only one row.
    """
    resp = await http_client.get_client().get(
        f"{settings.supabase_url}/rest/v1/{table}",
        params=filters or {},
        headers={
            **_service_headers(),
            "Prefer": "count=exact",
            "Range-Unit": "items",
            "Range": "0-0",
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    total = resp.headers.get("content-range", "*/0").rsplit("/", 1)[-1]
    return int(total) if total.isdigit() else 0


async def sum_storage_bytes(limit: int = 10000) -> int:
    """Sum size_bytes across the generated-files mirror (demo-scale aggregation)."""
    rows = await _list("files", {"select": "size_bytes", "limit": str(limit)})
    return sum(int(r.get("size_bytes") or 0) for r in rows)


async def list_users(limit: int = 500) -> list[dict]:
    return await _list(
        "profiles", {"select": "*", "order": "created_at.desc", "limit": str(limit)}
    )


async def list_subscriptions(limit: int = 500) -> list[dict]:
    return await _list(
        "subscriptions", {"select": "*", "order": "created_at.desc", "limit": str(limit)}
    )


async def list_jobs(limit: int = 500) -> list[dict]:
    return await _list(
        "generation_jobs",
        {"select": "*,files(*)", "order": "created_at.desc", "limit": str(limit)},
    )


async def list_files(limit: int = 500) -> list[dict]:
    return await _list(
        "files", {"select": "*", "order": "created_at.desc", "limit": str(limit)}
    )


async def list_provider_runs(limit: int = 500) -> list[dict]:
    return await _list(
        "provider_runs", {"select": "*", "order": "created_at.desc", "limit": str(limit)}
    )


async def list_audit_events(limit: int = 500) -> list[dict]:
    return await _list(
        "admin_audit_events",
        {"select": "*", "order": "created_at.desc", "limit": str(limit)},
    )


async def record_audit_event(row: dict) -> None:
    """Append one audit row (service role; the table has no client write policy)."""
    resp = await http_client.get_client().post(
        f"{settings.supabase_url}/rest/v1/admin_audit_events",
        headers={**_service_headers(), "Prefer": "return=minimal"},
        json=row,
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()


async def update_user_role(*, user_id: str, role: str, access_token: str) -> dict | None:
    """PATCH a profile's role using the CALLER'S token.

    Using the admin's own token (not the service role) lets the profiles
    `prevent_role_escalation` trigger see a valid auth.uid() and allow the change;
    the RLS `profiles_update_admin` policy gates it to admins. Returns the updated
    row, or None if no row matched.
    """
    resp = await http_client.get_client().patch(
        f"{settings.supabase_url}/rest/v1/profiles",
        params={"id": f"eq.{user_id}"},
        headers={
            "apikey": settings.supabase_anon_key,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        json={"role": role},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    rows = resp.json()
    return rows[0] if rows else None
