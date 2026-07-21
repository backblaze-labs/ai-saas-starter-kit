<!-- last_verified: 2026-07-16 -->
# Security

Security principles and implementation for the ai-saas-starter-kit.

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

Uploads go **directly from the browser to B2** via a presigned PUT (the bytes
never transit the API), so validation is split across the two control requests:

- **At `POST /upload/presign` (before signing):** filename sanitization (path
  traversal, null bytes, unsafe chars stripped); MIME/extension consistency
  check; content-type allowlist (images, PDFs, text, archives, audio/video) —
  **SVG is excluded** (it can embed `<script>` that executes when served from a
  public bucket URL → stored XSS; re-add only with server-side sanitization);
  declared size enforcement (>0 and ≤ 100MB default). The presigned URL is bound
  to the exact object key **and** `Content-Type`, so the browser can't store a
  different type than was validated.
- **At `POST /upload/complete` (after the object exists):** ownership check (the
  key must be under the caller's own `uploads/` prefix, else `403` before any B2
  call); **true stored size** re-checked against the limit (`413`); and a
  **magic-byte signature re-check** — the API Range-GETs the object header and,
  for binary types, requires the leading bytes to match the declared content type
  so a script payload can't masquerade as `image/png`. A mismatch **deletes** the
  object and returns `415`. Text-like types (plain/CSV/JSON) have no signature
  and skip this check.
- Empty file rejection (declared size 0, or 0 bytes stored).

## Rate Limiting

- Per-IP fixed-window limiter (`app/runtime/ratelimit.py`), configurable via `RATE_LIMIT_PER_MINUTE` (reads) and `RATE_LIMIT_WRITE_PER_MINUTE` (uploads/deletes/downloads). Guards against DoS and Backblaze transaction/egress cost amplification.
- In-process, per replica. Horizontal scaling needs a shared store (e.g. Redis) — see [RELIABILITY.md](RELIABILITY.md#rate-limiting).

## File Surface: Authentication & Per-User Isolation

- **Every file route is authenticated.** `GET /files`, `GET /files/stats`, `GET /files/stats/activity`, the `/files-by-key/*` and legacy `/files/{key}` reads/deletes, and both upload steps (`POST /upload/presign`, `POST /upload/complete`) all depend on `get_current_user`; a missing or invalid bearer token returns `401`. (Rate limiting runs ahead of auth, so abusive unauthenticated traffic is still throttled per IP.)
- **Reads/listings are scoped to the caller.** Listings and stats cover only the union of the caller's `uploads/{user_id}/` and `generated/{user_id}/` prefixes — never a bucket-wide scan — so one tenant cannot see another's uploads or generated media.
- **Writes are scoped to the caller.** Uploaded objects are keyed under `uploads/{user_id}/…`, not a flat `uploads/…`, so users' uploads never collide with or shadow each other.
- **Ownership is enforced on key-addressed ops.** `metadata`/`download`/`preview`/`delete` for a key outside the caller's own prefixes return `404` — not `403` — so a guessed key never confirms another user's object exists, and no user can read or delete another user's object.

## File Key Validation

- Empty keys rejected
- Path traversal patterns rejected (`../`, `%2e%2e`, backslashes, null bytes)
- Optional prefix confinement: set `ALLOWED_KEY_PREFIX` (e.g. `uploads/`) to add a **global** static confinement (a `400` before ownership is even checked) when the bucket is shared with other workloads. **Off (empty) by default**, and independent of the always-on per-user ownership scoping above. Note this app writes under *two* prefixes — `uploads/` and `generated/` — so confining to a single one would `400` the other's keys; don't enable `uploads/` blindly.

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
