<!-- last_verified: 2026-07-20 -->
# Tech Debt Tracker

Known tech debt items. Agents update this when they discover or create tech debt.

## 2026-07-20 — production-readiness hardening

Resolved on the `production-readiness-hardening` branch (see
`docs/exec-plans/completed/2026-07-20-production-readiness-hardening.md`):
double-billing on plan change (checkout 409 + portal routing), open-redirect via
control chars in `safeNextPath`, unbounded upload body → disk DoS (ASGI body-size
cap), generation threadpool starvation (dedicated executor) + per-user daily
quota, `/metrics` gated by optional `METRICS_TOKEN`, first-user auto-admin
removed, docs off by default, per-user listing now cached, boto3 timeouts/pool,
webhook exempt from the IP rate-limit, price→free mismatch now logged, PDF inline
preview, `PyPDF2`→`pypdf`, exact-pinned Python deps + committed `railway.json`,
and frontend entitlement-error / global-401 handling.

Deliberately **deferred** (not ship blockers; recorded here after red-team review):

- **Shared httpx client / connection pooling** — every Supabase repo opens a
  fresh `AsyncClient` (2 round-trips per authed request in `get_current_user`). A
  lifespan-managed singleton trips pytest-asyncio event-loop reuse and isn't
  exercised by the (fully monkeypatched) tests, so it needs a real integration
  test alongside it. Priority: Medium (latency, not correctness).
- **e2e (Playwright) not in CI** — the 4 journey specs need the full stack
  (Supabase + API + Stripe CLI + mailpit); wiring an ephemeral stack into CI is a
  separate effort. Run locally with `pnpm test:e2e` as a pre-release gate.
- **Per-user-scoped list-cache invalidation** — any upload/delete clears the
  whole listing cache (coarse but correct). Scope invalidation to the mutating
  user's prefixes at higher tenant counts. Priority: Low.
- **Generation daily quota is a soft cap** — check-then-create can race a few
  past the limit. A hard cap needs a DB-side counter. Priority: Low.
- **`repo/b2_client.py` is at the 300-line limit** — the next change to it should
  split the listing-cache helpers into their own module. Priority: Low.

## 2026-07-16 — verify

Nitpicks surfaced by the verify pass on the file surface (logged, not blocking; the auth/ownership blocker and the preview-spinner friction were fixed in the same change):

- **A1** — Signup screen copy tells the user to "then sign in" even though the flow may hand them straight into a session; reconcile the wording with the actual post-signup behavior.
- **A3** — Dashboard renders a Free-plan "Inactive" badge that reads like an error state rather than simply "no paid subscription"; soften the label/variant.
- **A4** — "Design System" link lives in the primary product nav; consider moving it to a utility/footer slot so the main nav is product-only.
- **B-delete** — File delete has no optimistic removal; the row only disappears after the round-trip completes.
- **C3** — Generated object keys carry a redundant date segment (`generated/{user_id}/{date}/runs/{date}/…`); purely cosmetic — collapse the duplicate date.

## Open

| Description | Impact | Proposed Resolution | Priority |
|---|---|---|---|
| Download counter & `/metrics` not durable across restart/replicas | Counter resets on redeploy (ephemeral FS); both fragment across replicas | Back the counter with a shared store (Redis/DB); label/aggregate metrics per instance. Now isolated in `repo/counter.py` and documented in RELIABILITY.md | Medium |
| Upload buffers the whole file in memory | The disk-exhaustion DoS is fixed (an ASGI body cap rejects oversized bodies before form parsing), but a valid upload up to `max_file_size` is still read into RAM (~2× transiently) | Concurrency is now capped (`MAX_CONCURRENT_UPLOADS` semaphore, default 8) so peak upload memory is bounded per worker; **remaining:** stream to B2 multipart above a size threshold to drop the per-file buffering | Medium |
| `get_upload_activity` re-materializes `FileMetadata` for every object just to bucket dates | Wasted O(n) CPU per `/files/stats/activity` (the prefix scan is now cached; the materialization is not) | Aggregate dates straight from the raw listing dicts instead of building `FileMetadata` | Low |
| No component/render tests (pure-logic units only); e2e not in CI | Render-time UI states aren't asserted. Plan-gating and 401-signout decisions were extracted to pure `lib/query-helpers.ts` (unit-tested), but component rendering still isn't | Add jsdom + @testing-library/react render tests; wire `test:e2e` into CI with an ephemeral stack | Medium |
| Allowed file types hardcoded in `service/upload.py` | Reuse friction — each new app edits source to change accepted types | Make `ALLOWED_TYPES` / `MIME_EXTENSION_MAP` env-configurable | Low |
| No `docker-compose.yaml` | Manual venv + dual-process startup slows first run | Add compose with `web` + `api` services and Dockerfiles | Low |
| `api-client.ts` hand-synced to FastAPI | Endpoint drift between client and server | Note an OpenAPI codegen strategy or link the spec | Low |
| No dedicated connection-status banner | Offline only surfaced reactively per failed query | Add a global connectivity banner (route + global error boundaries already exist) | Low |
| Rich file metadata not surfaced in the browser | Extracted at upload and returned in the `POST /upload` response but not persisted, so `GET /files-by-key/metadata` and the browser preview show basic metadata (size, type, key, date) only | Persist rich metadata at upload (e.g. in the `files` table) + return it from `GET /files-by-key/metadata`, then render it in the preview dialog | Low |
| Settings page is a non-persisting preview & Danger Zone "Empty bucket" is disabled | Users can't save preferences or empty the bucket from the UI — both are marked "preview"/"not available in this starter" (no misleading fake-success) rather than wired | Persist preferences (a `settings` table or `profiles` columns) + implement a prefix-scoped bucket-empty behind a typed confirm | Low |

## Resolved

| Description | Resolution |
|---|---|
| Double-billing: an active subscriber hitting Checkout opened a 2nd Stripe subscription | `create_checkout_url` 409s an active sub; the billing UI routes existing subscribers to the Billing Portal (`service/billing.py`, `billing/page.tsx`) |
| Out-of-order Stripe events: a stale/retried `customer.subscription.*` could overwrite newer state (delivery is unordered) | Added `subscriptions.last_event_created_at` (Stripe event `created`) + `apply_subscription_event` Postgres function; the webhook applies subscription events via PostgREST RPC with an atomic `ON CONFLICT … WHERE incoming >= stored` freshness guard, so a staler event is a DB-side no-op (`init.sql`, `repo/supabase_billing.py`, `service/billing.py`) |
| Open redirect: `safeNextPath` missed control chars the URL parser strips | Reject any `\x00-\x1f\x7f` char pre-parse (`lib/safe-redirect.ts`) |
| Unbounded upload body spooled to disk before the size check (disk DoS) | ASGI `BodySizeLimitMiddleware` rejects on Content-Length AND meters the stream, inner to CORS (`runtime/bodylimit.py`) |
| Generation could starve the shared request threadpool (leaked timed-out threads) | Blocking pipeline runs on a dedicated bounded `ThreadPoolExecutor` (`service/generation.py`) |
| No cost ceiling on paid generation | Soft per-user daily job quota → 429 (`generation_daily_limit`) |
| `/metrics` world-readable (route + traffic-volume leak) | Optional `METRICS_TOKEN` bearer gate; stays open when unset for local/private scrape |
| First signup auto-promoted to admin (public-deploy takeover) | Auto-promote branch removed from `handle_new_user` in the init schema; admin granted explicitly via SQL |
| Per-user file listings bypassed the cache (≈6 uncached B2 scans/dashboard) | `_list_all_objects` caches all prefixes (size-capped); dead empty-prefix `get_upload_stats` removed |
| boto3 had no timeouts/retry cap; pool(10) < threadpool(40) | Explicit `connect/read_timeout`, capped retries, `max_pool_connections=40` |
| Stripe webhook throttled by the per-IP limiter | `/billing/webhook` exempt from rate-limiting (signature-verified) |
| PDF preview downloaded instead of rendering (forced `attachment`) | `inline` disposition for previews; `attachment` kept for real downloads |
| `PyPDF2` deprecated/EOL | Migrated to maintained `pypdf` |
| Unpinned Python deps / non-reproducible build | Exact `==` pins in `requirements.txt`; committed `railway.json` per service |
| Interactive docs (`/docs`) exposed by default | `ENABLE_DOCS` defaults off |
| Blocking boto3 in `async def` handlers froze the single event loop | B2 handlers are sync `def` (Starlette threadpool); upload offloads via `run_in_threadpool` |
| Full-bucket scan on every list/stats/activity request, uncached | Short-TTL cache in `repo/b2_client._list_all_objects`, invalidated on upload/delete |
| No CI — quality gates ran only when a human remembered | `.github/workflows/ci.yml` runs web + API gates on PR and push to `main` |
| SVG stored-XSS; declared MIME trusted; unused `python-magic` dep | Dropped SVG from allow-list; added magic-byte signature check; removed dead `python-magic` |
| No rate limiting → DoS + B2 cost amplification | Per-IP fixed-window limiter (`runtime/ratelimit.py`), read/write budgets |
| Counter persistence lived in the service layer (layering violation) | Moved file I/O to `repo/counter.py` behind `get/increment_download_count` |
| CORS `allow_credentials=True` was unnecessary for this app's bearer-token auth | Default `allow_credentials=False` — the API is authenticated by a Supabase bearer token in the `Authorization` header, not a cross-origin cookie; empty origins filtered |
| No security headers on API responses | `X-Content-Type-Options: nosniff` + `Referrer-Policy: no-referrer` on every response |
| Key-addressed ops could target any bucket object | Opt-in `ALLOWED_KEY_PREFIX` confinement (off by default; note this app writes under both `uploads/` and `generated/`) |
| File endpoints had no auth and no per-user isolation — anyone (even anonymous) could list/preview/download/delete any object, and a signed-in user saw every tenant's `uploads/`/`generated/` keys | Every file + upload route now requires a Supabase bearer token (`401` otherwise); reads/listings/stats are scoped to the caller's `uploads/{user_id}/` + `generated/{user_id}/` prefixes; uploads are keyed under `uploads/{user_id}/`; key-addressed ops `404` for keys the caller doesn't own (no existence leak) |
| Redundant triple-scan + double sort per dashboard mount | TTL cache + single-flight collapse the concurrent empty-prefix scans; dropped the repo-layer sort so `get_files` owns newest-first ordering once |
| Unguarded `int(content-length)`; always-on `/docs`; uncached `/health` B2 call | Content-Length parse guarded; `ENABLE_DOCS` toggle (documented in SECURITY.md); connectivity cached ~5s |
| Upload validation sad-paths (413/415) + sanitizer untested | `tests/test_upload_validation.py` covers the rejection matrix, signature check, `uploads_total` |
| `get_upload_stats()` / `list_files()` object listing capped at 1000 | Shared `_list_all_objects()` paginator follows `ContinuationToken` |
| `datetime.utcnow()` deprecated in Python 3.12+ | Replaced with `datetime.now(UTC)` in `repo/b2_client.py`, `service/metadata.py` |
| S3 client recreated on every API call | Cached module-level singleton via `lru_cache` |
| `record_upload()` never called | Called from `runtime/upload.py` after successful upload |
| Metrics counters not thread-safe | Guarded by `threading.Lock` |
| `_humanize_bytes` duplicated in Python (repo + service) | Extracted to `app/types/formatting.py` shared util |
| `humanizeBytes` / `formatDate` duplicated in TypeScript | Extracted to `lib/utils.ts` (tested) |
| No test harness for feature specs | pytest suite across upload, files, activity, errors, validation, rate limit, pagination |
| No auth layer or placeholder (upstream starter had none) | N/A here — this app ships Supabase bearer-token auth + Row Level Security; see docs/SECURITY.md |
| `NEXT_PUBLIC_API_URL` missing from `.env.example` | Already present in `.env.example` with guidance |
