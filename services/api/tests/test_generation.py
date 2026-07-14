"""Tests for the generation slice.

External boundaries (the Genblaze/NVIDIA pipeline, Supabase PostgREST) are
stubbed so the route, plan-gating, persistence orchestration, and error mapping
are covered hermetically — no NVIDIA key, no network. A separate no-network
signature guard asserts the installed Genblaze SDK still exposes the API surface
the pipeline binds to (drift on a clean install is otherwise a false green).
"""

import pytest

from app.repo import generation_pipeline, supabase_generation
from app.service import billing as billing_service
from app.types.auth import AuthUser
from app.types.billing import Entitlements

# --- fakes -----------------------------------------------------------------


class FakeGenStore:
    """In-memory stand-in for the supabase_generation repo."""

    def __init__(self) -> None:
        self.jobs: dict[str, dict] = {}
        self.files: list[dict] = []
        self.provider_runs: list[dict] = []
        self.usage_events: list[dict] = []

    async def create_job(self, *, user_id, prompt, model, provider="nvidia", seed=None):
        job = {
            "id": "job-1",
            "user_id": user_id,
            "prompt": prompt,
            "model": model,
            "provider": provider,
            "status": "running",
            "seed": seed,
            "created_at": "2026-07-08T00:00:00Z",
        }
        self.jobs[job["id"]] = job
        return job

    async def complete_job(self, job_id, **patch):
        self.jobs.setdefault(job_id, {}).update(patch)

    async def insert_files(self, rows):
        self.files.extend(rows)

    async def record_provider_run(self, row):
        self.provider_runs.append(row)

    async def record_usage_event(self, row):
        self.usage_events.append(row)

    async def list_jobs(self, user_id, *, limit=50):
        return [
            {**j, "files": [f for f in self.files if f["job_id"] == j["id"]]}
            for j in self.jobs.values()
            if j.get("user_id") == user_id
        ]


@pytest.fixture
def fake_store(monkeypatch):
    store = FakeGenStore()
    for name in (
        "create_job",
        "complete_job",
        "insert_files",
        "record_provider_run",
        "record_usage_event",
        "list_jobs",
    ):
        monkeypatch.setattr(supabase_generation, name, getattr(store, name))
    return store


def _fake_result(**over):
    base = {
        "run_id": "run-abc",
        "manifest_uri": "b2://bucket/generated/u/2026-07-08/run-abc/manifest.json",
        "canonical_hash": "a" * 64,
        "cost_usd": None,
        "model": "black-forest-labs/flux.1-schnell",
        "assets": [
            {
                "key": "generated/u/2026-07-08/run-abc/img.png",
                "url": "https://s3.us-west.example/bucket/generated/u/2026-07-08/run-abc/img.png",
                "sha256": "b" * 64,
                "media_type": "image/png",
                "size_bytes": 12345,
                "width": 1024,
                "height": 1024,
            }
        ],
        "failed": 0,
        "error": None,
    }
    base.update(over)
    return base


def _auth_as(monkeypatch, *, tier: str):
    from app.service import auth as auth_service

    async def fake_user(_token: str):
        return AuthUser(id="u", email="u@example.com", role="user")

    async def fake_entitlements(_uid: str):
        rank = {"free": 0, "pro": 1, "team": 2}[tier]
        return Entitlements(tier=tier, rank=rank, active=rank > 0, can_generate=rank >= 1)

    monkeypatch.setattr(auth_service, "user_from_token", fake_user)
    monkeypatch.setattr(billing_service, "get_entitlements", fake_entitlements)


# --- route: plan gating ----------------------------------------------------


@pytest.mark.asyncio
async def test_generate_402_for_free(client, monkeypatch):
    _auth_as(monkeypatch, tier="free")
    resp = await client.post(
        "/generation/generate",
        headers={"Authorization": "Bearer x"},
        json={"prompt": "a red bicycle"},
    )
    assert resp.status_code == 402


@pytest.mark.asyncio
async def test_generate_503_without_nvidia_key(client, monkeypatch, fake_store):
    _auth_as(monkeypatch, tier="pro")
    monkeypatch.setattr(generation_pipeline, "is_configured", lambda: False)
    resp = await client.post(
        "/generation/generate",
        headers={"Authorization": "Bearer x"},
        json={"prompt": "a red bicycle"},
    )
    assert resp.status_code == 503


# --- route: happy path + persistence orchestration -------------------------


@pytest.mark.asyncio
async def test_generate_persists_job_files_usage(client, monkeypatch, fake_store):
    _auth_as(monkeypatch, tier="pro")
    monkeypatch.setattr(generation_pipeline, "is_configured", lambda: True)
    monkeypatch.setattr(generation_pipeline, "generate_image", lambda **kw: _fake_result())

    resp = await client.post(
        "/generation/generate",
        headers={"Authorization": "Bearer x"},
        json={"prompt": "a red bicycle", "seed": 7},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "succeeded"
    assert body["run_id"] == "run-abc"
    assert len(body["assets"]) == 1
    assert body["assets"][0]["key"].startswith("generated/")

    # Persistence side effects.
    assert fake_store.jobs["job-1"]["status"] == "succeeded"
    assert len(fake_store.files) == 1
    assert fake_store.files[0]["b2_key"].startswith("generated/")
    assert len(fake_store.provider_runs) == 1
    assert len(fake_store.usage_events) == 1


@pytest.mark.asyncio
async def test_generate_marks_failed_and_502_when_no_asset(client, monkeypatch, fake_store):
    _auth_as(monkeypatch, tier="pro")
    monkeypatch.setattr(generation_pipeline, "is_configured", lambda: True)
    monkeypatch.setattr(
        generation_pipeline,
        "generate_image",
        lambda **kw: _fake_result(assets=[], failed=1, error="provider error"),
    )
    resp = await client.post(
        "/generation/generate",
        headers={"Authorization": "Bearer x"},
        json={"prompt": "a red bicycle"},
    )
    assert resp.status_code == 502
    assert fake_store.jobs["job-1"]["status"] == "failed"


@pytest.mark.asyncio
async def test_generate_times_out_cleanly_instead_of_hanging(client, monkeypatch, fake_store):
    """A provider that hangs must yield a bounded 502 + a failed job, never a hang."""
    import time

    from app.config import settings as app_settings

    _auth_as(monkeypatch, tier="pro")
    monkeypatch.setattr(generation_pipeline, "is_configured", lambda: True)
    monkeypatch.setattr(app_settings, "generation_deadline", 0.3)
    monkeypatch.setattr(generation_pipeline, "generate_image", lambda **kw: time.sleep(5))

    start = time.monotonic()
    resp = await client.post(
        "/generation/generate",
        headers={"Authorization": "Bearer x"},
        json={"prompt": "hangs"},
    )
    elapsed = time.monotonic() - start
    assert resp.status_code == 502
    assert elapsed < 3, f"request should abort near the 0.3s deadline, took {elapsed:.1f}s"
    assert fake_store.jobs["job-1"]["status"] == "failed"


@pytest.mark.asyncio
async def test_generate_502_when_pipeline_raises(client, monkeypatch, fake_store):
    _auth_as(monkeypatch, tier="pro")
    monkeypatch.setattr(generation_pipeline, "is_configured", lambda: True)

    def boom(**kw):
        raise RuntimeError("nvidia preflight rejected the key")

    monkeypatch.setattr(generation_pipeline, "generate_image", boom)
    resp = await client.post(
        "/generation/generate",
        headers={"Authorization": "Bearer x"},
        json={"prompt": "x"},
    )
    assert resp.status_code == 502
    assert fake_store.jobs["job-1"]["status"] == "failed"


# --- route: list jobs ------------------------------------------------------


@pytest.mark.asyncio
async def test_list_jobs_returns_user_jobs_with_assets(client, monkeypatch, fake_store):
    _auth_as(monkeypatch, tier="pro")
    monkeypatch.setattr(generation_pipeline, "is_configured", lambda: True)
    monkeypatch.setattr(generation_pipeline, "generate_image", lambda **kw: _fake_result())
    await client.post(
        "/generation/generate",
        headers={"Authorization": "Bearer x"},
        json={"prompt": "a red bicycle"},
    )
    resp = await client.get("/generation/jobs", headers={"Authorization": "Bearer x"})
    assert resp.status_code == 200
    jobs = resp.json()
    assert len(jobs) == 1
    assert jobs[0]["prompt"] == "a red bicycle"
    assert len(jobs[0]["assets"]) == 1


# --- no-network signature guard against the installed Genblaze SDK ----------


def test_genblaze_api_surface_is_stable():
    """The pipeline binds to this exact Genblaze API — assert it still exists.

    Skips cleanly when genblaze isn't installed; when it is, it fails loudly on
    an API drift that would otherwise only surface at generation time. No network.
    """
    core = pytest.importorskip("genblaze_core")
    nvidia = pytest.importorskip("genblaze_nvidia")
    s3 = pytest.importorskip("genblaze_s3")

    import inspect

    for name in ("Pipeline", "ObjectStorageSink", "KeyStrategy", "Modality", "Manifest", "Run"):
        assert hasattr(core, name), f"genblaze_core.{name} missing"
    assert hasattr(core.KeyStrategy, "HIERARCHICAL")
    assert hasattr(core.Modality, "IMAGE")
    assert hasattr(nvidia, "NvidiaImageProvider")
    assert hasattr(s3.S3StorageBackend, "for_backblaze")
    assert hasattr(s3.S3StorageBackend, "key_from_url")

    # Bind-check the exact constructor/classmethod kwargs the pipeline binds to,
    # so a Genblaze *signature* drift (not just a missing symbol) fails here at
    # test time rather than at generation time on a clean install.
    def _params(fn):
        return set(inspect.signature(fn).parameters)

    for_backblaze = _params(s3.S3StorageBackend.for_backblaze)
    assert {"region", "key_id", "app_key", "public_url_base"} <= for_backblaze, for_backblaze
    provider_init = _params(nvidia.NvidiaImageProvider.__init__)
    assert {"api_key", "output_dir"} <= provider_init, provider_init
    pipeline_init = _params(core.Pipeline.__init__)
    assert "project_id" in pipeline_init, pipeline_init
    assert hasattr(core.Pipeline, "step") and hasattr(core.Pipeline, "run")
