# Plan: /auth/confirm handles the PKCE `code` email link

## Problem
Signup email confirmation failed against the hosted Supabase project. Root cause
was a flow mismatch, not link expiry:

- The hosted project is **free tier using Supabase's built-in email provider**,
  which **cannot customize email templates** (confirmed: `config push` returns
  `Email template modification is not available for free tier projects using the
  default email provider`). So hosted sends the **default** `{{ .ConfirmationURL }}`
  template — a PKCE link: `/auth/v1/verify?token=pkce_…&redirect_to=…/auth/confirm`.
- Supabase's `/verify` endpoint redirects that to `/auth/confirm?code=…`, but the
  route only handled `token_hash` and never called `exchangeCodeForSession`, so it
  always fell through to `/signin?error=confirmation-failed` — the "invalid or
  expired" message the user saw.
- A corporate mail scanner (Proofpoint URL Defense) was a secondary factor: it
  pre-fetches links and can consume the single-use token before the user clicks.

## Fix
Make `apps/web/src/app/auth/confirm/route.ts` handle **both** link shapes:
- `?code=…` → `exchangeCodeForSession(code)` (PKCE; the default hosted template).
- `?token_hash=&type=` → `verifyOtp` (the local custom SSR template).

This makes the default hosted email work on the free tier with **no custom SMTP
and no template customization**. Standing up custom SMTP (for a branded template,
higher send limits, and cross-device confirmation) is left to whoever deploys the
app for production — see docs/deployment.md.

## Caveats (documented, not fixed here)
- PKCE `exchangeCodeForSession` needs the `code_verifier` cookie set at signup, so
  the link must be opened in the **same browser** that signed up. Cross-device
  confirmation needs the `token_hash` template (which needs custom SMTP on a
  hosted free-tier project).
- Link-based confirmation is inherently fragile behind mail scanners (Proofpoint,
  SafeLinks, Mimecast) that pre-consume one-time links. Test with a personal /
  non-scanning address; production should use a verified sending domain.

## Steps
1. `apps/web/src/app/auth/confirm/route.ts`: add the `code` branch (done).
2. `docs/features/authentication.md`: Flow + Edge Cases + Canonical Files + date.
3. `docs/deployment.md`: signup checklist note (default email works; scanner caveat).
4. Verify: `pnpm lint`, `pnpm build`; hosted signup with a personal email.

## Out of scope
- Custom SMTP setup (deployer's responsibility; documented).
- Switching the signup UX to an in-app OTP code (considered, reverted — needs a
  customized template, which the hosted free tier blocks).
