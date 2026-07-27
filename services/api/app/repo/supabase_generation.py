"""PostgREST adapter for the generation tables.

Reads and writes use the service-role key (bypasses RLS) and run only from the
trusted server path — the generation service already holds the validated user
id from the FastAPI auth dependency. Mirrors supabase_billing.py.
"""

import httpx

from app.config import settings
from app.repo import http_client

_TIMEOUT = httpx.Timeout(15.0)


def is_configured() -> bool:
    """Persistence needs the service-role key; report if it's set."""
    return bool(settings.supabase_service_role_key)


def _service_headers() -> dict[str, str]:
    key = settings.supabase_service_role_key
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


async def count_jobs_since(user_id: str, since_iso: str) -> int:
    """Count a user's generation jobs created at/after `since_iso`.

    Counts jobs (attempts), not successes, so the daily quota also charges for
    failed runs — each attempt spends real provider budget. Uses PostgREST's
    exact-count header so only one row is transferred.
    """
    resp = await http_client.get_client().get(
        f"{settings.supabase_url}/rest/v1/generation_jobs",
        params={
            "user_id": f"eq.{user_id}",
            "created_at": f"gte.{since_iso}",
            "select": "id",
        },
        headers={**_service_headers(), "Prefer": "count=exact", "Range": "0-0"},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    total = resp.headers.get("content-range", "*/0").rsplit("/", 1)[-1]
    return int(total) if total.isdigit() else 0


async def create_job(
    *, user_id: str, prompt: str, model: str, provider: str = "nvidia", seed: int | None = None
) -> dict:
    """Insert a 'running' job row and return it (with its generated id)."""
    row = {
        "user_id": user_id,
        "prompt": prompt,
        "model": model,
        "provider": provider,
        "status": "running",
        "seed": seed,
    }
    resp = await http_client.get_client().post(
        f"{settings.supabase_url}/rest/v1/generation_jobs",
        headers={**_service_headers(), "Prefer": "return=representation"},
        json=row,
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    rows = resp.json()
    return rows[0] if rows else row


async def complete_job(
    job_id: str,
    *,
    status: str,
    run_id: str | None = None,
    manifest_uri: str | None = None,
    canonical_hash: str | None = None,
    cost_usd: float | None = None,
    error: str | None = None,
) -> None:
    """Patch a job to its terminal state (succeeded/failed) + run provenance."""
    patch = {
        "status": status,
        "run_id": run_id,
        "manifest_uri": manifest_uri,
        "canonical_hash": canonical_hash,
        "cost_usd": cost_usd,
        "error": error,
    }
    resp = await http_client.get_client().patch(
        f"{settings.supabase_url}/rest/v1/generation_jobs",
        params={"id": f"eq.{job_id}"},
        headers={**_service_headers(), "Prefer": "return=minimal"},
        json=patch,
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()


async def insert_files(rows: list[dict]) -> None:
    """Insert generated-file rows (idempotent on b2_key)."""
    if not rows:
        return
    resp = await http_client.get_client().post(
        f"{settings.supabase_url}/rest/v1/files",
        params={"on_conflict": "b2_key"},
        headers={**_service_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
        json=rows,
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()


async def record_provider_run(row: dict) -> None:
    """Persist one provider-invocation provenance row."""
    resp = await http_client.get_client().post(
        f"{settings.supabase_url}/rest/v1/provider_runs",
        headers={**_service_headers(), "Prefer": "return=minimal"},
        json=row,
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()


async def record_usage_event(row: dict) -> None:
    """Persist one usage-meter row."""
    resp = await http_client.get_client().post(
        f"{settings.supabase_url}/rest/v1/usage_events",
        headers={**_service_headers(), "Prefer": "return=minimal"},
        json=row,
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()


async def list_jobs(user_id: str, *, limit: int = 50) -> list[dict]:
    """Return a user's jobs newest-first, with their generated files embedded."""
    resp = await http_client.get_client().get(
        f"{settings.supabase_url}/rest/v1/generation_jobs",
        params={
            "user_id": f"eq.{user_id}",
            "select": "*,files(*)",
            "order": "created_at.desc",
            "limit": str(limit),
        },
        headers=_service_headers(),
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()
