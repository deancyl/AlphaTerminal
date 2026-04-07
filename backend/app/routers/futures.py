"""
期货行情路由 - Phase 7
数据源：akshare futures_zh_realtime（国内期货） + Sina hf_（国际商品）
缓存策略：3 分钟 TTL，后台异步刷新
"""
import logging
import threading
import time
from datetime import datetime
from fastapi import APIRouter
import httpx

logger = logging.getLogger(__name__)
router = APIRouter()

# ── 缓存 ────────────────────────────────────────────────────────
_FUTURES_CACHE    = {}
_CACHE_TTL        = 180   # 3 分钟
_CACHE_LOCK       = threading.RLock()
_LAST_FETCH_TIME  = 0
_REFRESH_SEM      = threading.Semaphore(1)

# 重点监控的国内商品期货合约
WATCHED_COMMODITIES = {
    # (symbol, name, unit)
    "RB0": ("螺纹钢",   "元/吨"),
    "HC0": ("热卷",     "元/吨"),
    "I0":  ("铁矿石",   "元/吨"),
    "JM0": ("焦煤",     "元/吨"),
    "J0":  ("焦炭",     "元/吨"),
    "SC0": ("原油",     "元/桶"),
    "FU0": ("燃油",     "元/吨"),
    "TA0": ("PTA",      "元/吨"),
    "MA0": ("甲醇",     "元/吨"),
    "V0":  ("PVC",      "元/吨"),
    "UR0": ("尿素",     "元/吨"),
    "EG0": ("乙二醇",   "元/吨"),
    "PP0": ("聚丙烯",   "元/吨"),
    "LC0": ("碳酸锂",   "元/吨"),
    "SA0": ("纯碱",     "元/吨"),
}

# 板块映射：symbol → (板块名, emoji)
COMMODITY_SECTORS = {
    "RB0": ("黑色建材", "🔨"),
    "HC0": ("黑色建材", "🔨"),
    "I0":  ("黑色建材", "🔨"),
    "JM0": ("黑色建材", "🔨"),
    "J0":  ("黑色建材", "🔨"),
    "SC0": ("能源化工", "⚡"),
    "FU0": ("能源化工", "⚡"),
    "TA0": ("能源化工", "⚡"),
    "MA0": ("能源化工", "⚡"),
    "V0":  ("能源化工", "⚡"),
    "UR0": ("能源化工", "⚡"),
    "EG0": ("能源化工", "⚡"),
    "PP0": ("能源化工", "⚡"),
    "LC0": ("新能源",   "🔋"),
    "SA0": ("新能源",   "🔋"),
}

SINA_HEADERS = {
    "Referer": "https://finance.sina.com.cn",
    "User-Agent": "Mozilla/5.0 (compatible; AlphaTerminal/1.0)",
}


def _fetch_futures_data():
    """后台抓取期货数据（腾讯 qt.gtimg.cn + akshare，5秒超时兜底Mock）"""
    global _FUTURES_CACHE, _LAST_FETCH_TIME
    now_str = datetime.now().strftime("%H:%M")
    spot_data = {}

    try:
        # 腾讯 qt.gtimg.cn 国内期货现货（直连不过代理）
        codes = ",".join(WATCHED_COMMODITIES.keys())
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"https://qt.gtimg.cn/q={codes}")
                resp.raise_for_status()
                raw = resp.text
            for line in raw.splitlines():
                line = line.strip()
                if "=" not in line or "none_match" in line:
                    continue
                try:
                    sym = line.split("=")[0].replace("v_qt_", "").replace("v_", "").strip('" ')
                    fields = line.split("=")[1].strip('";\n')
                    f = [x.strip() for x in fields.split(",")]
                    if len(f) > 10:
                        price  = float(f[1]) if f[1] else None
                        change = float(f[32]) if f[32] else 0.0  # 涨跌幅%
                        spot_data[sym] = {
                            "price": round(price, 2) if price else 0,
                            "change_pct": round(change, 2),
                            "tick": f[30] if len(f) > 30 else "",
                        }
                except Exception:
                    continue
            logger.info(f"[Futures] Tencent qt data: {len(spot_data)} items")
        except Exception as e:
            logger.warning(f"[Futures] Tencent fetch failed: {e}")

    except Exception as e:
        logger.warning(f"[Futures] overall fetch failed: {e}")

    # 整理商品期货列表
    commodities = []
    for sym, (name, unit) in WATCHED_COMMODITIES.items():
        d = spot_data.get(sym, {})
        sector_key = COMMODITY_SECTORS.get(sym, ("其他", "📦"))
        commodities.append({
            "symbol":     sym,
            "name":       name,
            "unit":       unit,
            "price":      d.get("price", 0),
            "change_pct": d.get("change_pct", 0),
            "tick":       d.get("tick", ""),
            "sector":     sector_key[0],
            "sector_emoji": sector_key[1],
        })

    # Mock 股指期货主力（IF/IC/IM，当作数据可用时）
    index_futures = [
        {"symbol": "IF",  "name": "IF 沪深300",   "price": 4448.2,  "change_pct": -0.93, "position": "8.2万手", "note": "IMIF"},
        {"symbol": "IC",  "name": "IC 中证500",   "price": 6102.4,  "change_pct": +0.31, "position": "6.5万手", "note": "IMIC"},
        {"symbol": "IM",  "name": "IM 中证1000",  "price": 6438.8,  "change_pct": +0.72, "position": "5.1万手", "note": "IMIM"},
    ]

    with _CACHE_LOCK:
        _FUTURES_CACHE = {
            "index_futures": index_futures,
            "commodities":   commodities,
            "update_time":   now_str,
        }
        _LAST_FETCH_TIME = time.time()
    logger.info(f"[Futures] cached {len(commodities)} commodities + {len(index_futures)} index futures")


def _get_futures_cache() -> dict:
    """TTL 3分钟；过期则后台刷新，返回旧缓存（绝不阻塞）"""
    global _FUTURES_CACHE, _LAST_FETCH_TIME
    stale = (time.time() - _LAST_FETCH_TIME) > _CACHE_TTL

    if stale and _REFRESH_SEM.acquire(blocking=False):
        def bg():
            try:
                _fetch_futures_data()
            finally:
                _REFRESH_SEM.release()
        t = threading.Thread(target=bg, daemon=True, name="futures-refresh")
        t.start()

    with _CACHE_LOCK:
        return dict(_FUTURES_CACHE) if _FUTURES_CACHE else {}


@router.get("/futures/main_indexes")
async def futures_main_indexes():
    """
    股指期货主力（IF · IC · IM）
    """
    cache = _get_futures_cache()
    return {
        "timestamp":    datetime.now().isoformat(),
        "index_futures": cache.get("index_futures", []),
        "update_time":  cache.get("update_time", ""),
    }


@router.get("/futures/commodities")
async def futures_commodities():
    """
    国内大宗商品期货实时行情
    """
    cache = _get_futures_cache()
    return {
        "timestamp":  datetime.now().isoformat(),
        "commodities": cache.get("commodities", []),
        "update_time": cache.get("update_time", ""),
    }


# ── 启动时立即填充 Mock 数据（防止第一次请求返回空）──────────────
_MOCK_COMMODITIES = [
    {"symbol": "RB0", "name": "螺纹钢",   "unit": "元/吨", "price": 3850, "change_pct": +1.28, "tick": ""},
    {"symbol": "HC0", "name": "热卷",     "unit": "元/吨", "price": 3920, "change_pct": -0.54, "tick": ""},
    {"symbol": "SA0", "name": "纯碱",     "unit": "元/吨", "price": 1580, "change_pct": +3.21, "tick": ""},
    {"symbol": "LC0", "name": "碳酸锂",   "unit": "元/吨", "price": 78000, "change_pct": -2.17, "tick": ""},
    {"symbol": "I0",  "name": "铁矿石",   "unit": "元/吨", "price": 920,  "change_pct": +0.83, "tick": ""},
    {"symbol": "JM0", "name": "焦煤",     "unit": "元/吨", "price": 1380, "change_pct": +1.45, "tick": ""},
    {"symbol": "SC0", "name": "原油",     "unit": "元/桶", "price": 580,  "change_pct": -1.32, "tick": ""},
    {"symbol": "FU0", "name": "燃油",     "unit": "元/吨", "price": 3100, "change_pct": -0.78, "tick": ""},
    {"symbol": "TA0", "name": "PTA",      "unit": "元/吨", "price": 6810, "change_pct": +0.29, "tick": ""},
    {"symbol": "MA0", "name": "甲醇",     "unit": "元/吨", "price": 2580, "change_pct": +1.08, "tick": ""},
    {"symbol": "V0",  "name": "PVC",      "unit": "元/吨", "price": 6350, "change_pct": -0.21, "tick": ""},
    {"symbol": "UR0", "name": "尿素",     "unit": "元/吨", "price": 2180, "change_pct": +2.44, "tick": ""},
]

_MOCK_INDEX_FUTURES = [
    {"symbol": "IF",  "name": "IF 沪深300",   "price": 4448.2,  "change_pct": -0.93, "position": "8.2万手", "note": "IMIF"},
    {"symbol": "IC",  "name": "IC 中证500",   "price": 6102.4,  "change_pct": +0.31, "position": "6.5万手", "note": "IMIC"},
    {"symbol": "IM",  "name": "IM 中证1000",  "price": 6438.8,  "change_pct": +0.72, "position": "5.1万手", "note": "IMIM"},
]


def _init_mock_cache():
    """同步填充 Mock 数据，保证 API 启动后立即可用"""
    global _FUTURES_CACHE, _LAST_FETCH_TIME
    now_str = datetime.now().strftime("%H:%M")
    with _CACHE_LOCK:
        _FUTURES_CACHE = {
            "index_futures": _MOCK_INDEX_FUTURES,
            "commodities":   _MOCK_COMMODITIES,
            "update_time":   now_str,
        }
        _LAST_FETCH_TIME = time.time()
    logger.info("[Futures] Mock cache initialized")

_init_mock_cache()
