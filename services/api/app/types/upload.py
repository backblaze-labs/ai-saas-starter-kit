from datetime import datetime

from pydantic import BaseModel


class PrepareUploadRequest(BaseModel):
    """Client's intent to upload, sent to POST /upload/presign.

    No bytes — just what's needed to validate the request and mint a scoped,
    type-bound presigned PUT URL. ``size_bytes`` is the client-declared size; the
    real stored size is re-checked against the limit at finalize time.
    """

    filename: str
    content_type: str
    size_bytes: int


class PresignedUpload(BaseModel):
    """A short-lived presigned PUT the browser uses to upload straight to B2."""

    upload_url: str
    key: str
    method: str = "PUT"
    # Headers the browser MUST replay on the PUT for the signature to verify —
    # currently just Content-Type, which is bound into the signature.
    headers: dict[str, str]


class CompleteUploadRequest(BaseModel):
    """Sent to POST /upload/complete once the browser's PUT to B2 succeeds."""

    key: str


class FileUploadResponse(BaseModel):
    key: str
    filename: str
    size_bytes: int
    size_human: str
    content_type: str
    uploaded_at: datetime
    url: str | None = None
