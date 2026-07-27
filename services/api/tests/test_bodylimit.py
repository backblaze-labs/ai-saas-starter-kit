"""Tests for the ASGI body-size-limit middleware.

Exercised in isolation around a tiny echo app so the cap can be a few bytes
(no need to push 100MB through the suite). Covers both the Content-Length fast
path and the streamed-body meter that catches a chunked / no-Content-Length
request the header check can't see.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.runtime.bodylimit import BodySizeLimitMiddleware


async def _echo_app(scope, receive, send):
    # Drain the whole body (as FastAPI's form parser would) before responding.
    more = True
    while more:
        message = await receive()
        more = message.get("more_body", False)
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain")],
        }
    )
    await send({"type": "http.response.body", "body": b"ok"})


def _client(max_body_size: int) -> AsyncClient:
    app = BodySizeLimitMiddleware(_echo_app, max_body_size=max_body_size)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_body_under_cap_passes():
    async with _client(1000) as ac:
        resp = await ac.post("/x", content=b"a" * 500)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_content_length_over_cap_rejected():
    async with _client(1000) as ac:
        resp = await ac.post("/x", content=b"a" * 2000)
    assert resp.status_code == 413


@pytest.mark.asyncio
async def test_streamed_body_over_cap_rejected():
    # A generator body has no Content-Length, so only the streaming meter can
    # catch it — this is the bypass the header check alone would miss.
    async def gen():
        for _ in range(5):
            yield b"a" * 400  # 2000 bytes total > 1000 cap

    async with _client(1000) as ac:
        resp = await ac.post("/x", content=gen())
    assert resp.status_code == 413
