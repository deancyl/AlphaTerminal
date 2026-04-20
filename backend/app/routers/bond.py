"""
债券行情路由 - Phase 7
数据源：akshare bond_china_yield + 国债/信用债 Mock
缓存策略：5 分钟 TTL，后台异步刷新

Phase B: 统一 API 响应格式
"""
import asyncio
import logging
import threading
import time
from datetime import datetime
from fastapi import APIRouter
import httpx
import pandas as pd

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

class ErrorCode:
    SUCCESS = 0
    BAD_REQUEST = 100
    NOT_FOUND = 104
    INTERNAL_ERROR = 200

# ── 缓存 ────────────────────────────────────────────────────────
_BOND_CACHE      = {}
_CACHE_TTL       = 300   # 5 分钟
_CACHE_LOCK      = threading.RLock()
_LAST_FETCH_TIME = 0
_REFRESH_SEM     = threading.Semaphore(1)

# ── 历史数据缓存（1小时，避免每次请求都爬 akshare）─────────────────
_HISTORY_CACHE      = None   # DataFrame 或 None
_HISTORY_CACHE_TIME = 0
_HISTORY_TTL        = 3600  # 1 小时（秒）

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
    """后台抓取国债收益率曲线（akshare bond_china_yield，5秒超时兜底Mock）
    同时提取商业银行普通债(AAA)曲线，用于计算真实信用利差"""
    global _BOND_CACHE, _LAST_FETCH_TIME
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    def parse_row(row):
        tenors = {}
        for col in ["3月", "6月", "1年", "3年", "5年", "7年", "10年", "30年"]:
            if col in row and row[col] is not None:
                try:
                    tenors[col] = round(float(row[col]), 4)
                except (ValueError, TypeError):
                    pass
        return tenors

    def calc_spreads(gov_row, other_row):
        spreads = {}
        for col in ["3月", "6月", "1年", "3年", "5年", "7年", "10年", "30年"]:
            g = gov_row.get(col)
            o = other_row.get(col)
            if g is not None and o is not None:
                spreads[col] = round((o - g) * 100, 2)   # bps
        return spreads

    try:
        import akshare as ak
        import warnings
        warnings.filterwarnings("ignore")

        df = ak.bond_china_yield()
        if df is not None and not df.empty:
            # 按日期升序排列，按唯一日期索引历史截面
            df = df.sort_values("日期").reset_index(drop=True)
            unique_dates = sorted(df["日期"].unique())

            def get_gov_row(df_slice):
                """从同日期的多曲线行中提取国债行"""
                for _, row in df_slice.iterrows():
                    cn = str(row.get("曲线名称", ""))
                    if "国债" in cn:
                        return parse_row(row)
                return None

            latest_date  = unique_dates[-1]
            latest_df    = df[df["日期"] == latest_date]
            gov_row      = get_gov_row(latest_df)

            # 历史截面：取唯一日期列表中的 1个月前（约22交易日）和 1年前（约252交易日）
            date_1m = unique_dates[-22] if len(unique_dates) >= 22 else None
            date_1y = unique_dates[-252] if len(unique_dates) >= 252 else None
            gov_row_1m = get_gov_row(df[df["日期"] == date_1m]) if date_1m else None
            gov_row_1y = get_gov_row(df[df["日期"] == date_1y]) if date_1y else None

            # 商业银行 AAA 曲线（取最新日期截面）
            comm_row = None
            for _, row in latest_df.iterrows():
                cn = str(row.get("曲线名称", ""))
                if "商业" in cn and comm_row is None:
                    comm_row = parse_row(row)

            spreads = calc_spreads(gov_row, comm_row) if gov_row and comm_row else {}

            with _CACHE_LOCK:
                _BOND_CACHE = {
                    "yield_curve":      gov_row or {},
                    "yield_curve_1m":  gov_row_1m or {},
                    "yield_curve_1y":  gov_row_1y or {},
                    "comm_yield":      comm_row or {},
                    "spreads_bps":     spreads,
                    "update_time":     now_str,
                    "source":          "akshare",
                }
                _LAST_FETCH_TIME = time.time()
            logger.info(f"[Bond] yield curve + spreads + history fetched")
            return
    except Exception as e:
        logger.warning(f"[Bond] bond_china_yield failed: {type(e).__name__}: {e}")

    # 降级兜底：静态 Mock（含历史截面）
    with _CACHE_LOCK:
        _BOND_CACHE = {
            "yield_curve": {
                "3月": 2.0316, "6月": 2.1355, "1年": 2.4525,
                "3年": 2.7645, "5年": 2.9373, "7年": 3.1112,
                "10年": 3.1185, "30年": 3.7156,
            },
            "yield_curve_1m": {
                "3月": 2.0816, "6月": 2.1955, "1年": 2.5225,
                "3年": 2.8345, "5年": 3.0273, "7年": 3.2012,
                "10年": 3.1985, "30年": 3.7956,
            },
            "yield_curve_1y": {
                "3月": 2.2316, "6月": 2.3355, "1年": 2.6525,
                "3年": 2.9645, "5年": 3.1373, "7年": 3.3112,
                "10年": 3.2185, "30年": 3.9156,
            },
            "comm_yield": {
                "3月": 2.5210, "6月": 2.6557, "1年": 2.8580,
                "3年": 3.3284, "5年": 3.5453, "7年": 3.6985,
                "10年": 3.8367, "30年": 4.4626,
            },
            "spreads_bps": {},
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


@router.get("/bond/curve")
async def bond_curve():
    """
    完整债券曲线数据（含信用利差 + 历史曲线对比）

    返回:
      yield_curve:      国债收益率曲线 {期限: 收益率%}
      yield_curve_1m:   1个月前国债收益率曲线（用于曲线形态对比）
      yield_curve_1y:   1年前国债收益率曲线（用于长期趋势判断）
      comm_yield:       商业银行普通债(AAA)收益率曲线
      spreads_bps:      商业债-国债利差 {期限: bps数}（正数=信用溢价）
      update_time:     数据时间
      source:           数据来源

    利差含义：
      bp > 0：信用债收益率高于国债（正常）
      bp < 0：信用债收益率低于国债（异常，可能为数据问题）
    """
    try:
        cache = _get_bond_cache()
        return success_response({
            "yield_curve":     cache.get("yield_curve", {}),
            "yield_curve_1m":  cache.get("yield_curve_1m", {}),
            "yield_curve_1y":  cache.get("yield_curve_1y", {}),
            "comm_yield":      cache.get("comm_yield", {}),
            "spreads_bps":     cache.get("spreads_bps", {}),
            "update_time":     cache.get("update_time", ""),
            "source":          cache.get("source", "unknown"),
        })
    except Exception as e:
        logger.error(f"[bond_curve] 错误: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取债券曲线失败: {str(e)}")


@router.get("/bond/yield_curve")
async def bond_yield_curve():
    """
    国债收益率曲线（仅国债，回落兼容）
    """
    try:
        cache = _get_bond_cache()
        return success_response({
            "yield_curve": cache.get("yield_curve", {}),
            "update_time": cache.get("update_time", ""),
            "source": cache.get("source", "unknown"),
        })
    except Exception as e:
        logger.error(f"[bond_yield_curve] 错误: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取国债收益率曲线失败: {str(e)}")


@router.get("/bond/active")
async def bond_active():
    """
    活跃债券列表（Mock 数据 + 真实来源开发中）
    返回：{bonds: [{code, name, rate, ytm, change_bps, type}]}
    """
    return success_response({
        "bonds": _MOCK_BONDS,
        "source": "mock",
    })


async def _get_bond_history_df():
    """带 1 小时 TTL 的内存缓存，避免每次请求都爬 akshare"""
    global _HISTORY_CACHE, _HISTORY_CACHE_TIME
    now = time.time()
    if _HISTORY_CACHE is None or (now - _HISTORY_CACHE_TIME) > _HISTORY_TTL:
        import akshare as ak, warnings
        warnings.filterwarnings("ignore")
        logger.info("[Bond] _get_bond_history_df: fetching fresh data from akshare (cache miss)")
        df = await asyncio.to_thread(ak.bond_china_yield)
        _HISTORY_CACHE = df
        _HISTORY_CACHE_TIME = now
    return _HISTORY_CACHE


@router.get("/bond/history")
async def bond_history(tenor: str = "10年", period: str = "1Y"):
    """
    国债历史分位数（用于收益率曲线图表的历史背景）
    - tenor: 期限（1年/3年/5年/10年/30年）
    - period: 回溯窗口（1M/3M/6M/1Y/3Y）
    返回: {tenor, current, percentile, history: [{date, yield}], source}
    """
    try:
        import numpy as np
        df = await _get_bond_history_df()
        if df is None or df.empty:
            raise ValueError("empty df")
        tenor_col = next((c for c in df.columns if c == tenor or c.startswith(tenor + '(') or c.startswith(tenor + '（')), None)
        if not tenor_col:
            raise ValueError(f"tenor column not found: {tenor}")
        # 安全转换：过滤非数字值
        raw = df[tenor_col].dropna()
        numeric = pd.to_numeric(raw, errors='coerce').dropna()
        if numeric.empty:
            raise ValueError(f"no numeric data in column: {tenor_col}")
        current_yield = numeric.iloc[-1] if len(numeric) else None
        if current_yield is not None:
            percentile = float(np.sum(numeric < current_yield) / len(numeric) * 100)
        else:
            percentile = None
        days_map = {"1M": 22, "3M": 66, "6M": 132, "1Y": 252, "3Y": 756}
        n_rows = days_map.get(period, 252)
        history = [
            {"date": str(r[0]), "yield": float(r[1])}
            for r in df[[df.columns[0], tenor_col]].dropna().tail(n_rows).values
        ]
        return success_response({
            "tenor": tenor,
            "current": round(current_yield, 6) if current_yield else None,
            "percentile": round(percentile, 1) if percentile is not None else None,
            "history": history,
            "source": "akshare",
        })
    except Exception as e:
        logger.warning(f"[Bond] history endpoint error: {e}")
        return success_response({
            "tenor": tenor,
            "current": _BOND_CACHE.get("yield_curve", {}).get(tenor, 0),
            "percentile": None,
            "history": [],
            "source": "error",
        })


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
