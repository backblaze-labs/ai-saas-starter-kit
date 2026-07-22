"""Billing business logic: plan catalog, entitlements, checkout/portal session
creation, and idempotent Stripe-webhook -> Supabase subscription sync.

Stripe price IDs are account-specific and live in settings, so this module maps
plan tier <-> Stripe price in both directions rather than storing price IDs in
the database.
"""

import logging
from datetime import UTC, datetime
from functools import partial

from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.repo import stripe_client, supabase_billing
from app.repo.stripe_client import StripeConfigError
from app.types.billing import TIER_RANK, Entitlements, Plan, Subscription

logger = logging.getLogger(__name__)


class ActiveSubscriptionError(RuntimeError):
    """Raised when a user with an active subscription tries to start a new
    Checkout. A second subscription-mode Checkout would create a SECOND Stripe
    subscription on the same customer (double billing) — plan changes must go
    through the Billing Portal instead. The route maps this to 409."""


# Stripe subscription statuses that entitle the user to paid features.
_ACTIVE_STATUSES = frozenset({"active", "trialing"})

# Stripe subscription events whose object is a Subscription we can sync directly.
_SUBSCRIPTION_EVENTS = frozenset(
    {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }
)


def _tier_to_price(plan_id: str) -> str | None:
    return {
        "pro": settings.stripe_price_pro,
        "team": settings.stripe_price_team,
    }.get(plan_id) or None


def _price_to_tier(price_id: str | None) -> str:
    if not price_id:
        return "free"
    mapping = {
        settings.stripe_price_pro: "pro",
        settings.stripe_price_team: "team",
    }
    # Drop the empty-string key that unset env vars would introduce.
    mapping.pop("", None)
    return mapping.get(price_id, "free")


def _iso_from_unix(ts: int | None) -> str | None:
    if not ts:
        return None
    return datetime.fromtimestamp(int(ts), tz=UTC).isoformat()


async def list_plans() -> list[Plan]:
    return [Plan(**row) for row in await supabase_billing.list_plans()]


def subscription_from_row(row: dict) -> Subscription:
    """Map a subscriptions PostgREST row to the API model (keeps only modelled
    fields). Shared by the per-user read here and the admin all-subs list.

    `test_mode` is stamped by the service (see `get_subscription`), never read
    from the row."""
    fields = {k: row.get(k) for k in Subscription.model_fields if k != "test_mode"}
    return Subscription(**fields)


async def get_subscription(user_id: str) -> Subscription:
    row = await supabase_billing.get_subscription(user_id)
    if not row:
        sub = Subscription(user_id=user_id, plan_id="free", status="inactive")
    else:
        sub = subscription_from_row(row)
    sub.test_mode = stripe_client.is_test_mode()
    return sub


async def get_entitlements(user_id: str) -> Entitlements:
    sub = await get_subscription(user_id)
    active = sub.status in _ACTIVE_STATUSES
    tier = sub.plan_id if active else "free"
    rank = TIER_RANK.get(tier, 0)
    return Entitlements(tier=tier, rank=rank, active=active, can_generate=rank >= 1)


async def create_checkout_url(*, user_id: str, email: str | None, plan_id: str) -> str:
    """Create a Checkout Session for `plan_id` and return its hosted URL."""
    if not stripe_client.is_configured():
        raise StripeConfigError("STRIPE_SECRET_KEY is not configured")
    price_id = _tier_to_price(plan_id)
    if not price_id:
        raise ValueError(
            f"No Stripe price configured for plan '{plan_id}' "
            "(set STRIPE_PRICE_PRO / STRIPE_PRICE_TEAM)."
        )
    existing = await supabase_billing.get_subscription(user_id)
    # Guard against double billing: an active subscriber must change plans via the
    # Billing Portal (which swaps/prorates the existing subscription), not a new
    # Checkout (which would open a second concurrent subscription).
    if existing and existing.get("status") in _ACTIVE_STATUSES:
        raise ActiveSubscriptionError(
            "You already have an active subscription. Use 'Manage billing' to "
            "change your plan."
        )
    customer_id = existing.get("stripe_customer_id") if existing else None
    # The Stripe SDK is synchronous (blocking HTTP). Offload it so the network
    # round-trip doesn't stall the event loop for every other in-flight request.
    return await run_in_threadpool(
        partial(
            stripe_client.create_checkout_session,
            price_id=price_id,
            customer_email=email,
            client_reference_id=user_id,
            success_url=settings.billing_success_url,
            cancel_url=settings.billing_cancel_url,
            customer_id=customer_id,
        )
    )


async def create_portal_url(*, user_id: str) -> str:
    """Create a Billing Portal session for the user's Stripe customer."""
    if not stripe_client.is_configured():
        raise StripeConfigError("STRIPE_SECRET_KEY is not configured")
    existing = await supabase_billing.get_subscription(user_id)
    customer_id = existing.get("stripe_customer_id") if existing else None
    if not customer_id:
        raise ValueError("No Stripe customer for this user yet — subscribe first.")
    # Offload the blocking Stripe SDK call off the event loop (see checkout).
    return await run_in_threadpool(
        partial(
            stripe_client.create_portal_session,
            customer_id=customer_id,
            return_url=settings.billing_portal_return_url,
        )
    )


async def handle_webhook(payload: bytes, sig_header: str) -> dict:
    """Verify + process a Stripe webhook event, idempotently.

    Signature/config errors propagate (the route maps them to 400/503). A
    duplicate event (already in stripe_events) is a no-op.
    """
    event = stripe_client.construct_event(payload, sig_header)
    event_id = event["id"]
    event_type = event["type"]

    if await supabase_billing.event_seen(event_id):
        return {"status": "duplicate", "id": event_id}

    obj = event["data"]["object"]
    if event_type in _SUBSCRIPTION_EVENTS:
        # event["created"] (unix seconds) orders subscription events; a staler
        # one is rejected DB-side (see repo.apply_subscription_event).
        await _sync_subscription(
            obj,
            deleted=event_type.endswith("deleted"),
            event_created_at=event.get("created"),
        )
    elif event_type == "checkout.session.completed":
        await _sync_from_checkout(obj)

    await supabase_billing.record_event(event_id, event_type)
    logger.info("Processed Stripe event id=%s type=%s", event_id, event_type)
    return {"status": "processed", "id": event_id, "type": event_type}


async def _sync_subscription(
    sub_obj: dict, *, deleted: bool, event_created_at: int | None
) -> None:
    """Upsert the per-user subscription row from a Stripe Subscription object.

    `event_created_at` is the enclosing Stripe event's `created` timestamp; it
    lets the repo reject an out-of-order (staler) event DB-side."""
    user_id = (sub_obj.get("metadata") or {}).get("user_id")
    if not user_id:
        logger.warning(
            "Subscription %s has no user_id metadata; skipping sync",
            sub_obj.get("id"),
        )
        return

    items = (sub_obj.get("items") or {}).get("data") or []
    first_item = items[0] if items else {}
    price_id = (first_item.get("price") or {}).get("id")
    tier = _price_to_tier(price_id)

    # A live, paying subscription whose price maps to "free" means STRIPE_PRICE_*
    # is unset/misconfigured for this deploy — the customer would be silently
    # locked out. Surface it loudly rather than writing a wrong entitlement.
    if not deleted and tier == "free" and sub_obj.get("status") in _ACTIVE_STATUSES:
        logger.warning(
            "Active subscription %s price=%s did not map to a paid tier — check "
            "STRIPE_PRICE_PRO / STRIPE_PRICE_TEAM.",
            sub_obj.get("id"),
            price_id,
        )

    # Stripe's 2025 "basil" API moved current_period_end from the Subscription
    # onto each subscription item; fall back to the legacy top-level field for
    # older API versions.
    period_end = first_item.get("current_period_end") or sub_obj.get("current_period_end")

    row = {
        "user_id": user_id,
        "plan_id": "free" if deleted else tier,
        "status": "canceled" if deleted else sub_obj.get("status", "inactive"),
        "stripe_customer_id": sub_obj.get("customer"),
        "stripe_subscription_id": sub_obj.get("id"),
        "current_period_end": _iso_from_unix(period_end),
        "cancel_at_period_end": bool(sub_obj.get("cancel_at_period_end", False)),
    }
    await supabase_billing.apply_subscription_event(row, event_created_at=event_created_at)


async def _sync_from_checkout(session_obj: dict) -> None:
    """On checkout completion, persist ONLY the Stripe id mapping.

    Plan tier and status are owned exclusively by the customer.subscription.*
    events (which carry the price + user_id metadata). This event fires in the
    same instant and upserts the SAME per-user row, so it must NOT write plan_id
    or status: doing so once let its stale 'free'/'incomplete' defaults clobber
    the 'pro'/'active' row that customer.subscription.created had just written,
    when the two events were processed out of order — leaving a paying user
    locked on Free.

    Writing only the id columns keeps the billing portal working immediately (it
    needs the customer id) while leaving tier/status untouched: the merge-upsert
    only overwrites the columns present here. On a brand-new row the not-null DB
    defaults ('free'/'inactive') apply, so the user stays correctly locked until
    the subscription event lands. Omitting stripe_subscription_id when the
    session has none likewise preserves any id already on the row.
    """
    user_id = session_obj.get("client_reference_id")
    if not user_id:
        return
    row = {
        "user_id": user_id,
        "stripe_customer_id": session_obj.get("customer"),
    }
    subscription_id = session_obj.get("subscription")
    if subscription_id:
        row["stripe_subscription_id"] = subscription_id
    await supabase_billing.upsert_subscription(row)
