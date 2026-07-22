import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.config import settings
from app.runtime.auth import get_current_user
from app.runtime.metrics import record_upload
from app.service.upload import UploadError, check_upload_type, process_upload
from app.types import FileUploadResponse
from app.types.auth import AuthUser

logger = logging.getLogger(__name__)

router = APIRouter()

# Bounds simultaneous in-flight uploads so N concurrent large bodies (each
# buffered in memory) can't OOM a small instance. Constructed at import; it
# binds once — to the loop of its first acquire (Python 3.10+) — which is the
# single app loop in production. `max(1, ...)` floors a 0/negative config to a
# usable semaphore.
_upload_semaphore = asyncio.Semaphore(max(1, settings.max_concurrent_uploads))


@router.post("/upload", response_model=FileUploadResponse)
async def upload(
    request: Request,
    file: UploadFile,
    current_user: AuthUser = Depends(get_current_user),
):
    content_type = file.content_type or "application/octet-stream"
    # A malformed Content-Length shouldn't 500 the request; the streaming loop
    # below enforces the real size limit regardless of the header.
    content_length_header = request.headers.get("content-length")
    try:
        content_length = int(content_length_header) if content_length_header else None
    except ValueError:
        content_length = None

    # Reject a disallowed type / extension mismatch (415) BEFORE buffering the
    # body or taking a concurrency slot — only allowed uploads pay those costs.
    # Delegates to the service helper; no validation logic lives in runtime.
    try:
        check_upload_type(file.filename or "", content_type)
    except UploadError as e:
        logger.warning("Upload rejected pre-buffer: %s", e.detail)
        record_upload(success=False)
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None

    # Buffer + process under the concurrency gate so simultaneous large uploads
    # can't collectively exhaust memory (each body is held in RAM until the B2
    # put completes). Excess requests wait here for a free slot.
    async with _upload_semaphore:
        # Read file with chunked streaming and early size rejection
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = await file.read(1024 * 1024)  # 1MB chunks
            if not chunk:
                break
            total += len(chunk)
            if total > settings.max_file_size:
                raise HTTPException(status_code=413, detail="File too large")
            chunks.append(chunk)
        file_data = b"".join(chunks)

        try:
            # process_upload does blocking work (hashing, metadata, B2 put_object).
            # Offload it so the streaming event loop isn't blocked while it runs.
            result = await run_in_threadpool(
                process_upload,
                file_data=file_data,
                filename=file.filename or "",
                content_type=content_type,
                content_length=content_length,
                user_id=current_user.id,
            )
        except UploadError as e:
            logger.warning("Upload rejected: %s", e.detail)
            record_upload(success=False)
            raise HTTPException(status_code=e.status_code, detail=e.detail) from None

    record_upload(success=True)
    logger.info(
        "File uploaded: key=%s size=%d type=%s",
        result.key,
        result.size_bytes,
        result.content_type,
    )
    return result
