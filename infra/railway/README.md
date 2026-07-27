# Railway Deployment

Deploy both services (web + api) on Railway.

## Setup

1. Create a new Railway project
2. Add two services from the same repo. Each service's build/start command,
   `/health` (API) or `/signin` (web) healthcheck, and restart policy are
   codified in a committed `railway.json` at that service's root
   (`services/api/railway.json`, `apps/web/railway.json`) so the deploy is
   reproducible rather than hand-configured in the dashboard.

### Web Service (Next.js)
- **Root Directory**: `apps/web`
- **Build Command**: `pnpm install --frozen-lockfile && pnpm build` (frozen so a
  deploy resolves the exact locked versions CI tested)
- **Start Command**: `pnpm start`
- **Port**: `3000`

### API Service (FastAPI)
- **Root Directory**: `services/api`
- **Build Command**: `pip install -r requirements.txt` (versions are exact-pinned
  in `requirements.txt` for reproducibility)
- **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Healthcheck**: `/health`

## Environment Variables

Set these on the API service:

| Variable | Value |
|----------|-------|
| `B2_APPLICATION_KEY_ID` | Your B2 key ID |
| `B2_APPLICATION_KEY` | Your B2 application key |
| `B2_BUCKET_NAME` | Your bucket name |
| `B2_REGION` | Your bucket's region (e.g. `us-west-004`) — the S3 endpoint is derived from it |
| `B2_PUBLIC_URL_BASE` | Public URL base for the bucket (e.g. `https://<bucket>.s3.<region>.backblazeb2.com`) |
| `API_CORS_ORIGINS` | Your web service URL (e.g., `https://web-production-xxx.up.railway.app`) |

Billing + auth also require (see `.env.example` for the full list):
`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, and the
`STRIPE_*` keys/price IDs.

### Production hardening (recommended)

| Variable | Value |
|----------|-------|
| `ENABLE_DOCS` | Leave unset/`false` in production — hides `/docs`, `/redoc`, `/openapi.json` (defaults off) |
| `METRICS_TOKEN` | Set a random token so `/metrics` isn't world-readable; the scraper sends `Authorization: Bearer <token>` |
| `TRUST_PROXY` | Set to `true` — Railway terminates TLS at its edge proxy, so the real client IP arrives in `X-Forwarded-For`. Left unset, the rate limiter keys on Railway's proxy socket peer, collapsing every client into one shared bucket (one busy user throttles everyone). Only enable behind a trusted proxy that appends `X-Forwarded-For`. |

After the first deploy, grant yourself admin explicitly (the first signup is **not**
auto-promoted): `update public.profiles set role='admin' where email='you@…';`

Set this on the Web service:

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_API_URL` | Your API service URL (e.g., `https://api-production-xxx.up.railway.app`) |
