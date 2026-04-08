"""
Debug / Diagnostics Router - Phase 3.6

Phase B: 统一 API 响应格式
"""
import logging
import time
from datetime import datetime
from fastapi import APIRouter

from app.services.scheduler import scheduler
from app.services.news_engine import get_cached_news, is_cache_ready, _NEWS_CACHE

logger = logging.getLogger(__name__)

router = APIRouter()

# ── API 响应标准化工具 ─────────────────────────────────────────────────
def success_response(data, message="success"):
    """创建成功响应"""
    return {
        "code": 0,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000)
    }

def error_response(code, message, data=None):
    """创建错误响应"""
    return {
        "code": code,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000)
    }

class ErrorCode:
    SUCCESS = 0
    BAD_REQUEST = 100
    INTERNAL_ERROR = 200


@router.get("/debug/scheduler")
async def debug_scheduler():
    """
    返回调度器状态 + 当前新闻缓存条数（用于排查数据滞后）
    """
    try:
        # 调度器任务状态
        jobs = []
        if scheduler.running:
            for job in scheduler.get_jobs():
                jobs.append({
                    "id":       job.id,
                    "name":     job.name,
                    "next_run": str(job.next_run_time) if job.next_run_time else None,
                    "pending":  job.pending,
                })

        # 新闻缓存状态
        news_count = len(_NEWS_CACHE) if is_cache_ready() else 0

        return success_response({
            "scheduler_running": scheduler.running,
            "jobs": jobs,
            "news_count":   news_count,
            "news_ready":   is_cache_ready(),
            "server_time":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
    except Exception as e:
        logger.error(f"[debug_scheduler] 错误: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取调度器状态失败: {str(e)}")
