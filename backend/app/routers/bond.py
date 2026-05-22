"""
债券行情路由 - Phase 7
数据源：akshare bond_china_yield + 国债/信用债 Mock
缓存策略：5 分钟 TTL，后台异步刷新

Phase B: 统一 API 响应格式
Phase C: 多数据源降级 + 数据新鲜度检查
"""
import asyncio
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from fastapi import APIRouter, Query
from app.utils.errors import success_response, error_response, ErrorCode
from app.services.data_cache import get_cache
from app.services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from app.services.fetchers.bond_fetcher import get_bond_fetcher
from app.utils.error_decorator import handle_errors

_bond_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="bond_")

logger = logging.getLogger(__name__)
router = APIRouter()

_cache = get_cache()
NAMESPACE = "bond:"
TTL = 300  # 5 minutes
_CACHE_LOCK = threading.RLock()
_LAST_FETCH_TIME = 0

# Circuit breaker for bond data fetching
_bond_cb = CircuitBreaker(
    "bond_akshare",
    CircuitBreakerConfig(
        failure_threshold=5,
        timeout=60.0,
    )
)

_bond_fetcher = get_bond_fetcher(_bond_executor)


_HISTORY_CACHE_KEY = f"{NAMESPACE}history_df"
_HISTORY_TTL = 3600  # 1 hour

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


async def _fetch_curve_data_for_cache():
    """Fetch function for get_or_set_async - returns curve data dict
    
    Uses bond_fetcher's multi-source fallback chain:
    1. bond_spot_quote (real-time dealer quotes) - PRIMARY
    2. bond_spot_deal (real-time deals)
    3. akshare bond_china_yield (historical, may be stale)
    4. CFETS / Chinabond
    5. Mock data
    """
    global _LAST_FETCH_TIME

    try:
        if not _bond_cb.is_available():
            logger.warning("[Bond] Circuit breaker is OPEN, using mock fallback")
            with _CACHE_LOCK:
                _LAST_FETCH_TIME = time.time()
            return _bond_fetcher._get_mock_data(is_stale=True)

        # Use bond_fetcher's multi-source fallback chain
        # This will try bond_spot_quote (real-time) first, then fallback to other sources
        data = await _bond_fetcher.fetch_yield_curve()

        if data and data.get("yield_curve"):
            _bond_cb.record_success()
            with _CACHE_LOCK:
                _LAST_FETCH_TIME = time.time()

            source = data.get("source", "unknown")
            last_update = data.get("last_update", "")
            logger.info(f"[Bond] Yield curve fetched from {source}, last_update: {last_update}")

            return data
        else:
            _bond_cb.record_failure()
            logger.warning("[Bond] bond_fetcher returned empty data")

    except asyncio.TimeoutError:
        _bond_cb.record_failure()
        logger.warning("[Bond] bond_fetcher timeout", exc_info=True)
    except Exception as e:
        _bond_cb.record_failure()
        logger.warning(f"[Bond] bond_fetcher failed: {type(e).__name__}: {e}", exc_info=True)

    # Last resort: mock data
    with _CACHE_LOCK:
        _LAST_FETCH_TIME = time.time()
    logger.warning("[Bond] Using mock fallback")
    return _bond_fetcher._get_mock_data(is_stale=True)


async def _fetch_history_df_for_cache():
    """Fetch function for get_or_set_async - returns DataFrame"""
    import akshare as ak
    import warnings
    warnings.filterwarnings("ignore")
    logger.info("[Bond] _fetch_history_df_for_cache: fetching fresh data from akshare (cache miss)")
    try:
        loop = asyncio.get_running_loop()
        df = await asyncio.wait_for(
            loop.run_in_executor(_bond_executor, ak.bond_china_yield),
            timeout=30.0
        )
        return df
    except asyncio.TimeoutError:
        logger.warning("[Bond] _fetch_history_df_for_cache timeout after 30s", exc_info=True)
        return None


@router.get("/bond/curve")
@handle_errors(module="bond")
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
      last_update:      数据最后更新日期
      is_stale:         数据是否过期（超过7天）
      warning:           数据过期警告（仅当数据过期时返回）
      warning_level:     警告级别 (critical/warning)

    利差含义：
      bp > 0：信用债收益率高于国债（正常）
      bp < 0：信用债收益率低于国债（异常，可能为数据问题）
    """
    try:
        cache_data = await _cache.get_or_set_async(
            key=f"{NAMESPACE}main",
            ttl=TTL,
            fetch_fn=_fetch_curve_data_for_cache
        )
        source = cache_data.get("source", "unknown")
        last_update = cache_data.get("last_update", "")
        is_stale = cache_data.get("is_stale", False)

        warning = None
        warning_level = None
        if is_stale:
            warning = f"⚠️ 数据已过期，最后更新于 {last_update}。建议接入中债登或上交所数据源。"
            warning_level = "critical"
        elif source == "akshare" and last_update:
            try:
                last_update_dt = datetime.strptime(last_update, "%Y-%m-%d")
                days_old = (datetime.now() - last_update_dt).days
                if days_old > 1:
                    warning = f"数据源 akshare bond_china_yield 最后更新于 {last_update}（{days_old}天前）。"
                    warning_level = "warning"
            except (ValueError, TypeError):
                pass

        return success_response({
            "yield_curve":     cache_data.get("yield_curve", {}),
            "yield_curve_1m":  cache_data.get("yield_curve_1m", {}),
            "yield_curve_1y":  cache_data.get("yield_curve_1y", {}),
            "comm_yield":      cache_data.get("comm_yield", {}),
            "spreads_bps":     cache_data.get("spreads_bps", {}),
            "update_time":     cache_data.get("update_time", ""),
            "source":          source,
            "last_update":     last_update,
            "is_stale":        is_stale,
            "warning":         warning,
            "warning_level":   warning_level,
        })
    except Exception as e:
        logger.error(f"[bond_curve] 错误: {e}", exc_info=True)
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取债券曲线失败: {str(e)}")


@router.get("/bond/yield_curve")
@handle_errors(module="bond")
async def bond_yield_curve():
    """
    国债收益率曲线（仅国债，回落兼容）
    """
    try:
        cache_data = await _cache.get_or_set_async(
            key=f"{NAMESPACE}main",
            ttl=TTL,
            fetch_fn=_fetch_curve_data_for_cache
        )
        return success_response({
            "yield_curve": cache_data.get("yield_curve", {}),
            "update_time": cache_data.get("update_time", ""),
            "source": cache_data.get("source", "unknown"),
        })
    except Exception as e:
        logger.error(f"[bond_yield_curve] 错误: {e}", exc_info=True)
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取国债收益率曲线失败: {str(e)}")


@router.get("/bond/active")
@handle_errors(module="bond")
async def bond_active():
    """
    活跃债券列表（Mock 数据 + 真实来源开发中）
    返回：{bonds: [{code, name, rate, ytm, change_bps, type}], source, is_demo}
    """
    return success_response({
        "bonds": _MOCK_BONDS,
        "source": "mock",
        "is_demo": True,
        "warning": "当前显示演示数据，真实数据源开发中",
    })


@router.get("/bond/history")
@handle_errors(module="bond")
async def bond_history(
    tenor: str = Query("10年", description="期限（1年/3年/5年/10年/30年）"),
    period: str = Query("1Y", description="回溯窗口（1M/3M/6M/1Y/3Y）"),
    limit: int = Query(252, ge=1, le=1000, description="返回条数限制"),
    offset: int = Query(0, ge=0, description="偏移量（用于分页）"),
):
    """
    国债历史分位数（用于收益率曲线图表的历史背景）
    - tenor: 期限（1年/3年/5年/10年/30年）
    - period: 回溯窗口（1M/3M/6M/1Y/3Y）
    - limit: 返回条数限制（默认252，最大1000）
    - offset: 偏移量（用于分页）
    返回: {tenor, current, percentile, history: [{date, yield}], total, limit, offset, source}
    """
    try:
        df = await _cache.get_or_set_async(
            key=_HISTORY_CACHE_KEY,
            ttl=_HISTORY_TTL,
            fetch_fn=_fetch_history_df_for_cache
        )
        if df is None or df.empty:
            raise ValueError("empty df")

        curve_name_col = df.columns[0]
        if "曲线名称" in df.columns or curve_name_col in df.columns:
            col_to_use = "曲线名称" if "曲线名称" in df.columns else curve_name_col
            df_gov = df[df[col_to_use].astype(str).str.contains("国债")].copy()
        else:
            df_gov = df.copy()

        if df_gov.empty:
            df_gov = df

        date_col = "日期" if "日期" in df_gov.columns else (df_gov.columns[1] if len(df_gov.columns) > 1 else df_gov.columns[0])
        if date_col in df_gov.columns:
            df_gov = df_gov.sort_values(date_col)

        tenor_col = next((c for c in df_gov.columns if c == tenor or c.startswith(tenor + '(') or c.startswith(tenor + '（')), None)
        if not tenor_col:
            raise ValueError(f"tenor column not found: {tenor}")

        numeric = []
        for val in df_gov[tenor_col]:
            if val is not None:
                try:
                    numeric.append(float(val))
                except (ValueError, TypeError):
                    pass
        if not numeric:
            raise ValueError(f"no numeric data in column: {tenor_col}")
        current_yield = numeric[-1] if numeric else None
        if current_yield is not None:
            percentile = float(sum(1 for v in numeric if v < current_yield) / len(numeric) * 100)
        else:
            percentile = None
        days_map = {"1M": 22, "3M": 66, "6M": 132, "1Y": 252, "3Y": 756}
        n_rows = days_map.get(period, 252)

        history = []
        tail_df = df_gov[[date_col, tenor_col]].dropna().tail(n_rows)
        for _, r in tail_df.iterrows():
            try:
                d_val = r[date_col]
                date_str = d_val.strftime("%Y-%m-%d") if hasattr(d_val, "strftime") else str(d_val)
                y_val = float(r[tenor_col])
                history.append({"date": date_str, "yield": y_val})
            except (ValueError, TypeError):
                pass

        total = len(history)

        if offset > 0 or limit < total:
            history = history[offset:offset + limit]

        return success_response({
            "tenor": tenor,
            "current": round(current_yield, 6) if current_yield else None,
            "percentile": round(percentile, 1) if percentile is not None else None,
            "history": history,
            "total": total,
            "limit": limit,
            "offset": offset,
            "source": "akshare",
        })
    except Exception as e:
        logger.warning(f"[Bond] history endpoint error: {e}", exc_info=True)
        cached = _cache.get(f"{NAMESPACE}main") or {}
        return success_response({
            "tenor": tenor,
            "current": cached.get("yield_curve", {}).get(tenor, 0),
            "percentile": None,
            "history": [],
            "total": 0,
            "limit": limit,
            "offset": offset,
            "source": "error",
        })


def _init_cache_warmup():
    """Start background cache warmup with real data."""
    global _LAST_FETCH_TIME
    logger.info("[Bond] Starting background cache warmup...")

    async def warmup():
        try:
            data = await _fetch_curve_data_for_cache()
            if data and data.get("yield_curve"):
                logger.info(f"[Bond] Cache warmup complete, source: {data.get('source')}")
            else:
                logger.warning("[Bond] Cache warmup returned empty data")
        except Exception as e:
            logger.warning(f"[Bond] Cache warmup failed: {e}", exc_info=True)

    import asyncio
    try:
        loop = asyncio.get_running_loop()
        asyncio.create_task(warmup())
    except RuntimeError:
        pass

_init_cache_warmup()


@router.get("/bond/health")
@handle_errors(module="bond")
async def bond_health():
    """Bond module health check endpoint."""
    return success_response({
        "status": "ok",
        "circuit_breaker": {
            "state": _bond_cb._state.value,
            "is_available": _bond_cb.is_available(),
        },
        "cache": {
            "has_data": _cache.get(f"{NAMESPACE}main") is not None,
            "last_fetch_time": _LAST_FETCH_TIME,
        },
    })


@router.get("/bond/risk_free_rate", summary="获取无风险利率")
@handle_errors(module="bond")
async def get_risk_free_rate():
    """
    获取当前无风险利率（10年期国债收益率）

    Returns:
        rate: 无风险利率（小数形式，如0.0275表示2.75%）
        source: 数据来源
        timestamp: 时间戳
    """
    try:
        # Fetch yield curve data
        curve_data = await _cache.get_or_set_async(
            key=f"{NAMESPACE}main",
            ttl=TTL,
            fetch_fn=_fetch_curve_data_for_cache
        )

        # Find 10Y yield
        yield_curve = curve_data.get("yield_curve", {})
        for tenor, rate in yield_curve.items():
            if tenor == "10年" or "10" in tenor:
                rate_decimal = rate / 100  # Convert percentage to decimal
                return success_response({
                    "rate": rate_decimal,
                    "source": curve_data.get("source", "unknown") + "_10y",
                    "timestamp": curve_data.get("update_time", "")
                })

        # Fallback if 10Y not found
        logger.warning("[Bond] 10Y yield not found in curve data, using fallback")
        return success_response({
            "rate": 0.025,
            "source": "fallback",
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        logger.warning(f"[Bond] Failed to get risk-free rate: {e}", exc_info=True)
        return success_response({
            "rate": 0.025,
            "source": "fallback",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })
