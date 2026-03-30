"""
APScheduler 调度器 - Phase 3 真实缓冲写入
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from app.db import flush_buffer_to_realtime

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def flush_write_buffer():
    """将 write_buffer 批量刷入 market_data_realtime"""
    try:
        count = flush_buffer_to_realtime()
        if count > 0:
            logger.info(f"[Scheduler] 已将 {count} 条行情从 write_buffer 刷入 market_data_realtime")
        else:
            logger.debug("[Scheduler] write_buffer 为空，无数据需刷入")
    except Exception as e:
        logger.error(f"[Scheduler] flush 失败: {e}", exc_info=True)


def start_scheduler():
    """启动 APScheduler"""
    from app.db import init_tables
    init_tables()  # 保证表已创建

    # 每 3 分钟拉取一次实时数据（akshare 有频率限制）
    from app.services.data_fetcher import fetch_all_and_buffer
    scheduler.add_job(
        fetch_all_and_buffer,
        "interval",
        seconds=180,
        id="data_fetch",
        name="AkShareDataFetch",
        replace_existing=True,
    )
    logger.info("[Scheduler] 数据拉取任务已注册（每3分钟）")

    # 每 10 秒将缓冲写入主表
    scheduler.add_job(
        flush_write_buffer,
        "interval",
        seconds=10,
        id="flush_write_buffer",
        name="WriteBufferFlush",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("[Scheduler] APScheduler 已启动")


def stop_scheduler():
    """停止 APScheduler"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[Scheduler] APScheduler 已关闭")
