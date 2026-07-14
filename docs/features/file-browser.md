<!-- last_verified: 2026-07-14 -->
# Feature: File Browser

## Purpose
List, preview, download, and delete files stored in Backblaze B2.

## Used By
- UI: `/files` page, file browser component
- API: `GET /files`, `GET /files-by-key/metadata?key=...`, `GET /files-by-key/download?key=...`, `GET /files-by-key/preview?key=...`, `DELETE /files-by-key?key=...`
- Legacy API: `GET /files/{key}`, `GET /files/{key}/download`, `GET /files/{key}/preview`, `DELETE /files/{key}`

## Core Functions
- `apps/web/src/components/files/file-browser.tsx` — tree view container with loading, empty, error, refresh, preview, download, and delete flows
- `apps/web/src/components/files/file-tree-row.tsx` — recursive folder/file rows with keyboard-friendly actions and long-name handling
- `apps/web/src/components/files/file-preview.tsx` — dialog modal for file preview
- `apps/web/src/lib/file-tree.ts` — `buildFileTree()` converts flat S3 keys to folder/file hierarchy
- `apps/web/src/lib/api-client.ts` — `getFiles()`, `getFile()`, `getDownloadUrl()`, `getPreviewUrl()`, `deleteFile()`; sends object keys as query parameters so slashes and reserved route names cannot be decoded into path segments
- `services/api/app/runtime/files.py` — HTTP handlers for list, get, download, delete
- `services/api/app/service/files.py` — business logic, key validation
- `services/api/app/repo/b2_client.py` — `list_files()`, `get_file_metadata()`, `get_presigned_url()`, `delete_file()`

## Canonical Files
- File route handlers: `services/api/app/runtime/files.py`
- File tree builder: `apps/web/src/lib/file-tree.ts`
- B2 data access pattern: `services/api/app/repo/b2_client.py`

## Inputs
- prefix: string (optional filter for file listing)
- limit: int (max files to return, 1-1000, default 100)
- key: string (file key for get/download/delete — sent as a query parameter by the web client; no path traversal)

## Outputs
- `GET /files` → `FileMetadata[]` (sorted most recent first)
- `GET /files-by-key/metadata?key=...` → `FileMetadata`
- `GET /files-by-key/download?key=...` → `{ url: string }` (presigned URL, attachment disposition, 10-min expiry). Increments the `total_downloads` counter exposed on `/files/stats`. The counter is persisted to `services/api/data/download_count.json` (override via `DOWNLOAD_COUNT_FILE` env var) so it survives API restarts.
- `GET /files-by-key/preview?key=...` → `{ url: string }` (presigned URL for inline rendering, 10-min expiry). Does **not** increment the download counter — used by the preview modal for images / PDFs.
- `DELETE /files-by-key?key=...` → `{ deleted: true, key: string }`
- Legacy `/files/{key}` routes remain available for compatibility. The web client uses them only as a rolling-deploy fallback when `/files-by-key` is unavailable and the key is safe to place in a legacy path.
- Side effects: DELETE removes file from B2; `/download` increments the in-memory download counter

## Flow
- Page loads → fetches file list from `GET /files` (sorted most recent first)
- Files organized into tree view — folders expand/collapse, files shown with type-specific icons
- Top-level folders auto-expand on load
- User hovers or focuses a file row → action menu appears (preview / download / delete); touch-sized menu button remains visible on small screens
- Preview: opens dialog, fetches a preview-only presigned URL via `/files-by-key/preview?key=...` (does not count as a download) and renders image/PDF inline
- Download: fetches presigned URL via `/files-by-key/download?key=...` (attachment disposition, 10-min expiry), opens in new tab, bumps the download counter, triggers a stats refresh
- Delete: calls `DELETE /files-by-key?key=...`, removes row from tree, shows toast
- All key-based API calls send the key in the query string and validate it against path-traversal patterns in the API service layer
- During frontend/API version skew, the web client falls back to legacy path routes only for keys that cannot collide with reserved file routes such as stats, download, or preview.

## Edge Cases
- File not found (deleted externally) → API returns 404
- Invalid file key (traversal attempt, empty key) → API returns 400
- File key contains `/`, spaces, `#`, `?`, `%`, reserved route names, or suffixes like `/download` and `/preview` → web client sends the key as a query parameter before calling get/download/preview/delete routes
- B2 unreachable → persistent error state with retry
- Empty bucket → upload prompt with direct Upload action
- Delete failure → API returns 500, toast error

## UX States
- Empty: centered message with upload prompt and Upload action
- Loading: skeleton rows
- Error: inline error state with Retry
- Loaded: tree view with expand/collapse folders and focus/hover action menus
- Preview: responsive dialog with wrapped file names, fallback copy for preview URL failures, and metadata that tolerates long keys

## Verification
- Test files: `services/api/tests/test_file_key_routes.py`, `apps/web/src/lib/api-client.test.ts`
- Required cases: list files, empty list, file not found, presigned URL generation, delete success, delete failure
- Quick verify command: `pnpm test:api`
- Client route-construction tests: `pnpm --filter @ai-media-saas-starter/web test`
- Full verify command: `pnpm lint && pnpm --filter @ai-media-saas-starter/web test && pnpm build && pnpm lint:api && pnpm test:api && pnpm check:structure`
- Pass criteria: all pytest tests green, no ruff violations

## Related Docs
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [App Workflows](../app-workflows.md)
