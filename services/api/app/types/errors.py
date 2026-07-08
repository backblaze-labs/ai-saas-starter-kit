from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Typed JSON body for unhandled server errors (HTTP 500).

    The shape mirrors FastAPI's `HTTPException` default (`{"detail": ...}`)
    so the frontend api-client can read `.detail` uniformly for every error
    status, whether the failure was a deliberate `HTTPException` or an
    uncaught exception converted to a 500 by the catch-all middleware.
    """

    detail: str = "Internal server error"
