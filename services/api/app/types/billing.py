"""Billing models + the canonical plan-tier ordering used for gating.

Lives in the lowest layer so both the service and runtime layers can import the
tier ranking without a backward import.
"""

from pydantic import BaseModel, Field

# Canonical tier ordering for plan-gating comparisons. The plans table carries a
# `rank` for display/seeding; this mirror keeps gating logic dependency-free (no
# DB round-trip just to compare two tiers).
TIER_RANK: dict[str, int] = {"free": 0, "pro": 1, "team": 2}


class Plan(BaseModel):
    """A row from the public.plans catalog."""

    id: str
    name: str
    rank: int
    price_cents: int
    currency: str = "usd"
    interval: str = "month"
    features: list[str] = Field(default_factory=list)
    is_public: bool = True


class Subscription(BaseModel):
    """A user's current subscription state, synced from Stripe.

    Absence of a stored row is represented as the Free tier (status 'inactive').
    """

    user_id: str
    plan_id: str = "free"
    status: str = "inactive"
    stripe_customer_id: str | None = None
    stripe_subscription_id: str | None = None
    current_period_end: str | None = None
    cancel_at_period_end: bool = False
    # Whether Stripe is in test mode (sk_test_ key). Stamped by the service
    # layer, never stored — lets the UI show test-only hints without leaking
    # them into a live deployment.
    test_mode: bool = False


class Entitlements(BaseModel):
    """What the caller's active plan unlocks (derived from the subscription)."""

    tier: str
    rank: int
    active: bool
    can_generate: bool


class CheckoutRequest(BaseModel):
    plan_id: str


class CheckoutResponse(BaseModel):
    url: str


class PortalResponse(BaseModel):
    url: str
