<!-- last_verified: 2026-07-16 -->
# Tech Debt Tracker

Known tech debt items. Agents update this when they discover or create tech debt.

## 2026-07-16 — verify

Nitpicks surfaced by the verify pass on the file surface (logged, not blocking; the auth/ownership blocker and the preview-spinner friction were fixed in the same change):

- **A1** — Signup screen copy tells the user to "then sign in" even though the flow may hand them straight into a session; reconcile the wording with the actual post-signup behavior.
- **A3** — Dashboard renders a Free-plan "Inactive" badge that reads like an error state rather than simply "no paid subscription"; soften the label/variant.
- **A4** — "Design System" link lives in the primary product nav; consider moving it to a utility/footer slot so the main nav is product-only.
- **B-delete** — File delete has no optimistic removal; the row only disappears after the round-trip completes.
- **C3** — Generated object keys carry a redundant date segment (`generated/{user_id}/{date}/runs/{date}/…`); purely cosmetic — collapse the duplicate date.

## Open

| Description | Impact | Proposed Resolution | Priority |
|---|---|---|---|
| Download counter & `/metrics` not durable across restart/replicas | Counter resets on redeploy (ephemeral FS); both fragment across replicas | Back the counter with a shared store (Redis/DB); label/aggregate metrics per instance. Now isolated in `repo/counter.py` and documented in RELIABILITY.md | Medium |
| `get_upload_activity` re-materializes `FileMetadata` for every object just to bucket dates | Wasted O(n) CPU per `/files/stats/activity` (scan is cached; materialization is not) | Aggregate from raw listing dicts like `get_upload_stats` does | Low |
| Upload signature check is a second B2 round-trip (Range GET at `/upload/complete`) | One extra request per upload; a client that PUTs then never calls `/upload/complete` leaves an unconfirmed, unvalidated object in the bucket until it's overwritten or the bucket TTL/cleanup removes it | Accept it (cost is small and objects are per-user scoped), or add a periodic sweep of stale unconfirmed `uploads/{uid}/` objects | Low |
| Frontend has only pure-logic unit tests; no component/render tests, and e2e only checks routing | UI states (loading/error/empty) and the real upload→delete journey are unverified | Add jsdom + @testing-library/react render tests; a fixture-driven upload e2e | Medium |
| Allowed file types hardcoded in `service/upload.py` | Reuse friction — each new app edits source to change accepted types | Make `ALLOWED_TYPES` / `MIME_EXTENSION_MAP` env-configurable | Low |
| No `docker-compose.yaml` | Manual venv + dual-process startup slows first run | Add compose with `web` + `api` services and Dockerfiles | Low |
| `api-client.ts` hand-synced to FastAPI | Endpoint drift between client and server | Note an OpenAPI codegen strategy or link the spec | Low |
| No dedicated connection-status banner | Offline only surfaced reactively per failed query | Add a global connectivity banner (route + global error boundaries already exist) | Low |
| Settings page is a non-persisting preview & Danger Zone "Empty bucket" is disabled | Users can't save preferences or empty the bucket from the UI — both are marked "preview"/"not available in this starter" (no misleading fake-success) rather than wired | Persist preferences (a `settings` table or `profiles` columns) + implement a prefix-scoped bucket-empty behind a typed confirm | Low |

## Resolved

| Description | Resolution |
|---|---|
| Upload buffered the whole file in memory (~3× file size RAM per upload) | Uploads now go browser→B2 directly via a presigned PUT; the API never holds the bytes |
| Rich file metadata (checksums, EXIF, PDF info) extracted at upload but never persisted or surfaced (dead `FileMetadataPanel`, `service/metadata.py`) | Removed — direct-to-B2 upload means the API never sees the bytes, so server-side extraction isn't possible; the browser shows basic metadata (size, type, key, date). Would return only as post-upload async processing if ever needed |
| Blocking boto3 in `async def` handlers froze the single event loop | B2 handlers are sync `def` (Starlette threadpool); upload offloads via `run_in_threadpool` |
| Full-bucket scan on every list/stats/activity request, uncached | Short-TTL single-flight cache in `repo/b2_listing.list_all_objects`, invalidated on upload/delete |
| No CI — quality gates ran only when a human remembered | `.github/workflows/ci.yml` runs web + API gates on PR and push to `main` |
| SVG stored-XSS; declared MIME trusted; unused `python-magic` dep | Dropped SVG from allow-list; added magic-byte signature check; removed dead `python-magic` |
| No rate limiting → DoS + B2 cost amplification | Per-IP fixed-window limiter (`runtime/ratelimit.py`), read/write budgets |
| Counter persistence lived in the service layer (layering violation) | Moved file I/O to `repo/counter.py` behind `get/increment_download_count` |
| CORS `allow_credentials=True` was unnecessary for this app's bearer-token auth | Default `allow_credentials=False` — the API is authenticated by a Supabase bearer token in the `Authorization` header, not a cross-origin cookie; empty origins filtered |
| No security headers on API responses | `X-Content-Type-Options: nosniff` + `Referrer-Policy: no-referrer` on every response |
| Key-addressed ops could target any bucket object | Opt-in `ALLOWED_KEY_PREFIX` confinement (off by default; note this app writes under both `uploads/` and `generated/`) |
| File endpoints had no auth and no per-user isolation — anyone (even anonymous) could list/preview/download/delete any object, and a signed-in user saw every tenant's `uploads/`/`generated/` keys | Every file + upload route now requires a Supabase bearer token (`401` otherwise); reads/listings/stats are scoped to the caller's `uploads/{user_id}/` + `generated/{user_id}/` prefixes; uploads are keyed under `uploads/{user_id}/`; key-addressed ops `404` for keys the caller doesn't own (no existence leak) |
| Redundant triple-scan + double sort per dashboard mount | TTL cache + single-flight collapse the concurrent empty-prefix scans; dropped the repo-layer sort so `get_files` owns newest-first ordering once |
| Unguarded `int(content-length)`; always-on `/docs`; uncached `/health` B2 call | Content-Length parse guarded; `ENABLE_DOCS` toggle (documented in SECURITY.md); connectivity cached ~5s |
| Upload validation sad-paths (413/415) + sanitizer untested | `tests/test_upload_validation.py` covers the rejection matrix, signature check, `uploads_total` |
| `get_upload_stats()` / `list_files()` object listing capped at 1000 | Shared `_list_all_objects()` paginator follows `ContinuationToken` |
| `datetime.utcnow()` deprecated in Python 3.12+ | Replaced with `datetime.now(UTC)` in `repo/b2_client.py`, `service/metadata.py` |
| S3 client recreated on every API call | Cached module-level singleton via `lru_cache` |
| `record_upload()` never called | Called from `runtime/upload.py` after successful upload |
| Metrics counters not thread-safe | Guarded by `threading.Lock` |
| `_humanize_bytes` duplicated in Python (repo + service) | Extracted to `app/types/formatting.py` shared util |
| `humanizeBytes` / `formatDate` duplicated in TypeScript | Extracted to `lib/utils.ts` (tested) |
| No test harness for feature specs | pytest suite across upload, files, activity, errors, validation, rate limit, pagination |
| No auth layer or placeholder (upstream starter had none) | N/A here — this app ships Supabase bearer-token auth + Row Level Security; see docs/SECURITY.md |
| `NEXT_PUBLIC_API_URL` missing from `.env.example` | Already present in `.env.example` with guidance |
