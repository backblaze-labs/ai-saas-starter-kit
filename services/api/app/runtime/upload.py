import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool

from app.runtime.auth import get_current_user
from app.runtime.metrics import record_upload
from app.service.upload import UploadError, finalize_upload, prepare_upload
from app.types import (
    CompleteUploadRequest,
    FileUploadResponse,
    PrepareUploadRequest,
    PresignedUpload,
)
from app.types.auth import AuthUser

logger = logging.getLogger(__name__)

router = APIRouter()

# Uploads are a two-step, direct-to-B2 flow so the payload never transits the
# API (a serverless request-body cap — Vercel's hard 4.5 MB — would otherwise
# block anything larger):
#   1. POST /upload/presign  -> validate the intent, return a scoped, type-bound
#      presigned PUT URL.
#   2. browser PUTs the bytes straight to B2 with that URL.
#   3. POST /upload/complete -> confirm the object landed and re-check the size +
#      magic-byte signature the sign step couldn't see.
# Both steps require auth and key everything under the caller's own prefix.


@router.post("/upload/presign", response_model=PresignedUpload)
async def presign_upload(
    body: PrepareUploadRequest,
    current_user: AuthUser = Depends(get_current_user),
):
    # Presigning is a local HMAC computation (no network I/O), so no threadpool.
    try:
        return prepare_upload(
            filename=body.filename,
            content_type=body.content_type,
            size_bytes=body.size_bytes,
            user_id=current_user.id,
        )
    except UploadError as e:
        logger.warning("Upload presign rejected: %s", e.detail)
        record_upload(success=False)
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.post("/upload/complete", response_model=FileUploadResponse)
async def complete_upload(
    body: CompleteUploadRequest,
    current_user: AuthUser = Depends(get_current_user),
):
    try:
        # finalize_upload does blocking B2 I/O (head + Range GET, and a delete on
        # a bad payload). Offload it so the event loop isn't blocked.
        result = await run_in_threadpool(
            finalize_upload, key=body.key, user_id=current_user.id
        )
    except UploadError as e:
        logger.warning("Upload finalize rejected: %s", e.detail)
        record_upload(success=False)
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None

    record_upload(success=True)
    logger.info(
        "File upload finalized: key=%s size=%d type=%s",
        result.key,
        result.size_bytes,
        result.content_type,
    )
    return result
