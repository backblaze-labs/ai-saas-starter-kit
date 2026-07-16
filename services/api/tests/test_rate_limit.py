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
async def test_write_tier_has_separate_budget(client, monkeypatch):
    # Reads exhausted, but a DELETE draws from the (separate) write budget.
    from app.service import files as files_service

    monkeypatch.setattr(settings, "rate_limit_per_minute", 1)
    monkeypatch.setattr(settings, "rate_limit_write_per_minute", 5)
    monkeypatch.setattr(files_service, "delete_file", lambda key: None)

    await client.get("/health")
    assert (await client.get("/health")).status_code == 429  # read budget spent

    # Delete uses the (still-unspent) write tier, so it is not throttled.
    resp = await client.delete("/files-by-key", params={"key": "uploads/x.txt"})
    assert resp.status_code == 200
