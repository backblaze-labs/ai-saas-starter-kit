"""Billing routes + the reusable `require_plan` plan-gating dependency.

Endpoints:
  GET  /billing/plans          public plan catalog
  GET  /billing/subscription   caller's current subscription
  GET  /billing/entitlements   caller's derived entitlements
  POST /billing/checkout       create a Stripe Checkout Session (returns url)
  POST /billing/portal         create a Stripe Billing Portal session (returns url)
  POST /billing/webhook        Stripe webhook sink (signature-verified, no auth)
  GET  /billing/pro/preview    Pro-gated demo endpoint (402 for Free)

`require_plan(min_tier)` is the gate the generation slice reuses to lock its
endpoint behind a paid plan.
"""

import logging
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.repo.stripe_client import StripeConfigError, StripeSignatureError
from app.runtime.auth import get_current_user
from app.service import billing as billing_service
from app.service.billing import ActiveSubscriptionError
from app.types.auth import AuthUser
from app.types.billing import (
    TIER_RANK,
    CheckoutRequest,
    CheckoutResponse,
    Entitlements,
    Plan,
    PortalResponse,
    Subscription,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/plans", response_model=list[Plan])
async def list_plans() -> list[Plan]:
    return await billing_service.list_plans()


@router.get("/subscription", response_model=Subscription)
async def read_subscription(
    current_user: AuthUser = Depends(get_current_user),
) -> Subscription:
    return await billing_service.get_subscription(current_user.id)


@router.get("/entitlements", response_model=Entitlements)
async def read_entitlements(
    current_user: AuthUser = Depends(get_current_user),
) -> Entitlements:
    return await billing_service.get_entitlements(current_user.id)


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    body: CheckoutRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> CheckoutResponse:
    try:
        url = await billing_service.create_checkout_url(
            user_id=current_user.id, email=current_user.email, plan_id=body.plan_id
        )
    except StripeConfigError as e:
        raise HTTPException(status_code=503, detail=str(e)) from None
    except ActiveSubscriptionError as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    return CheckoutResponse(url=url)


@router.post("/portal", response_model=PortalResponse)
async def create_portal(
    current_user: AuthUser = Depends(get_current_user),
) -> PortalResponse:
    try:
        url = await billing_service.create_portal_url(user_id=current_user.id)
    except StripeConfigError as e:
        raise HTTPException(status_code=503, detail=str(e)) from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    return PortalResponse(url=url)


@router.post("/webhook")
async def stripe_webhook(request: Request) -> dict:
    """Stripe posts events here. Verified by signature, not by a bearer token."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        return await billing_service.handle_webhook(payload, sig_header)
    except StripeSignatureError as e:
        raise HTTPException(status_code=400, detail=f"Invalid signature: {e}") from None
    except StripeConfigError as e:
        raise HTTPException(status_code=503, detail=str(e)) from None


# --- Plan-gating dependency ------------------------------------------------


def require_plan(
    min_tier: str,
) -> Callable[..., Coroutine[Any, Any, AuthUser]]:
    """Return a dependency that 402s unless the caller's tier >= `min_tier`.

    Reused by the generation slice to lock its endpoint behind a paid plan.
    """

    async def _dependency(
        current_user: AuthUser = Depends(get_current_user),
    ) -> AuthUser:
        entitlements = await billing_service.get_entitlements(current_user.id)
        if TIER_RANK.get(entitlements.tier, 0) < TIER_RANK.get(min_tier, 0):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"This feature requires the {min_tier.capitalize()} plan or higher.",
            )
        return current_user

    return _dependency


@router.get("/pro/preview")
async def pro_preview(
    current_user: AuthUser = Depends(require_plan("pro")),
) -> dict:
    """Demonstrates plan-gating: 402 for Free, 200 once on Pro or Team.

    The generation slice (B3) guards its real endpoint with this same
    `require_plan("pro")`.
    """
    return {"unlocked": True, "message": "Pro features are unlocked for your plan."}
