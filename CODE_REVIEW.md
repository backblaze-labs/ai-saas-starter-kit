# Code Review: AI Media SaaS Starter

**Reviewer:** Claude | **Date:** 2026-02-26

---

## Overall Impression

This is a well-architected starter kit with strong fundamentals — strict backend layering, mechanical enforcement via structural tests, clean separation of concerns, and solid documentation. The agent-first design philosophy is evident and well-executed. That said, the review below identifies several bugs, performance issues, and opportunities that would make this a more robust and polished foundation for someone building on top of it.

---

## Bugs

### 1. `datetime.utcnow()` is deprecated (High)

**Files:** `services/api/app/repo/b2_client.py` (lines 78, 172), `services/api/app/service/metadata.py` (line 83)

`datetime.utcnow()` has been deprecated since Python 3.12 and returns a naive datetime. The codebase already imports `UTC` correctly in `main.py` but doesn't use it consistently elsewhere.

```python
# Current (deprecated, naive datetime)
uploaded_at=datetime.utcnow()

# Fix
from datetime import UTC, datetime
uploaded_at=datetime.now(UTC)
```

### 2. S3 client recreated on every single API call (High)

**File:** `services/api/app/repo/b2_client.py` — `get_s3_client()`

Every function (`upload_file`, `list_files`, `get_file_metadata`, `delete_file`, `get_presigned_url`, `get_upload_stats`, `check_connectivity`) calls `get_s3_client()`, which creates a brand-new `boto3.client()` each time. Boto3 clients maintain HTTP connection pools internally, so recreating them on every request throws away connection reuse and adds significant latency.

```python
# Fix: cache the client as a module-level singleton
import functools

@functools.lru_cache(maxsize=1)
def get_s3_client():
    return boto3.client(...)
```

### 3. `get_upload_stats()` pagination is broken (High)

**File:** `services/api/app/repo/b2_client.py` (lines 165-181)

`MaxKeys=10000` is passed to `list_objects_v2`, but the S3 API hard caps at 1000 objects per response. The code never checks `IsTruncated` or uses `ContinuationToken`. For any bucket with more than 1000 objects, stats will be silently wrong — it'll only count the first 1000.

The same issue exists in `list_files()` (line 83) though the caller currently caps at 1000 anyway.

### 4. `record_upload()` is never called (Medium)

**File:** `services/api/app/runtime/metrics.py` (line 21)

The `record_upload()` function is defined but never invoked from `runtime/upload.py` or anywhere else. The `/metrics` endpoint will always report `uploads_total 0` and `upload_errors_total 0`.

### 5. Metrics counters are not thread-safe (Medium)

**File:** `services/api/app/runtime/metrics.py` (lines 9-11, 15-18)

`_request_count[key] += 1` and `_request_duration_sum[key] += duration` are not atomic operations. Under concurrent requests, these will have race conditions. Contrast with `service/files.py` which correctly uses a `threading.Lock` for `_download_count`.

### 6. Metrics key parsing is fragile (Medium)

**File:** `services/api/app/runtime/metrics.py` (lines 34-37)

The key format is `{method}_{path}_{status}`, but `rsplit("_", 1)` only splits on the last underscore. Paths with underscores (like `/files/uploads/my_file.jpg`) will cause the method+path to be misparsed. The status code will be `jpg` and the path will be wrong.

```python
# Current (breaks on paths with underscores)
key = f'{method}_{path}_{status}'
parts = key.rsplit("_", 1)

# Fix: use a proper separator or structured storage
key = f'{method}|{path}|{status}'
```

### 7. `FileNotFoundError` shadows Python built-in (Medium)

**File:** `services/api/app/service/files.py` (line 38)

`class FileNotFoundError` shadows Python's built-in `FileNotFoundError` (which is a subclass of `OSError`). Any code in this module that intends to catch the built-in will catch this custom one instead (or vice versa). Rename to `FileNotFoundServiceError` or similar.

### 8. No early termination during upload streaming (Medium)

**File:** `services/api/app/runtime/upload.py` (lines 20-28)

The chunked read loop accumulates all data before validation. A malicious client could send a multi-GB file and the server would read the entire body into memory before eventually rejecting it in `process_upload`. Add a size check inside the loop:

```python
while True:
    chunk = await file.read(1024 * 1024)
    if not chunk:
        break
    total += len(chunk)
    if total > settings.max_file_size:
        raise HTTPException(status_code=413, detail="File too large")
    chunks.append(chunk)
```

### 9. Upload chart date ordering is unreliable (Low)

**File:** `apps/web/src/components/dashboard/upload-chart.tsx` (lines 28-40)

`aggregateByDay` converts dates to locale strings like "Feb 26", aggregates counts, then calls `.slice(-7)`. But `Object.entries()` returns keys in insertion order (which is by file order — newest first from the API). The chart may show dates in reverse chronological order or jumbled, depending on upload patterns.

### 10. Preview increments download counter (Low)

**File:** `apps/web/src/components/files/file-preview.tsx` (line 30)

`FilePreview` calls `getDownloadUrl()` which hits `/files/{key}/download`, which calls `_record_download()`. Previewing a file shouldn't count as a download. Consider a separate endpoint or query param (`?preview=true`) that generates a presigned URL without incrementing the counter.

### 11. No delete confirmation dialog (Low)

**File:** `apps/web/src/components/files/file-browser.tsx` (lines 222-230)

`handleDelete` immediately deletes the file with no confirmation. This is a destructive action that should prompt the user first.

---

## DRY Violations

### 12. `_humanize_bytes` is duplicated in Python (AGENTS.md §3 violation)

Identical implementations exist in `repo/b2_client.py` and `service/metadata.py`. Additionally, `service/upload.py` imports it from `b2_client` directly (crossing the layer boundary via an internal function). Extract it to `app/types/` or a shared utils module within the `types` layer.

### 13. `humanizeBytes` is duplicated in TypeScript

Identical implementations in `upload-form.tsx` and `upload-progress.tsx`. Extract to `lib/utils.ts`.

### 14. `formatDate` is duplicated in TypeScript

Same function in `file-browser.tsx` and `recent-uploads-table.tsx`. Extract to `lib/utils.ts`.

---

## Performance Optimizations

### 15. Entire file buffered in memory for upload

**Files:** `runtime/upload.py`, `service/upload.py`, `repo/b2_client.py`

The current flow reads the entire file into `bytes`, passes it to `process_upload`, computes hashes, extracts metadata, then uploads to B2 via `put_object`. For a 100MB file, this uses ~300MB+ of RAM (chunks list + joined bytes + re-wrapped in BytesIO). Consider streaming to a temp file, or using S3 multipart upload for files above a threshold.

### 16. Dashboard makes 3 independent API calls

`StatsCards`, `UploadChart`, and `RecentUploadsTable` each independently fetch from the API on mount. Consider adding a data-fetching layer (SWR or React Query) to deduplicate requests, add caching, and enable stale-while-revalidate patterns. This would also benefit the Files page.

### 17. File keys not URL-encoded in API client

**File:** `apps/web/src/lib/api-client.ts` (lines 33, 37)

`getFile(key)` and `getDownloadUrl(key)` interpolate the key directly into the URL path: `` `/files/${key}` ``. Keys containing special characters (spaces, `#`, `?`) will break the request. Use `encodeURIComponent` on each path segment, or encode the full key.

### 18. Dropzone doesn't filter by allowed MIME types

**File:** `apps/web/src/components/upload/dropzone.tsx`

The dropzone has `maxSize` but no `accept` filter. Users can drag any file type and it'll only fail after uploading to the server. Adding an `accept` prop matching the backend's `ALLOWED_TYPES` would provide instant client-side feedback and save bandwidth.

---

## Starter Kit Usability Recommendations

These are suggestions for making the kit easier for someone to pick up and customize as a base for their own app.

### 19. Add authentication middleware placeholder

The kit has no auth layer at all. For a starter kit, even a placeholder middleware with a `TODO` comment and an example (API key header check or JWT validation) would save someone significant time understanding where to add it. The CORS config is there but auth is the first thing anyone will need to add.

### 20. Make allowed file types configurable via environment

`ALLOWED_TYPES` and `MIME_EXTENSION_MAP` in `service/upload.py` are hardcoded. Making these configurable (or at least documenting that they should be customized) would save time for someone building a different kind of app (e.g., documents only, images only).

### 21. Add a `docker-compose.yaml`

The kit requires manually starting both the frontend and backend, plus a Python venv setup. A `docker-compose.yaml` with `web` and `api` services would let someone clone and `docker compose up` in under a minute. This is especially valuable for a starter kit.

### 22. Mention the auto-generated API docs

FastAPI auto-generates OpenAPI docs at `/docs` (Swagger UI) and `/redoc`. These aren't mentioned in the README or AGENTS.md. For a starter kit, highlighting these is a huge usability win — it's free interactive API documentation.

### 23. Add an `api-client` generation strategy or note

The TypeScript `api-client.ts` is manually written to match the FastAPI endpoints. If someone adds a new endpoint, they have to update both sides manually. A note about using OpenAPI codegen (or even just a comment pointing to the Swagger spec) would help maintain sync.

### 24. Add a `.env.example` entry for `NEXT_PUBLIC_API_URL`

The frontend's `api-client.ts` defaults to `http://localhost:8000`, but in production the API URL needs to be set via `NEXT_PUBLIC_API_URL`. This variable isn't in `.env.example`, which only covers backend vars. Someone deploying will have to dig through the source to find it.

### 25. Add error boundary / loading states at the page level

The individual components handle their own loading/error states, but there's no top-level error boundary. If the API is completely down, each card and table shows its own error independently. A page-level error boundary or a connection status banner would be cleaner.

---

## Summary Table

| # | Severity | Category | Issue |
|---|----------|----------|-------|
| 1 | High | Bug | `datetime.utcnow()` deprecated |
| 2 | High | Perf | S3 client recreated per call |
| 3 | High | Bug | Stats pagination broken at 1000 objects |
| 4 | Medium | Bug | `record_upload()` never called |
| 5 | Medium | Bug | Metrics counters not thread-safe |
| 6 | Medium | Bug | Metrics key parsing breaks on underscores |
| 7 | Medium | Bug | `FileNotFoundError` shadows built-in |
| 8 | Medium | Security | No upload size check during streaming |
| 9 | Low | Bug | Chart date ordering unreliable |
| 10 | Low | Bug | Preview counts as download |
| 11 | Low | UX | No delete confirmation |
| 12 | Medium | DRY | `_humanize_bytes` duplicated (Python) |
| 13 | Low | DRY | `humanizeBytes` duplicated (TS) |
| 14 | Low | DRY | `formatDate` duplicated (TS) |
| 15 | Medium | Perf | Full file buffered in memory |
| 16 | Low | Perf | Dashboard triple-fetches |
| 17 | Medium | Bug | File keys not URL-encoded |
| 18 | Low | UX | Dropzone has no MIME filter |
| 19 | — | Starter Kit | Add auth placeholder |
| 20 | — | Starter Kit | Configurable allowed types |
| 21 | — | Starter Kit | Add docker-compose |
| 22 | — | Starter Kit | Document /docs endpoint |
| 23 | — | Starter Kit | API client sync strategy |
| 24 | — | Starter Kit | Add NEXT_PUBLIC_API_URL to .env.example |
| 25 | — | Starter Kit | Page-level error boundary |

---

## What's Already Done Well

To be clear, this codebase has a lot of things going for it that most starter kits don't:

- **Strict layered architecture** with mechanical enforcement via tests — this is rare and valuable.
- **AGENTS.md as single source of truth** — concise, well-structured, easy to onboard with.
- **Pydantic at all boundaries** — type safety end-to-end.
- **Shared TypeScript types** mirroring backend models — good monorepo hygiene.
- **Structured JSON logging** from day one — production-ready observability.
- **Security-conscious design** — presigned URLs, filename sanitization, path traversal protection, CORS scoping.
- **File size limits enforced by test** — keeps the codebase agent-friendly.
- **Pre-commit hooks** — catches issues before they land.

The architectural foundation is solid. The issues above are mostly implementation-level fixes that would bring the code quality up to match the architecture's ambition.
