from fastapi import APIRouter

from app.repo import check_connectivity

router = APIRouter()


# Sync `def` so the blocking B2 connectivity check runs in Starlette's
# threadpool rather than on the event loop (see runtime/files.py rationale).
@router.get("/health")
def health():
    b2_ok = check_connectivity()
    return {
        "status": "healthy" if b2_ok else "degraded",
        "b2_connected": b2_ok,
    }
