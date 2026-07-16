"""Thin adapter over the Stripe SDK.

This is the ONLY module that imports `stripe`, so the architectural invariant
"external SDKs are wrapped in repo/ adapters" holds (enforced by
tests/test_structure.py::test_stripe_only_in_repo). Callers work with plain
dicts + the two typed errors below, never the Stripe types directly.
"""

import stripe

from app.config import settings

# Provenance tag so this sample's traffic is identifiable in Stripe API logs.
# (Stripe is not an S3 service, so the B2 custom-user-agent standard does not
# apply here; this is the Stripe-native equivalent.)
stripe.set_app_info(
    "b2ai-ai-saas-starter-kit",
    url="https://github.com/backblaze-labs/ai-saas-starter-kit",
)


class StripeConfigError(RuntimeError):
    """Raised when a Stripe call is attempted without STRIPE_SECRET_KEY set."""


class StripeSignatureError(RuntimeError):
    """Raised when a webhook payload fails signature verification."""


def is_configured() -> bool:
    """True when a secret key is set, so callers can 503 cleanly if not."""
    return bool(settings.stripe_secret_key)


def is_test_mode() -> bool:
    """True when the configured secret key is a Stripe test-mode key.

    Lets the UI show test-only hints (e.g. the 4242 test card) without leaking
    them into a live deployment. False when Stripe isn't configured.
    """
    return settings.stripe_secret_key.startswith("sk_test_")


def _api_key() -> str:
    if not settings.stripe_secret_key:
        raise StripeConfigError("STRIPE_SECRET_KEY is not configured")
    return settings.stripe_secret_key


def create_checkout_session(
    *,
    price_id: str,
    customer_email: str | None,
    client_reference_id: str,
    success_url: str,
    cancel_url: str,
    customer_id: str | None = None,
) -> str:
    """Create a subscription-mode Checkout Session and return its hosted URL.

    `client_reference_id` (our Supabase user id) is echoed back on the resulting
    events and stamped into the subscription metadata, so the webhook can map a
    Stripe subscription to a user with no extra lookup.
    """
    session = stripe.checkout.Session.create(
        api_key=_api_key(),
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=client_reference_id,
        # Reuse an existing customer if we have one; otherwise Stripe creates one
        # and prefills the email.
        customer=customer_id or None,
        customer_email=None if customer_id else customer_email,
        subscription_data={"metadata": {"user_id": client_reference_id}},
        metadata={"user_id": client_reference_id},
    )
    return session.url


def create_portal_session(*, customer_id: str, return_url: str) -> str:
    """Create a Billing Portal session and return its hosted URL."""
    session = stripe.billing_portal.Session.create(
        api_key=_api_key(),
        customer=customer_id,
        return_url=return_url,
    )
    return session.url


def retrieve_subscription(subscription_id: str) -> dict:
    """Fetch a subscription object (dict-like) from Stripe."""
    return stripe.Subscription.retrieve(subscription_id, api_key=_api_key())


def construct_event(payload: bytes, sig_header: str) -> dict:
    """Verify a webhook signature and return the event, or raise.

    Raises StripeConfigError when no signing secret is set, and
    StripeSignatureError for a bad/absent signature or malformed payload.
    """
    if not settings.stripe_webhook_secret:
        raise StripeConfigError("STRIPE_WEBHOOK_SECRET is not configured")
    try:
        return stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError as e:
        raise StripeSignatureError(f"signature verification failed: {e}") from None
    except ValueError as e:  # malformed JSON payload
        raise StripeSignatureError(f"invalid payload: {e}") from None
