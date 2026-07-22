<!-- last_verified: 2026-07-15 -->
# Architecture

## Components

- **apps/web/** — Next.js 16 frontend (App Router, Tailwind v4, shadcn/ui)
  - Supabase auth: sign in/up, `/account`, session refresh + route protection via `proxy.ts`
  - Route groups: `(app)` (authenticated shell) and `(auth)` (chrome-free sign-in/up)
  - Stripe billing: `/billing` plan catalog, Checkout/Portal redirects, plan-gated surfaces
  - Dashboard with stats, upload chart, recent uploads
  - File upload with drag-and-drop, progress tracking
  - File browser with preview, download, delete
  - Dark mode via `next-themes`
- **services/api/** — FastAPI backend (layered architecture)
  - REST API for file upload, listing, deletion
  - B2 S3 integration via boto3
  - Stripe billing: checkout/portal sessions, signature-verified webhook → Supabase sync, `require_plan` gate
  - File metadata extraction (images, PDFs)
  - Health check endpoint with B2 connectivity verification
  - Structured JSON logging with request tracing
  - Prometheus-format metrics endpoint
- **packages/shared/** — TypeScript type definitions
  - Mirrors Pydantic models from the API
  - Consumed by `apps/web/` as workspace dependency

## Backend Layering

The API follows a strict layered architecture:

```
types/     Pydantic models — no logic, no imports from other layers
  |
config/    Settings (pydantic-settings) — depends only on types
  |
repo/      Data access (boto3 B2 client) — no business logic
  |
service/   Business logic — calls repo, returns types
  |
runtime/   FastAPI routes — calls service, never repo directly
```

### Layering Rules

1. Dependencies flow downward only: `types` -> `config` -> `repo` -> `service` -> `runtime`
2. No backward imports (e.g., service must not import from runtime)
3. `boto3` only allowed in `repo/` layer
4. All boundary data uses Pydantic models (no raw dicts across layers)
5. Each file stays under 300 lines

### Directory Structure

```
services/api/
  main.py                  App entrypoint, middleware, router registration
  app/
    types/                 Pydantic models (FileMetadata, UploadStats, etc.)
    config/                Settings loaded from environment
    repo/                  B2 S3 client (data access layer)
    service/               Business logic (upload, files, metadata)
    runtime/               FastAPI route handlers
  tests/                   pytest tests (structural + integration)
```

## Boundary Invariants

- **No external SDK leakage**: `boto3` is only imported in `app/repo/`. All other layers interact with B2 through the repo interface.
- **No raw dicts at boundaries**: All data crossing layer boundaries uses typed Pydantic models.
- **No cross-layer mutable state**: Configuration is read-only after init, and no mutable state is shared *between* layers. Intra-layer caches/counters (the listing cache in `repo/b2_client.py`, the download counter in `repo/counter.py`, the rate-limit and metrics state in `runtime/`) are module-local and guarded by a `threading.Lock`.
- **Validated inputs**: All HTTP inputs validated by FastAPI/Pydantic. File keys reject empty and path-traversal patterns; optional prefix confinement via `ALLOWED_KEY_PREFIX` (off by default).

## Deployment

- **Local dev** — `pnpm dev` runs both services via `concurrently`
  - Web: `localhost:3000`
  - API: `localhost:8000`
- **Railway** — two services from the same repo
  - See `infra/railway/README.md` for configuration

## Data Stores

- **Backblaze B2** — object storage (S3-compatible API)
  - All uploaded files stored in a single bucket
  - File listing and metadata via S3 `list_objects_v2` / `head_object`
- **Supabase Postgres** — auth + application database
  - `auth.users` (managed by Supabase) plus `public.profiles` (1:1) and `public.roles`
  - Billing: `public.plans` (catalog), `public.subscriptions` (one synced row/user),
    `public.stripe_events` (webhook idempotency) — subscription rows are written only
    by the webhook via the service role (RLS lets a user read only their own)
  - Row Level Security scopes reads/writes to the owning user (admins see all)
  - Schema lives in a single init file, `supabase/migrations/00000000000000_init.sql` (auth, billing, generation, admin sections); local dev runs the full stack via `supabase start`

## External Services

- **Backblaze B2 S3 API** — file storage, retrieval, deletion, presigned URLs
- **Supabase** — authentication (GoTrue) + Postgres/PostgREST; local or hosted, config-only swap
- **Stripe** — subscription billing (Checkout, Billing Portal, webhooks); test-mode for local dev

## Trust Boundaries

See [docs/SECURITY.md](docs/SECURITY.md) for full security documentation.

- **Frontend -> API** — CORS-restricted to configured origins. `CORSMiddleware` is registered LAST in `main.py` (outermost) so it wraps **every** response, including uncaught-exception 500s — otherwise the browser would block error responses and the UI would only see an opaque "network error". See [docs/RELIABILITY.md](docs/RELIABILITY.md#error-handling). A per-IP rate-limit middleware sits inner to CORS; see [docs/SECURITY.md](docs/SECURITY.md#rate-limiting).
- **API -> B2** — authenticated via application keys, signature v4
- **Client -> B2** — presigned URLs for download (10-min expiry, forced attachment)

## Data Flows

- **Auth**: Browser -> Supabase (sign up/in) -> confirm via `/auth/confirm` -> cookie session; `proxy.ts` refreshes it per request and redirects unauthenticated users to `/signin`. API calls carry the token; the API validates it against Supabase (`repo/supabase_auth.py`).
- **Billing**: Browser -> `POST /billing/checkout` -> Stripe Checkout (redirect) -> Stripe -> `POST /billing/webhook` (signature-verified) -> `service/billing.py` upserts the subscription into Supabase (service role). `require_plan(min_tier)` reads the derived entitlements and 402s below the required tier.
- **Upload**: Browser -> `POST /upload` (multipart) -> API validates -> service orchestrates -> repo writes to B2 -> metadata extracted -> response
- **List**: Browser -> `GET /files` -> service calls repo -> returns file list
- **Download**: Browser -> `GET /files/{key}/download` -> service validates key -> repo generates presigned URL -> browser downloads
- **Delete**: Browser -> `DELETE /files/{key}` -> service validates key -> repo deletes from B2

## Observability

- Structured JSON logging on all requests with `request_id`
- Request timing middleware (logs duration per request; also the catch-all that converts uncaught exceptions to a typed JSON 500)
- `/metrics` endpoint (Prometheus format: request count, latency, upload count)
- `/health` endpoint (B2 connectivity check)

## Canonical Files

- Layered API handler: `services/api/app/runtime/upload.py`
- Service orchestration: `services/api/app/service/upload.py`
- B2 data access (repo layer): `services/api/app/repo/b2_client.py`
- Pydantic models: `services/api/app/types/` (`files.py`, `upload.py`, `stats.py`, `formatting.py`)
- Billing (layered): `services/api/app/runtime/billing.py` → `service/billing.py` → `repo/{stripe_client,supabase_billing}.py`
- Config (pydantic-settings): `services/api/app/config/settings.py`
- Structural tests: `services/api/tests/test_structure.py`
- Frontend API client: `apps/web/src/lib/api-client.ts`
- Shared TypeScript types: `packages/shared/src/types.ts`

## Core Features

- [Authentication](docs/features/authentication.md)
- [Billing](docs/features/billing.md)
- [File Upload](docs/features/file-upload.md)
- [File Browser](docs/features/file-browser.md)
- [Dashboard](docs/features/dashboard.md)
- [Metadata Extraction](docs/features/metadata-extraction.md)

## References

- [docs/SECURITY.md](docs/SECURITY.md) — security principles and implementation
- [docs/RELIABILITY.md](docs/RELIABILITY.md) — reliability expectations
- [AGENTS.md](AGENTS.md) — architectural invariants and agent instructions
