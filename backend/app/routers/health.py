"""Health check router - Backend initialization status tracking"""
from fastapi import APIRouter
from app.utils.response import success_response

router = APIRouter(prefix="/health", tags=["health"])

_backend_ready = False


def set_backend_ready(ready: bool):
    """Set backend ready status"""
    global _backend_ready
    _backend_ready = ready


def is_backend_ready() -> bool:
    """Check if backend is ready"""
    return _backend_ready


@router.get("/ready")
async def health_ready():
    """Check if backend initialization is complete"""
    return success_response({"ready": _backend_ready})
