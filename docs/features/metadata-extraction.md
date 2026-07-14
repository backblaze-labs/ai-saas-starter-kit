<!-- last_verified: 2026-07-14 -->
# Feature: Metadata Extraction

## Purpose
Extract rich metadata from uploaded files and return it in the `POST /upload` response.

## Scope
Rich metadata is computed at upload time and returned in the `POST /upload` response, but it is **not persisted**. The file-browser endpoints (`GET /files-by-key/metadata`) therefore return **basic** metadata only (size, type, key, upload date), and the browser preview shows those basic fields. Persisting the rich metadata so the browser can surface it is tracked in [tech-debt-tracker.md](../exec-plans/tech-debt-tracker.md).

## Used By
- API: `POST /upload` (called after B2 upload; the rich metadata is returned in the upload response)

## Core Functions
- `services/api/app/service/metadata.py` — `extract_metadata()`, `_extract_image_metadata()`, `_extract_pdf_metadata()`

## Canonical Files
- Metadata extraction pattern: `services/api/app/service/metadata.py`

## Inputs
- file_data: bytes
- filename: string
- content_type: string

## Outputs
- `FileMetadataDetail`: filename, size_bytes, size_human, mime_type, extension, md5, sha256, uploaded_at
- Image-specific (optional): image_width, image_height, exif dict
- PDF-specific (optional): pdf_pages, pdf_author, pdf_title
- Audio/Video (optional): duration_seconds, codec, bitrate

## Flow
- Upload route receives file and stores in B2
- `extract_metadata()` called with file bytes, filename, content type
- Computes MD5 and SHA-256 hashes
- If image: opens with Pillow, extracts dimensions and EXIF data
- If PDF: opens with PyPDF2, extracts page count, author, title
- Returns `FileMetadataDetail` model in the `POST /upload` response

## Edge Cases
- Corrupt image → Pillow fails silently, image fields remain null
- Corrupt PDF → PyPDF2 fails silently, PDF fields remain null
- Unknown content type → only common fields populated (hashes, size, extension)
- EXIF contains binary data → decoded as UTF-8 with replace, converted to string
- Large file → hashing may be slow (computed in-memory)

## UX States
- Not applicable. The rich metadata is part of the `POST /upload` response; the file-browser preview surfaces basic fields only (size, type, key, upload date) — see Scope.

## Verification
- Test files: `services/api/tests/` (no dedicated metadata tests yet)
- Required cases: image with EXIF, image without EXIF, PDF with metadata, PDF without metadata, unknown file type, corrupt file handling
- Quick verify command: `pnpm test:api`
- Full verify command: `pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure`
- Pass criteria: all pytest tests green, no ruff violations

## Related Docs
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [File Upload](file-upload.md)
