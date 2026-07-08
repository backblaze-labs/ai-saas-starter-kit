"""Generation models: the request body, a generated asset, and a job record.

Lives in the lowest layer so the repo/service/runtime layers can all import
these without a backward import. The API speaks these models; the Genblaze SDK
types never leak past the repo layer.
"""

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    """Body for POST /generation/generate."""

    prompt: str = Field(min_length=1, max_length=2000)
    # Optional seed for reproducible output; omitted -> the provider randomizes.
    seed: int | None = Field(default=None, ge=0, le=4294967295)


class GeneratedAsset(BaseModel):
    """One generated image, mirrored from B2 into the response/`files` table."""

    key: str
    url: str | None = None
    sha256: str | None = None
    media_type: str = "image/png"
    size_bytes: int | None = None
    width: int | None = None
    height: int | None = None


class GenerationJob(BaseModel):
    """A single generation run and its outputs (the API's job record)."""

    id: str
    user_id: str
    prompt: str
    provider: str = "nvidia"
    model: str
    status: str = "running"  # running | succeeded | failed
    error: str | None = None
    seed: int | None = None
    run_id: str | None = None
    manifest_uri: str | None = None
    canonical_hash: str | None = None
    cost_usd: float | None = None
    assets: list[GeneratedAsset] = Field(default_factory=list)
    created_at: str | None = None
