# Production-Readiness Panel Fixes — 2026-07-27

Deep panel review (6 parallel subsystem reviewers) over a fully-green `main`
(209 API tests, 67 web tests, ruff+eslint clean, 6/6 structural). Findings below
are the verified, production-impacting subset. Fixes ship as focused PRs; larger
architectural items are logged to the tech-debt tracker, not force-fit here.

## PR sequence

### PR 1 — billing: close duplicate-subscription / double-billing paths
- **B1 (High)** Checkout TOCTOU: before the first subscription row lands, two
  rapid Checkout starts both pass the guard, each with `customer=None` → two
  Stripe customers + two subscriptions → double charge, invisible in-app.
- **B2 (High)** Guard allowlists only `active`/`trialing`; a `past_due`/`unpaid`/
  `incomplete` subscriber can start a *second* subscription.
- **B4 (Low)** An active subscription whose price doesn't map to a paid tier
  writes `plan_id='free'` with `status='active'`, silently locking out a payer.
- **Fix:** (1) invert the guard to allow a fresh Checkout only when there is no
  subscription or its status is terminal (`canceled`/`incomplete_expired`);
  everything else → 409 "use Manage billing". (2) Pass a Stripe
  `idempotency_key` keyed on `(user_id, price_id)` so a double-submit within
  Stripe's window returns the *same* session instead of a duplicate. (3) On an
  unmapped price for a live/active sub, skip the tier/status write (preserve the
  prior row) instead of downgrading to free.
- **Residual (documented):** two *different-plan* checkouts opened before any row
  lands is still possible; the guard+idempotency cover the realistic
  double-click/refresh/same-plan case. Noted in tech-debt tracker.

### PR 2 — generation: never strand jobs; stop leaking provider error text
- **G1 (High)** The four post-success Supabase writes (`complete_job`,
  `record_provider_run`, `insert_files`, `record_usage_event`) are unguarded; a
  PostgREST blip after a paid, B2-written run leaves the job stuck `running`
  forever with orphaned files and no usage event.
- **G2 (Medium)** Raw `str(exc)` / provider error text flows to the 502 body and
  into `generation_jobs.error` (readable via `GET /generation/jobs`), risking
  key/URL leakage from SDK error messages.
- **Fix:** wrap the persistence block; on failure best-effort
  `complete_job(status="failed")` so a job never lingers as `running`, then raise
  a generic error. Store/return a generic message + log the full detail
  server-side (already `logger.exception`), never the raw provider string.

### PR 3 — auth: reject invalid tokens on a warm identity-cache hit
- **A1 (Medium)** On a cache hit, token signature/expiry is not re-validated; the
  live role fetch collapses a 401 (expired/revoked token) to `None` → defaults to
  role `user` → an invalid token authenticates as a valid user for up to the TTL.
- **A2 (Low)** `auth_cache_ttl_seconds` is unbounded and not capped by the
  token's own `exp`.
- **Fix:** have the live role fetch distinguish auth-failure (401/403) from an
  empty result; on auth-failure evict the cached identity and return `None`
  (→401). Clamp the effective TTL to a safe ceiling.

### PR 4 — frontend: resilience on auth + fetch-error states
- **F1 (High)** Global query `onError` hard-navigates to `/signin` on any 401;
  when a valid Supabase cookie disagrees with an API that rejects the bearer
  (classic misconfig), this becomes an infinite redirect/reload loop.
- **F2–F4 (Medium)** Dashboard stat cards, the generate "recent" list, and the
  billing Pro-preview render *misleading* state (FREE/0/empty/locked) on a
  transient fetch error instead of an error/retry surface; file download
  silently no-ops behind popup blockers.
- **Lows:** `ApiError.message` becomes `"[object Object]"` on FastAPI 422.
- **Fix:** add a short-lived redirect guard so a second 401 surfaces an inline
  "session invalid" state instead of re-navigating; add error/retry branches to
  the three surfaces; download via a hidden `<a download>` in the click context;
  coerce non-string `detail` to a status-based message.

### PR 5 — infra/observability + docs
- **I1 (Medium)** The 500 handler's `JSONFormatter` logs only the exception
  message, never the traceback — blind debugging on the one sink for unhandled
  errors.
- **I2 (Low)** `.env.example` ships `ENABLE_DOCS=true`, contradicting the safe
  code default and the Railway "leave unset in prod" note.
- Reconcile the AGENTS.md §6 e2e claim with actual CI.
- **Fix:** include the formatted traceback when `exc_info` is present; ship
  `ENABLE_DOCS` commented/false; reconcile the doc.

## Deferred → tech-debt tracker (need infra / are acceptable for a starter kit)
- **G3** Abandoned genblaze worker threads can exhaust the dedicated pool under a
  hanging-endpoint scenario (needs fast-fail/watchdog).
- **Files cache** Per-replica invalidation staleness, process-wide single-flight
  lock throughput cliff, and prefix-count (not object/byte) memory bound — all
  need a shared cache (Redis) to fix properly at scale.
- **B3** Non-atomic webhook idempotency (safe today because handlers are
  idempotent; documenting rather than reworking to avoid a lost-event regression).
- Per-user/global generation **cost** ceiling (only an attempt-count cap today).

## Revisions after red-team (adopted)

1. **Sequencing / hidden coupling.** PR3(auth) turns today's silent
   expired-token-as-`user` into a clean 401 — which is exactly what triggers the
   F1 redirect loop. So the **frontend PR (incl. F1) ships before the auth PR**.
   Revised order: (1) billing, (2) generation, (3) frontend resilience incl. F1,
   (4) auth cache, (5) infra/docs.
2. **PR1 idempotency key** must be *time-bucketed* — `sha256(user:price:floor(
   now/60s))` — so it dedupes double-clicks without Stripe's 24h replay breaking
   a legitimate re-subscribe-after-cancel. **Guard** becomes an explicit
   live/pending **block-set** `{active,trialing,past_due,unpaid,incomplete}`→409;
   `{canceled,incomplete_expired,inactive,no-row}`→allow (avoids stranding the
   `inactive` webhook-race default). B4 → minimal early-return skip.
3. **PR2** must scope the anti-stranding fix to the `complete_job` (running→
   terminal) transition ONLY. Secondary writes (`record_provider_run`,
   `insert_files`, `record_usage_event`) **log-and-continue, never flip a
   succeeded job to failed** (else a late blip → user re-generates → double
   spend). The `status=="failed" → raise` check stays OUTSIDE the catch.
4. **PR3(auth)** `fetch_profile_role` needs explicit 4-way handling: role /
   no-row (→`user`) / **401·403 → evict + 401** / **5xx·timeout → propagate,
   leave auth state untouched** (a transient PostgREST 5xx must NOT mass-logout).
   A2 → static TTL ceiling only; drop JWT `exp` parsing (the module deliberately
   avoids local JWT verification).
5. **PR4(frontend)** the redirect guard must be **cleared on success** (else it
   permanently disables redirects in that tab); also `signOut()` the stale
   Supabase session on a hard 401 (the true root cause of the loop).

## Process per PR
Branch → TDD test → implement smallest coherent change → run
`pnpm lint && pnpm test:web && pnpm lint:api && pnpm test:api && pnpm check:structure`
→ panel-review the diff → open PR (no merge) → update docs in the same PR.
