<!-- last_verified: 2026-07-20 -->
# Production-Readiness Hardening

Close the gaps surfaced by the deep audit so the starter kit is safe to ship as a
public, multi-tenant, billed SaaS. Grouped by blast radius; each item lists the
root cause, the fix, and the test that proves it.

## Scope decision

**In scope** (blocks a public production deploy): security hardening, DoS/cost
vectors, billing correctness (double-billing, entitlement fail-open UX, event
ordering), event-loop/threadpool starvation, connection/timeout hygiene, and the
frontend correctness gaps that lock out paying users or hide data.

**Deferred** (tracked in tech-debt-tracker, not ship blockers): full streaming
upload rewrite to B2 multipart (we add a hard body cap instead), settings-form
persistence, docker-compose, OpenAPI codegen, rich metadata persistence.

## A. Security

- **A1 — Open redirect.** `safeNextPath` misses `\t\r\n`; the URL parser strips
  them post-guard → cross-origin. Strip/reject all C0 control chars before the
  existing checks. Test: control-char cases in `safe-redirect.test.ts`.
- **A2 — `/metrics` unauthenticated.** Gate behind `require_admin`. Keep `/health`
  public (boolean only). Test: 401/403 without admin in `test_metrics` (new).
- **A3 — First-user auto-admin.** Gate the `handle_new_user` auto-promote behind a
  DB setting (`app.settings.auto_promote_first_admin`), default OFF. Local seed
  turns it on. Forward migration. Doc the manual grant in README.
- **A4 — Interactive docs default.** Default `enable_docs=False`; README documents
  flipping on for exploration.

## B. DoS / cost

- **B1 — Unbounded upload body → disk DoS.** `request.form()` spools the whole
  body to disk before the handler's size check. Add an ASGI body-size-limit
  middleware (reject on `Content-Length` > cap, and guard streamed bodies) sized
  to `max_file_size` + small overhead. Test: oversized `Content-Length` → 413
  before parsing.
- **B2 — Generation threadpool starvation.** Blocking Genblaze runs on the shared
  40-thread pool; abandoned timed-out threads leak. Add a bounded
  `asyncio.Semaphore` capping concurrent generations well under the pool size so
  file I/O + `/health` keep threads. Test: semaphore bound respected.
- **B3 — Generation cost/quota.** No per-user ceiling. Add a per-user daily
  generation count check against `usage_events` before running; 429 over cap.
  Configurable via settings. Test: over-cap → 429.
- **B4 — Webhook rate-limited.** `/billing/webhook` shares the per-IP write bucket
  keyed on Stripe's egress IP. Exempt the webhook path from the limiter. Test:
  webhook not throttled.

## C. Billing correctness

- **C1 — Double-billing on plan change.** Existing subscribers hitting Checkout
  create a second subscription. Backend: if the user has an active sub, the
  checkout endpoint returns a portal URL / 409 directing them to manage. Frontend:
  existing-subscriber plan buttons open the Portal, not Checkout. Test: active sub
  + checkout → portal path.
- **C2 — Out-of-order event clobber.** `_sync_subscription` writes any event with
  no ordering guard. Guard on the Stripe object's `created`/`updated` vs the
  stored row (skip strictly-older events). Test: stale event does not overwrite
  newer state.
- **C3 — Silent free downgrade.** Unmapped price → `plan_id=free` + `active`, no
  log. Log a WARNING when an active sub maps to `free`. Test: warning emitted.
- **C4 — Entitlement fail-open UX (frontend).** Errored `useEntitlements` /
  `useSubscription` currently render as "Free"/locked. Render an ErrorState +
  retry on billing and generate; never treat query-error as unentitled. Test:
  component/render test with an errored query (adds jsdom render tests).

## D. Scalability / hygiene

- **D1 — httpx connection pooling.** 17 call sites open a fresh `AsyncClient`;
  `get_current_user` does 2 per request. Introduce one lifespan-managed shared
  `AsyncClient` reused by all Supabase repos. Test: existing tests still pass
  (behavior unchanged); client is a singleton.
- **D2 — boto3 timeouts/pool.** Add `connect_timeout`, `read_timeout`,
  `retries={max_attempts}`, `max_pool_connections` to the botocore `Config`.
- **D3 — Per-user listing uncached.** Dashboard = up to 6 uncached B2 scans. Add a
  short-TTL per-user-prefix cache with per-prefix invalidation on that user's
  upload/delete. Retire the dead empty-prefix path or wire it. Test: second call
  within TTL hits cache; upload invalidates.

## E. Frontend correctness

- **E1 — Global 401 handling.** `QueryCache.onError` → sign out + redirect to
  `/signin` on 401. Test: render test.
- **E2 — Over-broad invalidation.** Scope mutation invalidations to affected keys
  (`files`/`stats`/`uploadActivity`, `generationJobs`) instead of `qk.all`.
- **E3 — File list cap.** Add load-more / higher limit + "showing N" indicator so
  files beyond 100 are reachable.
- **E4 — Command-palette fetch.** Convert `useEffect + getFiles()` to
  `useFiles({ enabled: open })`. Remove dead `getFile`.

## F. CI / infra

- **F1 — Deps reproducibility.** Pin Python deps with hashes (compile a
  `requirements.lock` via pip-tools/uv) or exact `==`; CI + Railway use it.
- **F2 — e2e in CI.** Wire `test:e2e` (or document why gated) — at minimum a
  smoke lane. If full stack is infeasible in CI, keep out but document.
- **F3 — Railway config codified.** Commit `railway.json` (healthcheck path,
  restart policy) or document; use `--frozen-lockfile` for web build.
- **F4 — PyPDF2 → pypdf.** Migrate the import; update requirements.

## G. Minor correctness

- **G1 — PDF inline preview.** Preview URLs force `attachment`; the modal iframe
  then downloads. Add an `inline` disposition mode for preview (keep `attachment`
  for real downloads). Test: preview URL uses inline, download uses attachment.
- **G2 — `/health` degraded status code.** Return 503 when B2 is unreachable so
  platform healthchecks evict broken instances (keep body shape).

## Revisions after red-team review

- **A2** → optional `METRICS_TOKEN` bearer gate (keeps `/metrics` Prometheus-scrapable) instead of `require_admin`. Update `test_metrics_returns_200`.
- **B1** → pure-ASGI middleware that checks `Content-Length` AND wraps `receive` to cap streamed bytes (chunked/no-CL bypass); register inner to CORS. Test both cases.
- **B2** → dedicated bounded `ThreadPoolExecutor` for generation (a shared-pool semaphore leaves the leaked thread holding a shared-pool token → doesn't fix starvation).
- **B3** → count today's `generation_jobs` before `create_job` (usage_events only logs successes → failures would be free). Soft cap (check-then-create race, acceptable).
- **C1** → backend raises **409** when an active sub exists; frontend routes existing paid subscribers to the existing `usePortal()`. No overloaded checkout response.
- **C2 → DEFERRED** to tech-debt: a correct ordering guard needs a schema migration (Stripe Subscription `created` is constant; `updated_at` is our write time). C1 is the higher-impact clobber.
- **A3** → remove the auto-promote branch from `handle_new_user` in the schema itself (no patch migration). Followed up by consolidating the four migrations into a single `00000000000000_init.sql` — a starter kit inits fresh, so the schema reads best as one file rather than an incremental trail (one migration even existed only to backfill grants an earlier one missed). Admin is granted explicitly (documented). No GUC.
- **D3** → cache non-empty prefixes through the existing `_list_all_objects` machinery (upload/delete already call the global invalidator) + a `_list_cache` size cap. Dead empty-prefix `get_upload_stats` already removed.
- **C4/E1** → extract pure decision fns (`entitlementViewState`, `shouldSignOut`) tested in node env; **no jsdom**. E1 wired narrowly (401 only, guard against loops).
- **D1 → DEFERRED** to tech-debt: a shared httpx client trips pytest-asyncio event-loop reuse and isn't exercised by the (fully monkeypatched) tests.
- **G2 → DROPPED**: returning 503 on B2-degraded would restart-storm otherwise-healthy instances during a shared-B2 outage; 200+body is the correct readiness-probe design.
- **F1** → exact `==` pins in `requirements.txt` (no new pip-tools/uv tooling).

## Verification gate (run before done)

`pnpm lint && pnpm test:web && pnpm build && pnpm lint:api && pnpm test:api && pnpm check:structure`
