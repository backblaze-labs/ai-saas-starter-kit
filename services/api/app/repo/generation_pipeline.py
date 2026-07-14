"""Genblaze image-generation pipeline — the ONLY home for ``genblaze_*`` imports.

This mirrors the starter's "boto3 only in repo/" structural rule: every
provider-orchestration import (``genblaze_core`` / ``genblaze_nvidia`` /
``genblaze_s3``) is confined to this module (enforced by
tests/test_structure.py::test_genblaze_only_in_repo). The service and runtime
layers consume the plain dict this module returns, never a Genblaze type.

Text-to-image via NVIDIA NIM ``flux.1-schnell``: a step with no inputs is a
plain generation (no reference image), so — unlike a reference-faithful *edit*
route — we pass just a prompt plus image params. Each run's assets and a
SHA-256 provenance manifest are written to B2 under
``generated/{user_id}/{date}/{run_id}/`` by the Genblaze ``ObjectStorageSink``
(``HIERARCHICAL`` groups a run's files under one folder). Genblaze owns the
boto3 client it builds for B2 and stamps its own ``b2ai-genblaze/…`` user agent
on it — the documented Genblaze UA-delegation exception to B2 standard #2; this
app's identity travels in ``Pipeline(name=…)`` and is written into every
manifest.
"""

import logging
import tempfile
from datetime import UTC, datetime

from genblaze_core import (
    KeyStrategy,
    Manifest,
    Modality,
    ObjectStorageSink,
    Pipeline,
    Run,
)
from genblaze_nvidia import NvidiaImageProvider
from genblaze_s3 import S3StorageBackend

from app.config import settings

logger = logging.getLogger(__name__)

# The pipeline slug is the provenance signal stamped into every B2 manifest.
PIPELINE_NAME = "ai-media-saas-starter"


def is_configured() -> bool:
    """Generation needs an NVIDIA NIM key; report it so callers 503 cleanly."""
    return bool(settings.nvidia_api_key)


def _backend() -> S3StorageBackend:
    """Build the genblaze-s3 backend with explicit B2 credentials.

    All B2_* values are passed explicitly — never Genblaze's B2_* env fallback.
    ``public_url_base`` is optional in this starter (parent standard: presigned
    URLs when unset), so pass ``None`` rather than an empty string; the backend
    then emits its raw-endpoint durable URL, and ``key_from_url`` still recovers
    the object key from it.
    """
    return S3StorageBackend.for_backblaze(
        settings.b2_bucket_name,
        region=settings.b2_region,
        key_id=settings.b2_application_key_id,
        app_key=settings.b2_application_key,
        public_url_base=settings.b2_public_url_base or None,
    )


def _asset_to_dict(backend: S3StorageBackend, asset) -> dict:
    """Map a Genblaze Asset to a plain dict (no SDK types leak upward).

    After the sink uploads, ``asset.url`` is the backend's durable (never
    presigned) URL; ``backend.key_from_url`` inverts it to the B2 object key
    regardless of whether ``public_url_base`` is set, so the app can address the
    object via its own boto3 client (preview/download) without importing
    genblaze types downstream.
    """
    return {
        "key": backend.key_from_url(asset.url),
        "url": asset.url,
        "sha256": asset.sha256,
        "media_type": asset.media_type,
        "size_bytes": asset.size_bytes,
        "width": asset.width,
        "height": asset.height,
    }


def generate_image(*, user_id: str, prompt: str, seed: int | None = None) -> dict:
    """Generate one image from a text prompt and persist it to B2.

    Blocking (Genblaze is a synchronous SDK) — the service layer runs it in a
    threadpool. Returns a plain dict (run_id, manifest_uri, canonical_hash,
    cost_usd, model, assets, failed, error) so upper layers never import
    Genblaze types. Raises RuntimeError when no NVIDIA key is configured.
    """
    if not is_configured():
        raise RuntimeError("NVIDIA_API_KEY is not configured")

    date = datetime.now(UTC).strftime("%Y-%m-%d")
    backend = _backend()
    sink = ObjectStorageSink(
        backend,
        prefix=f"{settings.generation_prefix}/{user_id}/{date}",
        key_strategy=KeyStrategy.HIERARCHICAL,
    )

    params: dict = {
        "width": settings.generation_width,
        "height": settings.generation_height,
        "steps": settings.generation_steps,
    }
    if seed is not None:
        params["seed"] = seed

    # NVIDIA returns the image inline (base64); the provider saves it to
    # ``output_dir`` and the sink then transfers it to B2. A per-run temp dir
    # keeps concurrent runs isolated and is cleaned up on exit.
    with tempfile.TemporaryDirectory(prefix="genblaze-nvidia-") as tmp:
        pipe = Pipeline(PIPELINE_NAME, project_id=user_id).step(
            NvidiaImageProvider(
                api_key=settings.nvidia_api_key,
                output_dir=tmp,
                # Bound the SDK's own HTTP + async-poll waits so a slow NVIDIA
                # endpoint surfaces as a failed step, not an unbounded hang.
                http_timeout=float(settings.generation_run_timeout),
                nvcf_timeout=float(settings.generation_run_timeout),
            ),
            model=settings.nvidia_image_model,
            modality=Modality.IMAGE,
            prompt=prompt,
            **params,
        )
        result = pipe.run(
            sink=sink,
            timeout=settings.generation_run_timeout,
            raise_on_failure=False,
        )

    run: Run = result.run
    manifest: Manifest | None = result.manifest

    assets: list[dict] = []
    total_cost = 0.0
    have_cost = False
    for step in result.succeeded_steps():
        if step.cost_usd is not None:
            total_cost += float(step.cost_usd)
            have_cost = True
        for asset in step.assets:
            assets.append(_asset_to_dict(backend, asset))

    failed = len(result.failed_steps())
    error = result.error_summary() if failed else None
    if failed:
        logger.warning(
            "generation: %d step(s) failed for user=%s: %s", failed, user_id, error
        )

    return {
        "run_id": run.run_id,
        "manifest_uri": manifest.manifest_uri if manifest else None,
        "canonical_hash": manifest.canonical_hash if manifest else None,
        "cost_usd": total_cost if have_cost else None,
        "model": settings.nvidia_image_model,
        "assets": assets,
        "failed": failed,
        "error": error,
    }
