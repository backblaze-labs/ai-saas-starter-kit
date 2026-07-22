"""Tests for the billing slice.

External boundaries (Stripe API, Supabase PostgREST) are stubbed so the routes,
webhook sync, idempotency, and plan-gating are covered hermetically. The one
thing exercised for real is webhook signature verification — it is security-
critical and Stripe's signing scheme is deterministic HMAC, so a locally-signed
payload is byte-identical to what Stripe sends.
"""

import hashlib
import hmac
import json
import time

import httpx
import pytest
from fastapi import HTTPException

from app.repo import stripe_client, supabase_billing
from app.repo.stripe_client import StripeConfigError, StripeSignatureError
from app.runtime.billing import require_plan
from app.service import billing as billing_service
from app.types.auth import AuthUser
from app.types.billing import Entitlements

# --- helpers ---------------------------------------------------------------


def _stripe_signature(payload: bytes, secret: str, ts: int | None = None) -> str:
    ts = ts or int(time.time())
    signed = f"{ts}.".encode() + payload
    mac = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={ts},v1={mac}"


def _sub_event(
    *,
    user_id: str = "u-1",
    price_id: str = "price_pro_test",
    status: str = "active",
    event_type: str = "customer.subscription.updated",
    event_id: str = "evt_test_1",
    created: int | None = 1_700_000_000,
) -> dict:
    return {
        "id": event_id,
        "type": event_type,
        # Stripe EVENT.created (unix seconds) — orders subscription events. Pass
        # created=None to model a webhook whose timestamp is absent.
        "created": created,
        "data": {
            "object": {
                "id": "sub_test_1",
                "customer": "cus_test_1",
                "status": status,
                "cancel_at_period_end": False,
                "metadata": {"user_id": user_id},
                # basil schema: current_period_end lives on the item, not the top level.
                "items": {
                    "data": [{"price": {"id": price_id}, "current_period_end": 1893456000}]
                },
            }
        },
    }


def _checkout_event(
    *,
    user_id: str = "u-1",
    customer: str = "cus_test_1",
    subscription: str | None = "sub_test_1",
    event_id: str = "evt_checkout_1",
) -> dict:
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": user_id,
                "customer": customer,
                "subscription": subscription,
            }
        },
    }


class FakeBillingStore:
    """In-memory stand-in for the supabase_billing repo."""

    def __init__(self) -> None:
        self.events: set[str] = set()
        self.subs: dict[str, dict] = {}

    async def event_seen(self, event_id: str) -> bool:
        return event_id in self.events

    async def record_event(self, event_id: str, event_type: str) -> None:
        self.events.add(event_id)

    async def upsert_subscription(self, row: dict) -> None:
        # Model PostgREST `resolution=merge-duplicates`: ON CONFLICT DO UPDATE
        # sets ONLY the columns present in the payload. Columns the payload
        # omits keep their prior value (on update) or the not-null DB default
        # (on insert). Replacing the whole row here would hide the very clobber
        # the checkout/subscription ordering fix is meant to prevent.
        uid = row["user_id"]
        # Not-null DB defaults from the subscriptions table, applied only when
        # the row is first inserted (see the init schema, billing section).
        db_defaults = {"plan_id": "free", "status": "inactive", "cancel_at_period_end": False}
        base = self.subs.get(uid) or db_defaults
        self.subs[uid] = {**base, **row}

    async def apply_subscription_event(self, row: dict, *, event_created_at: int | None) -> None:
        # Model the `apply_subscription_event` Postgres function's freshness
        # guard: the ON CONFLICT branch fires only when the incoming event is
        # same-or-newer, or ordering is impossible (row has no prior event, or
        # the incoming event has no timestamp). A staler event is a no-op.
        uid = row["user_id"]
        existing = self.subs.get(uid)
        if existing is not None:
            prev = existing.get("last_event_created_at")
            if prev is not None and event_created_at is not None and event_created_at < prev:
                return  # staler event — DB WHERE guard rejects it
        db_defaults = {"plan_id": "free", "status": "inactive", "cancel_at_period_end": False}
        base = existing or db_defaults
        self.subs[uid] = {**base, **row, "last_event_created_at": event_created_at}

    async def get_subscription(self, user_id: str) -> dict | None:
        return self.subs.get(user_id)


@pytest.fixture
def fake_store(monkeypatch):
    store = FakeBillingStore()
    for name in (
        "event_seen",
        "record_event",
        "upsert_subscription",
        "apply_subscription_event",
        "get_subscription",
    ):
        monkeypatch.setattr(supabase_billing, name, getattr(store, name))
    return store


# --- signature verification (real HMAC) ------------------------------------


def test_construct_event_accepts_valid_signature(monkeypatch):
    monkeypatch.setattr(
        stripe_client.settings, "stripe_webhook_secret", "whsec_unit_test"
    )
    payload = json.dumps(_sub_event()).encode()
    sig = _stripe_signature(payload, "whsec_unit_test")
    event = stripe_client.construct_event(payload, sig)
    assert event["id"] == "evt_test_1"


def test_construct_event_rejects_bad_signature(monkeypatch):
    monkeypatch.setattr(
        stripe_client.settings, "stripe_webhook_secret", "whsec_unit_test"
    )
    payload = json.dumps(_sub_event()).encode()
    bad = _stripe_signature(payload, "whsec_WRONG")
    with pytest.raises(StripeSignatureError):
        stripe_client.construct_event(payload, bad)


def test_construct_event_requires_secret(monkeypatch):
    monkeypatch.setattr(stripe_client.settings, "stripe_webhook_secret", "")
    with pytest.raises(StripeConfigError):
        stripe_client.construct_event(b"{}", "t=1,v1=deadbeef")


# --- webhook -> subscription sync ------------------------------------------


@pytest.mark.asyncio
async def test_webhook_syncs_active_subscription(monkeypatch, fake_store):
    monkeypatch.setattr(billing_service.settings, "stripe_price_pro", "price_pro_test")
    monkeypatch.setattr(
        stripe_client, "construct_event", lambda p, s: _sub_event()
    )
    result = await billing_service.handle_webhook(b"{}", "sig")
    assert result["status"] == "processed"
    row = fake_store.subs["u-1"]
    assert row["plan_id"] == "pro"
    assert row["status"] == "active"
    assert row["stripe_customer_id"] == "cus_test_1"
    # current_period_end read from the item (basil schema), not the top level.
    assert row["current_period_end"] is not None
    # entitlements derived from the synced row unlock Pro features.
    ent = await billing_service.get_entitlements("u-1")
    assert ent.tier == "pro" and ent.can_generate is True


@pytest.mark.asyncio
async def test_webhook_is_idempotent(monkeypatch, fake_store):
    monkeypatch.setattr(billing_service.settings, "stripe_price_pro", "price_pro_test")
    monkeypatch.setattr(stripe_client, "construct_event", lambda p, s: _sub_event())
    first = await billing_service.handle_webhook(b"{}", "sig")
    assert first["status"] == "processed"
    # Same event id again: recognised as a duplicate, no re-sync.
    fake_store.subs.clear()
    second = await billing_service.handle_webhook(b"{}", "sig")
    assert second["status"] == "duplicate"
    assert fake_store.subs == {}


@pytest.mark.asyncio
async def test_webhook_deletion_downgrades_to_free(monkeypatch, fake_store):
    monkeypatch.setattr(billing_service.settings, "stripe_price_pro", "price_pro_test")
    event = _sub_event(event_type="customer.subscription.deleted", event_id="evt_del")
    monkeypatch.setattr(stripe_client, "construct_event", lambda p, s: event)
    await billing_service.handle_webhook(b"{}", "sig")
    row = fake_store.subs["u-1"]
    assert row["plan_id"] == "free"
    assert row["status"] == "canceled"


# --- out-of-order subscription events (event-ordering guard) ---------------
# Stripe does not guarantee ordered delivery, so a stale/retried
# customer.subscription.* can arrive after a newer one. The freshness guard
# lives in the `apply_subscription_event` Postgres function; these tests mock
# the repo, so they assert the SERVICE threads the event's `created` through and
# that the guard's semantics (modelled in FakeBillingStore) hold. They do NOT
# execute the SQL — the guard itself is exercised by the RPC-payload test below
# plus manual/e2e DB runs.


@pytest.mark.asyncio
async def test_stale_subscription_update_is_noop(monkeypatch, fake_store):
    """(a) An older customer.subscription.updated arriving AFTER a newer one
    must not overwrite the newer state."""
    monkeypatch.setattr(billing_service.settings, "stripe_price_pro", "price_pro_test")
    monkeypatch.setattr(billing_service.settings, "stripe_price_team", "price_team_test")

    # Newer event lands first: team/active at t=2000.
    newer = _sub_event(
        price_id="price_team_test", event_id="evt_new", created=2_000_000_000
    )
    monkeypatch.setattr(stripe_client, "construct_event", lambda p, s: newer)
    await billing_service.handle_webhook(b"{}", "sig")
    assert fake_store.subs["u-1"]["plan_id"] == "team"

    # Older event (t=1000) is processed last — it downgrades to pro in its
    # payload but must be rejected by the freshness guard.
    older = _sub_event(
        price_id="price_pro_test", event_id="evt_old", created=1_000_000_000
    )
    monkeypatch.setattr(stripe_client, "construct_event", lambda p, s: older)
    await billing_service.handle_webhook(b"{}", "sig")

    row = fake_store.subs["u-1"]
    assert row["plan_id"] == "team", "stale event clobbered newer tier"
    assert row["last_event_created_at"] == 2_000_000_000


@pytest.mark.asyncio
async def test_newer_subscription_update_applies(monkeypatch, fake_store):
    """(b) A newer event arriving after an older one applies normally."""
    monkeypatch.setattr(billing_service.settings, "stripe_price_pro", "price_pro_test")
    monkeypatch.setattr(billing_service.settings, "stripe_price_team", "price_team_test")

    older = _sub_event(
        price_id="price_pro_test", event_id="evt_a", created=1_000_000_000
    )
    monkeypatch.setattr(stripe_client, "construct_event", lambda p, s: older)
    await billing_service.handle_webhook(b"{}", "sig")
    assert fake_store.subs["u-1"]["plan_id"] == "pro"

    newer = _sub_event(
        price_id="price_team_test", event_id="evt_b", created=2_000_000_000
    )
    monkeypatch.setattr(stripe_client, "construct_event", lambda p, s: newer)
    await billing_service.handle_webhook(b"{}", "sig")

    row = fake_store.subs["u-1"]
    assert row["plan_id"] == "team"
    assert row["last_event_created_at"] == 2_000_000_000


@pytest.mark.asyncio
async def test_first_subscription_event_applies_on_new_row(monkeypatch, fake_store):
    """(c) The first subscription event on a brand-new row applies (no prior
    last_event_created_at to compare against)."""
    monkeypatch.setattr(billing_service.settings, "stripe_price_pro", "price_pro_test")
    evt = _sub_event(event_id="evt_first", created=1_500_000_000)
    monkeypatch.setattr(stripe_client, "construct_event", lambda p, s: evt)

    await billing_service.handle_webhook(b"{}", "sig")

    row = fake_store.subs["u-1"]
    assert row["plan_id"] == "pro"
    assert row["status"] == "active"
    assert row["last_event_created_at"] == 1_500_000_000


@pytest.mark.asyncio
async def test_absent_event_created_still_applies(monkeypatch, fake_store):
    """(d) A webhook with no `created` timestamp can't be ordered, so it must
    still apply (guard treats NULL as 'apply') and land None in the column."""
    monkeypatch.setattr(billing_service.settings, "stripe_price_pro", "price_pro_test")
    evt = _sub_event(event_id="evt_no_ts", created=None)
    monkeypatch.setattr(stripe_client, "construct_event", lambda p, s: evt)

    await billing_service.handle_webhook(b"{}", "sig")

    row = fake_store.subs["u-1"]
    assert row["plan_id"] == "pro"
    assert row["last_event_created_at"] is None


@pytest.mark.asyncio
async def test_apply_subscription_event_builds_rpc_call(monkeypatch):
    """The repo must POST the subscription-event upsert to the RPC endpoint with
    the p_-prefixed function params (incl. the event's created timestamp) and
    the service-role auth headers. This asserts the request the DB function
    receives; the SQL guard itself is not executed here (no live Postgres)."""
    monkeypatch.setattr(supabase_billing.settings, "supabase_url", "https://db.example")
    monkeypatch.setattr(
        supabase_billing.settings, "supabase_service_role_key", "svc-role-key"
    )

    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["method"] = request.method
        captured["auth"] = request.headers.get("Authorization")
        captured["apikey"] = request.headers.get("apikey")
        captured["body"] = json.loads(request.content)
        return httpx.Response(204)

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        supabase_billing.httpx,
        "AsyncClient",
        lambda **kw: real_client(transport=transport, **kw),
    )

    row = {
        "user_id": "u-1",
        "plan_id": "pro",
        "status": "active",
        "stripe_customer_id": "cus_1",
        "stripe_subscription_id": "sub_1",
        "current_period_end": "2030-01-01T00:00:00+00:00",
        "cancel_at_period_end": False,
    }
    await supabase_billing.apply_subscription_event(row, event_created_at=1_700_000_000)

    assert captured["method"] == "POST"
    assert captured["url"] == "https://db.example/rest/v1/rpc/apply_subscription_event"
    assert captured["auth"] == "Bearer svc-role-key"
    assert captured["apikey"] == "svc-role-key"
    assert captured["body"] == {
        "p_user_id": "u-1",
        "p_plan_id": "pro",
        "p_status": "active",
        "p_stripe_customer_id": "cus_1",
        "p_stripe_subscription_id": "sub_1",
        "p_current_period_end": "2030-01-01T00:00:00+00:00",
        "p_cancel_at_period_end": False,
        "p_event_created_at": 1_700_000_000,
    }


@pytest.mark.asyncio
async def test_checkout_completed_does_not_clobber_active_subscription(
    monkeypatch, fake_store
):
    """Regression: checkout.session.completed must not downgrade a row that
    customer.subscription.created already set to an active paid tier.

    Both events fire in the same instant on checkout and upsert the SAME
    per-user row. Previously checkout.session.completed wrote plan_id/status
    defaults ('free'/'incomplete') that clobbered the paid row whenever it was
    processed last, leaving a paying customer locked on Free. It must now touch
    only the Stripe id columns.
    """
    monkeypatch.setattr(billing_service.settings, "stripe_price_pro", "price_pro_test")

    # 1. customer.subscription.created lands first: row becomes pro/active.
    sub_evt = _sub_event(event_type="customer.subscription.created", event_id="evt_sub")
    monkeypatch.setattr(stripe_client, "construct_event", lambda p, s: sub_evt)
    await billing_service.handle_webhook(b"{}", "sig")
    assert fake_store.subs["u-1"]["plan_id"] == "pro"
    assert fake_store.subs["u-1"]["status"] == "active"

    # 2. checkout.session.completed is processed last: it must NOT downgrade.
    monkeypatch.setattr(
        stripe_client, "construct_event", lambda p, s: _checkout_event(event_id="evt_chk")
    )
    await billing_service.handle_webhook(b"{}", "sig")

    row = fake_store.subs["u-1"]
    assert row["plan_id"] == "pro", "checkout.session.completed clobbered the paid tier"
    assert row["status"] == "active", "checkout.session.completed clobbered the status"
    # It still records the id mapping so the billing portal works immediately.
    assert row["stripe_customer_id"] == "cus_test_1"
    assert row["stripe_subscription_id"] == "sub_test_1"
    # Entitlements derived from the row stay unlocked.
    ent = await billing_service.get_entitlements("u-1")
    assert ent.tier == "pro" and ent.can_generate is True


@pytest.mark.asyncio
async def test_checkout_completed_persists_mapping_without_unlocking(
    monkeypatch, fake_store
):
    """checkout.session.completed on a brand-new user records the Stripe
    customer/subscription ids (so the portal works) but must not itself grant a
    paid tier — that is owned by the customer.subscription.* events. Until one
    arrives the row keeps the not-null DB defaults and stays locked on Free.
    """
    monkeypatch.setattr(
        stripe_client, "construct_event", lambda p, s: _checkout_event(event_id="evt_new")
    )
    await billing_service.handle_webhook(b"{}", "sig")

    row = fake_store.subs["u-1"]
    assert row["stripe_customer_id"] == "cus_test_1"
    assert row["stripe_subscription_id"] == "sub_test_1"
    # DB defaults, not an unlock.
    assert row["plan_id"] == "free"
    assert row["status"] == "inactive"
    ent = await billing_service.get_entitlements("u-1")
    assert ent.tier == "free" and ent.can_generate is False


# --- entitlements ----------------------------------------------------------


@pytest.mark.asyncio
async def test_entitlements_default_free(monkeypatch, fake_store):
    ent = await billing_service.get_entitlements("nobody")
    assert ent.tier == "free"
    assert ent.active is False
    assert ent.can_generate is False


# --- plan-gating dependency ------------------------------------------------


@pytest.mark.asyncio
async def test_require_plan_blocks_lower_tier(monkeypatch):
    async def fake_entitlements(_uid: str) -> Entitlements:
        return Entitlements(tier="free", rank=0, active=False, can_generate=False)

    monkeypatch.setattr(billing_service, "get_entitlements", fake_entitlements)
    dep = require_plan("pro")
    with pytest.raises(HTTPException) as exc:
        await dep(AuthUser(id="u", email=None, role="user"))
    assert exc.value.status_code == 402


@pytest.mark.asyncio
async def test_require_plan_allows_equal_or_higher(monkeypatch):
    async def fake_entitlements(_uid: str) -> Entitlements:
        return Entitlements(tier="team", rank=2, active=True, can_generate=True)

    monkeypatch.setattr(billing_service, "get_entitlements", fake_entitlements)
    dep = require_plan("pro")
    user = AuthUser(id="u", email=None, role="user")
    assert await dep(user) is user


# --- checkout / portal config guards ---------------------------------------


@pytest.mark.asyncio
async def test_checkout_requires_stripe_config(monkeypatch):
    monkeypatch.setattr(stripe_client.settings, "stripe_secret_key", "")
    with pytest.raises(StripeConfigError):
        await billing_service.create_checkout_url(
            user_id="u", email="u@example.com", plan_id="pro"
        )


@pytest.mark.asyncio
async def test_checkout_rejects_unknown_plan(monkeypatch, fake_store):
    monkeypatch.setattr(stripe_client.settings, "stripe_secret_key", "sk_test_x")
    monkeypatch.setattr(billing_service.settings, "stripe_price_pro", "price_pro_test")
    with pytest.raises(ValueError, match="No Stripe price"):
        await billing_service.create_checkout_url(
            user_id="u", email="u@example.com", plan_id="enterprise"
        )


@pytest.mark.asyncio
async def test_checkout_blocks_active_subscriber(monkeypatch, fake_store):
    # An active subscriber must not open a SECOND Checkout — that creates a second
    # concurrent Stripe subscription (double billing). They get a 409-mapped error
    # and are routed to the Billing Portal instead.
    monkeypatch.setattr(stripe_client.settings, "stripe_secret_key", "sk_test_x")
    monkeypatch.setattr(billing_service.settings, "stripe_price_team", "price_team_test")
    fake_store.subs["u"] = {
        "user_id": "u", "plan_id": "pro", "status": "active", "stripe_customer_id": "cus_x"
    }

    def _fail(**_kw):  # the guard must short-circuit before Stripe is called
        raise AssertionError("create_checkout_session must not run for an active sub")

    monkeypatch.setattr(stripe_client, "create_checkout_session", _fail)

    with pytest.raises(billing_service.ActiveSubscriptionError):
        await billing_service.create_checkout_url(
            user_id="u", email="u@example.com", plan_id="team"
        )


@pytest.mark.asyncio
async def test_checkout_allowed_for_canceled_subscriber(monkeypatch, fake_store):
    # A canceled/inactive user CAN re-subscribe via Checkout (reusing their
    # customer) — the guard only blocks currently-active subscriptions.
    monkeypatch.setattr(stripe_client.settings, "stripe_secret_key", "sk_test_x")
    monkeypatch.setattr(billing_service.settings, "stripe_price_pro", "price_pro_test")
    fake_store.subs["u"] = {
        "user_id": "u", "plan_id": "free", "status": "canceled", "stripe_customer_id": "cus_x"
    }
    monkeypatch.setattr(
        stripe_client, "create_checkout_session", lambda **kw: "https://checkout.example/s"
    )

    url = await billing_service.create_checkout_url(
        user_id="u", email="u@example.com", plan_id="pro"
    )
    assert url == "https://checkout.example/s"


@pytest.mark.asyncio
async def test_active_sub_with_unmapped_price_warns(monkeypatch, fake_store, caplog):
    # A live subscription whose price doesn't map to a paid tier means the
    # STRIPE_PRICE_* env is misconfigured for this deploy — it must be logged
    # loudly, not silently written as a "free" entitlement.
    monkeypatch.setattr(billing_service.settings, "stripe_price_pro", "price_pro_test")
    monkeypatch.setattr(billing_service.settings, "stripe_price_team", "price_team_test")
    evt = _sub_event(price_id="price_UNMAPPED", status="active", event_id="evt_unmapped")
    monkeypatch.setattr(stripe_client, "construct_event", lambda p, s: evt)

    with caplog.at_level("WARNING"):
        await billing_service.handle_webhook(b"{}", "sig")

    assert any("did not map to a paid tier" in r.getMessage() for r in caplog.records)


# --- routes via the ASGI client --------------------------------------------


@pytest.mark.asyncio
async def test_pro_preview_402_for_free(client, monkeypatch):
    from app.service import auth as auth_service

    async def fake_user(_token: str):
        return AuthUser(id="u-free", email="f@example.com", role="user")

    async def free_entitlements(_uid: str):
        return Entitlements(tier="free", rank=0, active=False, can_generate=False)

    monkeypatch.setattr(auth_service, "user_from_token", fake_user)
    monkeypatch.setattr(billing_service, "get_entitlements", free_entitlements)

    resp = await client.get(
        "/billing/pro/preview", headers={"Authorization": "Bearer x"}
    )
    assert resp.status_code == 402


@pytest.mark.asyncio
async def test_pro_preview_unlocks_for_pro(client, monkeypatch):
    from app.service import auth as auth_service

    async def fake_user(_token: str):
        return AuthUser(id="u-pro", email="p@example.com", role="user")

    async def pro_entitlements(_uid: str):
        return Entitlements(tier="pro", rank=1, active=True, can_generate=True)

    monkeypatch.setattr(auth_service, "user_from_token", fake_user)
    monkeypatch.setattr(billing_service, "get_entitlements", pro_entitlements)

    resp = await client.get(
        "/billing/pro/preview", headers={"Authorization": "Bearer x"}
    )
    assert resp.status_code == 200
    assert resp.json()["unlocked"] is True


@pytest.mark.asyncio
async def test_checkout_route_returns_503_without_config(client, monkeypatch):
    from app.service import auth as auth_service

    async def fake_user(_token: str):
        return AuthUser(id="u", email="u@example.com", role="user")

    monkeypatch.setattr(auth_service, "user_from_token", fake_user)
    monkeypatch.setattr(stripe_client.settings, "stripe_secret_key", "")

    resp = await client.post(
        "/billing/checkout",
        headers={"Authorization": "Bearer x"},
        json={"plan_id": "pro"},
    )
    assert resp.status_code == 503


# --- test-mode flag --------------------------------------------------------


def test_is_test_mode_detects_key_prefix(monkeypatch):
    monkeypatch.setattr(stripe_client.settings, "stripe_secret_key", "sk_test_abc")
    assert stripe_client.is_test_mode() is True

    monkeypatch.setattr(stripe_client.settings, "stripe_secret_key", "sk_live_abc")
    assert stripe_client.is_test_mode() is False

    # Unconfigured Stripe must never advertise test mode.
    monkeypatch.setattr(stripe_client.settings, "stripe_secret_key", "")
    assert stripe_client.is_test_mode() is False


@pytest.mark.asyncio
async def test_get_subscription_stamps_test_mode(monkeypatch, fake_store):
    # Derived from the live Stripe key, not stored on the row, so it's correct
    # even for a user who never subscribed (empty store -> synthesised Free).
    monkeypatch.setattr(stripe_client.settings, "stripe_secret_key", "sk_test_abc")
    sub = await billing_service.get_subscription("u-1")
    assert sub.plan_id == "free"
    assert sub.test_mode is True

    monkeypatch.setattr(stripe_client.settings, "stripe_secret_key", "sk_live_abc")
    assert (await billing_service.get_subscription("u-1")).test_mode is False
