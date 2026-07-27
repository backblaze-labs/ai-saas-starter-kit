"""ASGI middleware that caps request body size before it is buffered.

FastAPI resolves an ``UploadFile`` parameter by calling ``request.form()``, which
streams the ENTIRE multipart body into a spooled temp file (spilling to disk past
1MB) *before* the route handler runs. An in-handler size check is therefore too
late — the oversized body has already hit the disk. This middleware enforces the
cap at the ASGI layer instead:

* a declared ``Content-Length`` over the cap is refused up front (covers every
  real upload client — browsers, fetch/XHR, and Stripe all send Content-Length);
* the body is also metered as it streams, so a chunked / no-Content-Length
  request can't slip past the header check.

It is a pure-ASGI middleware (not ``BaseHTTPMiddleware``) so it can wrap the
``receive`` channel. Registered INNER to CORS/timing in main.py so its 413 is
recorded by the timing middleware and carries CORS headers.
"""

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class _BodyTooLarge(Exception):
    """Internal signal: the streamed body exceeded the cap mid-request."""


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp, max_body_size: int) -> None:
        self.app = app
        self.max_body_size = max_body_size

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Fast path: refuse an over-cap Content-Length before reading a byte.
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    if int(value) > self.max_body_size:
                        await self._send_413(send)
                        return
                except ValueError:
                    pass  # malformed header — fall through to the streaming meter
                break

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_body_size:
                    raise _BodyTooLarge()
            return message

        response_started = False

        async def guarded_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except _BodyTooLarge:
            # The body is read during dependency resolution, before the handler
            # emits anything, so no response has started — a clean 413 is safe.
            if not response_started:
                await self._send_413(send)
            else:
                raise

    async def _send_413(self, send: Send) -> None:
        body = b'{"detail":"Request body too large"}'
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
