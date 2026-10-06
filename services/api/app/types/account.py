"""Pydantic models for the account / settings endpoint."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class UserSettings(BaseModel):
    """Persisted user preferences returned by GET /account/settings."""

    display_name: Optional[str] = None
    bio: Optional[str] = None
    theme: Literal["light", "dark", "system"] = "system"
    default_view: Literal["grid", "list", "tree"] = "tree"
    email_on_upload: bool = False
    warn_near_quota: bool = True
    quota_threshold: int = Field(default=80, ge=50, le=95)


class UpdateSettingsRequest(BaseModel):
    """Partial update body for PATCH /account/settings.

    Every field is Optional so a request that omits a field leaves the stored
    value unchanged — only the fields that are explicitly sent are patched.
    """

    display_name: Optional[str] = None
    bio: Optional[str] = Field(default=None, max_length=160)
    theme: Optional[Literal["light", "dark", "system"]] = None
    default_view: Optional[Literal["grid", "list", "tree"]] = None
    email_on_upload: Optional[bool] = None
    warn_near_quota: Optional[bool] = None
    quota_threshold: Optional[int] = Field(default=None, ge=50, le=95)
