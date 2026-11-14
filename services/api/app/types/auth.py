from pydantic import BaseModel, Field


class AuthUser(BaseModel):
    """The authenticated identity, as validated against Supabase."""

    id: str
    email: str | None = None
    role: str = "user"
    token: str = Field(exclude=True)  # Never serialize the token in responses

