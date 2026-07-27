# Plan: Remove developer/demo/operator leakage from the customer view

## Problem
The app had exactly one audience boundary — `isAdmin` (the `/admin` console).
Everything else rendered to a normal signed-in customer, so developer/operator
and demo scaffolding leaked into the product:

- **Operator/dev instructions**: `ErrorState` told users to run `pnpm dev:api`,
  named `http://localhost:8000`, "check the API logs", and B2 key permissions;
  the health banner said "check your `.env` … restart the API"; billing/generate
  toasts said "add your Stripe keys / `NVIDIA_API_KEY` to `.env`"; raw backend
  error text and a "CORS … check the API logs" string reached toasts/boundaries.
- **Internal code names**: `require_plan("pro")` shown to free users (Generate +
  Billing); "NVIDIA NIM (flux.1-dev) … SHA-256 provenance manifest" in the
  Generate subtitle; a FastAPI/Supabase "API session" diagnostic on Account; the
  raw `role` string on the account badge and sidebar footer.
- **"This is a demo" / fake controls**: Settings faked a "Settings saved" toast
  and had phantom toggles; the Danger Zone "Empty bucket" was a no-op that said
  "This is a demo — no files were actually deleted"; the Billing "Test mode uses
  card 4242…" hint was hardcoded and shown even in a live deployment.
- **Polish drift**: two page-heading styles, `…` vs `...`, mixed card-title
  casing, "workspace/bucket/storage" terminology drift, command palette missing
  routes, emoji status on Billing, "Failed Jobs" KPI, two dead dashboard
  components, admin `m0…m8` placeholder labels.

## Fix
Make the default (ungated) view customer-appropriate; keep genuine detail out of
the UI (logs/docs) or, for the one operator affordance worth keeping, behind
`isAdmin`. No broad "demo mode" flag.

- **Copy**: rewrite `ErrorState` and `api-client` network copy to calm, generic
  strings (dev detail stays in the console/network tab); friendly toasts on
  billing/generate/upload/files; error boundaries stop rendering raw
  `error.message`; Account "API session" → neutral "Connection" card; drop
  `require_plan`/NVIDIA/flux/SHA jargon (keep B2 branding per `AGENTS.md §2`).
- **Health banner**: everyone sees "Some features are temporarily unavailable";
  the actionable `.env`/restart detail is appended for admins only.
- **Fake controls (kept, marked clearly)**: Settings shows a "Preview — saving
  isn't wired up" alert and a disabled Save (no fake toast); Danger Zone
  "Empty bucket" is disabled with "Not available in this starter". Logged in the
  tech-debt tracker.
- **Test-card hint (test-mode-gated)**: new `stripe_client.is_test_mode()`
  (`sk_test_` prefix) → `Subscription.test_mode` (backend Pydantic + shared TS
  type, stamped by the service, never stored) → Billing shows the `4242…` hint
  only when `test_mode` is true.
- **Polish**: unify Account/Billing headings with the shared `page-title` block;
  standardize `…` and sentence-case card titles; drop "workspace"; add
  Generate/Billing/Account to the command palette; replace Billing emoji with
  lucide icons; "Failed Jobs" → "Failed generations"; remove the unused
  `StatsCards`/`RecentUploadsTable`; fix the admin overview placeholder labels.

## Verification
`pnpm lint`, `pnpm lint:api`, `pnpm test:web`, `pnpm test:api` (incl. 2 new
`test_mode` tests), `pnpm check:structure`, `pnpm build` all green. Manually
drive Dashboard/Generate/Billing/Settings/Account plus an error state (admin sees
the operator hint on the banner; customer sees only the generic notice).

## Kept per starter contract (`AGENTS.md §2`)
`/design` + its sidebar link, Upload, Files, and their sidebar entries;
generated `components/ui/` untouched.
