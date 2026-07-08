from pydantic import BaseModel


class DailyUploadCount(BaseModel):
    date: str
    uploads: int


class UploadStats(BaseModel):
    total_files: int
    total_size_bytes: int
    total_size_human: str
    uploads_today: int
    total_downloads: int
