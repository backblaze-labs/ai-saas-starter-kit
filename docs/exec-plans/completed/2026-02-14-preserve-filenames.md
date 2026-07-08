# Plan: Preserve Filenames on Upload

## Scope
- Remove UUID prefix from stored object keys to keep original filenames intact.
- Reject duplicate filenames to avoid overwriting existing objects.
- Update upload feature documentation.
- Add tests for duplicate upload rejection.

## Steps
1. Update upload service to use `uploads/{sanitized_filename}` keys.
2. Add duplicate key check and return `409` on conflict.
3. Add unit test for duplicate upload behavior.
4. Update `docs/features/file-upload.md` to reflect new key format and conflict behavior.

