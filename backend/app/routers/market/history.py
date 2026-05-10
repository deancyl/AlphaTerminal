"""
Market History Endpoints

Price history and futures data endpoints extracted from market.py.
"""

import threading
from datetime import datetime
from fastapi import APIRouter

from app.utils.response import success_response
from .dependencies import (
    _clean_symbol,
    _inject_change_pct,
    _apply_adjustment,
    _parse_timestamp,
    MIN_KLINE_SUPPORTED,
    FREQUENCY_MAP,
    FUTURES_FREQ_MAP,
    logger,
)


router = APIRouter()


@router.get("/market/history/{symbol}")
async def market_history(
    symbol: str,
    limit: int = 300,
    period: str = "daily",
    offset: int = 0,
    trade_date: str = None,
    adjustment: str = "none",
):
    """
    获取某标的历史行情，支持多周期切换 + 懒加载分页。

    若本地数据库无该标的数据，立即触发 AkShare 穿透拉取
    （全量历史写入 SQLite），再返回给前端。

    周期与数据深度：
      daily   : 日K线，默认拉取上限 5000 条（约 20 年），可分页
      weekly : 周K线，默认上限 500 条（约 10 年），可分页
      monthly: 月K线，默认上限 300 条（约 25 年），可分页
      分钟系  : 分时/1/5/15/30/60 分钟，仅支持白名单 A 股指数

    offset : 分页偏移量（每次向后翻页 offset += limit）
    """
    clean_sym = _clean_symbol(symbol)
    from app.db import get_daily_history, get_periodic_history, get_daily_count, get_periodic_count

    chart_type = "candlestick"
    history     = []
    has_more    = False
    fetching    = False

    _NON_ASHARE = (
        clean_sym.startswith("us") or clean_sym.startswith("hk")
        or clean_sym.startswith("jp") or clean_sym.startswith("macro")
        or clean_sym in {
            "gold", "gld", "xau", "gc",
            "wti", "wtic", "cl",
            "vix", "cnhusd", "cnh", "dxy", "usdx",
            "ixic", "ndx", "spx", "dji",
            "hsi", "hk hsi",
            "n225",
        }
    )

    if _NON_ASHARE and period in ("daily", "weekly", "monthly"):
        raw_rows = get_daily_history(clean_sym, limit=limit, offset=offset)
        total    = get_daily_count(clean_sym)

        if (not raw_rows or (len(raw_rows) < 50 and offset == 0)) and offset == 0:
            def _bg_fetch():
                try:
                    from app.services.data_fetcher import fetch_us_stock_history
                    fetch_us_stock_history(clean_sym, period=period, limit=5000)
                    logger.info(f"[Market History] 后台补全 {clean_sym} 完成")
                except Exception as e:
                    logger.error(f"[Market History] 后台补全失败: {e}")
            fetching = True
            threading.Thread(target=_bg_fetch, daemon=True).start()

            try:
                from app.services.data_fetcher import fetch_us_stock_history
                sync_rows = fetch_us_stock_history(clean_sym, period=period, limit=5000)
                if sync_rows:
                    raw_rows = sync_rows
                    total = len(sync_rows)
                    fetching = False
                    logger.info(f"[Market History] 同步返回 {clean_sym}: {len(sync_rows)} 条")
            except Exception as e:
                logger.warning(f"[Market History] 同步拉取失败，回退DB: {e}")

        history  = _inject_change_pct(list(reversed(raw_rows))) if raw_rows else []
        has_more = (offset + len(raw_rows)) < total if raw_rows else False
        chart_type = "candlestick"

    elif period in FREQUENCY_MAP:
        freq = FREQUENCY_MAP[period]
        if clean_sym in MIN_KLINE_SUPPORTED:
            from app.services.data_fetcher import fetch_index_minute_history
            all_data = fetch_index_minute_history(clean_sym, limit=limit, frequency=freq, offset=offset, trade_date=trade_date)
            history  = all_data
            has_more = len(all_data) >= min(limit, 300)
            chart_type = "line"
        else:
            history = []
            chart_type = "candlestick"

    elif period == "minutely":
        if clean_sym in MIN_KLINE_SUPPORTED:
            from app.services.data_fetcher import fetch_index_minute_history
            history  = fetch_index_minute_history(clean_sym, limit=min(limit, 300), frequency=5, offset=offset)
            has_more = len(history) >= min(limit, 300)
            chart_type = "line"
        else:
            history = []
            chart_type = "line"

    elif period == "daily":
        raw_rows = get_daily_history(clean_sym, limit=limit, offset=offset)
        total    = get_daily_count(clean_sym)

        if not raw_rows and offset == 0:
            logger.info(f"[Market History] 本地无 {clean_sym} 日K，触发 AkShare 穿透…")
            fetching = True
            try:
                _INDEX_SYMBOLS = {"000001", "000300", "399001", "399006", "000688", "399005"}
                if clean_sym in _INDEX_SYMBOLS:
                    from app.services.data_fetcher import fetch_index_daily_history
                    rows = fetch_index_daily_history(clean_sym)
                else:
                    from app.services.data_fetcher import fetch_stock_history
                    rows = fetch_stock_history(clean_sym)
                if rows:
                    raw_rows = rows
                    total    = len(raw_rows)
            except Exception as e:
                logger.error(f"[Market History] AkShare 穿透失败: {e}")
            finally:
                fetching = False

        history  = _inject_change_pct(_apply_adjustment(list(reversed(raw_rows)), adjustment))
        has_more = (offset + len(raw_rows)) < total
        chart_type = "candlestick"

    elif period in ("weekly", "monthly"):
        raw_rows = get_periodic_history(clean_sym, period=period, limit=limit, offset=offset)
        total    = get_periodic_count(clean_sym, period)

        if not raw_rows and offset == 0:
            logger.info(f"[Market History] 本地无 {clean_sym} {period}K，触发穿透…")
            fetching = True
            try:
                _INDEX_SYMBOLS = {"000001", "000300", "399001", "399006", "000688", "399005"}
                if clean_sym in _INDEX_SYMBOLS:
                    from app.services.data_fetcher import fetch_index_daily_history
                    fetch_index_daily_history(clean_sym)
                else:
                    from app.services.data_fetcher import fetch_stock_history
                    fetch_stock_history(clean_sym)
                raw_rows = get_periodic_history(clean_sym, period=period, limit=limit, offset=offset)
                total    = get_periodic_count(clean_sym, period)
            except Exception as e:
                logger.error(f"[Market History] 穿透失败: {e}")

        history  = _inject_change_pct(_apply_adjustment(list(reversed(raw_rows)), adjustment))
        has_more = (offset + len(raw_rows)) < total
        chart_type = "candlestick"

    else:
        from app.db import get_price_history
        history    = get_price_history(clean_sym, limit=limit)
        chart_type = "candlestick"

    result = {
        "symbol":     clean_sym,
        "period":     period,
        "chart_type": chart_type,
        "has_more":   has_more,
        "offset":     offset,
        "fetching":   fetching,
        "timestamp":  datetime.now().isoformat(),
        "history":    history,
    }
    return success_response(result)


@router.get("/market/futures/{symbol}")
async def futures_history(
    symbol: str,
    period: str = "daily",
    limit: int = 2000,
):
    """
    期货历史行情 - 直连 AkShare Sina，无数据库层。

    周期：
      daily   日K（主力连续合约，symbol=IF0/RB0/...）
      1min/5min/15min/30min/60min  分钟K（当前主力合约）

    返回格式：
      { symbol, period, history: [{date, open, high, low, close, volume, hold}, ...] }

    hold（持仓量）是期货核心指标，代表多空双方未平仓合约数。
    """
    import akshare as ak

    clean_sym = symbol.strip().lower()

    if period == "daily":
        try:
            df = ak.futures_zh_daily_sina(symbol=clean_sym.upper())
            if df is None or df.empty:
                return {"symbol": clean_sym, "period": period, "history": []}
            df = df.tail(limit)
            df_work = df.copy()
            df_work['date'] = df_work['date'].astype(str)
            df_work['open'] = df_work['open'].apply(lambda x: round(float(x), 2))
            df_work['high'] = df_work['high'].apply(lambda x: round(float(x), 2))
            df_work['low'] = df_work['low'].apply(lambda x: round(float(x), 2))
            df_work['close'] = df_work['close'].apply(lambda x: round(float(x), 2))
            df_work['volume'] = df_work['volume'].apply(lambda x: int(x) if x == x else 0)
            df_work['hold'] = df_work['hold'].apply(lambda x: int(x) if x == x else 0)
            rows = df_work[['date', 'open', 'high', 'low', 'close', 'volume', 'hold']].to_dict('records')
            return {"symbol": clean_sym, "period": period, "history": list(reversed(rows))}
        except Exception as e:
            logger.error(f"[Futures] daily failed {clean_sym}: {e}")
            return success_response({"symbol": clean_sym, "period": period, "history": []}, f"获取失败: {e}")

    elif period in FUTURES_FREQ_MAP:
        freq = FUTURES_FREQ_MAP[period]
        try:
            df = ak.futures_zh_minute_sina(symbol=clean_sym.upper(), period=str(freq))
            if df is None or df.empty:
                return {"symbol": clean_sym, "period": period, "history": []}
            df = df.tail(limit)
            df_work = df.copy()
            df_work['date'] = df_work['datetime'].astype(str)
            df_work['open'] = df_work['open'].apply(lambda x: round(float(x), 2))
            df_work['high'] = df_work['high'].apply(lambda x: round(float(x), 2))
            df_work['low'] = df_work['low'].apply(lambda x: round(float(x), 2))
            df_work['close'] = df_work['close'].apply(lambda x: round(float(x), 2))
            df_work['volume'] = df_work['volume'].apply(lambda x: int(x) if x == x else 0)
            df_work['hold'] = df_work['hold'].apply(lambda x: int(x) if x == x else 0)
            df_work['timestamp'] = df_work['date'].apply(_parse_timestamp)
            rows = df_work[['date', 'open', 'high', 'low', 'close', 'volume', 'hold', 'timestamp']].to_dict('records')
            return {"symbol": clean_sym, "period": period, "history": rows}
        except Exception as e:
            logger.error(f"[Futures] minute failed {clean_sym}: {e}")
            return success_response({"symbol": clean_sym, "period": period, "history": []}, f"获取失败: {e}")

    else:
        return {"symbol": clean_sym, "period": period, "history": []}