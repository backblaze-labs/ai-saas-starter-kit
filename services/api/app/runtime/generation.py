"""Generation routes: run a text-to-image job and list a user's jobs.

The generate endpoint is gated behind a paid plan via the reusable
`require_plan("pro")` dependency from the billing slice — a Free user gets 402.
No business logic here; handlers translate typed service errors to HTTP.

Endpoints:
  POST /generation/generate   run one text-to-image job (Pro-gated)
  GET  /generation/jobs       the caller's generation jobs (newest first)
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.runtime.auth import get_current_user
from app.runtime.billing import require_plan
from app.service import generation as generation_service
from app.service.generation import (
    GenerationConfigError,
    GenerationError,
    GenerationQuotaError,
)
from app.types.auth import AuthUser
from app.types.generation import GenerateRequest, GenerationJob

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/generation", tags=["generation"])


@router.post("/generate", response_model=GenerationJob)
async def create_generation(
    body: GenerateRequest,
    current_user: AuthUser = Depends(require_plan("pro")),
) -> GenerationJob:
    try:
        return await generation_service.generate(
            user_id=current_user.id, prompt=body.prompt, seed=body.seed
        )
    except GenerationConfigError as e:
        raise HTTPException(status_code=503, detail=str(e)) from None
    except GenerationQuotaError as e:
        raise HTTPException(status_code=429, detail=str(e)) from None
    except GenerationError as e:
        raise HTTPException(status_code=502, detail=f"Generation failed: {e}") from None


@router.get("/jobs", response_model=list[GenerationJob])
async def list_generation_jobs(
    current_user: AuthUser = Depends(get_current_user),
) -> list[GenerationJob]:
    return await generation_service.list_jobs(current_user.id)
