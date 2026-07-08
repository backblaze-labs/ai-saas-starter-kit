<!-- last_verified: 2026-04-22 -->
# Security

Security principles and implementation for the ai-media-saas-starter.

## Trust Boundaries

- **Frontend -> API**: CORS-restricted to configured origins, scoped to `GET/POST/DELETE/OPTIONS`; authenticated calls carry a Supabase bearer token
- **API -> B2**: Authenticated via `B2_APPLICATION_KEY_ID` + `B2_APPLICATION_KEY`, signature v4
- **Client -> B2**: Presigned URLs for download (10-min expiry, `Content-Disposition: attachment`)
- **Client/API -> Supabase**: browser holds a cookie session (anon/publishable key only); the API validates tokens against Supabase and never ships the service-role key to the client

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
- Content-type allowlist (images, PDFs, text, archives, audio/video)
- Empty file rejection

## File Key Validation

- Empty keys rejected
- Path traversal patterns rejected (`../`, `%2e%2e`, backslashes, null bytes)
- The bucket is the only access boundary — add prefix scoping in
  `services/api/app/service/files.py::validate_key` if your deployment
  shares a bucket with other workloads

## Download Safety

- Presigned URLs force `Content-Disposition: attachment`
- Prevents inline rendering of user-uploaded content (XSS mitigation)

## Secrets Management

- All secrets loaded via environment variables (pydantic-settings)
- Never committed to source control
- `.env.example` documents required variables without values

## Agent Security Rules

- Never commit `.env`, credentials, or API keys
- Never weaken validation without explicit instruction
- Never bypass CORS, auth, or input sanitization
- Always validate at system boundaries
