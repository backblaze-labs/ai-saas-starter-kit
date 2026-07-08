from pydantic import BaseModel


class AuthUser(BaseModel):
    """The authenticated identity, as validated against Supabase."""

    id: str
    email: str | None = None
    role: str = "user"
