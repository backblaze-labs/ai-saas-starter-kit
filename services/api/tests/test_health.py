"""Integration tests for the health + metrics endpoints."""

import pytest

from app.config import settings


@pytest.mark.asyncio
async def test_health_returns_200(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "b2_connected" in data
    assert data["status"] in ("healthy", "degraded")


@pytest.mark.asyncio
async def test_metrics_open_when_no_token(client):
    # METRICS_TOKEN unset (default) → open, for local dev / private scrape.
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text
    assert "uploads_total" in response.text


@pytest.mark.asyncio
async def test_metrics_requires_token_when_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "metrics_token", "s3cret")

    # No token → 401.
    assert (await client.get("/metrics")).status_code == 401
    # Wrong token → 401.
    bad = await client.get("/metrics", headers={"Authorization": "Bearer nope"})
    assert bad.status_code == 401
    # Correct token → 200.
    ok = await client.get("/metrics", headers={"Authorization": "Bearer s3cret"})
    assert ok.status_code == 200
    assert "http_requests_total" in ok.text
