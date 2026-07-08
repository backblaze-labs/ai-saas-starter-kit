"""Generation business logic: run the Genblaze/NVIDIA image pipeline and persist
the job, its generated files, a provider-run row, and a usage event to Supabase.

The pipeline (repo/generation_pipeline) is a synchronous, blocking SDK call, so
it runs in a threadpool to keep the event loop free. Genblaze types never cross
this boundary — the repo returns plain dicts.
"""

import logging
from functools import partial

from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.repo import generation_pipeline, supabase_generation
from app.types.generation import GeneratedAsset, GenerationJob

logger = logging.getLogger(__name__)


class GenerationConfigError(RuntimeError):
    """Raised when generation is attempted without an NVIDIA key configured."""


class GenerationError(RuntimeError):
    """Raised when the provider run produced no usable asset."""


def is_configured() -> bool:
    """True when both the provider key and the persistence layer are set."""
    return generation_pipeline.is_configured() and supabase_generation.is_configured()


async def generate(*, user_id: str, prompt: str, seed: int | None = None) -> GenerationJob:
    """Run one text-to-image generation and return the persisted job record."""
    if not generation_pipeline.is_configured():
        raise GenerationConfigError("NVIDIA_API_KEY is not configured")

    model = settings.nvidia_image_model
    job = await supabase_generation.create_job(
        user_id=user_id, prompt=prompt, model=model, seed=seed
    )
    job_id = job["id"]

    try:
        result = await run_in_threadpool(
            partial(generation_pipeline.generate_image, user_id=user_id, prompt=prompt, seed=seed)
        )
    except Exception as exc:  # provider/preflight/network failure
        await supabase_generation.complete_job(job_id, status="failed", error=str(exc))
        logger.exception("generation pipeline raised for job=%s", job_id)
        raise GenerationError(str(exc)) from exc

    assets = result["assets"]
    status = "succeeded" if assets and not result["failed"] else "failed"

    await supabase_generation.complete_job(
        job_id,
        status=status,
        run_id=result["run_id"],
        manifest_uri=result["manifest_uri"],
        canonical_hash=result["canonical_hash"],
        cost_usd=result["cost_usd"],
        error=result["error"],
    )
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
    else:
        raise GenerationError(result["error"] or "Generation produced no image")

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


async def list_jobs(user_id: str, *, limit: int = 50) -> list[GenerationJob]:
    """Return a user's generation jobs (newest first) with their assets."""
    rows = await supabase_generation.list_jobs(user_id, limit=limit)
    jobs: list[GenerationJob] = []
    for row in rows:
        files = row.get("files") or []
        jobs.append(
            GenerationJob(
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
        )
    return jobs
