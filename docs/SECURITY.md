<!-- last_verified: 2026-07-21 -->
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
  privilege-escalation window). Because that live call carries the same bearer token,
  it also re-checks liveness: an **expired token 401/403s there even on a warm cache
  hit**, and the handler then evicts the cached identity and rejects the request (`401`)
  rather than defaulting to role `user` — so the cache does **not** extend a token's life
  past its own `exp`. A transient PostgREST `5xx` (as opposed to a `401/403`) is treated
  as an unknown role and fails safe to `user` **without** evicting or logging the caller
  out, so a backend blip can't mass-sign-out valid users. The residual staleness is
  therefore limited to identity fields (e.g. email) for up to the TTL, which is itself
  clamped to a ceiling (300s) regardless of a misconfigured `AUTH_CACHE_TTL_SECONDS`.
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

> **Caveat — the finalize checks are only enforced for objects the client finalizes.**
> The `Content-Type` binding at presign holds unconditionally, but the true-size
> (`413`) and magic-byte (`415`) checks run at `/upload/complete`. An object PUT to
> the presigned URL but never finalized lands under the caller's `uploads/` prefix
> and is listed/downloadable without those checks — so the size cap is
> **advisory** on the write path and a same-user oversized/mismatched object can
> persist. Cross-tenant isolation is unaffected (the key is server-built from the
> caller's id, and SVG/HTML are excluded so a mismatched payload still can't be a
> stored-XSS vector). Fully closing it (a staging prefix promoted on finalize, or
> a bucket-lifecycle sweep of stale unconfirmed objects) is tracked in the
> tech-debt tracker.

## Rate Limiting

- Per-IP fixed-window limiter (`app/runtime/ratelimit.py`), configurable via `RATE_LIMIT_PER_MINUTE` (reads) and `RATE_LIMIT_WRITE_PER_MINUTE` (uploads/deletes/downloads). Guards against DoS and Backblaze transaction/egress cost amplification.
- **`X-Forwarded-For` is NOT trusted by default.** `TRUST_PROXY` is **off** (`false`) — the limiter keys on the real socket peer (`request.client.host`), so a directly-exposed clone can't spoof/rotate the header to mint a fresh bucket per request and defeat the limit. Set `TRUST_PROXY=true` **only** when the app sits behind a known, trusted proxy that appends the real client IP as the rightmost XFF hop (e.g. Railway); then the limiter keys on that hop. **Leaving it off behind such a proxy is itself a footgun**: every request then keys on the proxy's socket peer (one low-cardinality IP), so all clients share a single bucket and one busy user throttles everyone. The documented Railway deploy therefore sets `TRUST_PROXY=true` (see [infra/railway/README.md](../infra/railway/README.md)).
- `/billing/webhook` is **exempt** — Stripe events arrive from a few shared egress IPs, so limiting them would throttle all customers' events into one bucket; the endpoint is guarded by signature verification instead.
- In-process, per replica. Horizontal scaling needs a shared store (e.g. Redis) — see [RELIABILITY.md](RELIABILITY.md#rate-limiting).

## Request Body Size Limit

- A pure-ASGI middleware (`app/runtime/bodylimit.py`) rejects any request body over `MAX_REQUEST_BODY_SIZE` with a `413` **before** FastAPI's multipart parser buffers it to disk — an in-handler size check runs too late (the body is already spooled). It refuses on `Content-Length` up front and also meters the streamed body, so a chunked / no-Content-Length request can't slip past. Registered inner to CORS so the `413` still carries CORS headers.

## Paid-Feature Abuse Controls

- **Plan changes go through the Billing Portal, not a second Checkout.** `POST /billing/checkout` returns `409` for a user who already has an active subscription (a second subscription-mode Checkout would open a *concurrent* Stripe subscription — double billing); the UI routes active subscribers to the portal.
- **Generation has a soft per-user daily cap** (`GENERATION_DAILY_LIMIT`, counted over jobs so failures count too) → `429` when exceeded, so a compromised/shared Pro session can't burn unbounded provider credits.

## File Surface: Authentication & Per-User Isolation

- **Every file route is authenticated.** `GET /files`, `GET /files/stats`, `GET /files/stats/activity`, the `/files-by-key/*` reads/deletes, and both upload steps (`POST /upload/presign`, `POST /upload/complete`) all depend on `get_current_user`; a missing or invalid bearer token returns `401`. (Rate limiting runs ahead of auth, so abusive unauthenticated traffic is still throttled per IP.)
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
- **Frontend baseline headers** on every route (`apps/web/next.config.ts` `headers()`): `X-Frame-Options: DENY` (anti-clickjacking), `Strict-Transport-Security: max-age=63072000; includeSubDomains` (pins HTTPS for 2 years once served over TLS — a no-op on plain-HTTP localhost), `Referrer-Policy: strict-origin-when-cross-origin`, `X-Content-Type-Options: nosniff`, and a conservative `Permissions-Policy` (`camera=(), microphone=(), geolocation=()`). **No `Content-Security-Policy`** is set: a hardcoded CSP needs env-specific `connect-src` (Supabase + API origins) and would break the app when re-deployed — clickjacking is already covered by `X-Frame-Options: DENY`. Add a CSP per-deployment once the real origins are known.
  - The frontend `Referrer-Policy` (`strict-origin-when-cross-origin`) deliberately differs from the API's stricter `no-referrer`: the app UI needs a same-origin referrer for normal navigation, while the API leaks nothing. The divergence is intentional, not a bug.
  - `Strict-Transport-Security` includes `includeSubDomains`, which pins **every** subdomain of the registrable domain to HTTPS. If you deploy on a shared apex and serve any sibling (e.g. a staging or internal tool) over plain HTTP, drop `includeSubDomains` (or shorten `max-age`). No `preload` is set, so it stays browser-recoverable.
- Interactive API docs (`/docs`, `/redoc`, `/openapi.json`) are **off by default**; set `ENABLE_DOCS=true` to expose them (e.g. for local exploration).
- `/metrics` is gated by an optional `METRICS_TOKEN` bearer token. Empty (default) keeps it open for local dev / a private-network scrape; set it on a public deploy so route templates and traffic/error volumes aren't world-readable. When the token is empty, the API **emits a startup WARNING** (structured log) so an operator who shipped the empty default is alerted that `/metrics` is world-readable.

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
