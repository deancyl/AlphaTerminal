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
            logger.info(f"[Scheduler] Backfill: Symbol {sym} success, items={len(rows)}")
        except Exception as e:
            logger.error(f"[Scheduler] Backfill: Symbol {sym} failed: {e}", exc_info=True)


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
        import time; time.sleep(1)
        try:
            # 回填历史K线（1年前数据，用于日K图）
            backfill_daily_history()
            logger.info("[Scheduler] 历史K线回填完成")
        except Exception as e:
            logger.error(f"[Scheduler] 历史K线回填失败: {e}", exc_info=True)
        
        # 立即触发 Sina HQ 拉取（后台线程，包含今日实时数据）
        from app.services.sentiment_engine import trigger_spot_fetch
        try:
            trigger_spot_fetch()
            logger.info("[Scheduler] Sina HQ 个股触发完成")
        except Exception as e:
            logger.error(f"[Scheduler] Sina HQ 触发失败: {e}", exc_info=True)
        
        logger.info("[Scheduler] 启动初始化完成")
    threading.Thread(target=initial_backfill, daemon=True).start()

    # 每 60 秒拉取一次实时数据（akshare 有频率限制）
    from app.services.data_fetcher import fetch_all_and_buffer
    scheduler.add_job(
        fetch_all_and_buffer,
        "interval",
        seconds=60,
        id="data_fetch",
        name="AkShareDataFetch",
        replace_existing=True,
    )
    logger.info("[Scheduler] 数据拉取任务已注册（每60秒，实时行情）")

    # 每 5 分钟刷新今日日K线（确保当日K线入库）
    def _refresh_today_daily():
        """今日日K线定时刷新"""
        from app.services.data_fetcher import fetch_china_index_history
        for sym in ["000001", "000300", "399001", "399006", "000688"]:
            try:
                rows = fetch_china_index_history(sym)
                logger.debug(f"[Scheduler] 今日K线 {sym}: {len(rows)} rows, latest={rows[-1]['date'] if rows else 'N/A'}")
            except Exception as e:
                logger.warning(f"[Scheduler] 今日K线 {sym} 刷新失败: {e}")

    scheduler.add_job(
        _refresh_today_daily,
        "interval",
        seconds=300,
        id="today_daily_refresh",
        name="TodayDailyRefresh",
        replace_existing=True,
    )
    logger.info("[Scheduler] 今日日K刷新任务已注册（每5分钟）")

    # ── 实时日K线刷新（每30秒，使用Sina HQ）──────────────────────────
    def _realtime_daily_job():
        from app.services.data_fetcher import refresh_today_from_minute
        try:
            refresh_today_from_minute()
        except Exception as e:
            logger.warning(f"[Scheduler] 实时日K刷新失败: {e}")

    scheduler.add_job(
        _realtime_daily_job,
        "interval", 
        seconds=30,
        id="realtime_daily",
        name="RealtimeDaily",
        replace_existing=True,
    )
    logger.info("[Scheduler] 实时日K刷新任务已注册（每30秒）")

    # 全市场A股定时刷新 (每10分钟抓取全量数据)
    def _fetch_all_stocks_job():
        from app.services.data_fetcher import fetch_all_china_stocks
        from app.db import upsert_all_stocks
        try:
            rows = fetch_all_china_stocks(max_pages=60)
            if rows:
                upsert_all_stocks(rows)
                logger.info(f"[Scheduler] 全市场A股刷新完成: {len(rows)} 只")
        except Exception as e:
            logger.error(f"[Scheduler] 全市场A股刷新失败: {e}", exc_info=True)

    scheduler.add_job(
        _fetch_all_stocks_job,
        "interval",
        seconds=600,
        id="all_stocks_refresh",
        name="AllStocksRefresh",
        replace_existing=True,
    )
    logger.info("[Scheduler] 全市场A股刷新任务已注册（每10分钟）")

    # 启动时立即触发一次全量抓取（后台）
    def _initial_all_stocks():
        import time as _time
        _time.sleep(3)
        _fetch_all_stocks_job()
    import threading
    threading.Thread(target=_initial_all_stocks, daemon=True).start()
    logger.info("[Scheduler] 全市场A股初始抓取已触发（后台，3秒后开始）")

    # 每 60 秒刷新全市场个股缓存（Sina HQ）
    from app.services.sentiment_engine import trigger_spot_fetch
    scheduler.add_job(
        trigger_spot_fetch,
        "interval",
        seconds=60,
        id="sentiment_fetch",
        name="SentimentFetch",
        replace_existing=True,
    )
    logger.info("[Scheduler] 全市场个股刷新任务已注册（每60秒，Sina HQ）")

    # 每 2 分钟刷新一次新闻池（多源轮询）
    from app.services.sentiment_engine import trigger_news_fetch
    scheduler.add_job(
        trigger_news_fetch,
        "interval",
        seconds=120,
        id="news_refresh",
        name="NewsRefresh",
        replace_existing=True,
    )
    logger.info("[Scheduler] 新闻刷新任务已注册（每2分钟，多源）")

    # Task 1: 每 2 分钟刷新行业板块缓存（后台 akshare，绝不在 API 线程调用）
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
        seconds=120,
        id="sectors_refresh",
        name="SectorsRefresh",
        replace_existing=True,
    )
    logger.info("[Scheduler] 行业板块刷新任务已注册（每2分钟，后台akshae）")

    # 启动时立即触发一次板块缓存（不阻塞主线程）
    def _startup_sectors():
        import time; time.sleep(3)
        _sectors_job()
        logger.info("[Scheduler] 启动时行业板块缓存已触发")
    threading.Thread(target=_startup_sectors, daemon=True).start()

    # ── P3: 每日收盘快照（15:30 执行）────────────────────────────
    def _record_portfolio_snapshots():
        """遍历所有账户，计算当日 total_asset，写入 portfolio_snapshots"""
        import datetime as _dt
        today = _dt.date.today().isoformat()
        try:
            from app.routers.portfolio import _save_snapshot_impl as _save_one
            # 动态获取所有 portfolio_id
            from app.db.database import _get_conn
            with _get_conn() as conn:
                rows = conn.execute("SELECT id FROM portfolios").fetchall()
            for (pid,) in rows:
                result = _save_one(pid)
                logger.info(f"[PortfolioSnap] pid={pid} date={today} asset={result.get('total_asset',0)}")
        except Exception as e:
            logger.error(f"[PortfolioSnap] 快照失败: {e}")

    scheduler.add_job(
        _record_portfolio_snapshots,
        "cron",
        hour=15, minute=30,
        id="portfolio_snapshot",
        name="PortfolioSnapshot",
        replace_existing=True,
    )
    logger.info("[Scheduler] 账户净值快照任务已注册（每个交易日 15:30）")

    # 启动时立即触发一次快照（非阻塞）
    def _startup_snapshot():
        import time as _t; _t.sleep(5)
        _record_portfolio_snapshots()
        logger.info("[Scheduler] 启动时账户快照已触发")
    threading.Thread(target=_startup_snapshot, daemon=True).start()

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

    # 启动时立即预热新闻缓存（非阻塞后台运行，20分钟后再由 NewsRefresh 任务接管）
    prefetch_news()


def stop_scheduler():
    """停止 APScheduler"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[Scheduler] APScheduler 已关闭")
