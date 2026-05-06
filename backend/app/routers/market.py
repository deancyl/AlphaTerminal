"""
市场数据接口 - Phase 7 + Phase 5
所有数据从 SQLite market_data_realtime 读取
宏观大宗商品（USD/CNH·黄金·WTI·VIX）由腾讯/Sina 实时接口抓取，10 分钟缓存

Phase B: 统一 API 响应格式
- 所有响应使用标准格式: {code, message, data, timestamp}
- code: 0 表示成功，非 0 表示错误
"""
import asyncio
import logging
import os
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Request
import httpx
from app.db import get_latest_prices, get_price_history
from app.utils.market_status import is_market_open
from app.services.fetchers import FetcherFactory, fetch_with_fallback, get_market_fetcher
from app.services.sentiment_engine import SpotCache
from app.services.quote_source import get_quote_with_fallback_async, get_source_status


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

# 错误码定义
class ErrorCode:
    SUCCESS = 0
    BAD_REQUEST = 100
    NOT_FOUND = 104
    INTERNAL_ERROR = 200
    THIRD_PARTY_ERROR = 302

# ── Phase 7: 宏观大宗商品缓存（10 分钟 TTL）─────────────────────────────
# 代理由 proxy_config.py 统一管理，从环境变量读取
# 用户需在启动前设置 HTTP_PROXY/HTTPS_PROXY 环境变量

_MACRO_CACHE       = {}   # {symbol: {price, change_pct, name, unit, timestamp}}
_MACRO_CACHE_TTL  = 600  # 10 分钟（Phase 7 延长 TTL）
_MACRO_CACHE_LOCK  = threading.RLock()  # RLock 可重入
_LAST_FETCH_TIME   = 0   # 0 = immediately refresh on first call
_REFRESH_SEMAPHORE = threading.Semaphore(1)  # 防止并发刷新

SINA_HEADERS = {
    "Referer": "https://finance.sina.com.cn",
    "User-Agent": "Mozilla/5.0 (compatible; AlphaTerminal/1.0)",
}


def _fetch_from_sina(symbols: list[str]) -> dict[str, list]:
    """从 Sina HQ 和腾讯 qt 拉取多个标的，返回 {symbol: [fields...]}"""
    results = {}

    # 1) Sina HQ（外汇、黄金、原油）
    sina_syms = [s for s in symbols if s not in ("CNHUSD",)]
    if sina_syms:
        codes = ",".join(sina_syms)
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(
                    f"https://hq.sinajs.cn/list={codes}",
                    headers=SINA_HEADERS,
                )
                resp.raise_for_status()
                raw = resp.text
            for line in raw.splitlines():
                line = line.strip()
                if not line or "=" not in line:
                    continue
                try:
                    m = re.match(r'var hq_str_(\w+)="(.*?)"', line)
                    if m:
                        sym = m.group(1)
                        fields = [f.strip() for f in m.group(2).split(",")]
                        results[sym] = fields
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"[Macro] Sina fetch failed: {e}")

    # 3) 腾讯 qt（CNH/USD 汇率 + VHSI 恒指波指 + 恒生指数HSI，不过代理）
    qt_syms = [s for s in symbols if s in ("CNHUSD", "hkVHSI", "hkHSI")]
    if qt_syms:
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(
                    f"https://qt.gtimg.cn/q={','.join(qt_syms)}",
                    headers={"Referer": "https://gu.qq.com", "User-Agent": "Mozilla/5.0"},
                )
                resp.raise_for_status()
                raw = resp.text
            for line in raw.splitlines():
                line = line.strip()
                if "none_match" in line or "=" not in line:
                    continue
                try:
                    sym = line.split("=")[0].replace("v_", "").strip('" \n')
                    # 腾讯 qt 格式: v_hkHSI="51~恒生指数~HSI~25357.23~..."
                    raw_val = line.split("=", 1)[1].strip('";\r\n ')
                    fields = raw_val.split("~")
                    results[sym] = [f.strip() for f in fields]
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"[Macro] Tencent qt fetch failed: {e}")

    return results


def _parse_cnyusd(data: dict) -> tuple[float, float, str]:
    """
    解析 CNYUSD，返回 (USDCNY, 涨跌幅%, 时间戳)
    Sina 格式: [时间, 中行汇买价, 钞买价, 汇卖价, ?, 汇买价2, 钞卖价2, 汇卖价2, 折算价, 货币名, 日期]
    中行汇买价 0.1452 ≈ 0.1452 USD per CNY → USDCNY = 1/0.1452 ≈ 6.887
    注意：Sina 数据可能有延迟，建议以央行中间价为准做参考
    """
    f = data.get("CNYUSD", [])
    if len(f) < 10:
        raise ValueError("CNYUSD data too short")
    price_usdpcny = float(f[1])   # USD per CNY (中行汇买价)
    prev          = float(f[2])   # 前一价格
    t             = f[0]
    pct           = ((price_usdpcny - prev) / prev * 100) if prev else 0.0
    usdcny        = round(1.0 / price_usdpcny, 4) if price_usdpcny else 7.25
    return usdcny, round(pct, 4), t


def _parse_hf_gold(data: dict) -> tuple[float, float, str]:
    """
    解析 hf_GC（上海金交易所 SGE 黄金现货，RMB/盎司）
    字段: [当前价, 涨跌%, 昨收, 开, 高, 低, 时间, 昨结算, ...]
    """
    f = data.get("hf_GC", [])
    if len(f) < 8:
        raise ValueError("hf_GC data too short")
    try:
        price = float(f[0])   # RMB/oz（SGE 现货金的报价单位）
        prev  = float(f[7])   # 昨结算 RMB/oz
        pct   = float(f[1]) if f[1] else (((price - prev) / prev * 100) if prev else 0.0)
        tick  = f[6] if len(f) > 6 else ""
    except Exception as e:
        raise ValueError(f"hf_GC parse error: {e}")
    return round(price, 2), round(pct, 2), tick


def _get_cnyusd_approx() -> float:
    """CNY/USD ≈ 7.25（固定估算，用于内部换算）"""
    return 7.25


def _parse_hkhsi(data: dict) -> tuple[float, float, str]:
    """
    解析 hkHSI（恒生指数，腾讯 qt 格式，~分隔）
    f[3]=当前价, f[4]=昨收, f[31]=涨跌额, f[32]=涨跌幅%
    """
    f = data.get("hkHSI", [])
    if len(f) < 33:
        raise ValueError("hkHSI data too short")
    try:
        price = float(f[3])   # 当前 HSI
        prev  = float(f[4])   # 昨收
        pct   = float(f[32]) if f[32] else (((price - prev) / prev * 100) if prev else 0.0)
        # f[30] = "2026/04/02 18:31:21"
        tick  = f[30][-8:-3] if f[30] and len(f[30]) > 4 else ""
    except Exception as e:
        raise ValueError(f"hkHSI parse error: {e}")
    return round(price, 2), round(pct, 2), tick


def _parse_hf_cl(data: dict) -> tuple[float, float, str]:
    """
    解析 hf_CL（WTI 原油期货，USD/桶）
    字段: [当前价, 涨跌%, 昨收, 开, 高, 低, 时间, 昨结算, ...]
    """
    f = data.get("hf_CL", [])
    if len(f) < 8:
        raise ValueError("hf_CL data too short")
    try:
        price = float(f[0])   # USD/桶（WTI 期货报价）
        prev  = float(f[7])   # 昨结算
        pct   = float(f[1]) if f[1] else (((price - prev) / prev * 100) if prev else 0.0)
        tick  = f[6] if len(f) > 6 else ""
    except Exception as e:
        raise ValueError(f"hf_CL parse error: {e}")
    return round(price, 2), round(pct, 2), tick


def _parse_hkvhsi(data: dict) -> tuple[float, float, str]:
    """
    解析 hkVHSI（恒指波幅指数，腾讯 qt 格式）
    _fetch_from_sina 返回 list：f[3]=当前 VHSI 值, f[4]=昨收, f[32]=涨跌幅%
    若解析失败（格式不符），返回 (20.0, 0.0, "") 而不崩溃
    """
    f = data.get("hkVHSI", [])
    if len(f) < 5:
        raise ValueError("hkVHSI data too short")
    try:
        price = float(f[3])   # VHSI 当前值
        prev  = float(f[4]) if f[4] else price
        # f[32] 是涨跌幅%，若为空则用 (price-prev)/prev 推算
        pct = 0.0
        if len(f) > 32 and f[32]:
            try:
                pct = float(f[32])
            except (ValueError, TypeError):
                pct = (price - prev) / prev * 100 if prev else 0.0
        else:
            pct = (price - prev) / prev * 100 if prev else 0.0
        tick = f[30][-8:-3] if len(f) > 30 and f[30] and len(f[30]) > 4 else ""
    except (ValueError, IndexError, TypeError) as e:
        raise ValueError(f"hkVHSI parse error: {e}")
    return round(price, 2), round(pct, 2), tick


def _fetch_macro_data():
    """
    Phase 7: 真实数据抓取（腾讯/Sina HQ）
    - USD/CNY: CNYUSD → 换算（Sina）
    - SGE黄金: Sina hf_GC → RMB/oz（上海金现货）
    - WTI原油: Sina hf_CL → USD/桶
    - VHSI: 恒指波幅指数（腾讯 qt hkVHSI）
    """
    global _MACRO_CACHE, _LAST_FETCH_TIME
    now_str = datetime.now().strftime("%H:%M")

    # 初始化默认值（静态兜底，网络失败时使用）
    usdcny_price = 6.8871; usdcny_pct = 0.0
    gold_price = 3318.40; gold_pct = 0.0
    wti_price = 68.92; wti_pct = 0.0
    vhsi_price = 20.0; vhsi_pct = 0.0

    try:
        raw = _fetch_from_sina(["CNYUSD", "hf_GC", "hf_CL", "hkVHSI"])

        if "CNYUSD" in raw and raw["CNYUSD"]:
            try:
                usdcny_price, usdcny_pct, _ = _parse_cnyusd(raw)
            except Exception as e:
                logger.warning(f"[Macro] CNYUSD parse error: {e}")

        if "hf_GC" in raw and raw["hf_GC"]:
            try:
                gold_price, gold_pct, _ = _parse_hf_gold(raw)
            except Exception as e:
                logger.warning(f"[Macro] GOLD parse error: {e}")

        if "hf_CL" in raw and raw["hf_CL"]:
            try:
                wti_price, wti_pct, _ = _parse_hf_cl(raw)
            except Exception as e:
                logger.warning(f"[Macro] WTI parse error: {e}")

        if "hkVHSI" in raw and raw["hkVHSI"]:
            try:
                vhsi_price, vhsi_pct, _ = _parse_hkvhsi(raw)
                logger.info(f"[Macro] VHSI fetched: {vhsi_price} ({vhsi_pct}%)")
            except Exception as e:
                logger.warning(f"[Macro] VHSI parse error: {e}")

        results = {
            "USD/CNY": {"name": "美元/离岸人民币", "price": round(usdcny_price, 4), "unit": "",    "change_pct": round(usdcny_pct, 4),  "timestamp": now_str},
            "GOLD":    {"name": "SGE黄金(人民币)",  "price": round(gold_price, 2),   "unit": "¥/oz","change_pct": round(gold_pct, 2),  "timestamp": now_str},
            "WTI":     {"name": "WTI原油(美元)",    "price": round(wti_price, 2),    "unit": "$/桶","change_pct": round(wti_pct, 2),   "timestamp": now_str},
            "VHSI":    {"name": "恒指波幅(VHSI)",   "price": round(vhsi_price, 2),    "unit": "",     "change_pct": round(vhsi_pct, 2),  "timestamp": now_str},
        }

        with _MACRO_CACHE_LOCK:
            _MACRO_CACHE = results
            _LAST_FETCH_TIME = time.time()
        logger.info(f"[Macro] Fetched: USD={usdcny_price} GOLD={gold_price}¥ WTI={wti_price} VHSI={vhsi_price}({vhsi_pct}%)")

    except Exception as e:
        logger.warning(f"[Macro] Fetch failed, keeping old cache: {e}")
        # 保持旧缓存不变，不抛异常


def _get_macro_data() -> dict:
    """
    返回宏观缓存（TTL 10 分钟）。
    缓存空或过期时：立即返回旧缓存，同时后台触发一次异步刷新（绝不阻塞 API）。
    """
    global _MACRO_CACHE, _LAST_FETCH_TIME
    stale = not _MACRO_CACHE or (time.time() - _LAST_FETCH_TIME) > _MACRO_CACHE_TTL

    if stale and _REFRESH_SEMAPHORE.acquire(blocking=False):
        # 立即返回旧缓存（避免阻塞），后台刷新
        def bg():
            try:
                _fetch_macro_data()
            finally:
                _REFRESH_SEMAPHORE.release()
        t = threading.Thread(target=bg, daemon=True, name="macro-refresh")
        t.start()

    with _MACRO_CACHE_LOCK:
        return dict(_MACRO_CACHE) if _MACRO_CACHE else {}


@router.get("/market/macro")
async def market_macro():
    """
    Phase 5: 宏观核心数据（USD/CNH · COMEX黄金 · WTI原油 · VIX恐慌指数）
    5 分钟 TTL 缓存，不阻塞 API 响应
    """
    try:
        return success_response({
            "macro": list(_get_macro_data().values()),
        })
    except Exception as e:
        logger.error(f"[market_macro] 错误: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取宏观数据失败: {str(e)}")

def _serialize_price_row(row: dict, include_status: bool = False, status: str = None) -> dict:
    """
    统一序列化价格数据行

    Args:
        row: 数据库原始行数据
        include_status: 是否包含市场状态字段
        status: 市场状态值（仅当 include_status=True 时有效）

    Returns:
        标准化后的数据字典
    """
    result = {
        "symbol": row["symbol"],
        "name": row["name"],
        "price": row["price"],
        "change_pct": row["change_pct"],
        "volume": row["volume"],
        "market": row["market"],
    }
    if include_status and status:
        result["status"] = status
    return result


def _serialize_price_rows(rows: list, include_status: bool = False, status: str = None) -> list:
    """批量序列化价格数据行"""
    return [_serialize_price_row(r, include_status, status) for r in rows]


# ── 风向标指数（Task 2: 精简 overview，只保留核心风向标）─────────────────
WIND_SYMBOLS = ["000001", "000300", "399001", "399006", "HSI", "IXIC"]
INDEX_SYMBOLS = ["000001", "000300", "399001", "399006"]
CHINA_ALL_SYMBOLS = [
    "000001", "000300", "399001", "399006",
    "000688", "000905", "000852", "000016",
    "000510", "399100",
]
RATE_SYMBOLS = ["shibor_1d", "shibor_1w", "shibor_1m", "shibor_3m", "shibor_1y"]
GLOBAL_SYMBOLS = ["HSI", "DJI", "IXIC", "SPX", "N225"]
DERIVATIVE_SYMBOLS = ["GC", "CL"]

# ── 实时行情缓存（10秒 TTL，避免频繁调 Sina）─────────────────────────
_REALTIME_CACHE = {"wind": None, "china_all": None, "_ts": 0}
_CACHE_TTL = 10  # 秒


def _get_cached_wind(force=False):
    """获取风向标实时数据，10秒内复用缓存"""
    import time
    now = time.time()
    if not force and _REALTIME_CACHE["wind"] and (now - _REALTIME_CACHE["_ts"]) < _CACHE_TTL:
        return _REALTIME_CACHE["wind"]
    try:
        from app.services.data_fetcher import fetch_china_indices, fetch_global_indices
        # A股4大指数（实时）+ 全球指数（港美）
        rows_cn  = fetch_china_indices()           # 新浪实时
        rows_int = fetch_global_indices()           # 腾讯/Sina 实时
        rows = rows_cn + rows_int
        wind_data = {}
        for r in rows:
            sym = r.get("symbol", "")
            wind_data[sym] = {
                "name":       r.get("name", sym),
                "price":      r.get("price", 0),
                "change_pct": r.get("change_pct", 0),
                "volume":     r.get("volume", 0),
                "market":     r.get("market", ""),
            }
        _REALTIME_CACHE["wind"] = wind_data
        _REALTIME_CACHE["_ts"]  = now
        return wind_data
    except Exception as e:
        logger.warning(f"[market_overview] 实时拉取失败，回退缓存: {e}")
        return _REALTIME_CACHE["wind"] or {}


# ── Task 2: 修复后的 market/overview ─────────────────────────────────────
@router.get("/market/overview")
def market_overview():
    """
    市场概览 - 风向标视图（实时调 Sina，10秒缓存）
    包含：上证、沪深300、恒生、纳斯达克（动态交易状态）
    """
    is_open_cn, status_cn = is_market_open("A_SHARE")
    is_open_hk, status_hk  = is_market_open("HK")
    is_open_us, status_us  = is_market_open("US")

    wind_labels = {
        "000001": ("上证指数",  "AShare", status_cn),
        "000300": ("沪深300",  "AShare", status_cn),
        "399001": ("深证成指",  "AShare", status_cn),
        "399006": ("创业板指",  "AShare", status_cn),
        "HSI":    ("恒生指数",  "HK",     status_hk),
        "IXIC":   ("纳斯达克",  "US",     status_us),
    }

    # 统一从 market_data_realtime 读取（确保全系统报价一致）
    # 仅当数据库缺失数据时，才回退到 Sina 实时拉取
    rows = get_latest_prices(WIND_SYMBOLS)
    wind_data = {}
    db_symbols = {r["symbol"]: r for r in rows}

    for sym, label in wind_labels.items():
        row = db_symbols.get(sym)
        price = row.get('price', 0) if row else 0

        # 修复：如果价格为0，使用昨日收盘价作为兜底
        if price == 0:
            from app.db.database import get_daily_history
            daily = get_daily_history(sym, limit=1)
            if daily:
                price = daily[0].get('close', 0)

        wind_data[sym] = {
            "name": (row.get("name", label[0]) if row else label[0]),
            "price": price,
            "change_pct": (row.get("change_pct", 0) if row and price else 0),
            "volume": (row.get("volume", 0) if row else 0),
            "market": label[1],
            "status": label[2],
        }

    result = success_response({
        "wind": wind_data,
        "meta": {
            "markets": {
                "AShare": {"open": is_open_cn, "status": status_cn},
                "HK": {"open": is_open_hk, "status": status_hk},
                "US": {"open": is_open_us, "status": status_us},
            }
        }
    })
    return result


# ── Task 2: 国内10+核心指数（实时）─────────────────────────────────────
@router.get("/market/china_all")
def market_china_all():
    """国内10+核心指数（统一从 market_data_realtime 读取，不再直连Sina，保证报价一致）"""
    try:
        is_open, status = is_market_open("A_SHARE")
        # 统一从数据库 market_data_realtime 读取，确保所有API报价一致
        rows = get_latest_prices(CHINA_ALL_SYMBOLS)

        # 修复：如果价格为0，使用昨日收盘价（从daily表获取）
        for row in rows:
            if row.get('price', 0) == 0 or row.get('price') is None:
                from app.db.database import get_daily_history
                sym = row.get('symbol')
                daily = get_daily_history(sym, limit=1)
                if daily:
                    row['price'] = daily[0].get('close', 0)
                    row['change_pct'] = daily[0].get('change_pct', 0)

        return success_response({
            "china_all": _serialize_price_rows(rows, include_status=True, status=status),
            "meta": {"market_open": is_open, "status": status}
        })
    except Exception as e:
        logger.error(f"[market_china_all] 错误: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取国内指数失败: {str(e)}")


@router.get("/market/all_stocks")
def market_all_stocks(request: Request):
    """
    全市场A股列表（来自 market_all_stocks 缓存表）
    支持搜索: ?search=茅台
    分页: ?page=1&page_size=50
    """
    try:
        from app.db.database import get_all_stocks, get_all_stocks_count
        from fastapi import Query

        # 获取参数 (从 Request 中提取)
        params = dict(request.query_params)
        search = params.get('search', '').strip()
        page = max(1, int(params.get('page', 1)))
        page_size = min(200, max(1, int(params.get('page_size', 50))))
        offset = (page - 1) * page_size

        total, rows = get_all_stocks(limit=page_size, offset=offset, search=search if search else None)

        return success_response({
            "stocks": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size if total > 0 else 0,
        })
    except Exception as e:
        logger.error(f"[market_all_stocks] 错误: {e}", exc_info=True)
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取全市场个股失败: {str(e)}")


@router.get("/market/all_stocks_lite")
async def market_all_stocks_lite():
    """全市场A股轻量列表（一次性返回，无分页，StockScreener专用）"""
    try:
        from app.db.database import get_all_stocks_lite
        rows = get_all_stocks_lite()
        return success_response({
            "stocks": rows,
            "total": len(rows),
        })
    except Exception as e:
        logger.error(f"[market_all_stocks_lite] 错误: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取全市场个股失败: {str(e)}")

@router.get("/market/stocks/search")
def search_stocks_api(
    keyword: str = None,
    min_pct_chg: float = None, max_pct_chg: float = None,
    min_turnover: float = None, max_turnover: float = None,
    min_price: float = None, max_price: float = None,
    min_pe: float = None, max_pe: float = None,
    min_pb: float = None, max_pb: float = None,
    min_mktcap: float = None, max_mktcap: float = None,
    sort_by: str = 'change_pct', sort_dir: str = 'desc',
    page: int = 1, page_size: int = 50,
):
    """
    全市场个股服务端搜索+过滤+排序+分页
    支持的过滤字段:
      keyword: 模糊搜索代码/名称
      min_pct_chg / max_pct_chg: 涨跌幅区间 (%)
      min_turnover / max_turnover: 换手率区间 (%)
      min_price / max_price: 价格区间（元）
      min_pe / max_pe: PE区间
      min_pb / max_pb: PB区间
      min_mktcap / max_mktcap: 市值区间（亿元）
    排序: sort_by=change_pct|turnover|volume|pe|pb|mktcap|code|name
    分页: page + page_size（每页最多200）
    """
    try:
        from app.db.database import search_stocks as _search
        total, rows, page, page_size = _search(
            keyword=keyword,
            min_pct_chg=min_pct_chg, max_pct_chg=max_pct_chg,
            min_turnover=min_turnover, max_turnover=max_turnover,
            min_price=min_price, max_price=max_price,
            min_pe=min_pe, max_pe=max_pe,
            min_pb=min_pb, max_pb=max_pb,
            min_mktcap=min_mktcap, max_mktcap=max_mktcap,
            sort_by=sort_by, sort_dir=sort_dir,
            page=page, page_size=page_size,
        )
        return success_response({
            "stocks": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size if total > 0 else 0,
        })
    except Exception as e:
        logger.exception("[search_stocks] 服务端搜索失败")
        return error_response(ErrorCode.INTERNAL_ERROR, f"搜索失败: {str(e)}")


@router.get("/market/indices")
def market_indices():
    """A股四大指数列表"""
    try:
        rows = get_latest_prices(INDEX_SYMBOLS)
        return success_response({
            "indices": _serialize_price_rows(rows)
        })
    except Exception as e:
        logger.error(f"[market_indices] 错误: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取指数列表失败: {str(e)}")


# ── Phase 10: 符号注册表（供前端搜索索引）───────────────────────────────
# 规范化 Symbol 前缀规则：sh=上证 sz=深证 us=美股 hk=港股 JP=日股
_MARKET_PREFIX = {
    '000001': 'sh', '000300': 'sh', '000688': 'sh',  # 上证体系
    '399001': 'sz', '399006': 'sz',                   # 深证体系
}
_SYMBOL_REGISTRY = [
    # A股指数
    { 'symbol': 'sh000001', 'code': '000001', 'name': '上证指数',   'pinyin': 'SCZS',  'market': 'AShare', 'type': 'index' },
    { 'symbol': 'sh000300', 'code': '000300', 'name': '沪深300',   'pinyin': 'HS300',  'market': 'AShare', 'type': 'index' },
    { 'symbol': 'sz399001', 'code': '399001', 'name': '深证成指',   'pinyin': 'SZCZS',  'market': 'AShare', 'type': 'index' },
    { 'symbol': 'sz399006', 'code': '399006', 'name': '创业板指',   'pinyin': 'CYBZZ',  'market': 'AShare', 'type': 'index' },
    { 'symbol': 'sh000688', 'code': '000688', 'name': '科创50',     'pinyin': 'KC50',   'market': 'AShare', 'type': 'index' },
    # 全球指数
    { 'symbol': 'usNDX',    'code': 'NDX',    'name': '纳斯达克100', 'pinyin': 'NDX',   'market': 'US',     'type': 'index' },
    { 'symbol': 'usSPX',    'code': 'SPX',    'name': '标普500',     'pinyin': 'SPX',   'market': 'US',     'type': 'index' },
    { 'symbol': 'usDJI',    'code': 'DJI',    'name': '道琼斯',      'pinyin': 'DJS',   'market': 'US',     'type': 'index' },
    { 'symbol': 'hkHSI',    'code': 'HSI',    'name': '恒生指数',    'pinyin': 'HSZS',  'market': 'HK',     'type': 'index' },
    { 'symbol': 'jpN225',   'code': 'N225',   'name': '日经225',     'pinyin': 'RJB',   'market': 'JP',     'type': 'index' },
    # A股个股（示例，实际可扩展到全市场）
    { 'symbol': 'sh600519', 'code': '600519', 'name': '贵州茅台',    'pinyin': 'GZMJ',  'market': 'AShare', 'type': 'stock' },
    { 'symbol': 'sh601318', 'code': '601318', 'name': '中国平安',    'pinyin': 'ZGPA',  'market': 'AShare', 'type': 'stock' },
    { 'symbol': 'sz000858', 'code': '000858', 'name': '五粮液',      'pinyin': 'WLY',   'market': 'AShare', 'type': 'stock' },
    { 'symbol': 'sh600036', 'code': '600036', 'name': '招商银行',    'pinyin': 'ZSYH',  'market': 'AShare', 'type': 'stock' },
    { 'symbol': 'sz002594', 'code': '002594', 'name': '比亚迪',      'pinyin': 'BYD',   'market': 'AShare', 'type': 'stock' },
    # 宏观
    { 'symbol': 'GOLD',     'code': 'GOLD',   'name': '黄金(USD)',   'pinyin': 'JH',    'market': 'Macro',   'type': 'commodity' },
    { 'symbol': 'WTI',      'code': 'WTI',    'name': 'WTI原油',     'pinyin': 'YSCY',  'market': 'Macro',   'type': 'commodity' },
    { 'symbol': 'CNHUSD',   'code': 'CNHUSD', 'name': '美元/人民币',  'pinyin': 'MYRMB', 'market': 'Macro',   'type': 'forex' },
    { 'symbol': 'VIX',      'code': 'VIX',    'name': 'VIX恐慌指数',  'pinyin': 'VIX',  'market': 'Macro',   'type': 'index' },
]

# ── 全市场A股名称懒加载（不阻塞后端启动）───────────────────────────────
_ALL_STOCK_NAMES: list[dict] = []      # 全量个股注册表
_STOCK_NAMES_LOADED: bool = False
_STOCK_LOAD_LOCK = threading.Lock()      # 防止并发多次加载

# 快速 lookup 表（动态 + 静态分开，market_lookup 合并查询）
_SYMBOL_LOOKUP_STATIC = { item['symbol']: item for item in _SYMBOL_REGISTRY }


def _get_combined_lookup() -> dict:
    """返回完整 lookup：静态注册表 + 已加载的动态全市场A股（线程安全）"""
    base = dict(_SYMBOL_LOOKUP_STATIC)
    if _STOCK_NAMES_LOADED:
        for s in _ALL_STOCK_NAMES:
            base[s['symbol']] = s
    return base

def _pinyin_fallback(name: str) -> str:
    """获取名称首字拼音（无 pypinyin 时回退到名称前4字）"""
    try:
        from pypinyin import lazy_pinyin
        py = lazy_pinyin(name)
        return ''.join(py) if py else name[:4]
    except Exception:
        return name[:4]  # 无 pypinyin 时用名称前4字做近似


def _load_all_stock_names() -> list[dict]:
    """
    调用 akshare stock_info_a_code_name() 获取全市场A股代码+名称，
    懒加载一次，线程安全，结果缓存于 _ALL_STOCK_NAMES。
    """
    global _ALL_STOCK_NAMES, _STOCK_NAMES_LOADED
    if _STOCK_NAMES_LOADED:
        return _ALL_STOCK_NAMES

    with _STOCK_LOAD_LOCK:
        if _STOCK_NAMES_LOADED:   # double-check（其他线程已加载）
            return _ALL_STOCK_NAMES

        try:
            import akshare as ak
            logger.info("[SymbolRegistry] 开始加载全市场A股名称...")
            df = ak.stock_info_a_code_name()
            rows = []
            for _, row in df.iterrows():
                code = str(row.get('code', '')).strip()
                name = str(row.get('name', '')).strip()
                if not code or not name or len(code) != 6:
                    continue
                # 交易所判断：6/9 开头=上海，0-3 开头=深圳，8 开头=北交所
                prefix = 'sh' if code[0] in ('6', '9') else ('bj' if code[0] == '8' else 'sz')
                symbol = f'{prefix}{code}'
                rows.append({
                    'symbol': symbol,
                    'code':   code,
                    'name':   name,
                    'pinyin': _pinyin_fallback(name),
                    'market': 'AShare',
                    'type':   'stock',
                })
            _ALL_STOCK_NAMES = rows
            _STOCK_NAMES_LOADED = True
            logger.info(f"[SymbolRegistry] 全市场A股加载完成: {len(rows)} 只")
        except Exception as e:
            logger.warning(f"[SymbolRegistry] 加载全市场A股失败，使用兜底数据: {e}")
            _ALL_STOCK_NAMES = []
            _STOCK_NAMES_LOADED = True   # 标记"已尝试"，避免重复拉取

    return _ALL_STOCK_NAMES


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


@router.get("/market/symbols")
async def market_symbols():
    """返回全量符号注册表（含全市场A股），供前端搜索索引构建"""
    # 懒加载全市场A股名称（首次调用时从 akshare 拉取，之后走缓存）
    all_stocks = _load_all_stock_names()
    # 合并：静态注册表（指数+示例股）+ 全市场A股
    static_symbols = {s['symbol'] for s in _SYMBOL_REGISTRY}
    merged = list(_SYMBOL_REGISTRY) + [
        s for s in all_stocks if s['symbol'] not in static_symbols
    ]
    return success_response({
        'symbols': merged,
        'count': len(merged),
        'loaded': _STOCK_NAMES_LOADED,
        'timestamp': datetime.now().isoformat(),
    })


@router.get("/market/lookup/{symbol}")
async def market_lookup(symbol: str):
    """单个 symbol 的元信息查询（大小写折叠兜底）"""
    norm = _normalize_symbol(symbol)
    lookup = _get_combined_lookup()
    item = lookup.get(norm)
    if item:
        return success_response(item)
    # 大小写折叠兜底（如 'hsi' → 'hkHSI'，'ndx' → 'usNDX'）
    norm_lower = norm.lower()
    for key, val in lookup.items():
        if key.lower() == norm_lower:
            return success_response(val)
    return success_response(None, 'symbol not found')


@router.get("/market/quote/{symbol}")
async def market_quote(symbol: str):
    """
    轻量实时行情（专用于高频轮询，不含历史数据）
    返回：最新价、涨跌额、涨跌幅、成交量、成交额、振幅、换手率
    """
    norm = _normalize_symbol(symbol)
    from app.db import get_price_history
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


# ── Phase 9: 历史K线（多周期路由）────────────────────────────────────────
def _unprefix(raw: str) -> str:
    """去掉 sh/sz/hk/us/jp 前缀，用于查询 market_data_realtime（该表存无前缀 symbol）。"""
    s = str(raw).strip()
    for p in ('sh', 'sz', 'hk', 'us', 'jp', 'SH', 'SZ', 'HK', 'US', 'JP'):
        if s.startswith(p):
            return s[len(p):]
    return s


def _clean_symbol(raw: str) -> str:
    """
    规范化 symbol：
    - A 股 sh/sz 前缀：去掉（DB 存纯数字如 '000001'）
    - 美股/港股/日经前缀：统一去掉（DB 存 'ixic'/'hsi' 等，不带 us/hk/jp 前缀）
    - macro 前缀：去掉
    - 返回纯数字/字母（用于 DB 查询），全部小写
    """
    s = raw.strip()
    # macro 前缀
    if s.lower().startswith("macro"):
        s = s[len("macro"):].lstrip('_')
    # 去掉 us/hk/jp 前缀（所有非 A 股指数存库时不带前缀）
    s = re.sub(r"^(us|hk|jp)", "", s, flags=re.IGNORECASE)
    # 去掉 A 股前缀（DB 用纯数字存 A 股），用 removeprefix 避免误删中间出现的 sh/sz
    for pfx in ("sh", "sz", "SH", "SZ"):
        if s.startswith(pfx):
            s = s[len(pfx):]
            break
    return s.lower()


def _inject_change_pct(rows: list[dict]) -> list[dict]:
    """
    对 ASC 排列的历史 K 线内联注入 change_pct（利用相邻 close 计算）。
    market_data_daily 表无 change_pct 列，需在此层内联计算。
    同时注入 amplitude（历史旧数据可能缺失）。
    """
    if not rows:
        return rows
    result = []
    prev_close = None
    for r in rows:
        close = float(r.get("close") or 0)
        high  = float(r.get("high") or 0)
        low   = float(r.get("low") or 0)
        if prev_close is not None and prev_close != 0:
            pct       = (close - prev_close) / prev_close * 100
            amplitude = round((high - low) / prev_close * 100, 4)
        else:
            pct       = 0.0
            amplitude = 0.0
        # 只注入缺失的字段，保留已有值
        item = {**r}
        if item.get("change_pct") is None:
            item["change_pct"] = round(pct, 4)
        if item.get("amplitude") is None:
            item["amplitude"] = amplitude
        result.append(item)
        prev_close = close
    return result


@router.get("/market/fund_flow")
async def get_fund_flow():
    """市场资金流向（超大单/大单/中单/小单主力净流入）- 5秒超时防前端断开"""
    import akshare as ak
    import asyncio, datetime, random

    try:
        # 【核心修复】：线程池执行 + 5秒绝对超时，防止 akshare 阻塞事件循环和前端超时断开
        df = await asyncio.wait_for(
            asyncio.to_thread(ak.stock_market_fund_flow),
            timeout=5.0
        )
        df = df.tail(30)

        result = []
        for _, row in df.iterrows():
            result.append({
                "date": str(row.get("日期", "")),
                "sh_close": float(row.get("上证-收盘价", 0) or 0),
                "sh_chg": float(row.get("上证-涨跌幅", 0) or 0),
                "sz_close": float(row.get("深证-收盘价", 0) or 0),
                "sz_chg": float(row.get("深证-涨跌幅", 0) or 0),
                "main_net": int(float(row.get("主力净流入-净额", 0) or 0)),
                "main_pct": float(row.get("主力净流入-净占比", 0) or 0),
                "large_net": int(float(row.get("大单净流入-净额", 0) or 0)),
                "large_pct": float(row.get("大单净流入-净占比", 0) or 0),
                "medium_net": int(float(row.get("中单净流入-净额", 0) or 0)),
                "medium_pct": float(row.get("中单净流入-净占比", 0) or 0),
                "small_net": int(float(row.get("小单净流入-净额", 0) or 0)),
                "small_pct": float(row.get("小单净流入-净占比", 0) or 0),
            })

        if not result:
            raise ValueError("Empty data from akshare")

        return success_response({
            "items": result, "total": len(result), "source": "akshare"
        })

    except asyncio.TimeoutError:
        logger.warning(f"[FundFlow] akshare timed out after 5s, triggering fallback")
    except ValueError:
        logger.warning(f"[FundFlow] empty result, triggering fallback")
    except Exception as e:
        logger.warning(f"[FundFlow] fetch error, triggered fallback: {e}")

    # Fallback（akshare 超时或空数据时）
    mock_result = []
    for i in range(30):
        d = (datetime.datetime.now() - datetime.timedelta(days=29 - i)).strftime("%m-%d")
        main_net = random.randint(-500000000, 500000000)
        mock_result.append({
            "date": d, "main_net": main_net, "main_pct": round(random.uniform(-5, 5), 2),
            "large_net": int(main_net * random.uniform(0.6, 0.9)), "large_pct": round(random.uniform(-2, 2), 2),
            "medium_net": int(main_net * random.uniform(0.2, 0.4)), "medium_pct": round(random.uniform(-1, 1), 2),
            "small_net": int(-main_net * random.uniform(0.5, 0.8)), "small_pct": round(random.uniform(-3, 3), 2),
        })
    return success_response({"items": mock_result, "total": 30, "source": "fallback_mock"})


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
    fetching    = False   # 正在穿透拉取中

    _MIN_KLINE_SUPPORTED = {"000001", "000300", "399001", "399006", "000688"}
    _FREQUENCY_MAP = {"1min": 1, "5min": 5, "15min": 15, "30min": 30, "60min": 60}

    # ── 非 A 股指数/宏观（美股/HK/JP/大宗）：走 AkShare 穿透路径 ───────────
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

        # 如果本地数据少于50条（第一页），触发 AkShare 补全
        if (not raw_rows or (len(raw_rows) < 50 and offset == 0)) and offset == 0:
            import threading
            def _bg_fetch():
                try:
                    from app.services.data_fetcher import fetch_us_stock_history
                    fetch_us_stock_history(clean_sym, period=period, limit=5000)
                    logger.info(f"[Market History] 后台补全 {clean_sym} 完成")
                except Exception as e:
                    logger.error(f"[Market History] 后台补全失败: {e}")
            fetching = True
            threading.Thread(target=_bg_fetch, daemon=True).start()

            # 同时在当前线程同步拉取（不等后台），直接返回给前端
            try:
                from app.services.data_fetcher import fetch_us_stock_history
                sync_rows = fetch_us_stock_history(clean_sym, period=period, limit=5000)
                if sync_rows:
                    raw_rows = sync_rows
                    total = len(sync_rows)
                    fetching = False   # 同步已拿到数据，无需后台
                    logger.info(f"[Market History] 同步返回 {clean_sym}: {len(sync_rows)} 条")
            except Exception as e:
                logger.warning(f"[Market History] 同步拉取失败，回退DB: {e}")

        history  = _inject_change_pct(list(reversed(raw_rows))) if raw_rows else []
        has_more = (offset + len(raw_rows)) < total if raw_rows else False
        chart_type = "candlestick"

    # ── 分钟K线（Eastmoney N分钟接口，仅支持部分 A 股指数）───────────────
    elif period in _FREQUENCY_MAP:
        freq = _FREQUENCY_MAP[period]
        if clean_sym in _MIN_KLINE_SUPPORTED:
            from app.services.data_fetcher import fetch_index_minute_history
            all_data = fetch_index_minute_history(clean_sym, limit=limit, frequency=freq, offset=offset, trade_date=trade_date)
            history  = all_data
            has_more = len(all_data) >= min(limit, 300)
            chart_type = "line"   # 分钟K也用线图（与传统"分时"一致）
        else:
            history = []
            chart_type = "candlestick"

    elif period == "minutely":
        if clean_sym in _MIN_KLINE_SUPPORTED:
            from app.services.data_fetcher import fetch_index_minute_history
            history  = fetch_index_minute_history(clean_sym, limit=min(limit, 300), frequency=5, offset=offset)
            has_more = len(history) >= min(limit, 300)
            chart_type = "line"
        else:
            history = []
            chart_type = "line"

    # ── A 股日K线（支持个股 + 指数，自动按需穿透）───────────────────────────
    elif period == "daily":
        raw_rows = get_daily_history(clean_sym, limit=limit, offset=offset)
        total    = get_daily_count(clean_sym)

        if not raw_rows and offset == 0:
            logger.info(f"[Market History] 本地无 {clean_sym} 日K，触发 AkShare 穿透…")
            fetching = True
            try:
                # 判断是个股还是指数
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

    # ── A 股周/月K线（支持个股 + 指数，自动按需穿透）────────────────────────
    elif period in ("weekly", "monthly"):
        raw_rows = get_periodic_history(clean_sym, period=period, limit=limit, offset=offset)
        total    = get_periodic_count(clean_sym, period)

        if not raw_rows and offset == 0:
            logger.info(f"[Market History] 本地无 {clean_sym} {period}K，触发穿透…")
            fetching = True
            try:
                # 判断是个股还是指数
                _INDEX_SYMBOLS = {"000001", "000300", "399001", "399006", "000688", "399005"}
                if clean_sym in _INDEX_SYMBOLS:
                    from app.services.data_fetcher import fetch_index_daily_history
                    # 指数周月线由日线聚合生成，只需拉取日线
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
        "fetching":   fetching,    # 前端据此显示"穿透拉取中"状态
        "timestamp":  datetime.now().isoformat(),
        "history":    history,
    }
    return success_response(result)


_FUTURES_FREQ_MAP = {"1min": 1, "5min": 5, "15min": 15, "30min": 30, "60min": 60}


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
    import time

    clean_sym = symbol.strip().lower()

    # 日K
    if period == "daily":
        try:
            df = ak.futures_zh_daily_sina(symbol=clean_sym.upper())
            if df is None or df.empty:
                return {"symbol": clean_sym, "period": period, "history": []}
            df = df.tail(limit)
            rows = []
            for _, r in df.iterrows():
                rows.append({
                    "date":      str(r["date"]),
                    "open":      round(float(r["open"]), 2),
                    "high":      round(float(r["high"]), 2),
                    "low":       round(float(r["low"]), 2),
                    "close":     round(float(r["close"]), 2),
                    "volume":    int(r["volume"]) if r["volume"] == r["volume"] else 0,
                    "hold":      int(r["hold"]) if r["hold"] == r["hold"] else 0,   # 持仓量（Open Interest）
                })
            return {"symbol": clean_sym, "period": period, "history": list(reversed(rows))}
        except Exception as e:
            logger.error(f"[Futures] daily failed {clean_sym}: {e}")
            return success_response({"symbol": clean_sym, "period": period, "history": []}, f"获取失败: {e}")

    # 分钟K
    elif period in _FUTURES_FREQ_MAP:
        freq = _FUTURES_FREQ_MAP[period]
        try:
            df = ak.futures_zh_minute_sina(symbol=clean_sym.upper(), period=str(freq))
            if df is None or df.empty:
                return {"symbol": clean_sym, "period": period, "history": []}
            df = df.tail(limit)
            rows = []
            for _, r in df.iterrows():
                # datetime: "2026-04-07 14:40:00"
                dt_str = str(r["datetime"])
                # 转为 Unix timestamp（秒）
                try:
                    from datetime import datetime
                    dt_obj = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                    ts = int(dt_obj.timestamp() * 1000)
                except Exception:
                    ts = 0
                rows.append({
                    "date":    dt_str,
                    "open":    round(float(r["open"]), 2),
                    "high":    round(float(r["high"]), 2),
                    "low":     round(float(r["low"]), 2),
                    "close":   round(float(r["close"]), 2),
                    "volume":  int(r["volume"]) if r["volume"] == r["volume"] else 0,
                    "hold":    int(r["hold"]) if r["hold"] == r["hold"] else 0,
                    "timestamp": ts,
                })
            return {"symbol": clean_sym, "period": period, "history": rows}
        except Exception as e:
            logger.error(f"[Futures] minute failed {clean_sym}: {e}")
            return success_response({"symbol": clean_sym, "period": period, "history": []}, f"获取失败: {e}")

    else:
        return {"symbol": clean_sym, "period": period, "history": []}


@router.get("/market/rates")
async def market_rates():
    """利率数据"""
    try:
        rows = get_latest_prices(RATE_SYMBOLS)
        return success_response({
            "rates": [
                {
                    "symbol":  r["symbol"],
                    "name":    r["name"],
                    "rate":    r["price"],
                    "timestamp": r["timestamp"],
                }
                for r in rows
            ],
        })
    except Exception as e:
        logger.error(f"[market_rates] 错误: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取利率数据失败: {str(e)}")


# ── 复权因子计算（QFQ/HFQ）────────────────────────────────────────
def _apply_adjustment(rows, method):
    """
    对 OHLCV 历史数据应用复权因子。
    method: 'qfq' 前复权 | 'hfq' 后复权 | 'none' 不复权
    """
    if not rows or method == 'none':
        return rows

    # 取最新一根（最近交易日）的收盘价作为基准
    latest = rows[-1]  # 按 date ASC 排列时最后一条是最新
    latest_close = float(latest.get('close') or 0)
    if latest_close <= 0:
        return rows

    # 前复权：最新价为基准，向前倒推
    # qfq_factor_t = latest_close / close_t
    if method == 'qfq':
        result = []
        for r in rows:
            t_close = float(r.get('close') or 0)
            if t_close > 0:
                factor = latest_close / t_close
                result.append({
                    **r,
                    'open':   round(float(r.get('open')   or 0) * factor, 3),
                    'high':   round(float(r.get('high')   or 0) * factor, 3),
                    'low':    round(float(r.get('low')    or 0) * factor, 3),
                    'close':  round(t_close * factor, 3),
                })
            else:
                result.append({**r})
        return result

    # 后复权：简化版，以最新收盘价为基准等比放大
    # hfq_factor = latest_close（假设基准为1，前复权后价格 × 最新收盘价）
    if method == 'hfq':
        factor = latest_close  # 简化：恒定因子 = 最新收盘价
        return [{
            **r,
            'open':   round(float(r.get('open')  or 0) * factor, 3),
            'high':   round(float(r.get('high')  or 0) * factor, 3),
            'low':    round(float(r.get('low')   or 0) * factor, 3),
            'close':  round(float(r.get('close') or 0) * factor, 3),
        } for r in rows]

    return rows


# ── Task 2: 全球市场（扩容至5个指数）────────────────────────────────────
@router.get("/market/global")
async def market_global():
    """全球核心市场指数（恒生、道琼斯、纳斯达克、标普500、日经）"""
    try:
        is_open_hk, status_hk = is_market_open("HK")
        is_open_us, status_us = is_market_open("US")
        is_open_jp, status_jp = is_market_open("JP")

        status_map = {"HSI": status_hk, "DJI": status_us, "IXIC": status_us, "SPX": status_us, "N225": status_jp}

        rows = get_latest_prices(GLOBAL_SYMBOLS)
        return success_response({
            "global": [
                {
                    "symbol":     r["symbol"],
                    "name":       r["name"],
                    "price":      r["price"],
                    "change_pct": r["change_pct"],
                    "volume":     r["volume"],
                    "status":     status_map.get(r["symbol"], "已休市"),
                    "market":     r["market"],
                }
                for r in rows
            ],
        })
    except Exception as e:
        logger.error(f"[market_global] 错误: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取全球指数失败: {str(e)}")


# ── Task 1: 行业板块（只读缓存，后台Job填充，路由绝不阻塞）──────────────
@router.get("/market/sectors")
async def market_sectors():
    """
    真实行业板块数据 - Task 1: 毫秒级响应
    所有 akshare 调用全部移到后台 Job，API 只读 _SECTORS_CACHE
    """
    try:
        from app.services.sectors_cache import get_sectors
        sectors = get_sectors()
        return success_response({"sectors": sectors})
    except Exception as e:
        logger.error(f"[market_sectors] 错误: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取行业板块失败: {str(e)}")


# ── Phase 6: 期货与大宗商品 ──────────────────────────────────────────────
@router.get("/market/derivatives")
async def market_derivatives():
    """期货与大宗商品（IF期指主力、SGE黄金、WTI原油）"""
    try:
        rows = get_latest_prices(DERIVATIVE_SYMBOLS)
        return success_response({
            "derivatives": [
                {
                    "symbol":     r["symbol"],
                    "name":       r["name"],
                    "price":      r["price"],
                    "change_pct": r["change_pct"],
                    "volume":     r["volume"],
                    "status":     "日内更新",
                    "market":     r["market"],
                }
                for r in rows
            ],
        })
    except Exception as e:
        logger.error(f"[market_derivatives] 错误: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取期货数据失败: {str(e)}")


# ══════════════════════════════════════════════════════════════
# 详细行情（综合报价面板）
# ══════════════════════════════════════════════════════════════

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
    from app.db import get_price_history, get_daily_history

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


# ── 数据源状态管理 ───────────────────────────────────────────────────────
@router.get("/source/status")
async def source_status():
    """获取数据源状态"""
    return success_response(get_source_status())


@router.post("/source/switch")
async def switch_source(source: str):
    """手动切换主源"""
    from app.services.quote_source import set_primary_source
    ok = set_primary_source(source)
    if ok:
        return success_response({"message": f"主源已切换为: {source}"})
    return error_response(ErrorCode.BAD_REQUEST, f"无效的数据源: {source}")


@router.get("/source/test")
async def test_all_sources_api(symbol: str = "sh000001"):
    """测试所有数据源连通性"""
    from app.services.quote_source import test_all_sources
    results = test_all_sources(symbol)
    return success_response(results)


@router.get("/source/config")
async def source_config():
    """获取数据源完整配置"""
    from app.services.quote_source import DATA_SOURCES
    return success_response({
        k: {
            "name": v["name"],
            "name_cn": v.get("name_cn"),
            "type": v["type"],
            "proxy": v.get("proxy"),
            "has_pepb": v.get("has_pepb"),
            "has_realtime": v.get("has_realtime"),
            "api_key": "***" if v.get("api_key") else None,
        } for k, v in DATA_SOURCES.items()
    })


# ── 代理设置 ───────────────────────────────────────────────────────────
_proxy_config = {"proxy_url": "", "enabled": False}

@router.get("/source/proxy")
async def get_proxy():
    """获取当前代理设置"""
    return success_response(_proxy_config)


@router.post("/source/proxy")
async def set_proxy(config: dict):
    """设置代理"""
    global _proxy_config
    proxy = config.get("proxy", "")
    _proxy_config = {
        "proxy_url": proxy,
        "enabled": bool(proxy)
    }
    # 更新所有需要代理的数据源
    from app.services import quote_source
    if proxy:
        for k, v in quote_source.DATA_SOURCES.items():
            if v.get("proxy"):
                v["proxy_url"] = proxy
    return success_response({"message": "代理设置已更新", "proxy": proxy})


# ── 探测所有源状态 ───────────────────────────────────────────────────
@router.get("/source/ping")
async def ping_all_sources():
    """主动探测所有数据源状态（并发异步，不阻塞事件循环）"""
    from app.services import quote_source

    # 测试符号映射
    test_map = {
        "tencent": "sh000001",
        "sina": "sh000001",
        "eastmoney": "sh000001",
        "sina_kline": "sh000001",
        "tencent_hk": "hk00700",
        "alpha_vantage": "AAPL",
    }

    # 并发探测所有源
    async def probe(name: str):
        sym = test_map.get(name, "sh000001")
        return name, await quote_source.test_source_async(name, sym)

    probes = [probe(name) for name in quote_source.DATA_SOURCES.keys()]
    probe_results = await asyncio.gather(*probes, return_exceptions=True)

    results = {}
    for item in probe_results:
        if isinstance(item, Exception):
            continue
        name, result = item
        results[name] = result

    return success_response(results)










# ── AlphaVantage API Key 设置 ─────────────────────────────────────────
@router.get("/source/alpha_vantage_key")
async def get_alpha_vantage_key():
    """获取AlphaVantage API Key"""
    from app.services.quote_source import DATA_SOURCES
    key = DATA_SOURCES.get("alpha_vantage", {}).get("api_key", "")
    return success_response({"api_key": key})


@router.post("/source/alpha_vantage_key")
async def set_alpha_vantage_key(config: dict):
    """设置AlphaVantage API Key"""
    from app.services.quote_source import DATA_SOURCES
    new_key = config.get("api_key", "").strip()
    if new_key:
        DATA_SOURCES["alpha_vantage"]["api_key"] = new_key
        return success_response({"message": "API Key已更新", "api_key": new_key})
    return error_response(ErrorCode.BAD_REQUEST, "API Key不能为空")


# ── 版本与系统信息 ─────────────────────────────────────────────────────
def _read_frontend_version():
    """从 frontend/package.json 动态读取版本号"""
    import json, os
    # __file__ = AlphaTerminal/backend/app/routers/market.py
    # parent.parent.parent = AlphaTerminal/backend/ -> AlphaTerminal/ -> workspace/
    # 需要再加一层 parent = AlphaTerminal/ 然后 /frontend/package.json
    root = Path(__file__).resolve().parent.parent.parent.parent
    pkg_path = root / "frontend" / "package.json"
    try:
        if pkg_path.exists():
            with open(pkg_path, "r", encoding="utf-8") as f:
                return json.load(f).get("version", "unknown")
    except Exception:
        pass
    return "unknown"


@router.get("/system/version")
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


@router.get("/system/info")
async def get_system_info():
    """获取系统详细信息"""
    import platform
    import psutil
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


# ═══════════════════════════════════════════════════════════════
# Level 2 10档买卖盘口
# ═══════════════════════════════════════════════════════════════

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
    except:
        pass

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
            import re
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


# ══════════════════════════════════════════════════════════════
# V2 API: 使用数据源抽象层 (FetcherFactory)
# ══════════════════════════════════════════════════════════════

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
