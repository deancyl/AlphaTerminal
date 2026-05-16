"""Health check router - Backend initialization status tracking"""
import time
import psutil
import sqlite3
from pathlib import Path
from fastapi import APIRouter
from app.utils.response import success_response
from app.db.database import _db_path

router = APIRouter(prefix="/health", tags=["health"])

_backend_ready = False
_start_time = time.time()


def set_backend_ready(ready: bool):
    """Set backend ready status"""
    global _backend_ready
    _backend_ready = ready


def is_backend_ready() -> bool:
    """Check if backend is ready"""
    return _backend_ready


def _get_db_status():
    try:
        conn = sqlite3.connect(_db_path)
        cursor = conn.execute("PRAGMA integrity_check")
        result = cursor.fetchone()[0]
        conn.close()
        return {"status": "ok" if result == "ok" else "corrupted", "path": str(_db_path)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _get_memory_status():
    try:
        process = psutil.Process()
        mem_info = process.memory_info()
        return {
            "rss_mb": round(mem_info.rss / 1024 / 1024, 2),
            "vms_mb": round(mem_info.vms / 1024 / 1024, 2),
            "percent": round(process.memory_percent(), 2)
        }
    except Exception:
        return {"status": "unavailable"}


@router.get("/ready")
async def health_ready():
    """Check if backend initialization is complete"""
    return success_response({"ready": _backend_ready})


@router.get("/live")
async def health_live():
    """Liveness probe - basic check that the process is running"""
    return success_response({"status": "alive", "uptime_seconds": round(time.time() - _start_time, 2)})


@router.get("/detailed")
async def health_detailed():
    """Detailed health check with system metrics"""
    return success_response({
        "ready": _backend_ready,
        "uptime_seconds": round(time.time() - _start_time, 2),
        "database": _get_db_status(),
        "memory": _get_memory_status(),
        "backend_version": "0.6.39"
    })
