<!-- last_verified: 2026-07-16 -->
# Feature: Authentication

## Purpose
Gate the app behind Supabase auth so every screen and B2 operation belongs to a
signed-in user, and introduce the first real database (profiles + roles).

## Used By
- UI: `/signin`, `/signup`, `/account`; the whole `(app)` route group is protected.
- API: `GET /me` (returns the authenticated identity); `get_current_user` /
  `require_admin` dependencies for future protected/admin endpoints.
- Middleware: `apps/web/src/proxy.ts` (Next 16 proxy convention) refreshes the
  session and redirects unauthenticated requests to `/signin`.

## Core Functions
- `apps/web/src/lib/supabase/{client,server,middleware}.ts` — SSR-safe Supabase clients.
- `apps/web/src/components/auth/auth-provider.tsx` — `useAuth()` (user, profile, isAdmin, signOut).
- `services/api/app/repo/supabase_auth.py` — validates a token via Supabase `/auth/v1/user`.
- `public.handle_new_user()` / `public.is_admin()` / `public.prevent_role_escalation()` (migration).

## Canonical Files
- Email confirmation landing: `apps/web/src/app/auth/confirm/route.ts` (handles `?code=` and `?token_hash=`)
- Route protection: `apps/web/src/proxy.ts` + `apps/web/src/lib/supabase/middleware.ts`
- DB + RLS: `supabase/migrations/00000000000000_init.sql` (auth section)
- API auth: `services/api/app/runtime/auth.py` (thin) → `service/auth.py` → `repo/supabase_auth.py`

## Inputs
- email + password, or email + 6-digit OTP code (sign-in UI)
- `Authorization: Bearer <supabase access token>` (API requests)

## Outputs
- A cookie-based Supabase session (managed by `@supabase/ssr`)
- A `public.profiles` row per user (created by the `on_auth_user_created` trigger)
- Side effects: first-ever user is promoted to `admin`; `GET /me` returns `{id, email, role}`

## Flow
- Sign up → Supabase sends a confirmation email → user clicks the link → `/auth/confirm`
  completes it and sets the session → redirect into the app. The route accepts both
  Supabase link shapes: `?code=` (PKCE, from the default `{{ .ConfirmationURL }}`
  template that hosted free-tier projects send) via `exchangeCodeForSession`, and
  `?token_hash=&type=` (the local custom template) via `verifyOtp`.
- Sign in (password or email OTP) → session cookies set → redirect to `next` (default `/`).
- Every request passes through `proxy.ts`: no session on a protected route → `/signin?next=…`.
- Client API calls attach the access token (`lib/api-client.ts`); the API validates it
  against Supabase and reads the caller's role from `profiles` (RLS-scoped).
- On a hard API `401`, the global TanStack Query error handler (`lib/query-client.tsx`)
  signs the stale client session out and bounces to `/signin?next=…`. If a *valid*
  Supabase cookie disagrees with an API that rejects the bearer (misconfig:
  mismatched JWT secret / wrong Supabase project), a naïve redirect would loop
  (`/signin` → cookie-based middleware → back into the app → `401` …). Two guards
  prevent it: the `signOut()` clears the cookie so the middleware stops bouncing,
  and a short self-expiring `sessionStorage` window (`shouldRedirectToSignin`)
  suppresses a second redirect so a persistent mismatch surfaces as an inline
  error instead of an infinite loop.

## Edge Cases
- Invalid/expired confirmation link → redirect to `/signin?error=confirmation-failed`.
- PKCE (`?code=`) confirmation requires the `code_verifier` cookie set at signup, so
  the link must be opened in the **same browser** that signed up. Cross-device
  confirmation needs the `token_hash` template (a custom template → custom SMTP on
  hosted free tier).
- Corporate mail scanners (Proofpoint URL Defense, Microsoft SafeLinks, Mimecast)
  pre-fetch links and can consume the single-use token before the user clicks,
  yielding `confirmation-failed`. Use a non-scanning address for testing; production
  should use a verified sending domain.
- Signed-in user visiting `/signin` or `/signup` → redirected into the app.
- `next` param that isn't a same-site relative path → ignored (no open redirect).
- Non-admin editing their own `role` → blocked by `prevent_role_escalation` trigger.
- Missing/!bearer Authorization on the API → 401; valid token but non-admin on an admin route → 403.

## UX States
- Empty: sign-in / sign-up forms.
- Loading: "Signing in…", "Creating account…", "Checking…" (Connection card).
- Error: inline `role="alert"` messages from Supabase; account API card degrades gracefully.

## Verification
- Test files: `apps/web/e2e/auth.spec.ts`, `apps/web/e2e/auth.setup.ts`, `services/api/tests/test_auth.py`
- Required cases: unauthenticated redirect (+`next`), signup→email-confirm→session,
  protected dashboard reached, `/me` validates the session, sign-out.
- Quick verify command: `pnpm test:api` (API auth unit tests)
- Full verify command: `supabase start` + `pnpm dev`, then `pnpm test:e2e`
- Pass criteria: API auth tests green; e2e auth + upload specs green against a running stack.

## Related Docs
- [README.md](../../README.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [docs/SECURITY.md](../SECURITY.md)
- [docs/app-workflows.md](../app-workflows.md)
