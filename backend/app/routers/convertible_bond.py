"""
可转债行情路由
数据源：akshare bond_zh_cov, bond_zh_hs_cov_spot, bond_cov_comparison, bond_zh_cov_value_analysis
缓存策略：5 分钟 TTL，后台异步刷新

Timeout Behavior:
    Background refresh threads have 30s timeout.
    API endpoints return 504 on timeout.
"""
import asyncio
import logging
import threading
import time
from datetime import datetime
from fastapi import APIRouter
import akshare as ak
from app.utils.response import success_response, error_response, ErrorCode
from app.config.timeout import BOND_REFRESH_TIMEOUT

logger = logging.getLogger(__name__)
router = APIRouter()

_COV_LIST_CACHE = {}
_COV_LIST_CACHE_TIME = 0
_COV_SPOT_CACHE = {}
_COV_SPOT_CACHE_TIME = 0
_COV_COMPARE_CACHE = {}
_COV_COMPARE_CACHE_TIME = 0
_CACHE_TTL = 300
_CACHE_LOCK = threading.RLock()
_REFRESH_SEM = threading.Semaphore(1)

# ── Mock 可转债数据（无可靠免费接口时的兜底）────────────────────
_MOCK_COV_LIST = [
    {
        "code": "113527",
        "name": "核建转债",
        "underlying_code": "601611",
        "underlying_name": "中国核建",
        "underlying_price": 8.52,
        "conversion_price": 8.85,
        "conversion_value": 96.27,
        "bond_price": 112.50,
        "conversion_premium": 16.85,
        "credit_rating": "AAA",
        "issue_size": 30.0,
        "subscribe_date": "2019-04-08"
    },
    {
        "code": "110059",
        "name": "浦发转债",
        "underlying_code": "600000",
        "underlying_name": "浦发银行",
        "underlying_price": 10.25,
        "conversion_price": 12.50,
        "conversion_value": 82.00,
        "bond_price": 105.80,
        "conversion_premium": 29.02,
        "credit_rating": "AAA",
        "issue_size": 500.0,
        "subscribe_date": "2019-10-28"
    },
    {
        "code": "113050",
        "name": "上银转债",
        "underlying_code": "601229",
        "underlying_name": "上海银行",
        "underlying_price": 6.85,
        "conversion_price": 8.15,
        "conversion_value": 84.05,
        "bond_price": 108.20,
        "conversion_premium": 28.73,
        "credit_rating": "AAA",
        "issue_size": 200.0,
        "subscribe_date": "2021-01-25"
    }
]

_MOCK_COV_SPOT = [
    {"symbol": "sh113527", "name": "核建转债", "trade": 112.50, "pricechange": 0.35, "volume": 125000, "amount": 14062500, "code": "113527", "ticktime": "15:00:00"},
    {"symbol": "sh110059", "name": "浦发转债", "trade": 105.80, "pricechange": -0.15, "volume": 850000, "amount": 89930000, "code": "110059", "ticktime": "15:00:00"},
    {"symbol": "sh113050", "name": "上银转债", "trade": 108.20, "pricechange": 0.20, "volume": 320000, "amount": 34624000, "code": "113050", "ticktime": "15:00:00"}
]

_MOCK_COV_COMPARE = [
    {
        "code": "113527",
        "name": "核建转债",
        "bond_price": 112.50,
        "underlying_code": "601611",
        "underlying_name": "中国核建",
        "conversion_price": 8.85,
        "conversion_value": 96.27,
        "conversion_premium": 16.85,
        "pure_bond_premium": 8.50,
        "put_trigger_price": 6.20,
        "call_trigger_price": 11.51
    },
    {
        "code": "110059",
        "name": "浦发转债",
        "bond_price": 105.80,
        "underlying_code": "600000",
        "underlying_name": "浦发银行",
        "conversion_price": 12.50,
        "conversion_value": 82.00,
        "conversion_premium": 29.02,
        "pure_bond_premium": 5.80,
        "put_trigger_price": 8.75,
        "call_trigger_price": 16.25
    }
]


async def _fetch_cov_list_async():
    """Async version with cross-platform timeout using asyncio.wait_for"""
    global _COV_LIST_CACHE, _COV_LIST_CACHE_TIME
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    try:
        import warnings
        warnings.filterwarnings("ignore")
        
        # Use asyncio.wait_for for cross-platform timeout
        df = await asyncio.wait_for(
            asyncio.to_thread(ak.bond_zh_cov),
            timeout=float(BOND_REFRESH_TIMEOUT)
        )
        
        if df is not None and not df.empty:
            bonds = []
            for _, row in df.iterrows():
                try:
                    bond = {
                        "code": str(row.get("债券代码", "")),
                        "name": str(row.get("债券简称", "")),
                        "subscribe_date": str(row.get("申购日期", "")),
                        "underlying_code": str(row.get("正股代码", "")),
                        "underlying_name": str(row.get("正股简称", "")),
                        "underlying_price": _safe_float(row.get("正股价")),
                        "conversion_price": _safe_float(row.get("转股价")),
                        "conversion_value": _safe_float(row.get("转股价值")),
                        "bond_price": _safe_float(row.get("债现价")),
                        "conversion_premium": _safe_float(row.get("转股溢价率")),
                        "issue_size": _safe_float(row.get("发行规模")),
                        "credit_rating": str(row.get("信用评级", "")),
                    }
                    bonds.append(bond)
                except Exception as e:
                    logger.debug(f"[ConvertibleBond] parse row error: {e}")
                    continue
            
            with _CACHE_LOCK:
                _COV_LIST_CACHE = {
                    "bonds": bonds,
                    "total": len(bonds),
                    "update_time": now_str,
                    "source": "akshare",
                }
                _COV_LIST_CACHE_TIME = time.time()
            logger.info(f"[ConvertibleBond] list fetched, total: {len(bonds)}")
            return
    except asyncio.TimeoutError:
        logger.warning(f"[ConvertibleBond] bond_zh_cov timed out after {BOND_REFRESH_TIMEOUT}s")
    except Exception as e:
        logger.warning(f"[ConvertibleBond] bond_zh_cov failed: {type(e).__name__}: {e}")
    
    with _CACHE_LOCK:
        _COV_LIST_CACHE = {
            "bonds": _MOCK_COV_LIST,
            "total": len(_MOCK_COV_LIST),
            "update_time": now_str,
            "source": "mock",
        }
        _COV_LIST_CACHE_TIME = time.time()
    logger.info("[ConvertibleBond] Using mock list fallback")


async def _fetch_cov_spot_async():
    """Async version with cross-platform timeout using asyncio.wait_for"""
    global _COV_SPOT_CACHE, _COV_SPOT_CACHE_TIME
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    try:
        import warnings
        warnings.filterwarnings("ignore")
        
        df = await asyncio.wait_for(
            asyncio.to_thread(ak.bond_zh_hs_cov_spot),
            timeout=float(BOND_REFRESH_TIMEOUT)
        )
        
        if df is not None and not df.empty:
            spots = []
            for _, row in df.iterrows():
                try:
                    spot = {
                        "symbol": str(row.get("symbol", "")),
                        "name": str(row.get("name", "")),
                        "trade": _safe_float(row.get("trade")),
                        "pricechange": _safe_float(row.get("pricechange")),
                        "changepercent": _safe_float(row.get("changepercent")),
                        "volume": _safe_float(row.get("volume")),
                        "amount": _safe_float(row.get("amount")),
                        "code": str(row.get("code", "")),
                        "ticktime": str(row.get("ticktime", "")),
                    }
                    spots.append(spot)
                except Exception as e:
                    logger.debug(f"[ConvertibleBond] parse spot row error: {e}")
                    continue
            
            with _CACHE_LOCK:
                _COV_SPOT_CACHE = {
                    "spots": spots,
                    "total": len(spots),
                    "update_time": now_str,
                    "source": "akshare",
                }
                _COV_SPOT_CACHE_TIME = time.time()
            logger.info(f"[ConvertibleBond] spot fetched, total: {len(spots)}")
            return
    except asyncio.TimeoutError:
        logger.warning(f"[ConvertibleBond] bond_zh_hs_cov_spot timed out after {BOND_REFRESH_TIMEOUT}s")
    except Exception as e:
        logger.warning(f"[ConvertibleBond] bond_zh_hs_cov_spot failed: {type(e).__name__}: {e}")
    
    with _CACHE_LOCK:
        _COV_SPOT_CACHE = {
            "spots": _MOCK_COV_SPOT,
            "total": len(_MOCK_COV_SPOT),
            "update_time": now_str,
            "source": "mock",
        }
        _COV_SPOT_CACHE_TIME = time.time()
    logger.info("[ConvertibleBond] Using mock spot fallback")


async def _fetch_cov_compare_async():
    """Async version with cross-platform timeout using asyncio.wait_for"""
    global _COV_COMPARE_CACHE, _COV_COMPARE_CACHE_TIME
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    try:
        import warnings
        warnings.filterwarnings("ignore")
        
        df = await asyncio.wait_for(
            asyncio.to_thread(ak.bond_cov_comparison),
            timeout=float(BOND_REFRESH_TIMEOUT)
        )
        
        if df is not None and not df.empty:
            compares = []
            for _, row in df.iterrows():
                try:
                    compare = {
                        "code": str(row.get("转债代码", "")),
                        "name": str(row.get("转债名称", "")),
                        "bond_price": _safe_float(row.get("转债最新价")),
                        "underlying_code": str(row.get("正股代码", "")),
                        "underlying_name": str(row.get("正股名称", "")),
                        "conversion_price": _safe_float(row.get("转股价")),
                        "conversion_value": _safe_float(row.get("转股价值")),
                        "conversion_premium": _safe_float(row.get("转股溢价率")),
                        "pure_bond_premium": _safe_float(row.get("纯债溢价率")),
                        "put_trigger_price": _safe_float(row.get("回售触发价")),
                        "call_trigger_price": _safe_float(row.get("强赎触发价")),
                    }
                    compares.append(compare)
                except Exception as e:
                    logger.debug(f"[ConvertibleBond] parse compare row error: {e}")
                    continue
            
            with _CACHE_LOCK:
                _COV_COMPARE_CACHE = {
                    "compares": compares,
                    "total": len(compares),
                    "update_time": now_str,
                    "source": "akshare",
                }
                _COV_COMPARE_CACHE_TIME = time.time()
            logger.info(f"[ConvertibleBond] compare fetched, total: {len(compares)}")
            return
    except asyncio.TimeoutError:
        logger.warning(f"[ConvertibleBond] bond_cov_comparison timed out after {BOND_REFRESH_TIMEOUT}s")
    except Exception as e:
        logger.warning(f"[ConvertibleBond] bond_cov_comparison failed: {type(e).__name__}: {e}")
    
    with _CACHE_LOCK:
        _COV_COMPARE_CACHE = {
            "compares": _MOCK_COV_COMPARE,
            "total": len(_MOCK_COV_COMPARE),
            "update_time": now_str,
            "source": "mock",
        }
        _COV_COMPARE_CACHE_TIME = time.time()
    logger.info("[ConvertibleBond] Using mock compare fallback")


def _safe_float(val):
    """安全转换为 float，失败返回 None；处理 NaN/Inf"""
    if val is None:
        return None
    try:
        f = float(val)
        # 检查 NaN/Inf，这些值不能 JSON 序列化
        if not isinstance(f, float) or f != f:  # NaN check (NaN != NaN)
            return None
        if f == float('inf') or f == float('-inf'):
            return None
        return f
    except (ValueError, TypeError):
        return None


def _get_cov_list_cache() -> dict:
    """TTL 5分钟；过期则后台刷新，返回旧缓存（绝不阻塞）"""
    global _COV_LIST_CACHE, _COV_LIST_CACHE_TIME
    stale = (time.time() - _COV_LIST_CACHE_TIME) > _CACHE_TTL
    
    if stale and _REFRESH_SEM.acquire(blocking=False):
        def bg():
            try:
                asyncio.run(_fetch_cov_list_async())
            finally:
                _REFRESH_SEM.release()
        t = threading.Thread(target=bg, daemon=True, name="cov-list-refresh")
        t.start()
    
    with _CACHE_LOCK:
        return dict(_COV_LIST_CACHE) if _COV_LIST_CACHE else {}


def _get_cov_spot_cache() -> dict:
    """TTL 5分钟；过期则后台刷新，返回旧缓存（绝不阻塞）"""
    global _COV_SPOT_CACHE, _COV_SPOT_CACHE_TIME
    stale = (time.time() - _COV_SPOT_CACHE_TIME) > _CACHE_TTL
    
    if stale and _REFRESH_SEM.acquire(blocking=False):
        def bg():
            try:
                asyncio.run(_fetch_cov_spot_async())
            finally:
                _REFRESH_SEM.release()
        t = threading.Thread(target=bg, daemon=True, name="cov-spot-refresh")
        t.start()
    
    with _CACHE_LOCK:
        return dict(_COV_SPOT_CACHE) if _COV_SPOT_CACHE else {}


def _get_cov_compare_cache() -> dict:
    """TTL 5分钟；过期则后台刷新，返回旧缓存（绝不阻塞）"""
    global _COV_COMPARE_CACHE, _COV_COMPARE_CACHE_TIME
    stale = (time.time() - _COV_COMPARE_CACHE_TIME) > _CACHE_TTL
    
    if stale and _REFRESH_SEM.acquire(blocking=False):
        def bg():
            try:
                asyncio.run(_fetch_cov_compare_async())
            finally:
                _REFRESH_SEM.release()
        t = threading.Thread(target=bg, daemon=True, name="cov-compare-refresh")
        t.start()
    
    with _CACHE_LOCK:
        return dict(_COV_COMPARE_CACHE) if _COV_COMPARE_CACHE else {}


@router.get("/bond/convertible/list")
async def convertible_bond_list():
    """
    可转债列表
    返回：所有可转债基本信息 + 转股溢价率分析
    
    字段说明：
      code: 债券代码
      name: 债券简称
      subscribe_date: 申购日期
      underlying_code: 正股代码
      underlying_name: 正股简称
      underlying_price: 正股价
      conversion_price: 转股价
      conversion_value: 转股价值
      bond_price: 债现价
      conversion_premium: 转股溢价率(%)
      issue_size: 发行规模(亿)
      credit_rating: 信用评级
    """
    try:
        cache = _get_cov_list_cache()
        return success_response({
            "bonds": cache.get("bonds", []),
            "total": cache.get("total", 0),
            "update_time": cache.get("update_time", ""),
            "source": cache.get("source", "unknown"),
        })
    except Exception as e:
        logger.error(f"[convertible_bond_list] 错误: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取可转债列表失败: {str(e)}")


@router.get("/bond/convertible/spot")
async def convertible_bond_spot():
    """
    可转债实时行情
    返回：实时报价、涨跌幅、成交量
    
    字段说明：
      symbol: 交易代码（含交易所前缀）
      name: 债券名称
      trade: 最新价
      pricechange: 涨跌额
      changepercent: 涨跌幅(%)
      volume: 成交量
      amount: 成交额
      code: 债券代码
      ticktime: 更新时间
    """
    try:
        cache = _get_cov_spot_cache()
        return success_response({
            "spots": cache.get("spots", []),
            "total": cache.get("total", 0),
            "update_time": cache.get("update_time", ""),
            "source": cache.get("source", "unknown"),
        })
    except Exception as e:
        logger.error(f"[convertible_bond_spot] 错误: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取可转债实时行情失败: {str(e)}")


@router.get("/bond/convertible/comparison")
async def convertible_bond_comparison():
    """
    可转债比价表
    返回：转股溢价率、纯债溢价率对比
    
    字段说明：
      code: 转债代码
      name: 转债名称
      bond_price: 转债最新价
      underlying_code: 正股代码
      underlying_name: 正股名称
      conversion_price: 转股价
      conversion_value: 转股价值
      conversion_premium: 转股溢价率(%)
      pure_bond_premium: 纯债溢价率(%)
      put_trigger_price: 回售触发价
      call_trigger_price: 强赎触发价
    """
    try:
        cache = _get_cov_compare_cache()
        return success_response({
            "compares": cache.get("compares", []),
            "total": cache.get("total", 0),
            "update_time": cache.get("update_time", ""),
            "source": cache.get("source", "unknown"),
        })
    except Exception as e:
        logger.error(f"[convertible_bond_comparison] 错误: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取可转债比价表失败: {str(e)}")


@router.get("/bond/convertible/{symbol}/value")
async def convertible_bond_value(symbol: str):
    try:
        import warnings
        warnings.filterwarnings("ignore")
        
        df = await asyncio.wait_for(
            asyncio.to_thread(ak.bond_zh_cov_value_analysis, symbol=symbol),
            timeout=BOND_REFRESH_TIMEOUT
        )
        
        if df is not None and not df.empty:
            values = []
            for _, row in df.iterrows():
                try:
                    value = {
                        "date": str(row.get("日期", "")),
                        "close": _safe_float(row.get("收盘价")),
                        "pure_bond_value": _safe_float(row.get("纯债价值")),
                        "conversion_value": _safe_float(row.get("转股价值")),
                        "pure_bond_premium": _safe_float(row.get("纯债溢价率")),
                        "conversion_premium": _safe_float(row.get("转股溢价率")),
                    }
                    values.append(value)
                except Exception as e:
                    logger.debug(f"[ConvertibleBond] parse value row error: {e}")
                    continue
            
            return success_response({
                "symbol": symbol,
                "values": values,
                "total": len(values),
                "source": "akshare",
            })
        else:
            raise ValueError("empty dataframe")
    except asyncio.TimeoutError:
        logger.warning(f"[ConvertibleBond] bond_zh_cov_value_analysis timed out for {symbol}")
        return error_response("请求超时，请稍后重试", code=504)
    except Exception as e:
        logger.warning(f"[ConvertibleBond] bond_zh_cov_value_analysis failed for {symbol}: {e}")
        return success_response({
            "symbol": symbol,
            "values": [],
            "total": 0,
            "source": "error",
            "message": f"获取可转债价值分析失败: {str(e)}",
        })


# ── 启动时立即填充 Mock 数据（防止第一次请求返回空）──────────────
def _init_mock_cache():
    """同步填充 Mock 数据，保证 API 启动后立即可用"""
    global _COV_LIST_CACHE, _COV_LIST_CACHE_TIME, _COV_SPOT_CACHE, _COV_SPOT_CACHE_TIME, _COV_COMPARE_CACHE, _COV_COMPARE_CACHE_TIME
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    with _CACHE_LOCK:
        _COV_LIST_CACHE = {
            "bonds": _MOCK_COV_LIST,
            "total": len(_MOCK_COV_LIST),
            "update_time": now_str,
            "source": "mock",
        }
        _COV_LIST_CACHE_TIME = time.time()
        
        _COV_SPOT_CACHE = {
            "spots": _MOCK_COV_SPOT,
            "total": len(_MOCK_COV_SPOT),
            "update_time": now_str,
            "source": "mock",
        }
        _COV_SPOT_CACHE_TIME = time.time()
        
        _COV_COMPARE_CACHE = {
            "compares": _MOCK_COV_COMPARE,
            "total": len(_MOCK_COV_COMPARE),
            "update_time": now_str,
            "source": "mock",
        }
        _COV_COMPARE_CACHE_TIME = time.time()
    
    logger.info("[ConvertibleBond] Mock data initialized")

_init_mock_cache()
