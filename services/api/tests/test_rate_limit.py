"""Tests for per-IP fixed-window rate limiting."""

import pytest

from app.config import settings


@pytest.mark.asyncio
async def test_read_requests_are_rate_limited(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_per_minute", 3)

    # /health is a read-tier GET; the 4th within the window is rejected.
    statuses = [(await client.get("/health")).status_code for _ in range(4)]
    assert statuses == [200, 200, 200, 429]


@pytest.mark.asyncio
async def test_rate_limited_response_shape(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_per_minute", 1)

    await client.get("/health")
    resp = await client.get("/health")

    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    assert resp.json()["detail"]


@pytest.mark.asyncio
async def test_write_tier_has_separate_budget(auth_client, monkeypatch):
    # Reads exhausted, but a DELETE draws from the (separate) write budget.
    from app.service import files as files_service

    from .conftest import TEST_USER_ID

    monkeypatch.setattr(settings, "rate_limit_per_minute", 1)
    monkeypatch.setattr(settings, "rate_limit_write_per_minute", 5)
    monkeypatch.setattr(files_service, "delete_file", lambda key: None)

    await auth_client.get("/health")
    assert (await auth_client.get("/health")).status_code == 429  # read budget spent

    # Delete uses the (still-unspent) write tier, so it is not throttled. The key
    # is under the caller's own prefix so ownership scoping resolves it.
    resp = await auth_client.delete(
        "/files-by-key", params={"key": f"uploads/{TEST_USER_ID}/x.txt"}
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_stripe_webhook_is_not_rate_limited(client, monkeypatch):
    # Stripe webhooks arrive from a few shared egress IPs, so the endpoint is
    # exempt from the per-IP limiter (signature verification is its guard). Even
    # with a write budget of 1, repeated posts are never 429 — they fall through
    # to the endpoint (503 here: no STRIPE_WEBHOOK_SECRET configured in tests).
    monkeypatch.setattr(settings, "rate_limit_write_per_minute", 1)

    statuses = [(await client.post("/billing/webhook")).status_code for _ in range(3)]
    assert 429 not in statuses


@pytest.mark.asyncio
async def test_xff_ignored_when_trust_proxy_off(client, monkeypatch):
    # Default (trust_proxy=False): a directly-exposed deploy must NOT trust
    # X-Forwarded-For. A client rotating the header per request must not mint a
    # fresh bucket each time — all requests key on the real socket peer, so the
    # limit is shared and the 3rd (over a budget of 2) is rejected.
    assert settings.trust_proxy is False
    monkeypatch.setattr(settings, "rate_limit_per_minute", 2)

    statuses = [
        (
            await client.get(
                "/health", headers={"X-Forwarded-For": f"{i}.{i}.{i}.{i}"}
            )
        ).status_code
        for i in range(3)
    ]
    assert statuses == [200, 200, 429]


@pytest.mark.asyncio
async def test_xff_honored_when_trust_proxy_on(client, monkeypatch):
    # Behind a trusted proxy (trust_proxy=True): the limiter keys on the
    # rightmost XFF hop, so distinct client IPs get distinct buckets and none is
    # throttled even though they exceed a single bucket's budget.
    monkeypatch.setattr(settings, "trust_proxy", True)
    monkeypatch.setattr(settings, "rate_limit_per_minute", 2)

    statuses = [
        (
            await client.get(
                "/health", headers={"X-Forwarded-For": f"{i}.{i}.{i}.{i}"}
            )
        ).status_code
        for i in range(4)
    ]
    assert statuses == [200, 200, 200, 200]

    # Same trusted-proxy client IP still shares one bucket — the 3rd trips.
    same_ip = {"X-Forwarded-For": "10.0.0.9"}
    repeat = [
        (await client.get("/health", headers=same_ip)).status_code
        for _ in range(3)
    ]
    assert repeat == [200, 200, 429]
