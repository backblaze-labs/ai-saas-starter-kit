<!-- last_verified: 2026-07-08 -->
# Feature: AI Media Generation (Genblaze + NVIDIA NIM)

## Purpose
The app's marquee workflow: turn a text prompt into an image via NVIDIA NIM
(`flux.1-schnell`), orchestrated by the Genblaze SDK and written — with a
SHA-256 provenance manifest — to Backblaze B2. It is gated behind a paid plan
and its outputs also appear in the B2-backed file manager.

## Used By
- UI: `/generate` (prompt form + live loader + result grid + recent generations).
- API: `POST /generation/generate` (Pro-gated), `GET /generation/jobs`.
- Dependency: reuses `require_plan("pro")` from the billing slice.

## Core Functions
- `services/api/app/repo/generation_pipeline.py` — the ONLY module importing
  `genblaze_*`. Builds a `Pipeline` → `NvidiaImageProvider` → `ObjectStorageSink`
  (B2, HIERARCHICAL) and returns a plain dict (no SDK types leak upward).
- `services/api/app/repo/supabase_generation.py` — PostgREST reads/writes
  (service role) for the job/files/provider-run/usage tables.
- `services/api/app/service/generation.py` — runs the (blocking) pipeline in a
  threadpool, then persists the job + files + provider run + usage event.
- `apps/web/src/app/(app)/generate/page.tsx` + `lib/queries.ts` (`useGenerate`,
  `useGenerationJobs`).

## Canonical Files
- Backend flow: `runtime/generation.py` (thin) → `service/generation.py` →
  `repo/{generation_pipeline,supabase_generation}.py`
- DB + RLS + grants: `supabase/migrations/20260708210000_generation_files_jobs.sql`
- Genblaze exemplar: `repo/generation_pipeline.py::generate_image`

## Inputs
- `prompt` (1–2000 chars) and optional `seed` (POST body from the Generate UI).
- `Authorization: Bearer <token>` on every endpoint.
- Config: `NVIDIA_API_KEY` (required to generate), `NVIDIA_IMAGE_MODEL`,
  `GENERATION_WIDTH/HEIGHT/STEPS`, `GENERATION_PREFIX`.

## Outputs
- Image object(s) + a `manifest.json` written to B2 under
  `generated/{user_id}/{date}/{run_id}/…` (Genblaze `ObjectStorageSink`).
- `public.generation_jobs` row (status/model/run_id/manifest_uri/canonical_hash).
- `public.files` rows (one per generated asset: b2_key + provenance).
- `public.provider_runs` + `public.usage_events` rows.
- The `GenerationJob` returned to the client (with its assets).

## Flow
- Client POSTs a prompt → `require_plan("pro")` gate (402 for Free).
- Service inserts a `running` job, runs the Genblaze/NVIDIA pipeline in a
  threadpool. NVIDIA returns the image inline (base64); the sink transfers it +
  a manifest to B2.
- Service marks the job `succeeded`, mirrors each asset into `public.files`,
  records the provider run + a usage event, and returns the job.
- The UI renders each asset via a short-lived presigned preview URL (by B2 key)
  — the same path the file manager uses, so it works with or without
  `B2_PUBLIC_URL_BASE`.

## Edge Cases
- No `NVIDIA_API_KEY` → `503` (clean "not configured"); the rest of the app runs.
- Free tier → `402` (locked card links to `/billing`).
- Provider failure / no asset → job persisted as `failed`, endpoint `502`.
- Private bucket (no public URL base) → assets still render (presigned preview).

## UX States (if applicable)
- Empty: "No generations yet…" prompt.
- Loading: `GeneratingLoader` while the model runs + uploads.
- Locked: Pro-upgrade card for Free users.
- Error: toast (config 503 / gate 402 / failure).

## Verification
- Test files: `services/api/tests/test_generation.py`,
  `services/api/tests/test_structure.py::test_genblaze_only_in_repo`,
  `apps/web/e2e/generate.spec.ts`.
- Required cases: 402 (Free), 503 (no key), happy path persists
  job+files+usage, failed-run → 502, list jobs, genblaze-only-in-repo,
  no-network SDK signature guard.
- Quick verify command: `pnpm test:api && pnpm check:structure`
- Full verify command: `pnpm lint && pnpm build && pnpm test:api && pnpm test:e2e`
  (the live e2e generation test needs `NVIDIA_API_KEY` + Stripe/Supabase config;
  it skips cleanly otherwise).
- Pass criteria: all listed tests green; a prompt on `/generate` (Pro) yields an
  image under `generated/…` in B2, visible on the page and in the file manager.

## Related Docs
- [README.md](../../README.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [docs/features/billing.md](billing.md)
- [docs/features/file-browser.md](file-browser.md)
