import logging

from fastapi import APIRouter, HTTPException

from app.service.files import (
    FileKeyError,
    FileNotFoundError,
    get_download_url,
    get_file,
    get_files,
    get_preview_url,
    get_stats,
    get_upload_activity,
    remove_file,
)
from app.types import DailyUploadCount, FileMetadata, UploadStats

logger = logging.getLogger(__name__)

router = APIRouter()


def _file_url_response(key: str, *, preview: bool) -> dict[str, str]:
    try:
        url = get_preview_url(key) if preview else get_download_url(key)
    except FileKeyError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.detail) from None
    return {"url": url}


def _file_metadata_response(key: str) -> FileMetadata:
    try:
        return get_file(key)
    except FileKeyError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.detail) from None


def _delete_file_response(key: str) -> dict[str, bool | str]:
    try:
        remove_file(key)
    except FileKeyError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None
    except RuntimeError:
        raise HTTPException(status_code=500, detail="Failed to delete file") from None
    logger.info("File deleted: key=%s", key)
    return {"deleted": True, "key": key}


@router.get("/files", response_model=list[FileMetadata])
async def list_files_endpoint(prefix: str = "", limit: int = 100):
    try:
        return get_files(prefix=prefix, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.get("/files/stats", response_model=UploadStats)
async def stats_endpoint():
    return get_stats()


@router.get("/files/stats/activity", response_model=list[DailyUploadCount])
async def upload_activity_endpoint(days: int = 7):
    if days < 1 or days > 90:
        raise HTTPException(status_code=400, detail="Days must be between 1 and 90")
    return get_upload_activity(days=days)


@router.get("/files-by-key/download")
async def download_file_by_key_endpoint(key: str):
    return _file_url_response(key, preview=False)


@router.get("/files-by-key/preview")
async def preview_file_by_key_endpoint(key: str):
    """Return a presigned URL for inline preview. Does not count as a download."""
    return _file_url_response(key, preview=True)


@router.get("/files-by-key/metadata", response_model=FileMetadata)
async def get_file_by_key_endpoint(key: str):
    return _file_metadata_response(key)


@router.delete("/files-by-key")
async def delete_file_by_key_endpoint(key: str):
    return _delete_file_response(key)


@router.get("/files/{key:path}/download")
async def download_file_endpoint(key: str):
    return _file_url_response(key, preview=False)


@router.get("/files/{key:path}/preview")
async def preview_file_endpoint(key: str):
    """Return a presigned URL for inline preview. Does not count as a download."""
    return _file_url_response(key, preview=True)


@router.get("/files/{key:path}", response_model=FileMetadata)
async def get_file_endpoint(key: str):
    return _file_metadata_response(key)


@router.delete("/files/{key:path}")
async def delete_file_endpoint(key: str):
    return _delete_file_response(key)
