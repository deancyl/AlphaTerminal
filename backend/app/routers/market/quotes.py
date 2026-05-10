"""
Quote-related endpoints extracted from market.py
"""
import logging
import re
import time
from datetime import datetime
from fastapi import APIRouter
import httpx

from app.db import get_latest_prices, get_price_history, get_daily_history
from app.services.fetchers import FetcherFactory
from app.services.sentiment_engine import SpotCache
from app.services.quote_source import get_quote_with_fallback_async
from app.utils.response import success_response, error_response, ErrorCode


logger = logging.getLogger(__name__)
router = APIRouter()


# ── Helper functions (copied from market.py) ─────────────────────────────────

def _normalize_symbol(raw: str) -> str:
    """
    将各种前端传入格式统一为带市场前缀的规范 symbol。
    例如: '000001' → 'sh000001', 'sh000001' → 'sh000001', 'NDX' → 'usNDX'
    """
    s = raw.strip()
    # 已知美股（无前缀形式，如 'ndx'）
    if s.upper() in ('NDX', 'SPX', 'DJI'):
        return 'us' + s.upper()
    # 已知日经
    if s.upper() in ('N225', 'NI225', 'NIKKEI'):
        return 'jpN225'
    # 已知港股
    if s.upper() in ('HSI',):
        return 'hkHSI'
    # 已知宏观（无前缀）
    if s.upper() in ('GOLD', 'WTI', 'VIX'):
        return s.upper()
    # CNH/USD 特殊处理：保留 removeprefix 风格，s.upper() 用于比较
    upper_s = s.upper()
    if upper_s == 'CNHUSD':
        return 'CNHUSD'
    if upper_s.startswith('CNH'):
        suffix = upper_s[len('CNH'):]
        if suffix.isdigit() or suffix.startswith('USD'):
            return 'CNHUSD'
    # 去掉 sh/sz/hk/us/jp 前缀（仅去掉头部前缀，用 removeprefix 更安全）
    clean = s.lower()
    for pfx in ('sh', 'sz', 'hk', 'us', 'jp'):
        if clean.startswith(pfx):
            clean = clean[len(pfx):]
            break
    # A股数字段判断：6开头→上海；其余（0/3开头）→深圳
    # 特殊：A股指数000001/000300/000688 → 上海；399001/399006 → 深圳
    if clean.isdigit():
        if clean.startswith('6') or clean in ('000001', '000300', '000688'):
            return 'sh' + clean
        if clean.startswith(('0', '2', '3')):
            return 'sz' + clean
        # 8xx → 北交所，本项目暂不处理
        return 'sz' + clean
    return s


def _unprefix(raw: str) -> str:
    """去掉 sh/sz/hk/us/jp 前缀，用于查询 market_data_realtime（该表存无前缀 symbol）。"""
    s = str(raw).strip()
    for p in ('sh', 'sz', 'hk', 'us', 'jp', 'SH', 'SZ', 'HK', 'US', 'JP'):
        if s.startswith(p):
            return s[len(p):]
    return s


# ═════════════════════════════════════════════════════════════════════════════
# Endpoint 1: Basic Quote (lines 758-785)
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/market/quote/{symbol}")
async def market_quote(symbol: str):
    """
    轻量实时行情（专用于高频轮询，不含历史数据）
    返回：最新价、涨跌额、涨跌幅、成交量、成交额、振幅、换手率
    """
    norm = _normalize_symbol(symbol)
    rows = get_price_history(_unprefix(norm), limit=2)  # 最新+昨日（realtime表存无前缀）
    if not rows:
        return success_response(None, 'no data')
    latest = rows[0]  # DESC，最新在前
    prev   = rows[1] if len(rows) > 1 else latest
    close  = float(latest.get('close') or 0)
    prev_c = float(prev.get('close') or close)
    chg    = close - prev_c
    chg_pct = (chg / prev_c * 100) if prev_c else 0
    return success_response({
        'symbol':       norm,
        'price':        close,
        'change':       round(chg, 3),
        'change_pct':   round(chg_pct, 2),
        'volume':       float(latest.get('volume') or 0),
        'amount':       float(latest.get('amount') or 0),
        'amplitude':    round((float(latest.get('high') or 0) - float(latest.get('low') or 0)) / prev_c * 100, 2) if latest.get('high') and latest.get('low') and prev_c and prev_c != 0 else 0,
        'turnover_rate': float(latest.get('turnover_rate') or 0),
        'timestamp':     datetime.now().isoformat(),
    })


# ═════════════════════════════════════════════════════════════════════════════
# Endpoint 2: Detailed Quote (lines 1341-1521)
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/market/quote_detail/{symbol}")
async def market_quote_detail(symbol: str):
    """
    综合报价面板数据（模块一~四合一接口）。

    返回字段含以下模块（部分字段需数据库有历史数据才能计算，
    无数据时返回 null 而非报错，保证面板降级可用）：

    Module 1 - 基础行情与估值：
      name, symbol, price, change, change_pct, volume, amount,
      open, high, low, close,
      amplitude, turnover_rate,
      pe_ttm, pb,                       # 无数据→null
      returns_5d, returns_20d, returns_60d, returns_ytd,  # 无数据→null
      high_52w, low_52w, high_52w_date, low_52w_date,    # 无数据→null

    Module 2 - 市场情绪（仅指数）：
      advance_count, decline_count, unchanged_count,  # 暂无→null
      advance_rate,                                  # 涨家数占比

    Module 3 - 资金流向（暂无数据源→全 null，预留结构）：
      fund_main_net, fund_main_in, fund_main_out,
      fund_huge_in, fund_huge_out,   # 超大单
      fund_big_in,  fund_big_out,    # 大单
      fund_medium_in, fund_medium_out, # 中单
      fund_small_in, fund_small_out   # 小单

    Module 4 - 板块联动（暂无数据源→全 null，预留结构）：
      industry, industry_change_pct,
      concepts: [{name, change_pct}, ...]
    """
    norm = _normalize_symbol(symbol)

    # ── 基础实时行情（market_data_realtime 存无前缀 symbol，用 _unprefix 查）──
    db_sym = _unprefix(norm)   # 'sh000001' → '000001'
    rows_latest = get_latest_prices([db_sym]) if callable(get_latest_prices) else []
    w = rows_latest[0] if rows_latest else {}

    # 修复：market_data_realtime 表的 price 字段即为当前价（不是 'index'）
    price      = float(w.get('price') or 0.0)
    change_pct = float(w.get('change_pct') or 0.0)
    change_val = round(price * change_pct / 100, 3) if price and change_pct else 0.0
    volume     = float(w.get('volume') or 0.0) or None
    status     = w.get('status') or ''
    market     = w.get('market') or 'AShare'

    # ── 历史 K 线（单次查询，复用于 OHLC/振幅/收益率/52周高低）──────────────────
    # 优化：将原来的3次查询（get_price_history limit=2 + get_daily_history limit=250 + limit=9999）
    # 合并为1次查询（limit=400），足够覆盖所有需求
    # market_data_daily 存无前缀代码，用 db_sym 查询
    _HIST_LIMIT = 400  # 252(52周) + 60 + 20 + 5 + buffer
    hist_all = get_daily_history(db_sym, limit=_HIST_LIMIT, offset=0) if callable(get_daily_history) else []

    # 实时快照：从 hist_all 前2条获取（最新 + 前一日）
    latest_row = hist_all[0] if hist_all else {}
    prev_row   = hist_all[1] if len(hist_all) > 1 else latest_row

    open_  = float(latest_row.get('open')  or price)
    high_  = float(latest_row.get('high')  or price)
    low_   = float(latest_row.get('low')   or price)
    close_ = float(latest_row.get('close') or price)
    # 指数的 amount/turnover_rate 字段在 DB 中常为 0（AkShare 不提供），视为无数据
    amount = float(latest_row.get('amount') or 0.0) or None
    turnover_rate = round(float(latest_row.get('turnover_rate') or 0.0), 4) or None
    # 振幅 = (最高-最低)/昨收 × 100；当日仅一价时用 (现价-昨收)/昨收
    prev_close = float(prev_row.get('close') or 0.0)
    if low_ and low_ > 0 and high_ != low_:
        amplitude = round((high_ - low_) / prev_close * 100, 2) if prev_close else None
    else:
        amplitude = round(abs(price - prev_close) / prev_close * 100, 2) if prev_close and prev_close > 0 else None

    def _period_return(hist, n):
        """最近 n 日收益率（DESC 排序：最新在前）"""
        if len(hist) < n + 1: return None
        cur  = float(hist[0].get('close', 0))   # 最新 = 第一条
        prev = float(hist[n].get('close', 0))   # n 日前 = 第 n+1 条
        if not prev: return None
        return round((cur / prev - 1) * 100, 4)

    def _52w_bounds(hist):
        """52 周最高/最低（最近 252 个交易日）。hist 为 DESC 排序（最新在前）。"""
        if not hist: return None, None, None, None
        recent = hist[:252] if len(hist) >= 252 else hist
        # O(n) 扫描替代 O(n log n) 排序
        max_close = max((float(r.get('close', 0) or 0), r.get('date', '')) for r in recent if r.get('close'))
        min_close = min((float(r.get('close', 0) or 0), r.get('date', '')) for r in recent if r.get('close'))
        return max_close[0], max_close[1], min_close[0], min_close[1]

    ret_5d  = _period_return(hist_all, 5)
    ret_20d = _period_return(hist_all, 20)
    ret_60d = _period_return(hist_all, 60)
    # 今年以来（累计收益率，粗略用年初至今交易日）
    ytd_start = [r for r in hist_all if str(r.get('date', ''))[:4] == str(datetime.now().year)]
    ret_ytd  = _period_return(ytd_start, len(ytd_start) - 1) if len(ytd_start) >= 2 else None
    high_52w, h52w_date, low_52w, l52w_date = _52w_bounds(hist_all)

    # ── 涨跌家数（来自 SpotCache 的 Sina HQ 实时全市场数据）───
    # SpotCache 由后台线程定期刷新，包含沪深全市场股票涨跌幅统计
    _hist = SpotCache.get_histogram()
    _ready = SpotCache.is_ready()
    if _ready and _hist.get("total", 0) > 0:
        advance_count   = _hist.get("advance", 0)
        decline_count   = _hist.get("decline", 0)
        unchanged_count = _hist.get("unchanged", 0)
        advance_rate    = _hist.get("up_ratio", 0)   # 上涨比例 0~1
    else:
        advance_count   = None
        decline_count   = None
        unchanged_count = None
        advance_rate    = None

    # ── 资金流向（暂无数据源→返回 null）────────────────────────
    fund_main_net   = None
    fund_main_in    = None
    fund_main_out   = None
    fund_huge_in    = None; fund_huge_out   = None
    fund_big_in     = None; fund_big_out    = None
    fund_medium_in  = None; fund_medium_out = None
    fund_small_in   = None; fund_small_out  = None

    # ── 板块联动（暂无数据源→返回 null）────────────────────────
    industry        = None
    industry_change_pct = None
    concepts        = []

    # ── 估值 ── 调用多源fallback获取PE/PB
    quote_data = await get_quote_with_fallback_async(norm)
    pe_static = quote_data.get("pe_static")
    pe_ttm_val = quote_data.get("pe_ttm")
    pb_val = quote_data.get("pb")

    result = {
        # ── Module 1: 基础行情 ──
        "name":             w.get('name') or norm,
        "symbol":           norm,
        "price":            round(price, 3),
        "change":           change_val,
        "change_pct":       round(change_pct, 2),
        "open":             round(open_,  3),
        "high":             round(high_,  3),
        "low":              round(low_,   3),
        "close":            round(close_, 3),
        "volume":           volume,
        "amount":           round(amount, 2) if amount is not None else None,
        "amplitude":        amplitude,
        "turnover_rate":    round(turnover_rate, 4) if turnover_rate is not None else None,
        "status":           status,
        "market":           market,
        # ── 估值 ──
        "pe_ttm":           pe_ttm_val,   # 从腾讯/东财/新浪获取
        "pb":               pb_val,       # 从腾讯/东财/新浪获取
        # ── 周期收益 ──
        "returns_5d":       ret_5d,
        "returns_20d":      ret_20d,
        "returns_60d":      ret_60d,
        "returns_ytd":      ret_ytd,
        # ── 52 周高低 ──
        "high_52w":         round(high_52w, 3) if high_52w else None,
        "low_52w":          round(low_52w,  3) if low_52w  else None,
        "high_52w_date":    h52w_date,
        "low_52w_date":    l52w_date,
        # ── Module 2: 市场情绪 ──
        "advance_count":    advance_count,
        "decline_count":    decline_count,
        "unchanged_count": unchanged_count,
        "advance_rate":     advance_rate,
        # ── Module 3: 资金流向 ──
        "fund_main_net":    fund_main_net,
        "fund_main_in":     fund_main_in,
        "fund_main_out":   fund_main_out,
        "fund_huge_in":    fund_huge_in,  "fund_huge_out":  fund_huge_out,
        "fund_big_in":     fund_big_in,   "fund_big_out":   fund_big_out,
        "fund_medium_in":  fund_medium_in,"fund_medium_out": fund_medium_out,
        "fund_small_in":   fund_small_in, "fund_small_out": fund_small_out,
        # ── Module 4: 板块联动 ──
        "industry":               industry,
        "industry_change_pct":   industry_change_pct,
        "concepts":              concepts,
    }
    return success_response(result)


# ═════════════════════════════════════════════════════════════════════════════
# Endpoint 3: Quote V2 (lines 1835-1869)
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/market/quote_v2/{symbol}")
async def market_quote_v2(symbol: str):
    """
    V2 实时行情接口 - 使用 FetcherFactory 数据源抽象层。

    直接从数据源获取实时报价，不依赖本地数据库。
    支持熔断器自动降级（失败3次自动切换到备用数据源）。
    """
    try:
        fetcher = FetcherFactory.get_fetcher()
        if not fetcher:
            return error_response(404, "无可用数据源")

        data = await fetcher.get_quote(symbol)

        if not data:
            return error_response(404, f"获取 {symbol} 数据失败")

        return success_response({
            "symbol": data.get("symbol", symbol),
            "name": data.get("name", symbol),
            "price": data.get("price", 0),
            "change": round(data.get("price", 0) - data.get("prev_close", 0), 3),
            "change_pct": data.get("change_pct", 0),
            "open": data.get("open", 0),
            "high": data.get("high", 0),
            "low": data.get("low", 0),
            "prev_close": data.get("prev_close", 0),
            "volume": data.get("volume", 0),
            "source": data.get("source", "sina"),
            "timestamp": int(time.time() * 1000),
        })
    except Exception as e:
        logger.error(f"quote_v2 error: {e}")
        return error_response(500, str(e))


# ═════════════════════════════════════════════════════════════════════════════
# Endpoint 4: Order Book (lines 1736-1828)
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/market/order_book/{symbol}")
async def get_order_book(symbol: str):
    """Level 2 10档买卖盘口数据（实时）"""
    norm = _normalize_symbol(symbol)

    # 转换为新浪格式
    # 判断是否为指数（上证sh000001, 深证sz399001等）
    code_digits = norm[2:]  # 去掉sh/sz后的数字部分

    # 简单判断: 000001-009999 通常是指数, 600000以上是股票
    is_index = False
    try:
        code_num = int(code_digits)
        if code_num < 100000:  # 0-99999 可能是指数
            # 常见指数: 000001, 000300, 399001, 399006, 000688
            is_index = True
    except (ValueError, TypeError):
        pass  # Non-numeric code, treat as stock

    if is_index:
        # 指数没有Level 2数据，返回说明
        return success_response({
            "symbol": symbol,
            "note": "指数暂无Level 2数据",
            "asks": [],
            "bids": [],
            "source": "N/A"
        })

    # 个股: 正常获取Level 2数据
    if norm.startswith('sh'):
        sina_code = f'sh{norm[2:]}'
    elif norm.startswith('sz'):
        sina_code = f'sz{norm[2:]}'
    else:
        sina_code = norm

    url = f"https://hq.sinajs.cn/list={sina_code}"
    headers = {"Referer": "https://finance.sina.com.cn"}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, headers=headers)
            text = resp.text

            # DEBUG
            logger.info(f"[order_book] symbol={symbol}, norm={norm}, sina_code={sina_code}, text_len={len(text)}")

            # 解析数据
            match = re.search(r'="(.+)"', text)
            if not match:
                return error_response(ErrorCode.NOT_FOUND, "无数据")

            fields = match.group(1).split(',')
            if len(fields) < 30:
                return error_response(ErrorCode.NOT_FOUND, "数据不足")

            # 解析10档数据
            # 字段10-19是卖盘(5档): [卖5量,卖5价,卖4量,卖4价,卖3量,卖3价,卖2量,卖2价,卖1量,卖1价]
            # 字段20-29是买盘(5档): [买1量,买1价,买2量,买2价,买3量,买3价,买4量,买4价,买5量,买5价]

            asks = []
            # 卖盘: 字段10-19 (卖5到卖1)
            for i in range(10, 20, 2):
                vol = int(fields[i]) if fields[i] and fields[i].isdigit() else 0
                price = float(fields[i+1]) if fields[i+1] else 0
                asks.append({
                    "position": (20 - i) // 2,  # 10→5,12→4,14→3,16→2,18→1
                    "price": price,
                    "volume": vol
                })

            bids = []
            for i in range(20, 30, 2):
                vol = int(fields[i]) if fields[i] and fields[i].isdigit() else 0
                price = float(fields[i+1]) if fields[i+1] else 0
                bids.append({
                    "position": (i - 20) // 2 + 1,  # 1,2,3,4,5
                    "price": price,
                    "volume": vol
                })

            return success_response({
                "symbol": symbol,
                "timestamp": int(time.time() * 1000),
                "asks": asks,
                "bids": bids,
                "source": "Sina HQ Level2"
            })
    except Exception as e:
        logger.error(f"order_book error: {e}")
        return error_response(500, str(e))
