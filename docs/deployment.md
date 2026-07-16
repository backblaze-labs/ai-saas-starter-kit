<!-- last_verified: 2026-07-16 -->
# Deployment

This starter kit is two deployable services plus three managed dependencies:

```
┌─────────────────────┐        ┌──────────────────────┐
│  Next.js frontend   │  HTTPS │  FastAPI backend      │
│  (Vercel)           │ ─────▶ │  (Railway / Render /  │
│  apps/web           │        │   Fly.io) services/api│
└─────────────────────┘        └──────────┬───────────┘
                                           │
              ┌────────────────────────────┼────────────────────────────┐
              ▼                             ▼                            ▼
     ┌────────────────┐          ┌──────────────────┐        ┌────────────────────┐
     │ Supabase       │          │ Stripe           │        │ Backblaze B2        │
     │ (auth+Postgres)│          │ (billing)        │        │ (object storage)    │
     └────────────────┘          └──────────────────┘        └────────────────────┘
```

The frontend is a static/edge Next.js app and belongs on Vercel; the backend is a
long-running FastAPI process (it talks to B2 with server-only credentials and runs
the Genblaze generation pipeline), so it needs a container/VM host — Railway,
Render, or Fly.io all work. Everything else (auth DB, billing, storage) is a
managed service you point env vars at.

> Local development needs none of this — see the [README Quick Start](../README.md#quick-start).
> This guide is only for shipping to a public URL.

## 1. Frontend → Vercel

### One-click

The **Deploy to Vercel** button in the [README](../README.md#deploy) clones the repo
and pre-fills the three public env vars. When prompted, set:

- **Root Directory**: `apps/web` — this is a pnpm monorepo; Vercel installs the
  workspace from the repo root and builds only the web app. (The button sets this
  for you; confirm it in the import screen.)
- **Framework Preset**: Next.js (auto-detected).

### Environment variables (Vercel → Project → Settings → Environment Variables)

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_API_URL` | Your deployed backend origin (e.g. `https://api-production-xxxx.up.railway.app`) — **no trailing slash** |
| `NEXT_PUBLIC_SUPABASE_URL` | Your Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Your Supabase anon/publishable key |

These are the only browser-exposed values. Everything secret (service-role key,
Stripe secret, B2 keys, NVIDIA key) lives on the backend and never ships to the
client.

> Deploy the backend **first** so you have its URL to paste into `NEXT_PUBLIC_API_URL`.
> Then redeploy the frontend if you set it after the first build (Next.js inlines
> `NEXT_PUBLIC_*` at build time).

## 2. Backend → Railway (or Render / Fly.io)

`services/api` is a standard FastAPI app started with
`uvicorn main:app --host 0.0.0.0 --port $PORT`. Step-by-step Railway config
(both services, root directories, build/start commands) lives in
[`infra/railway/README.md`](../infra/railway/README.md). Render and Fly.io follow
the same shape — set the root directory to `services/api`, install with
`pip install -r requirements.txt`, and bind uvicorn to the platform's `$PORT`.

### Environment variables (backend service)

| Variable | Required | Notes |
|----------|:--------:|-------|
| `B2_APPLICATION_KEY_ID` | ✅ | B2 key ID (Read & Write) |
| `B2_APPLICATION_KEY` | ✅ | B2 application key |
| `B2_BUCKET_NAME` | ✅ | Bucket unique name |
| `B2_REGION` | ✅ | e.g. `us-west-004` — the S3 endpoint is derived from it |
| `B2_PUBLIC_URL_BASE` | — | Optional; unset → presigned URLs (works with a private bucket) |
| `NEXT_PUBLIC_SUPABASE_URL` | ✅ | Supabase project URL — same name the frontend uses; the backend falls back to it |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | ✅ | Anon/publishable key — same name as the frontend |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | **Server-only.** Required at boot (billing + plan-gating writes bypass RLS) |
| `NVIDIA_API_KEY` | — | Required only to run `/generate` (503 without it) |
| `STRIPE_SECRET_KEY` | — | Required only for billing (503 without it) |
| `STRIPE_WEBHOOK_SECRET` | — | The signing secret of your **production** webhook endpoint (see §4) |
| `STRIPE_PRICE_PRO` / `STRIPE_PRICE_TEAM` | — | `price_...` IDs from your Stripe catalog |
| `API_CORS_ORIGINS` | ✅ | **Comma-separated** allowlist — must include your Vercel URL, e.g. `https://your-app.vercel.app` |
| `BILLING_SUCCESS_URL` | — | Stripe redirect back to the frontend, e.g. `https://your-app.vercel.app/billing?checkout=success` |
| `BILLING_CANCEL_URL` | — | e.g. `https://your-app.vercel.app/billing?checkout=cancelled` |
| `BILLING_PORTAL_RETURN_URL` | — | e.g. `https://your-app.vercel.app/billing` |

> The backend reads the Supabase URL + anon key from the `NEXT_PUBLIC_*` names above —
> one source of truth shared with the frontend, nothing to duplicate. If you'd rather not
> carry `NEXT_PUBLIC_*` names on this host, set `SUPABASE_URL` / `SUPABASE_ANON_KEY`
> instead; they override the fallback.

> **Two production gotchas that pass locally and fail in prod:**
> 1. `API_CORS_ORIGINS` defaults to `localhost` — the browser will get CORS errors
>    against the deployed frontend until you add your Vercel URL here.
> 2. `BILLING_*_URL` default to `localhost:3000` — Stripe Checkout will redirect
>    users back to localhost after payment until you point these at your frontend.

## 3. Supabase (hosted)

1. Create a project at [supabase.com](https://supabase.com).
2. Link the CLI to that project, then apply the migrations from `supabase/migrations/`.
   Linking is what tells `db push` which project to target — without it you get
   `cannot find project ref`:
   ```bash
   supabase login                                  # once per machine (opens the browser)
   supabase link --project-ref <your-project-ref>  # ref = your project URL subdomain
   supabase db push
   ```
   This creates every table (profiles, roles, plans, subscriptions, stripe_events,
   files, generation_jobs, provider_runs, usage_events, admin_audit_events), all
   RLS policies, and the explicit table grants — the app is production-ready after
   `db push`. (Recent Supabase CLIs mint a temporary login role from your `supabase
   login` session, so `link`/`db push` no longer prompt for the database password.)
3. Copy **Project Settings → API** into your env — the same three names on both hosts:
   - Project URL → `NEXT_PUBLIC_SUPABASE_URL`
   - anon/publishable key → `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - service-role key → `SUPABASE_SERVICE_ROLE_KEY` (backend only — **never** the frontend)

   The backend reads the URL + anon key from the `NEXT_PUBLIC_*` pair, so there is
   nothing to duplicate into separate `SUPABASE_URL` / `SUPABASE_ANON_KEY` vars.

> ⚠️ **Admin bootstrap:** the first user to sign up is auto-promoted to admin
> (convenient locally, risky on a public URL). Sign up yourself first before
> announcing the app, or remove the auto-promote branch in the auth migration and
> grant admin manually. See [SECURITY.md](SECURITY.md).

> ℹ️ **Signup email deliverability.** `/auth/confirm` handles Supabase's default
> confirmation link out of the box, so signup works on the free tier with no email
> config. But the built-in sender is rate-limited to a few emails/hour, and the
> single-use link can be **consumed by corporate mail scanners** (Proofpoint URL
> Defense, Microsoft SafeLinks, Mimecast) before the user clicks — which surfaces
> as `confirmation-failed`. For production, configure a **custom SMTP provider**
> (Resend/Postmark/SES) with a verified sending domain; this also unlocks a branded
> `token_hash` template that confirms across devices.

## 4. Stripe (production billing)

1. Switch the [Stripe Dashboard](https://dashboard.stripe.com) to **live mode** and
   copy the live `STRIPE_SECRET_KEY` (or stay in test mode for a demo deploy — the
   test card `4242 4242 4242 4242` keeps working).
2. Create the plan prices with **`pnpm stripe:seed`** — with a live `sk_live_...` key
   in `STRIPE_SECRET_KEY` it creates the Pro/Team products + recurring prices in **live
   mode** and writes `STRIPE_PRICE_PRO` / `STRIPE_PRICE_TEAM` for you (the same one
   command as local dev; idempotent). Prefer the Dashboard? Create a recurring Price per
   plan by hand and paste the `price_...` IDs into those two vars.
3. Add a **webhook endpoint** pointing at your deployed API:
   `https://<your-api-host>/billing/webhook`. Subscribe to the
   `customer.subscription.*` and `checkout.session.completed` events, then copy the
   endpoint's **signing secret** into `STRIPE_WEBHOOK_SECRET`. (Unlike local dev,
   production does not use `stripe listen`.)
4. Set the `BILLING_*_URL` vars (§2) to your frontend so post-checkout redirects
   land on the deployed app.

## 5. Backblaze B2

Same credentials as local — no production-specific setup. Use a **dedicated
bucket** per environment so staging and production never share objects, and an
application key scoped to that bucket. Generated media and uploads land under the
same prefixes documented in [features/generation.md](features/generation.md) and
[features/file-browser.md](features/file-browser.md).

## 6. Post-deploy checklist

- [ ] Backend `/health` returns `200` (confirms B2 connectivity).
- [ ] Frontend loads and `NEXT_PUBLIC_API_URL` points at the backend (no CORS errors in the console).
- [ ] Sign up → confirm email (hosted Supabase sends a real email; use a non-scanning address) → reach `/dashboard`.
- [ ] `/billing` → Stripe Checkout → webhook flips the subscription row in Supabase.
- [ ] `/generate` (on a Pro plan) produces an image under `generated/…` in B2 and it appears in `/files`.
- [ ] `/admin` is reachable by your admin account and returns `403` for a normal user.

## Related docs

- [README.md](../README.md) — local setup
- [infra/railway/README.md](../infra/railway/README.md) — backend host config
- [ARCHITECTURE.md](../ARCHITECTURE.md) — system layout
- [docs/SECURITY.md](SECURITY.md) — admin bootstrap, secret handling
