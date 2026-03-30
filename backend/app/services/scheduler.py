"""
APScheduler 调度器骨架 - Phase 2 占位实现
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def flush_write_buffer():
    """
    [占位任务] 定期将 write_buffer 表批量写入 market_data
    Phase 2 阶段：仅打印日志，不操作 SQLite
    """
    logger.info("[Scheduler] Buffer flushed (placeholder)")


def start_scheduler():
    """启动 APScheduler"""
    # 每 30 秒执行一次 buffer flush
    scheduler.add_job(
        flush_write_buffer,
        "interval",
        seconds=30,
        id="flush_write_buffer",
        name="WriteBufferFlush",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("[Scheduler] APScheduler 已启动（占位模式）")


def stop_scheduler():
    """停止 APScheduler"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[Scheduler] APScheduler 已关闭")
