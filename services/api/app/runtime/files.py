import logging

# NOTE: the B2-backed handlers below are intentionally sync `def`, not
# `async def`. The whole call chain is blocking boto3, and an `async def`
# handler runs directly on the event loop — a single slow bucket scan would
# then stall every other request (Railway runs one worker). Starlette runs
# sync handlers in its threadpool, giving real concurrency for B2 I/O.
from fastapi import APIRouter, Depends, HTTPException

from app.runtime.auth import get_current_user
from app.service.files import (
    FileKeyError,
    FileNotFoundServiceError,
    get_download_url,
    get_file,
    get_files,
    get_preview_url,
    get_stats,
    get_upload_activity,
    remove_file,
)
from app.types import DailyUploadCount, FileMetadata, UploadStats
from app.types.auth import AuthUser

logger = logging.getLogger(__name__)

router = APIRouter()

# Every route below is authenticated (401 without a valid bearer token) and
# scoped to the caller's own objects: listings/stats cover only the caller's
# uploads/ + generated/ prefixes, and key-addressed ops 404 for any key the
# caller doesn't own so no user can read/delete another tenant's object.


def _file_url_response(user_id: str, key: str, *, preview: bool) -> dict[str, str]:
    try:
        url = (
            get_preview_url(user_id, key) if preview else get_download_url(user_id, key)
        )
    except FileKeyError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None
    except FileNotFoundServiceError as e:
        raise HTTPException(status_code=404, detail=e.detail) from None
    return {"url": url}


def _file_metadata_response(user_id: str, key: str) -> FileMetadata:
    try:
        return get_file(user_id, key)
    except FileKeyError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None
    except FileNotFoundServiceError as e:
        raise HTTPException(status_code=404, detail=e.detail) from None


def _delete_file_response(user_id: str, key: str) -> dict[str, bool | str]:
    try:
        remove_file(user_id, key)
    except FileKeyError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None
    except FileNotFoundServiceError as e:
        raise HTTPException(status_code=404, detail=e.detail) from None
    except RuntimeError:
        raise HTTPException(status_code=500, detail="Failed to delete file") from None
    logger.info("File deleted: key=%s", key)
    return {"deleted": True, "key": key}


@router.get("/files", response_model=list[FileMetadata])
def list_files_endpoint(
    limit: int = 100,
    current_user: AuthUser = Depends(get_current_user),
):
    try:
        return get_files(current_user.id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.get("/files/stats", response_model=UploadStats)
def stats_endpoint(current_user: AuthUser = Depends(get_current_user)):
    return get_stats(current_user.id)


@router.get("/files/stats/activity", response_model=list[DailyUploadCount])
def upload_activity_endpoint(
    days: int = 7,
    current_user: AuthUser = Depends(get_current_user),
):
    if days < 1 or days > 90:
        raise HTTPException(status_code=400, detail="Days must be between 1 and 90")
    return get_upload_activity(current_user.id, days=days)


@router.get("/files-by-key/download")
def download_file_by_key_endpoint(
    key: str, current_user: AuthUser = Depends(get_current_user)
):
    return _file_url_response(current_user.id, key, preview=False)


@router.get("/files-by-key/preview")
def preview_file_by_key_endpoint(
    key: str, current_user: AuthUser = Depends(get_current_user)
):
    """Return a presigned URL for inline preview. Does not count as a download."""
    return _file_url_response(current_user.id, key, preview=True)


@router.get("/files-by-key/metadata", response_model=FileMetadata)
def get_file_by_key_endpoint(
    key: str, current_user: AuthUser = Depends(get_current_user)
):
    return _file_metadata_response(current_user.id, key)


@router.delete("/files-by-key")
def delete_file_by_key_endpoint(
    key: str, current_user: AuthUser = Depends(get_current_user)
):
    return _delete_file_response(current_user.id, key)


@router.get("/files/{key:path}/download")
def download_file_endpoint(
    key: str, current_user: AuthUser = Depends(get_current_user)
):
    return _file_url_response(current_user.id, key, preview=False)


@router.get("/files/{key:path}/preview")
def preview_file_endpoint(
    key: str, current_user: AuthUser = Depends(get_current_user)
):
    """Return a presigned URL for inline preview. Does not count as a download."""
    return _file_url_response(current_user.id, key, preview=True)


@router.get("/files/{key:path}", response_model=FileMetadata)
def get_file_endpoint(key: str, current_user: AuthUser = Depends(get_current_user)):
    return _file_metadata_response(current_user.id, key)


@router.delete("/files/{key:path}")
def delete_file_endpoint(key: str, current_user: AuthUser = Depends(get_current_user)):
    return _delete_file_response(current_user.id, key)
