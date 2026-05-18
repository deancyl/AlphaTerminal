"""
系统信息接口
提供系统版本和详细信息
"""
import json
import logging
import platform
import time
from pathlib import Path

import psutil
from fastapi import APIRouter

from app.utils.response import success_response

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/system", tags=["system"])


def _read_frontend_version():
    """从 frontend/package.json 动态读取版本号"""
    # __file__ = AlphaTerminal/backend/app/routers/market/system.py
    # parent.parent.parent.parent = AlphaTerminal/backend/ -> AlphaTerminal/ -> workspace/
    # 需要再加一层 parent = AlphaTerminal/ 然后 /frontend/package.json
    root = Path(__file__).resolve().parent.parent.parent.parent
    pkg_path = root / "frontend" / "package.json"
    try:
        if pkg_path.exists():
            with open(pkg_path, "r", encoding="utf-8") as f:
                return json.load(f).get("version", "unknown")
    except Exception as e:
        logger.warning(f"[SYSTEM] Failed to read frontend version: {type(e).__name__}: {e}")
    return "unknown"


@router.get("/version")
async def get_version():
    """获取前后端版本信息"""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    try:
        from version import __version__
        backend_version = __version__
    except ImportError:
        backend_version = "0.5.51"

    frontend_version = _read_frontend_version()

    return success_response({
        "backend": backend_version,
        "frontend": frontend_version,
        "app_name": "AlphaTerminal",
        "description": "A股/港股/美股投研终端",
        "scheduler": "running",
    })


@router.get("/info")
async def get_system_info():
    """获取系统详细信息"""
    from app.services.sectors_cache import is_ready as sectors_ready
    from app.services.news_engine import is_cache_ready as news_ready

    try:
        from version import __version__
        backend_version = __version__
    except ImportError:
        backend_version = "0.5.51"

    frontend_version = _read_frontend_version()

    return success_response({
        "backend_version": backend_version,
        "frontend_version": frontend_version,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_percent": psutil.virtual_memory().percent,
        "scheduler_status": "running",
        "sectors_cache_ready": sectors_ready(),
        "news_cache_ready": news_ready() if 'news_ready' in dir() else True,
        "uptime_seconds": int(time.time() - psutil.Process().create_time()),
    })