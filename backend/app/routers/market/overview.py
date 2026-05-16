"""
市场概览接口 - Market Overview Endpoints
包含：宏观、概览、国内指数、全球指数、利率、资金流向、期货大宗
"""
import asyncio
import logging
import threading
import time
from datetime import datetime
from fastapi import APIRouter
import httpx
import re

from app.db import get_latest_prices
from app.utils.market_status import is_market_open
from app.utils.response import success_response, error_response, ErrorCode
from app.services.data_cache import get_cache

logger = logging.getLogger(__name__)
router = APIRouter(tags=["market"])

_cache = get_cache()
NAMESPACE = "overview:"
_MACRO_CACHE_KEY = f"{NAMESPACE}macro"
_MACRO_TTL = 60  # 1 minute
_MACRO_CACHE_LOCK = threading.RLock()
_LAST_FETCH_TIME = 0
_REFRESH_SEMAPHORE = threading.Semaphore(1)

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
    global _LAST_FETCH_TIME
    now_str = datetime.now().strftime("%H:%M")

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

        _cache.set(_MACRO_CACHE_KEY, results, ttl=_MACRO_TTL)
        with _MACRO_CACHE_LOCK:
            _LAST_FETCH_TIME = time.time()
        logger.info(f"[Macro] Fetched: USD={usdcny_price} GOLD={gold_price}¥ WTI={wti_price} VHSI={vhsi_price}({vhsi_pct}%)")

    except Exception as e:
        logger.warning(f"[Macro] Fetch failed, keeping old cache: {e}")


def _get_macro_data() -> dict:
    """
    返回宏观缓存（TTL 1 分钟）。
    缓存空或过期时：立即返回旧缓存，同时后台触发一次异步刷新（绝不阻塞 API）。
    """
    global _LAST_FETCH_TIME
    cached = _cache.get(_MACRO_CACHE_KEY)
    stale = cached is None or (time.time() - _LAST_FETCH_TIME) > _MACRO_TTL

    if stale and _REFRESH_SEMAPHORE.acquire(blocking=False):
        def bg():
            try:
                _fetch_macro_data()
            finally:
                _REFRESH_SEMAPHORE.release()
        t = threading.Thread(target=bg, daemon=True, name="macro-refresh")
        t.start()

    return cached if cached else {}


# ── 辅助函数 ─────────────────────────────────────────────────────────────
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


# ═════════════════════════════════════════════════════════════════════════
# API 端点
# ═════════════════════════════════════════════════════════════════════════

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


@router.get("/market/fund_flow")
async def get_fund_flow():
    """市场资金流向（超大单/大单/中单/小单主力净流入）- 5秒超时防前端断开"""
    import akshare as ak
    import random

    try:
        # 【核心修复】：线程池执行 + 5秒绝对超时，防止 akshare 阻塞事件循环和前端超时断开
        df = await asyncio.wait_for(
            asyncio.to_thread(ak.stock_market_fund_flow),
            timeout=5.0
        )
        df = df.tail(30)

        # 向量化处理
        df_work = df.copy()
        df_work['date'] = df_work['日期'].astype(str)
        df_work['sh_close'] = df_work['上证-收盘价'].apply(lambda x: float(x) if x else 0)
        df_work['sh_chg'] = df_work['上证-涨跌幅'].apply(lambda x: float(x) if x else 0)
        df_work['sz_close'] = df_work['深证-收盘价'].apply(lambda x: float(x) if x else 0)
        df_work['sz_chg'] = df_work['深证-涨跌幅'].apply(lambda x: float(x) if x else 0)
        df_work['main_net'] = df_work['主力净流入-净额'].apply(lambda x: int(float(x)) if x else 0)
        df_work['main_pct'] = df_work['主力净流入-净占比'].apply(lambda x: float(x) if x else 0)
        df_work['large_net'] = df_work['大单净流入-净额'].apply(lambda x: int(float(x)) if x else 0)
        df_work['large_pct'] = df_work['大单净流入-净占比'].apply(lambda x: float(x) if x else 0)
        df_work['medium_net'] = df_work['中单净流入-净额'].apply(lambda x: int(float(x)) if x else 0)
        df_work['medium_pct'] = df_work['中单净流入-净占比'].apply(lambda x: float(x) if x else 0)
        df_work['small_net'] = df_work['小单净流入-净额'].apply(lambda x: int(float(x)) if x else 0)
        df_work['small_pct'] = df_work['小单净流入-净占比'].apply(lambda x: float(x) if x else 0)
        result = df_work[['date', 'sh_close', 'sh_chg', 'sz_close', 'sz_chg',
                         'main_net', 'main_pct', 'large_net', 'large_pct',
                         'medium_net', 'medium_pct', 'small_net', 'small_pct']].to_dict('records')

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
        d = (datetime.now() - __import__('datetime').timedelta(days=29 - i)).strftime("%m-%d")
        main_net = random.randint(-500000000, 500000000)
        mock_result.append({
            "date": d, "main_net": main_net, "main_pct": round(random.uniform(-5, 5), 2),
            "large_net": int(main_net * random.uniform(0.6, 0.9)), "large_pct": round(random.uniform(-2, 2), 2),
            "medium_net": int(main_net * random.uniform(0.2, 0.4)), "medium_pct": round(random.uniform(-1, 1), 2),
            "small_net": int(-main_net * random.uniform(0.5, 0.8)), "small_pct": round(random.uniform(-3, 3), 2),
        })
    return success_response({"items": mock_result, "total": 30, "source": "fallback_mock"})


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
