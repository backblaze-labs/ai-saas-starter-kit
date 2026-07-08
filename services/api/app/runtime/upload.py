import logging

from fastapi import APIRouter, HTTPException, Request, UploadFile

from app.config import settings
from app.runtime.metrics import record_upload
from app.service.upload import UploadError, process_upload
from app.types import FileUploadResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/upload", response_model=FileUploadResponse)
async def upload(request: Request, file: UploadFile):
    content_type = file.content_type or "application/octet-stream"
    content_length_header = request.headers.get("content-length")
    content_length = int(content_length_header) if content_length_header else None

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
        result = process_upload(
            file_data=file_data,
            filename=file.filename or "",
            content_type=content_type,
            content_length=content_length,
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
