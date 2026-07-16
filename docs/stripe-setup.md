<!-- last_verified: 2026-07-15 -->
# Setting Up Stripe Billing: Subscriptions, Checkout, and Webhook Testing

> A zero-to-working guide to wiring Stripe subscription billing into the starter kit: install the Stripe CLI, create Pro/Team recurring prices, capture your webhook signing secret, fill `.env`, and test Checkout locally with card `4242 4242 4242 4242`. No prior Stripe experience assumed.

The billing integration itself is already built (Checkout, Billing Portal, webhook→database sync, and plan-gating). This guide is only about **configuring** it and **verifying** it end-to-end on your machine. For how it works under the hood, see the [Billing feature reference](features/billing.md).

Everything here uses Stripe **test mode** — no real charges, ever. You don't need to activate payments or provide a bank account to complete this guide.

## What you'll end up with

Three processes running at once:

| Terminal | Command | Role |
|----------|---------|------|
| 1 | `supabase start` | Postgres + Auth + Studio (local) |
| 2 | `pnpm dev` | Frontend (`:3000`) + API (`:8000`) |
| 3 | `stripe listen --forward-to localhost:8000/billing/webhook` | Relays Stripe events to your local API |

> **The port must match.** This app runs the API on **`8000`** by default. `pnpm dev` prints a banner (`⚠ API on http://localhost:XXXX`) if `8000` was busy and it had to pick another port — if you see that, use *that* port in the `stripe listen` command instead. The `--forward-to` port must always equal the port your API is actually listening on.

## Prerequisites

Install the two CLIs (macOS shown; see the [Stripe CLI docs](https://docs.stripe.com/stripe-cli) for other platforms):

```bash
brew install stripe/stripe-cli/stripe      # Stripe CLI
brew install supabase/tap/supabase         # Supabase CLI (if not already installed)
```

You also need **Docker running** (Colima or Docker Desktop) for `supabase start`, and a free [Stripe account](https://dashboard.stripe.com/register).

## 1. Log in to the Stripe CLI

```bash
stripe login
```

This opens your browser to authorize the CLI against your account in test mode. See [Use the Stripe CLI](https://docs.stripe.com/stripe-cli/use-cli) for details.

## 2. Create the Pro and Team recurring prices

Stripe needs one **recurring price** per paid plan. Price IDs (`price_...`) are account-specific, so the app reads them from env config rather than storing them. Create them with the CLI:

```bash
# Pro — $19/mo
stripe products create --name "Pro"
stripe prices create \
  --product prod_XXXXXXXX \
  --unit-amount 1900 --currency usd \
  -d "recurring[interval]=month"

# Team — $49/mo
stripe products create --name "Team"
stripe prices create \
  --product prod_YYYYYYYY \
  --unit-amount 4900 --currency usd \
  -d "recurring[interval]=month"
```

Each `products create` prints a `prod_...` id (paste it into the matching `prices create`), and each `prices create` prints a `price_...` id. **Save the two `price_...` ids** — they go into `.env` in step 4.

Prefer clicking? Create them in the [Dashboard](https://dashboard.stripe.com/test/products) under **Product catalog → Add product**, with a **recurring / monthly** price. Background on the model: [Recurring pricing models](https://docs.stripe.com/products-prices/pricing-models).

> The dollar amount is cosmetic for plan-gating — the backend maps the **price id** to a tier, not the amount. The `1900` / `4900` values simply match the plan catalog (`supabase/migrations/…_billing_plans_subscriptions.sql`).

## 3. Get your test-mode secret key

In the Stripe Dashboard, confirm the **Test mode** toggle is on, then open [Developers → API keys](https://dashboard.stripe.com/test/apikeys) and copy the **Secret key** (`sk_test_...`). More on keys: [API keys](https://docs.stripe.com/keys).

## 4. Start the webhook listener and capture the signing secret

In **Terminal 3**:

```bash
stripe listen --forward-to localhost:8000/billing/webhook
```

On startup it prints:

```
> Ready! Your webhook signing secret is whsec_xxxxxxxx...
```

That `whsec_...` is your `STRIPE_WEBHOOK_SECRET`. It's **stable** for your account/device, so you set it once. Leave this terminal running — it forwards `checkout.session.completed` and `customer.subscription.*` events to your API and prints each one live. Reference: [Test a webhook integration with the Stripe CLI](https://docs.stripe.com/webhooks#test-webhook).

## 5. Fill in `.env`

Add the four values you gathered to the root `.env` (see `.env.example`):

```bash
STRIPE_SECRET_KEY=sk_test_...        # step 3
STRIPE_WEBHOOK_SECRET=whsec_...      # step 4 (from `stripe listen`)
STRIPE_PRICE_PRO=price_...           # step 2 (Pro)
STRIPE_PRICE_TEAM=price_...          # step 2 (Team)
```

> **Order matters.** The API reads `.env` **only at startup**. If `pnpm dev` was already running, restart it after editing `.env` — otherwise webhook verification fails with a `400` ("Invalid signature") because the API is still running without the secret.

## 6. Start the database and the app

```bash
# Terminal 1
supabase start
node scripts/sync-supabase-env.mjs   # writes the local Supabase keys into .env

# Terminal 2 (after .env is complete)
pnpm dev
```

`supabase start` applies the migrations, which seed the plan catalog (Free/Pro/Team) and create the `subscriptions` and `stripe_events` tables. Confirm the `pnpm dev` banner shows the API on `:8000`; if not, re-point `stripe listen` at the port it printed.

## 7. Create test accounts

Sign up at `http://localhost:3000`. Confirmation emails are caught locally by **Mailpit** at `http://127.0.0.1:54324` (nothing is sent to a real inbox) — open the message there to confirm each account. The **first user to sign up becomes an admin**.

To exercise plan-gating, create two accounts: your main one (which you'll upgrade to Pro) and a second one that stays on Free.

## Verify it works

With all three terminals running:

1. **Free by default** — a brand-new account shows **Free** active on `/billing`. In [Studio](http://127.0.0.1:54323) → **Table Editor → `subscriptions`**, the user has `plan_id='free'` (or no row yet — absence of a row is treated as Free).

2. **Upgrade to Pro** — on `/billing`, click **Upgrade to Pro**, and in Stripe Checkout pay with test card **`4242 4242 4242 4242`**, any future expiry, any CVC, any ZIP. Then check:
   - **Terminal 3** prints `checkout.session.completed` + `customer.subscription.created`/`updated`.
   - **Stripe Dashboard (test)** → [Customers](https://dashboard.stripe.com/test/customers) and [Subscriptions](https://dashboard.stripe.com/test/subscriptions) show a new customer and an active Pro subscription.
   - **Studio → `stripe_events`** has rows with the event ids (proof of idempotent processing).
   - **Studio → `subscriptions`** shows your row as `plan_id='pro'`, `status='active'`, with `stripe_customer_id` / `stripe_subscription_id` populated and `current_period_end` set.
   - `/billing` in the app now shows **Pro**.
   - Full list of [test cards](https://docs.stripe.com/testing).

3. **Plan-gating** — as Pro, `/generate` is enabled. As the second (Free) user, `/generate` shows the upgrade/locked card, and the API returns `402` for a gated request.

4. **Billing Portal + cancellation** — `/billing` → **Manage billing** opens the [Stripe Billing Portal](https://docs.stripe.com/customer-management), where you can cancel. On cancel, Terminal 3 shows `customer.subscription.updated`/`deleted`, Studio → `subscriptions.status` reflects the downgrade, and `/generate` locks again.

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| Webhook `400 Invalid signature` | `STRIPE_WEBHOOK_SECRET` doesn't match `stripe listen`'s `whsec_`, or the API wasn't restarted after editing `.env`. |
| Checkout/portal returns `503` | `STRIPE_SECRET_KEY` isn't set (the app boots fine without it — billing is optional). |
| `400 No Stripe price configured for plan …` | `STRIPE_PRICE_PRO` / `STRIPE_PRICE_TEAM` missing or not a **recurring** price. |
| Events don't reach the API | `stripe listen --forward-to` port ≠ the port the API is actually on (default `8000`). |
| Want to re-run the upgrade flow | In Studio, delete the user's row in `subscriptions` (safe, local only), or use a fresh account. |

## Related docs

- [Billing feature reference](features/billing.md) — how the integration works internally (routes, layers, webhook sync, `require_plan`).
- [Deployment](deployment.md) — moving to Stripe live-mode and hosted webhooks in production.
- [Stripe: subscriptions overview](https://docs.stripe.com/billing/subscriptions/overview) · [SaaS subscriptions use-case](https://docs.stripe.com/get-started/use-cases/saas-subscriptions) — official background reading.
