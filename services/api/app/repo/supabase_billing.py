"""PostgREST adapter for the billing tables (plans, subscriptions, stripe_events).

Writes — subscription sync and the processed-events log — use the service-role
key and therefore bypass RLS. They run only from the trusted webhook path.

Reads of a user's own subscription are also done server-side by user_id with the
service role, because `require_plan` runs inside a FastAPI dependency that has
the validated user id but not the caller's raw access token.
"""

import httpx

from app.config import settings
from app.repo import http_client

_TIMEOUT = httpx.Timeout(10.0)


def is_configured() -> bool:
    """Billing DB writes/reads need the service-role key; report if it's set."""
    return bool(settings.supabase_service_role_key)


def _service_headers() -> dict[str, str]:
    key = settings.supabase_service_role_key
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


async def list_plans() -> list[dict]:
    """Return the public plan catalog ordered cheapest-first."""
    resp = await http_client.get_client().get(
        f"{settings.supabase_url}/rest/v1/plans",
        params={"select": "*", "is_public": "eq.true", "order": "rank.asc"},
        headers=_service_headers(),
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


async def get_subscription(user_id: str) -> dict | None:
    """Return the user's subscription row, or None when they have never subscribed."""
    resp = await http_client.get_client().get(
        f"{settings.supabase_url}/rest/v1/subscriptions",
        params={"user_id": f"eq.{user_id}", "select": "*"},
        headers=_service_headers(),
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    rows = resp.json()
    return rows[0] if rows else None


async def upsert_subscription(row: dict) -> None:
    """Merge-upsert the per-user subscription row (conflict on user_id).

    ON CONFLICT overwrites only the columns present in `row`; omitted columns
    keep their prior value. Used by the checkout path, which writes ONLY the
    Stripe id mapping so it never clobbers a tier/status the subscription event
    already set (see service._sync_from_checkout)."""
    resp = await http_client.get_client().post(
        f"{settings.supabase_url}/rest/v1/subscriptions",
        params={"on_conflict": "user_id"},
        headers={**_service_headers(), "Prefer": "resolution=merge-duplicates"},
        json=row,
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()


async def apply_subscription_event(row: dict, *, event_created_at: int | None) -> None:
    """Apply a customer.subscription.* event to the user's row, rejecting stale
    ones. Delegates to the `apply_subscription_event` Postgres function via RPC
    so the freshness comparison against `last_event_created_at` is atomic in the
    DB — a read-compare-write here would race under concurrent webhook
    deliveries (Stripe does not guarantee ordered delivery). An out-of-order
    (older) event is a no-op server-side.

    `event_created_at` is the Stripe EVENT's `created` (unix seconds), NOT the
    Subscription object's constant `created`."""
    payload = {
        "p_user_id": row["user_id"],
        "p_plan_id": row["plan_id"],
        "p_status": row["status"],
        "p_stripe_customer_id": row.get("stripe_customer_id"),
        "p_stripe_subscription_id": row.get("stripe_subscription_id"),
        "p_current_period_end": row.get("current_period_end"),
        "p_cancel_at_period_end": row.get("cancel_at_period_end", False),
        "p_event_created_at": event_created_at,
    }
    resp = await http_client.get_client().post(
        f"{settings.supabase_url}/rest/v1/rpc/apply_subscription_event",
        headers=_service_headers(),
        json=payload,
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()


async def event_seen(event_id: str) -> bool:
    """True when this Stripe event id was already processed (idempotency)."""
    resp = await http_client.get_client().get(
        f"{settings.supabase_url}/rest/v1/stripe_events",
        params={"id": f"eq.{event_id}", "select": "id"},
        headers=_service_headers(),
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return bool(resp.json())


async def record_event(event_id: str, event_type: str) -> None:
    """Persist a processed event id; ignore-duplicates keeps this idempotent."""
    resp = await http_client.get_client().post(
        f"{settings.supabase_url}/rest/v1/stripe_events",
        headers={**_service_headers(), "Prefer": "resolution=ignore-duplicates"},
        json={"id": event_id, "type": event_type},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
