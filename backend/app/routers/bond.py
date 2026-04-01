"""
债券行情路由 - Phase 7
数据源：akshare bond_china_yield + 国债/信用债 Mock
缓存策略：5 分钟 TTL，后台异步刷新
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
_BOND_CACHE      = {}
_CACHE_TTL       = 300   # 5 分钟
_CACHE_LOCK      = threading.RLock()
_LAST_FETCH_TIME = 0
_REFRESH_SEM     = threading.Semaphore(1)

# ── Mock 活跃债券数据（无可靠免费接口时的兜底）────────────────────
_MOCK_BONDS = [
    {"code": "019736", "name": "23附息国债05",  "rate": "1.721%", "ytm": 1.721, "change_bps": +1.3,  "type": "国债"},
    {"code": "019747", "name": "22附息国债15",  "rate": "1.638%", "ytm": 1.638, "change_bps": -2.1,  "type": "国债"},
    {"code": "092318001", "name": "22农发09",   "rate": "2.104%", "ytm": 2.104, "change_bps": -0.8,  "type": "政策性银行债"},
    {"code": "220312",   "name": "23进出01",   "rate": "1.953%", "ytm": 1.953, "change_bps": +0.5,  "type": "进出口债"},
    {"code": "220215",   "name": "22国开02",   "rate": "1.892%", "ytm": 1.892, "change_bps": -1.2,  "type": "国开债"},
    {"code": "152671",   "name": "23重庆债07",  "rate": "2.341%", "ytm": 2.341, "change_bps": +2.1,  "type": "地方债"},
    {"code": "220020",   "name": "22河北债22", "rate": "2.218%", "ytm": 2.218, "change_bps": -0.4,  "type": "地方债"},
    {"code": "136082",   "name": "AAA企业债(3Y)","rate":"2.89%", "ytm": 2.89,  "change_bps": +3.7,  "type": "企业债AAA"},
    {"code": "136255",   "name": "AA+企业债(3Y)","rate":"3.24%", "ytm": 3.24,  "change_bps": -1.5,  "type": "企业债AA+"},
    {"code": "188930",   "name": "城投债(5Y)AA+","rate":"3.01%", "ytm": 3.01,  "change_bps": +0.9,  "type": "城投债"},
]


def _fetch_bond_data():
    """后台抓取国债收益率曲线（akshare bond_china_yield，5秒超时兜底Mock）"""
    global _BOND_CACHE, _LAST_FETCH_TIME
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    try:
        import akshare as ak
        import warnings
        warnings.filterwarnings("ignore")

        df = ak.bond_china_yield()
        if df is not None and not df.empty:
            latest_date = df["日期"].max()
            row = df[df["日期"] == latest_date].iloc[-1]

            # 构建收益率曲线 {期限: 收益率}
            tenors = {}
            for col in ["3月", "6月", "1年", "3年", "5年", "7年", "10年", "30年"]:
                if col in row and row[col] is not None:
                    try:
                        tenors[col] = round(float(row[col]), 4)
                    except (ValueError, TypeError):
                        pass

            with _CACHE_LOCK:
                _BOND_CACHE = {
                    "yield_curve": tenors,
                    "update_time": now_str,
                    "source": "akshare",
                }
                _LAST_FETCH_TIME = time.time()
            logger.info(f"[Bond] yield curve fetched: {tenors}")
            return
    except Exception as e:
        logger.warning(f"[Bond] bond_china_yield failed: {type(e).__name__}: {e}")

    # 降级兜底：静态 Mock 收益率曲线
    with _CACHE_LOCK:
        _BOND_CACHE = {
            "yield_curve": {
                "3月": 2.0316, "6月": 2.1355, "1年": 2.4525,
                "3年": 2.7645, "5年": 2.9373, "7年": 3.1112,
                "10年": 3.1185, "30年": 3.7156,
            },
            "update_time": now_str,
            "source": "mock",
        }
        _LAST_FETCH_TIME = time.time()
    logger.info("[Bond] Using mock yield curve fallback")


def _get_bond_cache() -> dict:
    """TTL 5分钟；过期则后台刷新，返回旧缓存（绝不阻塞）"""
    global _BOND_CACHE, _LAST_FETCH_TIME
    stale = (time.time() - _LAST_FETCH_TIME) > _CACHE_TTL

    if stale and _REFRESH_SEM.acquire(blocking=False):
        def bg():
            try:
                _fetch_bond_data()
            finally:
                _REFRESH_SEM.release()
        t = threading.Thread(target=bg, daemon=True, name="bond-refresh")
        t.start()

    with _CACHE_LOCK:
        return dict(_BOND_CACHE) if _BOND_CACHE else {}


@router.get("/bond/yield_curve")
async def bond_yield_curve():
    """
    国债收益率曲线
    返回：{tenors: {期限: 收益率%}, update_time: str, source: str}
    """
    cache = _get_bond_cache()
    return {
        "timestamp": datetime.now().isoformat(),
        "yield_curve": cache.get("yield_curve", {}),
        "update_time": cache.get("update_time", ""),
        "source": cache.get("source", "unknown"),
    }


@router.get("/bond/active")
async def bond_active():
    """
    活跃债券列表（Mock 数据 + 真实来源开发中）
    返回：{bonds: [{code, name, rate, ytm, change_bps, type}]}
    """
    return {
        "timestamp": datetime.now().isoformat(),
        "bonds": _MOCK_BONDS,
        "source": "mock",
    }


# ── 启动时立即填充 Mock 数据（防止第一次请求返回空）──────────────
def _init_mock_cache():
    """同步填充 Mock 数据，保证 API 启动后立即可用"""
    global _BOND_CACHE, _LAST_FETCH_TIME
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    with _CACHE_LOCK:
        _BOND_CACHE = {
            "yield_curve": {
                "3月": 2.0316, "6月": 2.1355, "1年": 2.4525,
                "3年": 2.7645, "5年": 2.9373, "7年": 3.1112,
                "10年": 3.1185, "30年": 3.7156,
            },
            "update_time": now_str,
            "source": "mock",
        }
        _LAST_FETCH_TIME = time.time()
    logger.info("[Bond] Mock yield curve initialized")

_init_mock_cache()
