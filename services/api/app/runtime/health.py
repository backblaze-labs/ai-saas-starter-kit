from fastapi import APIRouter

from app.repo import check_connectivity

router = APIRouter()


@router.get("/health")
async def health():
    b2_ok = check_connectivity()
    return {
        "status": "healthy" if b2_ok else "degraded",
        "b2_connected": b2_ok,
    }
