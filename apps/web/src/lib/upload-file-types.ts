/**
 * Client-side allow-list for the dropzone, mirroring the backend's
 * `ALLOWED_TYPES` / `MIME_EXTENSION_MAP` in
 * `services/api/app/service/upload.py`. The server re-validates every upload —
 * this only gives instant feedback and filters the OS file picker. Keep the two
 * in sync when adding or removing a type.
 *
 * Shape matches react-dropzone's `accept`: MIME type → matching extensions.
 */
export const ACCEPTED_FILE_TYPES: Record<string, string[]> = {
  "image/jpeg": [".jpg", ".jpeg", ".jfif"],
  "image/png": [".png"],
  "image/gif": [".gif"],
  "image/webp": [".webp"],
  "application/pdf": [".pdf"],
  "text/plain": [".txt", ".text", ".log", ".md"],
  "text/csv": [".csv"],
  "application/json": [".json"],
  "application/zip": [".zip"],
  "video/mp4": [".mp4"],
  "audio/mpeg": [".mp3", ".mpeg"],
  "audio/wav": [".wav"],
};
