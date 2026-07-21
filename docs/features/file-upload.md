<!-- last_verified: 2026-07-17 -->
# Feature: File Upload

## Purpose
Upload files from the browser **straight to Backblaze B2** with real-time
progress tracking. The bytes never transit the API — only small JSON control
requests do — so uploads are not bounded by a serverless request-body cap
(Vercel's hard 4.5 MB limit) and the API stays cheap and stateless.

## Used By
- UI: `/upload` page, upload form component
- API: `POST /upload/presign`, `POST /upload/complete`

## Core Functions
- `apps/web/src/components/upload/upload-form.tsx` — orchestrates dropzone + progress + upload state
- `apps/web/src/components/upload/dropzone.tsx` — drag-and-drop via `react-dropzone`
- `apps/web/src/components/upload/upload-progress.tsx` — per-file progress, errors, and retry controls
- `apps/web/src/lib/api-client.ts` — `uploadFile()`: presign → XHR `PUT` to B2 (progress) → complete
- `services/api/app/runtime/upload.py` — the presign + complete HTTP handlers
- `services/api/app/service/upload.py` — `prepare_upload()` (validate + sign) and `finalize_upload()` (confirm)
- `services/api/app/repo/b2_client.py` — `get_presigned_upload_url()` (PUT), `get_object_head_bytes()` (signature re-check)

## Canonical Files
- Upload handler pattern: `services/api/app/runtime/upload.py`
- Service orchestration pattern: `services/api/app/service/upload.py`
- Frontend upload flow: `apps/web/src/components/upload/upload-form.tsx`

## Inputs
- Step 1 (`/upload/presign`): `filename`, `content_type`, `size_bytes` — the intent, no bytes
- Step 2 (browser → B2): the raw `File` bytes, PUT to the presigned URL
- Step 3 (`/upload/complete`): the object `key` returned by step 1

## Outputs
- `PresignedUpload`: `upload_url`, `key`, `method`, `headers` (the signed `Content-Type`)
- `FileUploadResponse`: key, filename, size, content_type, uploaded_at, url
- Side effects: file stored in B2 under `uploads/{user_id}/{sanitized_filename}`

## Flow
- User drops or selects files in the dropzone
- Client validates file size (max 100MB) and type — rejected files stay in the queue with a clear reason and toast feedback
- Client `POST`s the intent to `/upload/presign`
- API validates what it can without the bytes: filename present, declared size (`>0`, `<= 100MB`), content type against the allowlist (SVG excluded — stored-XSS risk), extension matches the declared MIME type
- API sanitizes the filename (strips path components, null bytes, unsafe chars, limits to 200 chars) and builds the key `uploads/{user_id}/{sanitized_filename}`
- API returns a presigned PUT URL **bound to that key and Content-Type** (a 15-minute HMAC — no network call)
- Client `PUT`s the bytes **directly to B2** using the presigned URL, replaying only the signed `Content-Type` header (XHR reports upload progress)
- Client `POST`s the key to `/upload/complete`
- API re-establishes the guarantees the sign step couldn't: ownership (key under the caller's `uploads/` prefix), existence (404 if the PUT never landed), true stored size vs. the limit, and a magic-byte signature re-check via a Range GET of the object header — a payload whose bytes don't match its declared type is **deleted** and rejected
- API returns `FileUploadResponse`
- Client shows a toast, updates progress state, and refreshes shared data after successful uploads

## Edge Cases
- File exceeds 100MB → client-side rejected row + toast; presign returns 413 (declared) and complete returns 413 (true stored size) if bypassed
- File type not in allowlist → presign returns 415
- File extension mismatches MIME type → presign returns 415
- File contents don't match the declared type (e.g. script bytes stored as `image/png`) → complete Range-GETs the header, returns 415, and deletes the bad object
- No filename provided → presign returns 400
- Empty file (declared size 0, or 0 bytes stored) → 400
- Key not under the caller's own `uploads/` prefix → complete returns 403 (before any B2 call)
- Object missing at complete (PUT failed / never happened) → 404
- Duplicate filename → B2 creates a new version (buckets are always versioned)
- Browser PUT blocked by CORS → the bucket needs a CORS rule for the frontend origin (see "Bucket CORS" below)
- B2 unreachable → API returns 500; UI keeps failed rows retryable
- Upload aborted by user → XHR abort, error state in UI

## Bucket CORS
The browser's direct PUT is cross-origin, so the B2 bucket must allow the
frontend origin (methods `GET`/`PUT`/`HEAD`, header `Content-Type`). Apply it
with `scripts/configure_b2_cors.py` (see `docs/deployment.md`). Server-side S3
calls are unaffected, so local dev that uploads only via a same-origin proxy may
not hit this — but any real browser→B2 upload does.

## UX States
- Empty: dropzone with instructions
- Loading: per-file progress bars with spinner icon (progress tracks the direct-to-B2 PUT)
- Error: red status icon, error message per file, retry action when applicable
- Complete: green checkmark, "Clear finished" button
- Rejected: persistent row with non-retryable reason
- Disabled: dropzone explains that new files can be added when the current queue finishes

## Verification
- Test files: `services/api/tests/test_upload_validation.py`, `services/api/tests/test_upload_conflict.py`, `services/api/tests/test_error_handling.py`
- Required cases: presign happy path (scoped, type-bound URL), presign rejections (400/413/415), finalize happy path, finalize ownership (403), traversal key, missing object (404), signature mismatch deletes + 415, oversized stored file deletes + 413, both routes require auth (401), `uploads_total` metric increments on complete
- Quick verify command: `pnpm test:api`
- Full verify command: `pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure`
- Pass criteria: all pytest tests green, no ruff violations

## Related Docs
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [Deployment](../deployment.md)
- [App Workflows](../app-workflows.md)
