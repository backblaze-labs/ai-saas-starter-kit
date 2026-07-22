<!-- last_verified: 2026-07-08 -->
# Feature: Billing (Stripe)

## Purpose
Turn the app into a real SaaS: paid plans (Free / Pro / Team), Stripe Checkout +
Billing Portal, a webhook that syncs subscription state into Supabase, and a
reusable plan-gating dependency that locks features behind a tier.

## Used By
- UI: `/billing` (plan catalog, upgrade, "Manage billing", Pro-feature preview).
- API: `GET /billing/plans`, `GET /billing/subscription`, `GET /billing/entitlements`,
  `POST /billing/checkout`, `POST /billing/portal`, `POST /billing/webhook`,
  `GET /billing/pro/preview` (gated demo).
- Dependency: `require_plan(min_tier)` — the gate the generation slice reuses.

## Core Functions
- `services/api/app/repo/stripe_client.py` — the only module importing `stripe`
  (checkout/portal session creation, webhook signature verification).
- `services/api/app/repo/supabase_billing.py` — PostgREST reads/writes (service role).
- `services/api/app/service/billing.py` — entitlements, tier↔price mapping,
  idempotent webhook → subscription sync.
- `apps/web/src/app/(app)/billing/page.tsx` + `lib/queries.ts` billing hooks.

## Canonical Files
- Backend flow: `runtime/billing.py` (thin) → `service/billing.py` → `repo/{stripe_client,supabase_billing}.py`
- DB + RLS: `supabase/migrations/00000000000000_init.sql` (billing section)
- Plan-gating exemplar: `require_plan("pro")` guarding `GET /billing/pro/preview`

## Inputs
- `plan_id` (`pro` | `team`) on checkout (from the Billing UI).
- Stripe webhook events (`customer.subscription.*`, `checkout.session.completed`),
  verified by the `Stripe-Signature` header against `STRIPE_WEBHOOK_SECRET`.
- `Authorization: Bearer <token>` on every endpoint except the webhook.

## Outputs
- A hosted Stripe Checkout / Billing Portal URL (the client redirects to it).
- A `public.subscriptions` row per user, upserted by the webhook (service role).
- A `public.stripe_events` row per processed event (idempotency).
- Side effect: entitlements (`tier`, `can_generate`) recomputed from the synced row.

## Flow
- A **Free** user clicks **Upgrade** → `POST /billing/checkout` creates a
  subscription-mode Checkout Session (user id in `client_reference_id` +
  subscription metadata) → browser redirects to Stripe → pays with test card
  `4242 4242 4242 4242`.
- An **existing subscriber** changing plans is routed to the **Billing Portal**
  (which swaps/prorates the current subscription), not a new Checkout. The
  checkout endpoint hard-guards this too: `409` if the caller already has an
  active subscription, because a second subscription-mode Checkout would open a
  *concurrent* Stripe subscription and double-bill.
- Stripe POSTs `customer.subscription.*` to `/billing/webhook` → signature
  verified → event deduped via `stripe_events` → subscription upserted into
  Supabase with the tier derived from the price id.
- `checkout.session.completed` (fired in the same instant) writes **only** the
  Stripe id mapping (`stripe_customer_id`, `stripe_subscription_id`) so the
  portal works immediately. It never writes `plan_id`/`status` — tier and status
  are owned solely by `customer.subscription.*`, so the two events can be
  processed in either order without one downgrading the other.
- `require_plan("pro")` reads the user's entitlements and 402s when the tier is
  below the minimum; the Billing page mirrors this with a locked/unlocked card.
- **Manage billing** → `POST /billing/portal` → redirect to the Stripe portal.

## Edge Cases
- Missing `STRIPE_SECRET_KEY` → checkout/portal return `503` (app still boots and
  the file manager works); the UI shows "Billing is temporarily unavailable".
- `test_mode` on the subscription payload (derived from an `sk_test_` key) gates
  the `4242…` test-card hint on the Billing page, so it never shows in live mode.
- Bad/absent webhook signature → `400`; missing `STRIPE_WEBHOOK_SECRET` → `503`.
- Duplicate event id → no-op (`{"status":"duplicate"}`).
- Unknown/unpriced plan on checkout → `400`. Active subscriber on checkout → `409` (use the portal).
- A live subscription whose price maps to no tier (misconfigured `STRIPE_PRICE_*`) is logged as a WARNING rather than silently written as `free`, so a locked-out paying customer is diagnosable.
- `customer.subscription.deleted` → downgrades the user to `free` (status `canceled`).
- Event ordering: `checkout.session.completed` and `customer.subscription.created`
  race on the same per-user row. Because checkout writes only id columns (and the
  merge-upsert overwrites only the columns it sends), a paid `pro`/`active` row is
  never clobbered back to `free`/`incomplete` regardless of which lands last.
- Out-of-order subscription events: Stripe does not guarantee ordered delivery, so
  a stale/retried `customer.subscription.*` can arrive after a newer one. Each
  subscription event carries the Stripe **event** `created` (unix seconds), stored
  as `subscriptions.last_event_created_at`. The webhook applies events through the
  `apply_subscription_event` Postgres function (via PostgREST RPC), whose
  `ON CONFLICT` branch fires only when the incoming event is same-or-newer (or
  ordering is impossible — first event on the row, or a missing timestamp). A
  staler event is a no-op DB-side, so the freshness check is atomic and cannot
  race under concurrent deliveries (no read-compare-write in the API). The
  checkout id-only path keeps its plain merge-upsert.

## UX States
- Empty/Free: three plan cards, current plan = `FREE`, Pro preview locked.
- Loading: "Loading plans…", "Opening…", "Checking your plan…".
- Error: toast on checkout/portal failure (503 → configuration hint).

## Verification
- Test files: `services/api/tests/test_billing.py`, `apps/web/e2e/billing.spec.ts`
  (+ `e2e/helpers/stripe-webhook.ts`).
- Required cases: webhook signature verify (good/bad/missing secret), idempotent
  sync, deletion→downgrade, `require_plan` 402/allow, checkout 503-without-config,
  `checkout.session.completed` not clobbering an active paid row (either ordering)
  and recording the id mapping without unlocking, out-of-order subscription events
  (stale=no-op, newer applies, first-on-new-row applies, missing timestamp applies)
  plus the RPC-payload shape for `apply_subscription_event`, and the live e2e
  webhook upgrade unlocking Pro. NOTE: the SQL freshness guard itself is not
  executed by the hermetic pytest suite (no live Postgres) — it is covered by the
  RPC-payload assertion and manual/e2e DB runs.
- Quick verify command: `pnpm test:api` (billing unit tests, hermetic).
- Full verify command: `supabase start` + `pnpm dev`, then `pnpm test:e2e`.
  The webhook-upgrade e2e also needs `STRIPE_WEBHOOK_SECRET` +
  `SUPABASE_SERVICE_ROLE_KEY` exported (it skips cleanly otherwise). A real
  browser checkout with `4242…` needs test-mode Stripe keys (manual QA).
- Pass criteria: billing unit tests green; e2e billing specs green against a
  running stack.

## Related Docs
- [docs/stripe-setup.md](../stripe-setup.md) — step-by-step setup + local testing walkthrough
- [README.md](../../README.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [docs/SECURITY.md](../SECURITY.md)
- [docs/app-workflows.md](../app-workflows.md)
