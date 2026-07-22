<!-- last_verified: 2026-07-15 -->
# Reliability

Reliability expectations and practices for this project.

## Health Checks

- `GET /health` verifies B2 connectivity and returns `healthy` or `degraded`
- Health endpoint is always available, even when B2 is down

## Error Handling

- HTTP handlers return structured error responses with appropriate status codes
- External service failures (B2) are caught and surfaced as 500/503 responses
- No unhandled exceptions leak stack traces to clients
- Uncaught exceptions are converted to a typed JSON 500 (`{"detail": "Internal server error"}`, modeled by `app.types.ErrorResponse`) by the catch-all in `timing_middleware`
- **Error responses carry CORS headers.** `CORSMiddleware` is registered LAST in `main.py` so it is the outermost middleware and wraps every response — including uncaught-exception 500s produced by the inner catch-all. This is intentional and load-bearing: if a 500 shipped without `Access-Control-Allow-Origin`, the browser would block it and the frontend would surface only an opaque "network error", hiding the real server bug. Regression-guarded by `tests/test_error_handling.py::test_unhandled_exception_500_carries_cors_headers`.

## Logging

- Structured JSON logging via Python stdlib
- Every request gets a `request_id` for tracing
- Log levels: ERROR for failures, WARNING for degraded state, INFO for requests

## Observability

- Request timing middleware logs duration for every request
- `/metrics` endpoint exposes basic Prometheus-format counters
- Upload success/failure counts tracked

## Stateful Counters — durability caveats

The download counter and the `/metrics` counters are **in-process, per replica**. Consequences to plan for before scaling:

- **Download counter** (`app/repo/counter.py`) persists to a JSON file at `DOWNLOAD_COUNT_FILE` (default `data/download_count.json`). On an ephemeral filesystem (Railway without a mounted volume) it **resets to 0 on every redeploy**. With multiple replicas each keeps its own file/count. For durable, shared counts: mount a persistent volume, or swap the adapter for Redis/DB.
- **`/metrics` counters** live in process memory and reset on restart. Behind a load balancer, each replica reports only its own slice — scrape with an instance label and aggregate, or push to a shared collector.

## Rate Limiting

- Per-IP fixed-window limiter (`app/runtime/ratelimit.py`); `RATE_LIMIT_PER_MINUTE` / `RATE_LIMIT_WRITE_PER_MINUTE` are the budgets. Rejected requests get `429` with a `Retry-After` header.
- Counters are in-process per replica; horizontal scaling needs a shared store (e.g. Redis) for a global limit.

## Graceful Degradation

- File listing returns empty list (not error) when B2 has no objects
- Metadata extraction failures don't block upload (return partial metadata)
- Frontend shows skeleton states while loading, error states on failure

## Resource Isolation & Limits

- **Threadpool isolation**: blocking B2/file work uses Starlette's shared request
  threadpool, but AI generation (which can hang on a slow provider past its
  deadline, leaking an unkillable thread) runs on a *dedicated* bounded
  `ThreadPoolExecutor` (`GENERATION_MAX_CONCURRENCY`) so those leaks can never
  starve file I/O or `/health`.
- **Body size**: an ASGI middleware caps request bodies at `MAX_REQUEST_BODY_SIZE`
  (`413`) before they are buffered — see [SECURITY.md](SECURITY.md#request-body-size-limit).
- **Upload memory & concurrency**: each upload buffers its **entire body in
  memory** (`list[bytes]` joined into one `bytes`) before the B2 put — worst-case
  ~`MAX_FILE_SIZE` of RAM per in-flight upload. Two guards bound the exposure:
  - The type/extension gate now runs **pre-buffer** in `runtime/upload.py` (via
    the service helper `check_upload_type`), so a **disallowed** type is rejected
    with `415` before any body is read. This is the whole win of that gate —
    **allowed** files are still fully buffered; it does not stream them to B2.
  - An `asyncio.Semaphore` (`MAX_CONCURRENT_UPLOADS`, default 8) caps how many
    uploads buffer+process at once, so peak upload memory is bounded by
    `MAX_CONCURRENT_UPLOADS * MAX_FILE_SIZE` **per worker process**, regardless
    of request volume; excess requests wait for a slot. It is a **global** cap
    (all users on a worker share it), so lower it on a memory-constrained
    instance and raise it if legitimate parallel uploads start queuing.
  - The gate makes excess uploads **wait**, not fail, so it assumes an
    upstream/proxy request-read timeout (uvicorn imposes none by default) —
    otherwise a few slow clients trickling bytes could hold every slot and stall
    uploads for everyone. Set one at the proxy/edge in production.
  - To remove the per-file buffering entirely, stream directly to B2 (multipart)
    — tracked as future work, not done here.
- **Backblaze client**: explicit connect/read timeouts, capped retries, and a
  connection pool sized to the request threadpool, so a hung B2 endpoint fails
  fast instead of tying up threads.
- **Per-user listing cache**: `_list_all_objects` caches all prefixes (30s TTL,
  size-capped, invalidated on any upload/delete) so a dashboard load doesn't
  re-scan a user's prefixes on every request.

## Deployment

- Build/start command, `/health` (API) or `/signin` (web) healthcheck, and
  `ON_FAILURE` restart policy are codified per service in `railway.json`.
- Zero-downtime deploys via rolling updates.
- Reproducible builds: exact-pinned `requirements.txt` (API) and
  `pnpm install --frozen-lockfile` (web).
- Environment-specific configuration via env vars (no config files in prod).
- `/health` returns `200` even when B2 is unreachable (body reports
  `degraded`) — B2 is a shared downstream dependency, so a `503` would restart
  otherwise-healthy instances during a B2 outage without helping.
