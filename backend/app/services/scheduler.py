"""
APScheduler 调度器 - Phase 3 真实缓冲写入
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from app.db import flush_buffer_to_realtime

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()

# 历史K线需要回填的指数列表
HISTORY_SYMBOLS = ["000001", "000300", "399001", "399006", "000688"]


def flush_write_buffer():
    """将 write_buffer 批量刷入 market_data_realtime"""
    try:
        flush_buffer_to_realtime()
        logger.debug("[Scheduler] write_buffer 已刷入 market_data_realtime")
    except Exception as e:
        logger.error(f"[Scheduler] flush 失败: {e}", exc_info=True)


def backfill_daily_history():
    """每日一次：回填A股指数日K线历史（写入 market_data_daily）"""
    from app.services.data_fetcher import fetch_china_index_history
    for sym in HISTORY_SYMBOLS:
        try:
            rows = fetch_china_index_history(sym)
            logger.info(f"[Scheduler] {sym} 日K回填完成: {len(rows)} 条")
        except Exception as e:
            logger.error(f"[Scheduler] {sym} 日K回填失败: {e}", exc_info=True)


def prefetch_news():
    """启动时预热：后台刷新新闻缓存池"""
    from app.services.news_engine import refresh_news_cache
    try:
        refresh_news_cache(background=True)
        logger.info("[Scheduler] 新闻缓存预热任务已触发（后台运行）")
    except Exception as e:
        logger.error(f"[Scheduler] 新闻预热失败: {e}", exc_info=True)


def start_scheduler():
    """启动 APScheduler"""
    from app.db import init_tables
    init_tables()  # 保证表已创建

    # 启动时：先从 SQLite 加载历史缓存 + 新闻预热 + 直接灌 china_all 备用数据
    import threading
    def initial_backfill():
        import time; time.sleep(2)
        # 直接触发 Sina HQ 拉取（后台线程）
        # 注意：新闻由 lifespan 触发的 refresh_news_cache 统一管理，不在此处重复触发
        from app.services.sentiment_engine import trigger_spot_fetch
        trigger_spot_fetch()
        logger.info("[Scheduler] 启动完成，Sina HQ 个股已触发")
    threading.Thread(target=initial_backfill, daemon=True).start()

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

    # 每 3 分钟刷新全市场个股缓存（Sina HQ）
    from app.services.sentiment_engine import trigger_spot_fetch
    scheduler.add_job(
        trigger_spot_fetch,
        "interval",
        seconds=180,
        id="sentiment_fetch",
        name="SentimentFetch",
        replace_existing=True,
    )
    logger.info("[Scheduler] 全市场个股刷新任务已注册（每3分钟，Sina HQ）")

    # 每 20 分钟刷新一次新闻池（多源轮询）
    from app.services.sentiment_engine import trigger_news_fetch
    scheduler.add_job(
        trigger_news_fetch,
        "interval",
        seconds=20 * 60,
        id="news_refresh",
        name="NewsRefresh",
        replace_existing=True,
    )
    logger.info("[Scheduler] 新闻刷新任务已注册（每20分钟，多源）")

    # Task 1: 每 5 分钟刷新行业板块缓存（后台 akshare，绝不在 API 线程调用）
    def _sectors_job():
        from app.services.sectors_cache import fetch_and_cache_sectors
        try:
            fetch_and_cache_sectors()
            logger.info("[Scheduler] 行业板块缓存已更新")
        except Exception as e:
            logger.error(f"[Scheduler] 行业板块刷新失败: {e}", exc_info=True)

    scheduler.add_job(
        _sectors_job,
        "interval",
        seconds=300,
        id="sectors_refresh",
        name="SectorsRefresh",
        replace_existing=True,
    )
    logger.info("[Scheduler] 行业板块刷新任务已注册（每5分钟，后台akshae）")

    # 启动时立即触发一次板块缓存（不阻塞主线程）
    def _startup_sectors():
        import time; time.sleep(3)
        _sectors_job()
        logger.info("[Scheduler] 启动时行业板块缓存已触发")
    threading.Thread(target=_startup_sectors, daemon=True).start()

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
