"""
APScheduler 调度器 - Phase 3 真实缓冲写入
"""
import logging
import fcntl
import os
from apscheduler.schedulers.background import BackgroundScheduler
from app.db import flush_buffer_to_realtime
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# ── File-based Process Lock (prevents multi-worker conflicts) ────────────────
LOCK_FILE_PATH = "/tmp/alphaterminal_scheduler.lock"
_lock_file = None

def acquire_scheduler_lock():
    """Acquire exclusive lock for scheduler (prevents multi-worker conflicts)"""
    global _lock_file
    try:
        _lock_file = open(LOCK_FILE_PATH, 'w')
        fcntl.flock(_lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        logger.info("[Scheduler] Acquired exclusive lock - this worker will run polling jobs")
        return True
    except (IOError, OSError):
        logger.info("[Scheduler] Another worker holds the lock - this worker will skip polling jobs")
        if _lock_file:
            _lock_file.close()
            _lock_file = None
        return False

def release_scheduler_lock():
    """Release scheduler lock"""
    global _lock_file
    if _lock_file:
        try:
            fcntl.flock(_lock_file.fileno(), fcntl.LOCK_UN)
            _lock_file.close()
            os.remove(LOCK_FILE_PATH)
        except:
            pass
        _lock_file = None

scheduler = BackgroundScheduler()

# 历史K线需要回填的指数列表
HISTORY_SYMBOLS = ["000001", "000300", "399001", "399006", "000688"]

# 内存监控配置
MEMORY_CHECK_INTERVAL = 300  # 每5分钟检查一次
MEMORY_THRESHOLD_MB = 512    # 内存阈值（MB），超过则强制gc

# ── 延迟导入工具（复用 macro.py 的模式）────────────────────────────
_akshare_module = None
_pandas_module = None
_macro_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="macro_poll_")


def _get_ak():
    """延迟加载akshare"""
    global _akshare_module
    if _akshare_module is None:
        import akshare as ak
        _akshare_module = ak
    return _akshare_module


def _get_pd():
    """延迟加载pandas"""
    global _pandas_module
    if _pandas_module is None:
        import pandas as pd
        _pandas_module = pd
    return _pandas_module


def _safe_float(val):
    """安全地将值转为float，处理None/NaN"""
    if val is None:
        return None
    pd = _get_pd()
    try:
        if pd.isna(val):
            return None
        return float(val)
    except (TypeError, ValueError):
        return None


def _safe_strftime(val, fmt='%Y年%m月份'):
    """安全地格式化日期"""
    if val is None:
        return None
    pd = _get_pd()
    try:
        if pd.isna(val):
            return None
        return val.strftime(fmt)
    except (AttributeError, TypeError):
        return str(val) if val else None


def flush_write_buffer():
    """将 write_buffer 批量刷入 market_data_realtime"""
    try:
        flush_buffer_to_realtime()
        logger.debug("[Scheduler] write_buffer 已刷入 market_data_realtime")
    except Exception as e:
        logger.error(f"[Scheduler] flush 失败: {e}", exc_info=True)


def _broadcast_realtime_ticks():
    """
    读取 market_data_realtime 最新数据，通过 ws_manager 广播 tick。
    使用 run_in_executor 桥接同步 → 异步，不阻塞调度器主循环。
    """
    try:
        from app.db import get_latest_prices
        from app.services.ws_manager import ws_manager
        import asyncio

        rows = get_latest_prices(limit=200)
        if not rows:
            return

        def _sync_broadcast():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                for r in rows:
                    sym = str(r.get("symbol", ""))
                    price      = float(r.get("price") or 0)
                    change_pct = float(r.get("change_pct") or 0)
                    prev       = price / (1 + change_pct / 100) if change_pct != -100 else price
                    chg        = round(price - prev, 3)
                    tick = {
                        "type":      "tick",  # 消息类型标识（协议一致性）
                        "symbol":    sym,
                        "name":      r.get("name", ""),
                        "price":     price,
                        "chg":       chg,
                        "chg_pct":   change_pct,
                        "volume":    float(r.get("volume") or 0),
                        "amount":    float(r.get("amount") or 0),
                        "turnover":  float(r.get("turnover") or 0),
                        "market":    r.get("market", ""),
                        "data_type": r.get("data_type", ""),
                        "timestamp": int(r.get("timestamp") or 0),
                    }
                    loop.run_until_complete(ws_manager.broadcast_tick(sym, tick))
                logger.debug(f"[WS-Broadcast] 推送 {len(rows)} 条 tick 到 {ws_manager.total()} 个连接")
            finally:
                loop.close()

        import threading
        t = threading.Thread(target=_sync_broadcast, daemon=True)
        t.start()
    except Exception as e:
        logger.warning(f"[Scheduler] WS 广播异常（不阻塞主循环）: {e}")


def flush_write_buffer_and_broadcast():
    """
    Task 5: 将 write_buffer 刷入 market_data_realtime，
    然后立即通过 ws_manager 广播 tick（后台线程，不阻塞调度器）。
    """
    try:
        flush_buffer_to_realtime()
        logger.debug("[Scheduler] write_buffer 已刷入 market_data_realtime")
    except Exception as e:
        logger.error(f"[Scheduler] flush 失败: {e}", exc_info=True)
        return

    # 广播放在后台，不阻塞调度器
    _broadcast_realtime_ticks()


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
    init_tables()

    is_primary_worker = acquire_scheduler_lock()
    
    if not is_primary_worker:
        logger.info("[Scheduler] Skipping job registration (secondary worker)")
        return

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
        
        # Mark backend as ready
        from app.routers.health import set_backend_ready
        set_backend_ready(True)
        logger.info("[Scheduler] 启动初始化完成")
    threading.Thread(target=initial_backfill, daemon=True).start()

    # 每 30 秒拉取一次实时数据（akshare 有频率限制）
    from app.services.data_fetcher import fetch_all_and_buffer
    scheduler.add_job(
        fetch_all_and_buffer,
        "interval",
        seconds=30,
        id="data_fetch",
        name="AkShareDataFetch",
        replace_existing=True,
    )
    logger.info("[Scheduler] 数据拉取任务已注册（每30秒，实时行情）")

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

    # ── 实时日K线刷新（每10秒，使用Sina HQ）──────────────────────────
    def _realtime_daily_job():
        from app.services.data_fetcher import refresh_today_from_minute, refresh_period_klines
        try:
            refresh_today_from_minute()
            refresh_period_klines()  # 周线/月线同步刷新
        except Exception as e:
            logger.warning(f"[Scheduler] 实时K线刷新失败: {e}")

    scheduler.add_job(
        _realtime_daily_job,
        "interval", 
        seconds=10,
        id="realtime_daily",
        name="RealtimeDaily",
        replace_existing=True,
    )
    logger.info("[Scheduler] 实时日K刷新任务已注册（每10秒）")

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

    # Task: 每 60 秒轮询外汇数据并写入全局缓存
    def _forex_polling_job():
        """后台轮询外汇数据并写入全局缓存"""
        from app.services.fetchers.forex_fetcher import forex_fetcher
        from app.services.data_cache import get_cache
        from datetime import datetime
        import asyncio
        
        try:
            cache = get_cache()
            
            # Fetch spot quotes (sync wrapper for async)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                quotes = loop.run_until_complete(forex_fetcher.get_spot_quotes())
                
                # Build cross-rate matrix data
                currency_list = ["USD", "EUR", "GBP", "JPY", "CNY", "AUD", "CAD", "CHF"]
                cfets_rmb = loop.run_until_complete(forex_fetcher.get_cfets_spot())
                cfets_cross = loop.run_until_complete(forex_fetcher.get_cfets_crosses())
                
                from decimal import Decimal
                rates_dict = {}
                for q in quotes:
                    symbol = q.get("symbol", "")
                    latest = q.get("latest")
                    if latest and len(symbol) == 6:
                        from_curr = symbol[:3]
                        to_curr = symbol[3:]
                        rates_dict[f"{from_curr}/{to_curr}"] = Decimal(str(latest))
                
                for q in cfets_rmb:
                    pair = q.get("pair", "")
                    mid = q.get("mid")
                    if mid and "/" in pair:
                        rates_dict[pair] = Decimal(str(mid))
                
                for q in cfets_cross:
                    pair = q.get("pair", "")
                    mid = q.get("mid")
                    if mid and "/" in pair:
                        rates_dict[pair] = Decimal(str(mid))
                
                # Build matrix
                matrix = []
                for base_curr in currency_list:
                    row_rates = []
                    for quote_curr in currency_list:
                        if base_curr == quote_curr:
                            row_rates.append({"rate": 1.0, "is_base": True})
                        else:
                            rate = forex_fetcher.calculate_cross_rate(base_curr, quote_curr, rates_dict)
                            direct_key = f"{base_curr}/{quote_curr}"
                            row_rates.append({
                                "rate": float(rate) if rate else None,
                                "is_base": False,
                                "is_calculated": direct_key not in rates_dict if rate else False
                            })
                    matrix.append({"base": base_curr, "rates": row_rates})
            finally:
                loop.close()
            
            # Cache spot quotes
            if quotes:
                cache.set("forex:spot_quotes", {
                    "quotes": quotes,
                    "last_update_time": datetime.now().isoformat(),
                    "status": "ready"
                }, ttl=120)
            
            # Cache matrix
            if matrix:
                cache.set("forex:matrix", {
                    "matrix": matrix,
                    "currencies": currency_list,
                    "last_update_time": datetime.now().isoformat(),
                    "status": "ready"
                }, ttl=120)
            
            logger.info(f"[Scheduler] Forex polling complete: {len(quotes) if quotes else 0} quotes, matrix {len(matrix)}x{len(matrix[0]['rates']) if matrix else 0}")
        except Exception as e:
            logger.error(f"[Scheduler] Forex polling failed: {e}", exc_info=True)

    scheduler.add_job(
        _forex_polling_job,
        "interval",
        seconds=60,
        id="forex_polling",
        name="ForexPolling",
        replace_existing=True,
    )
    logger.info("[Scheduler] 外汇轮询任务已注册（每60秒）")

    # 启动时立即触发一次外汇数据预热（不阻塞主线程）
    def _startup_forex():
        import time; time.sleep(2)
        _forex_polling_job()
        logger.info("[Scheduler] 启动时外汇数据预热已触发")
    threading.Thread(target=_startup_forex, daemon=True).start()

    # Task: 每 3600 秒轮询宏观数据并写入全局缓存
    scheduler.add_job(
        _macro_polling_job,
        "interval",
        seconds=3600,
        id="macro_polling",
        name="MacroPolling",
        replace_existing=True,
    )
    logger.info("[Scheduler] 宏观轮询任务已注册（每3600秒）")

    # 启动时立即触发一次宏观数据预热（不阻塞主线程）
    def _startup_macro():
        import time; time.sleep(3)
        _macro_polling_job()
        logger.info("[Scheduler] 启动时宏观数据预热已触发")
    threading.Thread(target=_startup_macro, daemon=True).start()

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

    # 每 10 秒将缓冲写入主表 + WS 广播
    scheduler.add_job(
        flush_write_buffer_and_broadcast,
        "interval",
        seconds=10,
        id="flush_write_buffer",
        name="WriteBufferFlush",
        replace_existing=True,
    )
    # 内存监控任务（每5分钟检查一次）
    scheduler.add_job(
        _memory_monitor,
        "interval",
        seconds=MEMORY_CHECK_INTERVAL,
        id="memory_monitor",
        name="MemoryMonitor",
        replace_existing=True,
    )
    
    scheduler.add_job(
        _cache_cleanup_job,
        "interval",
        seconds=300,
        id="cache_cleanup",
        name="CacheCleanup",
        replace_existing=True,
    )
    logger.info("[Scheduler] Cache cleanup job registered (every 5 minutes)")
    
    scheduler.start()
    logger.info("[Scheduler] APScheduler 已启动")

    # 启动时立即预热新闻缓存（非阻塞后台运行，20分钟后再由 NewsRefresh 任务接管）
    prefetch_news()


def _cache_cleanup_job():
    """Periodic cache cleanup to prevent memory leaks"""
    from app.services.data_cache import get_cache
    try:
        cache = get_cache()
        removed = cache.cleanup_expired()
        if removed > 0:
            logger.info(f"[Scheduler] Cache cleanup: removed {removed} expired entries")
    except Exception as e:
        logger.error(f"[Scheduler] Cache cleanup failed: {e}")


async def run_initial_data_fetch():
    """Blocking startup: Fetch core data before accepting HTTP requests"""
    import asyncio
    
    logger.info("[Startup] Starting blocking data fetch...")
    
    loop = asyncio.get_running_loop()
    
    try:
        await loop.run_in_executor(None, _forex_polling_job)
        logger.info("[Startup] Forex data fetched")
    except Exception as e:
        logger.error(f"[Startup] Forex fetch failed: {e}")
    
    try:
        await loop.run_in_executor(None, _macro_polling_job)
        logger.info("[Startup] Macro data fetched")
    except Exception as e:
        logger.error(f"[Startup] Macro fetch failed: {e}")
    
    logger.info("[Startup] Blocking data fetch complete")


def _memory_monitor():
    """内存监控：定期检查和清理"""
    try:
        import gc
        import psutil
        process = psutil.Process()
        mem_mb = process.memory_info().rss / 1024 / 1024
        
        if mem_mb > MEMORY_THRESHOLD_MB:
            logger.warning(f"[MemoryMonitor] 内存使用 {mem_mb:.1f}MB 超过阈值 {MEMORY_THRESHOLD_MB}MB，执行强制gc")
            gc.collect()
            # 再次检查
            new_mem_mb = process.memory_info().rss / 1024 / 1024
            logger.info(f"[MemoryMonitor] 强制gc后内存: {new_mem_mb:.1f}MB (释放 {mem_mb - new_mem_mb:.1f}MB)")
        else:
            logger.debug(f"[MemoryMonitor] 内存使用正常: {mem_mb:.1f}MB")
    except Exception as e:
        logger.warning(f"[MemoryMonitor] 监控异常: {e}")


def _macro_polling_job():
    """后台轮询宏观数据并写入全局缓存"""
    import asyncio
    from app.services.data_cache import get_cache
    
    try:
        cache = get_cache()
        ak = _get_ak()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        def fetch_sync():
            try:
                pd = _get_pd()
                
                gdp_df = ak.macro_china_gdp()
                cpi_df = ak.macro_china_cpi()
                ppi_df = ak.macro_china_ppi()
                pmi_df = ak.macro_china_pmi_yearly()
                m2_df = ak.macro_china_m2_yearly()
                social_df = ak.macro_china_shrzgm()
                industrial_df = ak.macro_china_gyzjz()
                unemployment_df = ak.macro_china_urban_unemployment()
                # calendar_df = ak.macro_china_event_report()  # Function removed from akshare
                
                return {
                    'gdp': gdp_df, 'cpi': cpi_df, 'ppi': ppi_df,
                    'pmi': pmi_df, 'm2': m2_df, 'social': social_df,
                    'industrial': industrial_df, 'unemployment': unemployment_df,
                    'calendar': None  # No calendar data available
                }
            except Exception as e:
                logger.error(f"[MacroPolling] Fetch error: {e}")
                return None
        
        data = loop.run_in_executor(_macro_executor, fetch_sync)
        results = loop.run_until_complete(data)
        loop.close()
        
        if results is None:
            logger.error("[MacroPolling] No data fetched")
            return
        
        dashboard = {}
        
        def process_df(df, limit, columns, rename_map):
            if df is None or len(df) == 0:
                return None
            df = df.head(limit)
            df_work = df[columns].copy()
            for old_col, new_col in rename_map.items():
                if old_col in df_work.columns:
                    if new_col in ('month', 'quarter'):
                        df_work[new_col] = df_work[old_col].apply(lambda x: str(x) if x is not None else None)
                    else:
                        df_work[new_col] = df_work[old_col].apply(_safe_float)
            df_work = df_work.drop(columns=[c for c in columns if c not in rename_map.values()])
            return df_work.to_dict('records')
        
        latest_gdp = results['gdp'].iloc[0] if len(results['gdp']) > 0 else None
        latest_cpi = results['cpi'].iloc[0] if len(results['cpi']) > 0 else None
        latest_ppi = results['ppi'].iloc[0] if len(results['ppi']) > 0 else None
        latest_pmi = results['pmi'].iloc[0] if len(results['pmi']) > 0 else None
        latest_m2 = results['m2'].iloc[0] if len(results['m2']) > 0 else None
        
        dashboard["overview"] = {
            "gdp": {
                "quarter": _safe_strftime(latest_gdp['季度']) if latest_gdp is not None else None,
                "value": _safe_float(latest_gdp['国内生产总值-绝对值']) if latest_gdp is not None else None,
                "yoy": _safe_float(latest_gdp['国内生产总值-同比增长']) if latest_gdp is not None else None,
            },
            "cpi": {
                "month": _safe_strftime(latest_cpi['月份'], '%Y年%m月') if latest_cpi is not None else None,
                "yoy": _safe_float(latest_cpi['全国-同比增长']) if latest_cpi is not None else None,
                "mom": _safe_float(latest_cpi['全国-环比增长']) if latest_cpi is not None else None,
            },
            "ppi": {
                "month": _safe_strftime(latest_ppi['月份'], '%Y年%m月') if latest_ppi is not None else None,
                "yoy": _safe_float(latest_ppi['当月同比增长']) if latest_ppi is not None else None,
            },
            "pmi": {
                "month": str(latest_pmi['日期']) if latest_pmi is not None else None,
                "value": _safe_float(latest_pmi['今值']) if latest_pmi is not None else None,
            },
            "m2": {
                "month": str(latest_m2['日期']) if latest_m2 is not None else None,
                "yoy": _safe_float(latest_m2['今值']) if latest_m2 is not None else None,
            },
        }
        
        calendar_items = []
        if results['calendar'] is not None and len(results['calendar']) > 0:
            for _, row in results['calendar'].head(20).iterrows():
                calendar_items.append({
                    "date": str(row.get('日期', '')),
                    "event": str(row.get('事件', '')),
                    "importance": "high" if "重要" in str(row.get('重要性', '')) else "normal"
                })
        dashboard["calendar"] = calendar_items
        
        dashboard["gdp"] = {
            "data": process_df(results['gdp'], 20, ['季度', '国内生产总值-绝对值', '国内生产总值-同比增长'],
                               {'季度': 'quarter', '国内生产总值-绝对值': 'gdp_absolute', '国内生产总值-同比增长': 'gdp_yoy'}),
            "unit": "亿元", "frequency": "季度"
        }
        
        dashboard["cpi"] = {
            "data": process_df(results['cpi'], 24, ['月份', '全国-当月', '全国-同比增长', '全国-环比增长'],
                               {'月份': 'month', '全国-当月': 'nation_current', '全国-同比增长': 'nation_yoy', '全国-环比增长': 'nation_mom'}),
            "unit": "", "frequency": "月度"
        }
        
        dashboard["ppi"] = {
            "data": process_df(results['ppi'], 24, ['月份', '当月', '当月同比增长'],
                               {'月份': 'month', '当月': 'current', '当月同比增长': 'yoy'}),
            "unit": "", "frequency": "月度"
        }
        
        dashboard["pmi"] = {
            "data": process_df(results['pmi'], 24, ['日期', '今值'],
                               {'日期': 'month', '今值': 'manufacturing_index'}),
            "unit": "", "frequency": "月度"
        }
        
        dashboard["m2"] = {
            "data": process_df(results['m2'], 24, ['日期', '今值'],
                               {'日期': 'month', '今值': 'm2_yoy'}),
            "unit": "%", "frequency": "月度"
        }
        
        dashboard["social_financing"] = {
            "data": process_df(results['social'], 24, ['月份', '社会融资规模增量'],
                               {'月份': 'month', '社会融资规模增量': 'total'}),
            "unit": "亿元", "frequency": "月度"
        }
        
        dashboard["industrial_production"] = {
            "data": process_df(results['industrial'], 24, ['月份', '同比增长'],
                               {'月份': 'month', '同比增长': 'yoy'}),
            "unit": "%", "frequency": "月度"
        }
        
        dashboard["unemployment"] = {
            "data": process_df(results['unemployment'], 24, ['date', 'value'],
                               {'date': 'month', 'value': 'rate'}),
            "unit": "%", "frequency": "月度"
        }
        
        dashboard["last_update"] = datetime.now().isoformat()
        dashboard["status"] = "ready"
        
        cache.set("macro:dashboard", dashboard, ttl=3600)
        logger.info(f"[MacroPolling] Complete, cached macro:dashboard with {len(dashboard)} indicators")
        
    except Exception as e:
        logger.error(f"[MacroPolling] Failed: {e}", exc_info=True)


def stop_scheduler():
    """停止 APScheduler"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
    release_scheduler_lock()
    logger.info("[Scheduler] APScheduler stopped and lock released")
