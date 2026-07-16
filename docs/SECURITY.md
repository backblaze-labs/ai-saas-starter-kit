<!-- last_verified: 2026-07-15 -->
# Security

Security principles and implementation for the ai-media-saas-starter.

## Trust Boundaries

- **Frontend -> API**: CORS-restricted to configured origins, scoped to `GET/POST/DELETE/OPTIONS`; authenticated calls carry a Supabase bearer token. `allow_credentials` is `False` — the frontend authenticates the API with that bearer token in the `Authorization` header, not a cross-origin cookie, so credentialed CORS is unnecessary. (The Supabase session cookie is held between the browser and Supabase/Next.js, never sent cross-origin to this API.)
- **API -> B2**: Authenticated via `B2_APPLICATION_KEY_ID` + `B2_APPLICATION_KEY`, signature v4
- **Client -> B2**: Presigned URLs for download (10-min expiry, `Content-Disposition: attachment`)
- **Client/API -> Supabase**: browser holds a cookie session (anon/publishable key only); the API validates tokens against Supabase and never ships the service-role key to the client
- **Stripe -> API webhook**: `POST /billing/webhook` is unauthenticated by bearer token — it is authenticated by verifying the `Stripe-Signature` header against `STRIPE_WEBHOOK_SECRET` (a bad/absent signature is rejected `400`). Events are deduped via `public.stripe_events` so a replayed event is a no-op.

## Authentication & Authorization

- Sessions are cookie-based via `@supabase/ssr`; `apps/web/src/proxy.ts` refreshes them
  and redirects unauthenticated requests off protected routes.
- Server code always calls `supabase.auth.getUser()` (revalidates the token) rather than
  trusting `getSession()`.
- The API validates bearer tokens by calling Supabase `/auth/v1/user` (portable across
  local HS256 and hosted asymmetric signing keys — no secret assumptions).
- **Row Level Security** is enabled on `profiles` and `roles`: a user reads/updates only
  their own profile; admins (`is_admin()`) may read/update all. A trigger
  (`prevent_role_escalation`) blocks non-admins from changing their own role.
- **Service-role key** is server-only (`SUPABASE_SERVICE_ROLE_KEY`), never `NEXT_PUBLIC_*`,
  never referenced in client code.
- Redirect targets (`next` param, `/auth/confirm`) are restricted to same-site relative
  paths via `apps/web/src/lib/safe-redirect.ts` (rejects `//`, `\`, and absolute URLs)
  to prevent open redirects.
- **First-user-admin:** the signup trigger promotes the first user to `admin` for
  out-of-the-box demo convenience. On a **public hosted** deploy this is a privilege
  risk (first stranger to register becomes admin) — sign up yourself first, or remove
  the auto-promote branch in the migration and grant admin manually.

## Upload Validation

- Filename sanitization: path traversal, null bytes, unsafe chars stripped
- MIME/extension consistency check against allowlist
- Chunked streaming with size enforcement (100MB default)
- Content-type allowlist (images, PDFs, text, archives, audio/video). **SVG is excluded** — it can embed `<script>` that executes when served from a public bucket URL (stored XSS). Re-add only with server-side sanitization.
- **Magic-byte signature check**: for binary types, the leading bytes must match the declared content type, so a script payload can't masquerade as `image/png`. Text-like types (plain/CSV/JSON) have no signature and skip this check.
- Empty file rejection

## Rate Limiting

- Per-IP fixed-window limiter (`app/runtime/ratelimit.py`), configurable via `RATE_LIMIT_PER_MINUTE` (reads) and `RATE_LIMIT_WRITE_PER_MINUTE` (uploads/deletes/downloads). Guards against DoS and Backblaze transaction/egress cost amplification.
- In-process, per replica. Horizontal scaling needs a shared store (e.g. Redis) — see [RELIABILITY.md](RELIABILITY.md#rate-limiting).

## File Key Validation

- Empty keys rejected
- Path traversal patterns rejected (`../`, `%2e%2e`, backslashes, null bytes)
- Optional prefix confinement: set `ALLOWED_KEY_PREFIX` (e.g. `uploads/`) to restrict key-addressed reads/deletes when the bucket is shared with other workloads. **Off (empty) by default.** Note this app writes under *two* prefixes — `uploads/` (user uploads) and `generated/` (AI-generated media) — so confining to a single prefix would exclude the other's keys; don't enable `uploads/` blindly. The by-key routes otherwise accept arbitrary folder and reserved-word keys by design.

## Download Safety

- Presigned URLs force `Content-Disposition: attachment`
- Prevents inline rendering of user-uploaded content (XSS mitigation)

## Response Hardening

- Baseline headers on every API response: `X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer`
- Interactive API docs (`/docs`, `/redoc`, `/openapi.json`) are on by default but can be disabled with `ENABLE_DOCS=false` to hide the API surface in production

## Secrets Management

- All secrets loaded via environment variables (pydantic-settings)
- Never committed to source control
- `.env.example` documents required variables without values
- Stripe keys (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`) are server-only. The frontend
  never talks to Stripe directly — it redirects to Checkout/Portal URLs the backend mints —
  so no Stripe key reaches the client.

## Agent Security Rules

- Never commit `.env`, credentials, or API keys
- Never weaken validation without explicit instruction
- Never bypass CORS, auth, or input sanitization
- Always validate at system boundaries
