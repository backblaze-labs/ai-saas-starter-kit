from datetime import datetime

from pydantic import BaseModel

from app.types.files import FileMetadataDetail


class FileUploadResponse(BaseModel):
    key: str
    filename: str
    size_bytes: int
    size_human: str
    content_type: str
    uploaded_at: datetime
    url: str | None = None
    metadata: FileMetadataDetail | None = None
