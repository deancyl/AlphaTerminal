"""
Debug / Diagnostics Router - Phase 3.6
"""
import logging
from datetime import datetime
from fastapi import APIRouter
from apscheduler.schedulers.background import BackgroundScheduler

from app.services.scheduler import scheduler
from app.services.news_engine import get_cached_news, is_cache_ready, _NEWS_CACHE

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/debug/scheduler")
async def debug_scheduler():
    """
    返回调度器状态 + 当前新闻缓存条数（用于排查数据滞后）
    """
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

    return {
        "scheduler_running": scheduler.running,
        "jobs": jobs,
        "news_count":   news_count,
        "news_ready":   is_cache_ready(),
        "server_time":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
