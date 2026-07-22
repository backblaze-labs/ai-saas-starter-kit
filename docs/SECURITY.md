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
- **Identity is cached; authorization is not.** The `/auth/v1/user` identity lookup is
  memoized for a short TTL (`AUTH_CACHE_TTL_SECONDS`, default 30s), keyed by a SHA-256
  hash of the bearer token (never the raw token, so plaintext tokens aren't held in
  memory). This drops one of the two per-request Supabase round-trips on a warm hit. The
  role/authorization decision (`/rest/v1/profiles`) is **never cached** — it is fetched
  live on every request, so a demoted admin loses access immediately (no
  privilege-escalation window). Tradeoff: what the cache skips is the identity/liveness
  check, so a token is honored for up to the TTL past its **expiry or revocation** (not
  just rotation) — bounded and low-risk here because Supabase access tokens are already
  bearer-valid until their own ~1h `exp` regardless of logout, and **privilege escalation
  is impossible** (a stale admin token's live role fetch fails and downgrades to `user`).
  Set `AUTH_CACHE_TTL_SECONDS=0` to disable the cache and revalidate identity on every
  request.
- **Row Level Security** is enabled on `profiles` and `roles`: a user reads/updates only
  their own profile; admins (`is_admin()`) may read/update all. A trigger
  (`prevent_role_escalation`) blocks non-admins from changing their own role.
- **Service-role key** is server-only (`SUPABASE_SERVICE_ROLE_KEY`), never `NEXT_PUBLIC_*`,
  never referenced in client code.
- Redirect targets (`next` param, `/auth/confirm`) are restricted to same-site relative
  paths via `apps/web/src/lib/safe-redirect.ts` (rejects `//`, `\`, absolute URLs, and
  any control char — `\t`/`\r`/`\n` are stripped by the URL parser and would otherwise
  slip a `//evil.com` past the guard) to prevent open redirects.
- **Admin role** is granted explicitly (no auto-promotion — every signup gets the
  default `user` role in `handle_new_user`). After the first deploy, run
  `update public.profiles set role='admin' where email='you@example.com';` as the
  service role. The `prevent_role_escalation` trigger blocks non-admins from changing
  their own role; the admin role-change API runs with the caller's own token so the
  trigger permits it.

## Upload Validation

- Filename sanitization: path traversal, null bytes, unsafe chars stripped
- MIME/extension consistency check against allowlist
- Chunked streaming with size enforcement (100MB default)
- Content-type allowlist (images, PDFs, text, archives, audio/video). **SVG is excluded** — it can embed `<script>` that executes when served from a public bucket URL (stored XSS). Re-add only with server-side sanitization.
- **Magic-byte signature check**: for binary types, the leading bytes must match the declared content type, so a script payload can't masquerade as `image/png`. Text-like types (plain/CSV/JSON) have no signature and skip this check.
- Empty file rejection

## Rate Limiting

- Per-IP fixed-window limiter (`app/runtime/ratelimit.py`), configurable via `RATE_LIMIT_PER_MINUTE` (reads) and `RATE_LIMIT_WRITE_PER_MINUTE` (uploads/deletes/downloads). Guards against DoS and Backblaze transaction/egress cost amplification.
- `/billing/webhook` is **exempt** — Stripe events arrive from a few shared egress IPs, so limiting them would throttle all customers' events into one bucket; the endpoint is guarded by signature verification instead.
- In-process, per replica. Horizontal scaling needs a shared store (e.g. Redis) — see [RELIABILITY.md](RELIABILITY.md#rate-limiting).

## Request Body Size Limit

- A pure-ASGI middleware (`app/runtime/bodylimit.py`) rejects any request body over `MAX_REQUEST_BODY_SIZE` with a `413` **before** FastAPI's multipart parser buffers it to disk — an in-handler size check runs too late (the body is already spooled). It refuses on `Content-Length` up front and also meters the streamed body, so a chunked / no-Content-Length request can't slip past. Registered inner to CORS so the `413` still carries CORS headers.

## Paid-Feature Abuse Controls

- **Plan changes go through the Billing Portal, not a second Checkout.** `POST /billing/checkout` returns `409` for a user who already has an active subscription (a second subscription-mode Checkout would open a *concurrent* Stripe subscription — double billing); the UI routes active subscribers to the portal.
- **Generation has a soft per-user daily cap** (`GENERATION_DAILY_LIMIT`, counted over jobs so failures count too) → `429` when exceeded, so a compromised/shared Pro session can't burn unbounded provider credits.

## File Surface: Authentication & Per-User Isolation

- **Every file route is authenticated.** `GET /files`, `GET /files/stats`, `GET /files/stats/activity`, the `/files-by-key/*` and legacy `/files/{key}` reads/deletes, and `POST /upload` all depend on `get_current_user`; a missing or invalid bearer token returns `401`. (Rate limiting runs ahead of auth, so abusive unauthenticated traffic is still throttled per IP.)
- **Reads/listings are scoped to the caller.** Listings and stats cover only the union of the caller's `uploads/{user_id}/` and `generated/{user_id}/` prefixes — never a bucket-wide scan — so one tenant cannot see another's uploads or generated media.
- **Writes are scoped to the caller.** Uploaded objects are keyed under `uploads/{user_id}/…`, not a flat `uploads/…`, so users' uploads never collide with or shadow each other.
- **Ownership is enforced on key-addressed ops.** `metadata`/`download`/`preview`/`delete` for a key outside the caller's own prefixes return `404` — not `403` — so a guessed key never confirms another user's object exists, and no user can read or delete another user's object.

## File Key Validation

- Empty keys rejected
- Path traversal patterns rejected (`../`, `%2e%2e`, backslashes, null bytes)
- Optional prefix confinement: set `ALLOWED_KEY_PREFIX` (e.g. `uploads/`) to add a **global** static confinement (a `400` before ownership is even checked) when the bucket is shared with other workloads. **Off (empty) by default**, and independent of the always-on per-user ownership scoping above. Note this app writes under *two* prefixes — `uploads/` and `generated/` — so confining to a single one would `400` the other's keys; don't enable `uploads/` blindly.

## Download Safety

- Download presigned URLs force `Content-Disposition: attachment` — prevents inline rendering of user-uploaded content (XSS mitigation).
- Preview presigned URLs use `inline` (so the modal can render an image/PDF), which is safe: the URL is on the isolated B2 origin (not the app origin) and SVG/HTML are excluded from the upload allow-list, so no allowed type executes script in the app's context.

## Response Hardening

- Baseline headers on every API response: `X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer`
- Interactive API docs (`/docs`, `/redoc`, `/openapi.json`) are **off by default**; set `ENABLE_DOCS=true` to expose them (e.g. for local exploration).
- `/metrics` is gated by an optional `METRICS_TOKEN` bearer token. Empty (default) keeps it open for local dev / a private-network scrape; set it on a public deploy so route templates and traffic/error volumes aren't world-readable.

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
