"""Generation business logic: run the Genblaze/NVIDIA image pipeline and persist
the job, its generated files, a provider-run row, and a usage event to Supabase.

The pipeline (repo/generation_pipeline) is a synchronous, blocking SDK call, so
it runs in a threadpool to keep the event loop free. Genblaze types never cross
this boundary — the repo returns plain dicts.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from functools import partial

from app.config import settings
from app.repo import generation_pipeline, supabase_generation
from app.types.generation import GeneratedAsset, GenerationJob

logger = logging.getLogger(__name__)

# DEDICATED thread pool for the blocking Genblaze SDK. Kept separate from
# Starlette's shared request threadpool on purpose: on a hard-deadline timeout we
# abandon the worker thread (a Python thread can't be force-killed), so a stuck
# NVIDIA endpoint leaks threads. Isolating them here means those leaks are bounded
# to `generation_max_concurrency` and can never starve the pool that serves file
# I/O and /health. Excess concurrent requests queue on this executor.
_gen_executor = ThreadPoolExecutor(
    max_workers=max(1, settings.generation_max_concurrency),
    thread_name_prefix="genblaze",
)


class GenerationConfigError(RuntimeError):
    """Raised when generation is attempted without an NVIDIA key configured."""


class GenerationError(RuntimeError):
    """Raised when the provider run produced no usable asset."""


class GenerationQuotaError(RuntimeError):
    """Raised when a user exceeds the per-day generation cap. Mapped to 429."""


# Generic, user-safe failure message. Raw provider/SDK error text can embed API
# keys or signed URLs, so it is logged server-side (logger.exception) but never
# returned to the client or written to the stored job.error (which the user can
# read back via GET /generation/jobs).
_GENERIC_FAILURE = "Image generation failed. Please try again."


async def _safe_mark_failed(job_id: str, error: str) -> None:
    """Best-effort transition a job to failed so it never lingers as 'running'.

    Swallows its own errors: if the persistence layer is unreachable there is
    nothing more to do here, and the caller is already surfacing a failure."""
    try:
        await supabase_generation.complete_job(job_id, status="failed", error=error)
    except Exception:
        logger.exception("could not mark job=%s failed", job_id)


def is_configured() -> bool:
    """True when both the provider key and the persistence layer are set."""
    return generation_pipeline.is_configured() and supabase_generation.is_configured()


async def _enforce_daily_quota(user_id: str) -> None:
    """Soft per-user daily cap on generation attempts (0 disables).

    Counts jobs created since UTC midnight *before* creating a new one, so both
    successes and failures count against a paid feature that spends real provider
    credits. This is a check-then-create soft cap (a burst can race past by a few)
    — acceptable for a starter kit; a hard cap would need a DB-side counter.
    """
    limit = settings.generation_daily_limit
    if limit <= 0:
        return
    midnight = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    used = await supabase_generation.count_jobs_since(user_id, midnight.isoformat())
    if used >= limit:
        raise GenerationQuotaError(
            f"Daily generation limit of {limit} reached. Try again tomorrow."
        )


async def generate(*, user_id: str, prompt: str, seed: int | None = None) -> GenerationJob:
    """Run one text-to-image generation and return the persisted job record."""
    if not generation_pipeline.is_configured():
        raise GenerationConfigError("NVIDIA_API_KEY is not configured")

    await _enforce_daily_quota(user_id)

    model = settings.nvidia_image_model
    job = await supabase_generation.create_job(
        user_id=user_id, prompt=prompt, model=model, seed=seed
    )
    job_id = job["id"]

    try:
        # Hard request backstop: some NIM endpoints hold/trickle a slow request
        # so the SDK's own read timeout never fires. wait_for guarantees the
        # request (and this coroutine) returns even then — the abandoned worker
        # thread is left to unwind on its own (on the DEDICATED _gen_executor, so
        # a leak can't starve the shared request pool). The job is marked failed
        # so it never lingers as "running".
        loop = asyncio.get_running_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(
                _gen_executor,
                partial(generation_pipeline.generate_image, user_id=user_id, prompt=prompt, seed=seed),
            ),
            timeout=settings.generation_deadline,
        )
    except TimeoutError:
        # The deadline value is our own config, not provider text — safe to show.
        msg = f"Generation timed out after {settings.generation_deadline}s"
        await _safe_mark_failed(job_id, msg)
        logger.warning("generation timed out for job=%s", job_id)
        raise GenerationError(msg) from None
    except Exception:  # provider/preflight/network failure
        # Log the full detail server-side; never surface raw provider/SDK text.
        logger.exception("generation pipeline raised for job=%s", job_id)
        await _safe_mark_failed(job_id, _GENERIC_FAILURE)
        raise GenerationError(_GENERIC_FAILURE) from None

    assets = result["assets"]
    status = "succeeded" if assets and not result["failed"] else "failed"
    if status == "failed":
        # result["error"] is the SDK's own error_summary() — log it, don't store it.
        logger.warning("generation job=%s produced no asset: %s", job_id, result.get("error"))
    stored_error = None if status == "succeeded" else _GENERIC_FAILURE

    # The run is already paid for and (on success) written to B2. The
    # running->terminal transition is the ONLY write that can strand a job as
    # 'running', so guard it on its own and fail loudly if it can't land.
    try:
        await supabase_generation.complete_job(
            job_id,
            status=status,
            run_id=result["run_id"],
            manifest_uri=result["manifest_uri"],
            canonical_hash=result["canonical_hash"],
            cost_usd=result["cost_usd"],
            error=stored_error,
        )
    except Exception:
        logger.exception("failed to finalize job=%s; marking failed", job_id)
        await _safe_mark_failed(job_id, _GENERIC_FAILURE)
        raise GenerationError(_GENERIC_FAILURE) from None

    # Secondary bookkeeping (provider-run, file rows, usage event). A blip here
    # must NOT flip an already-succeeded job to failed: the asset exists in B2, so
    # a re-generate would double provider spend. Log and continue — a missing
    # provider-run/usage row is a lesser, non-user-facing inconsistency.
    try:
        await supabase_generation.record_provider_run(
            {
                "job_id": job_id,
                "provider": "nvidia",
                "model": result["model"],
                "run_id": result["run_id"],
                "status": status,
                "cost_usd": result["cost_usd"],
                "assets_count": len(assets),
            }
        )
        file_rows = [
            {
                "user_id": user_id,
                "job_id": job_id,
                "b2_key": a["key"],
                "url": a["url"],
                "sha256": a["sha256"],
                "media_type": a["media_type"],
                "size_bytes": a["size_bytes"],
                "width": a["width"],
                "height": a["height"],
            }
            for a in assets
            if a.get("key")
        ]
        await supabase_generation.insert_files(file_rows)
        if status == "succeeded":
            await supabase_generation.record_usage_event(
                {
                    "user_id": user_id,
                    "job_id": job_id,
                    "kind": "image_generation",
                    "units": len(assets),
                    "cost_usd": result["cost_usd"],
                }
            )
    except Exception:
        logger.exception(
            "secondary persistence failed for job=%s (job left status=%s)", job_id, status
        )

    # A no-asset run is a failure from the user's perspective; raise AFTER the
    # terminal status is durably recorded so the job never lingers as 'running'.
    if status == "failed":
        raise GenerationError(_GENERIC_FAILURE)

    return GenerationJob(
        id=job_id,
        user_id=user_id,
        prompt=prompt,
        provider="nvidia",
        model=result["model"],
        status=status,
        seed=seed,
        run_id=result["run_id"],
        manifest_uri=result["manifest_uri"],
        canonical_hash=result["canonical_hash"],
        cost_usd=result["cost_usd"],
        created_at=job.get("created_at"),
        assets=[
            GeneratedAsset(
                key=a["key"],
                url=a["url"],
                sha256=a["sha256"],
                media_type=a["media_type"],
                size_bytes=a["size_bytes"],
                width=a["width"],
                height=a["height"],
            )
            for a in assets
            if a.get("key")
        ],
    )


def job_from_row(row: dict) -> GenerationJob:
    """Map a generation_jobs PostgREST row (with embedded files(*)) to the API
    model. Shared by the per-user list here and the admin all-jobs list, so the
    row->model mapping lives in exactly one place."""
    files = row.get("files") or []
    return GenerationJob(
        id=row["id"],
        user_id=row["user_id"],
        prompt=row["prompt"],
        provider=row.get("provider", "nvidia"),
        model=row["model"],
        status=row["status"],
        error=row.get("error"),
        seed=row.get("seed"),
        run_id=row.get("run_id"),
        manifest_uri=row.get("manifest_uri"),
        canonical_hash=row.get("canonical_hash"),
        cost_usd=row.get("cost_usd"),
        created_at=row.get("created_at"),
        assets=[
            GeneratedAsset(
                key=f["b2_key"],
                url=f.get("url"),
                sha256=f.get("sha256"),
                media_type=f.get("media_type") or "image/png",
                size_bytes=f.get("size_bytes"),
                width=f.get("width"),
                height=f.get("height"),
            )
            for f in files
        ],
    )


async def list_jobs(user_id: str, *, limit: int = 50) -> list[GenerationJob]:
    """Return a user's generation jobs (newest first) with their assets."""
    rows = await supabase_generation.list_jobs(user_id, limit=limit)
    return [job_from_row(row) for row in rows]
