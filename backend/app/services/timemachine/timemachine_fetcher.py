"""
TimeMachine Fetcher - 三级数据回退机制

三级数据回退链:
Level 1: market_data_daily 表 (本地SQLite缓存)
Level 2: DataCache (内存缓存)
Level 3: akshare (实时数据源)

功能特性:
- 自动去前缀 (sh600519 → 600519)
- CircuitBreaker 保护
- 新鲜度计算
- L1/L2 缓存持久化
"""

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from app.db.database import get_conn
from app.services.data_cache import get_cache
from app.utils.executor import get_executor

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# CircuitBreaker 导入（延迟导入避免循环依赖）
# ═══════════════════════════════════════════════════════════════

_timemachine_cb = None

def _get_circuit_breaker():
    """延迟获取 CircuitBreaker 实例"""
    global _timemachine_cb
    if _timemachine_cb is None:
        try:
            from app.services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState
            _timemachine_cb = CircuitBreaker(
                name="timemachine",
                config=CircuitBreakerConfig(
                    failure_threshold=5,
                    timeout=60,
                    success_threshold=2
                )
            )
        except ImportError:
            logger.warning("[TimeMachine] CircuitBreaker not available")
    return _timemachine_cb


# ═══════════════════════════════════════════════════════════════
# 主要函数
# ═══════════════════════════════════════════════════════════════

async def fetch_kline_with_fallback(
    symbol: str,
    start_date: date,
    end_date: date,
    circuit_breaker=None
) -> Dict:
    """
    三级数据回退链:
    Level 1: market_data_daily表 (本地SQLite缓存)
    Level 2: DataCache (内存缓存)
    Level 3: akshare (实时数据源)
    
    Args:
        symbol: 股票代码（带前缀，如 sh600519）
        start_date: 开始日期
        end_date: 结束日期
        circuit_breaker: 可选的熔断器实例
    
    Returns:
        {
            "bars": [...],
            "source_type": "cache" | "real" | "akshare",
            "timestamp": "2024-01-15T10:30:00",
            "is_mock": False,
            "freshness_seconds": 3600
        }
    """
    
    # 去前缀: sh600519 → 600519
    code = _unprefix_symbol(symbol)
    
    # 获取熔断器（如果未提供）
    if circuit_breaker is None:
        circuit_breaker = _get_circuit_breaker()
    
    # ═════════════════════════════════════════════════════════
    # Level 1: 从 market_data_daily 表获取
    # ═════════════════════════════════════════════════════════
    db_bars = await _fetch_from_sqlite_async(code, start_date, end_date)
    min_required = _min_required_bars(start_date, end_date)
    
    if db_bars and len(db_bars) >= min_required:
        logger.info(f"[TimeMachine] Level 1 SQLite hit: {symbol}, {len(db_bars)} bars (min: {min_required})")
        return {
            "bars": db_bars,
            "source_type": "cache",
            "timestamp": datetime.now().isoformat(),
            "is_mock": False,
            "freshness_seconds": _calculate_freshness(db_bars)
        }
    
    # ═════════════════════════════════════════════════════════
    # Level 2: 从 DataCache 获取
    # ═════════════════════════════════════════════════════════
    cache = get_cache()
    cache_key = f"timemachine:{symbol}:{start_date}:{end_date}"
    
    # 使用 get_with_sqlite_fallback 方法（L2缓存降级）
    cached = cache.get_with_sqlite_fallback(cache_key, source="timemachine")
    if cached:
        logger.info(f"[TimeMachine] Level 2 Cache hit: {cache_key}")
        # 确保 source_type 标记为 cache
        if isinstance(cached, dict):
            cached["source_type"] = "cache"
        return cached
    
    # ═════════════════════════════════════════════════════════
    # Level 3: 从 akshare 获取（受CircuitBreaker保护）
    # ═════════════════════════════════════════════════════════
    
    # 检查熔断器状态
    if circuit_breaker:
        try:
            from app.services.circuit_breaker import CircuitState
            if circuit_breaker.state == CircuitState.OPEN:
                logger.warning(f"[TimeMachine] Level 3 skipped: CB OPEN for {symbol}")
                return {
                    "bars": [],
                    "source_type": "cache",
                    "timestamp": datetime.now().isoformat(),
                    "is_mock": False,
                    "error": "Service temporarily unavailable (circuit breaker open)"
                }
        except (AttributeError, ImportError):
            pass  # 熔断器不可用，继续执行
    
    # 从 akshare 获取数据
    loop = asyncio.get_running_loop()
    try:
        bars = await asyncio.wait_for(
            loop.run_in_executor(
                get_executor(),
                _fetch_from_akshare,
                code,
                start_date,
                end_date
            ),
            timeout=30.0
        )
        
        # 构建结果
        result = {
            "bars": bars,
            "source_type": "akshare",
            "timestamp": datetime.now().isoformat(),
            "is_mock": False,
            "freshness_seconds": 0  # 实时数据
        }
        
        # 缓存结果（L1 内存缓存，5分钟）
        cache.set(cache_key, result, ttl=300)
        
        # 持久化到 SQLite（L2 缓存，24小时）
        cache.set_with_sqlite_persist(
            cache_key,
            result,
            ttl=86400,
            source="timemachine"
        )
        
        logger.info(f"[TimeMachine] Level 3 Akshare fetch: {symbol}, {len(bars)} bars")
        
        # 记录成功（恢复熔断器）
        if circuit_breaker:
            try:
                circuit_breaker.record_success()
            except (AttributeError, TypeError):
                pass
        
        return result
        
    except asyncio.TimeoutError:
        logger.error(f"[TimeMachine] Level 3 Timeout for {symbol}", exc_info=True)
        
        # 记录失败（触发熔断器）
        if circuit_breaker:
            try:
                circuit_breaker.record_failure()
            except (AttributeError, TypeError):
                pass
        
        return {
            "bars": [],
            "source_type": "cache",
            "timestamp": datetime.now().isoformat(),
            "is_mock": False,
            "error": "Timeout"
        }
        
    except Exception as e:
        logger.error(f"[TimeMachine] Level 3 Error for {symbol}: {e}", exc_info=True)
        
        # 记录失败（触发熔断器）
        if circuit_breaker:
            try:
                circuit_breaker.record_failure()
            except (AttributeError, TypeError):
                pass
        
        return {
            "bars": [],
            "source_type": "cache",
            "timestamp": datetime.now().isoformat(),
            "is_mock": False,
            "error": str(e)
        }


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════

def _unprefix_symbol(symbol: str) -> str:
    """
    去除股票代码前缀
    sh600519 → 600519
    sz000001 → 000001
    600519 → 600519
    """
    if symbol.startswith(("sh", "sz", "bj")):
        return symbol[2:]
    return symbol


async def _fetch_from_sqlite_async(symbol: str, start_date: date, end_date: date) -> List[Dict]:
    """异步从 market_data_daily 表查询历史数据"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        get_executor(),
        _fetch_from_sqlite_sync,
        symbol,
        start_date,
        end_date
    )


def _fetch_from_sqlite_sync(symbol: str, start_date: date, end_date: date) -> List[Dict]:
    """同步从 market_data_daily 表查询历史数据"""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT date, open, high, low, close, volume, amount
            FROM market_data_daily
            WHERE symbol = ? AND date >= ? AND date <= ?
            ORDER BY date ASC
            """,
            (symbol, start_date.isoformat(), end_date.isoformat())
        ).fetchall()
        
        if not rows:
            return []
        
        return [
            {
                "date": row["date"],
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["volume"]),
                "amount": float(row["amount"] or 0)
            }
            for row in rows
        ]


def _fetch_from_akshare(symbol: str, start_date: date, end_date: date) -> List[Dict]:
    """从 akshare 获取实时数据"""
    try:
        import akshare as ak
        
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            adjust="qfq",
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d")
        )
        
        if df is None or df.empty:
            return []
        
        bars = []
        for _, row in df.iterrows():
            bars.append({
                "date": str(row["日期"]),
                "open": float(row["开盘"]),
                "high": float(row["最高"]),
                "low": float(row["最低"]),
                "close": float(row["收盘"]),
                "volume": int(row["成交量"]),
                "amount": float(row.get("成交额", 0) or 0)
            })
        
        return bars
        
    except Exception as e:
        logger.error(f"[TimeMachine] akshare error: {e}", exc_info=True)
        return []


def _min_required_bars(start_date: date, end_date: date) -> int:
    """
    计算最小需要的bar数量（约80%交易日）
    用于判断 SQLite 缓存是否足够
    """
    days = (end_date - start_date).days
    # 估算交易日：约 5/7 的天数
    trading_days = int(days * 5 / 7)
    # 返回 80% 的交易日
    return int(trading_days * 0.8)


def _calculate_freshness(bars: List[Dict]) -> int:
    """
    计算数据新鲜度（秒）
    基于最后一条数据的日期
    """
    if not bars:
        return 0
    
    try:
        last_date_str = bars[-1].get("date", "")
        if not last_date_str:
            return 0
        
        # 尝试解析日期
        last_dt = datetime.strptime(last_date_str, "%Y-%m-%d")
        now = datetime.now()
        
        # 计算时间差（秒）
        delta = (now - last_dt).total_seconds()
        return max(0, int(delta))
        
    except (ValueError, TypeError, KeyError) as e:
        logger.debug(f"[TimeMachine] Failed to calculate freshness: {e}")
        return 0


# ═══════════════════════════════════════════════════════════════
# 导出函数
# ═══════════════════════════════════════════════════════════════

__all__ = [
    "fetch_kline_with_fallback",
]
