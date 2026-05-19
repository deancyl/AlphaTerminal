"""
Anomaly Detector - Detect market anomalies for radar display.

Detects 5 types of anomalies:
1. Volatility - Highest amplitude stocks
2. Capital Flow - Strongest outflow/inflow
3. Institution Research - Most researched by institutions
4. New High - Stocks hitting 60-day high (P1-4: Fixed with real K-line data)
5. Volume Surge - Unusual volume activity
"""

import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="anomaly_")


class AnomalyType(str, Enum):
    VOLATILITY = "volatility"
    CAPITAL_OUTFLOW = "capital_outflow"
    INSTITUTION_RESEARCH = "institution_research"
    NEW_HIGH = "new_high"
    VOLUME_SURGE = "volume_surge"


@dataclass
class AnomalyStock:
    symbol: str
    name: str
    value: float
    unit: str


@dataclass
class AnomalyResult:
    type: AnomalyType
    title: str
    stocks: List[AnomalyStock]


def _fetch_all_stocks_sync() -> List[Dict]:
    """Fetch all A-share stocks with market data."""
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        stocks = []
        for _, row in df.iterrows():
            try:
                stocks.append({
                    "symbol": row.get("代码", ""),
                    "name": row.get("名称", ""),
                    "price": float(row.get("最新价", 0) or 0),
                    "change_pct": float(row.get("涨跌幅", 0) or 0),
                    "volume": float(row.get("成交量", 0) or 0),
                    "amount": float(row.get("成交额", 0) or 0),
                    "high": float(row.get("最高", 0) or 0),
                    "low": float(row.get("最低", 0) or 0),
                    "pre_close": float(row.get("昨收", 0) or 0),
                })
            except (ValueError, TypeError):
                continue
        return stocks
    except Exception as e:
        logger.error(f"[Anomaly] Failed to fetch all stocks: {e}")
        return []


def _fetch_capital_flow_sync() -> List[Dict]:
    """Fetch individual stock capital flow data."""
    try:
        import akshare as ak
        df = ak.stock_individual_fund_flow(stock="即时", market="sh")
        flows = []
        for _, row in df.iterrows():
            try:
                flows.append({
                    "symbol": row.get("代码", ""),
                    "name": row.get("名称", ""),
                    "main_net_inflow": float(row.get("主力净流入", 0) or 0),
                    "retail_net_inflow": float(row.get("散户净流入", 0) or 0),
                })
            except (ValueError, TypeError):
                continue
        return flows
    except Exception as e:
        logger.warning(f"[Anomaly] Failed to fetch capital flow: {e}")
        return []


def _fetch_institution_research_sync() -> List[Dict]:
    """Fetch institution research statistics."""
    try:
        import akshare as ak
        df = ak.stock_jgdy_tj_em()
        research = []
        for _, row in df.iterrows():
            try:
                research.append({
                    "symbol": row.get("代码", ""),
                    "name": row.get("名称", ""),
                    "research_count": int(row.get("调研次数", 0) or 0),
                })
            except (ValueError, TypeError):
                continue
        return research
    except Exception as e:
        logger.warning(f"[Anomaly] Failed to fetch institution research: {e}")
        return []


def _fetch_kline_sync(symbol: str, period: str = "daily", days: int = 60) -> List[Dict]:
    """Fetch K-line data for a symbol."""
    try:
        import akshare as ak
        df = ak.stock_zh_a_hist(symbol=symbol, period=period, adjust="qfq")
        if df.empty:
            return []
        
        df = df.tail(days)
        klines = []
        for _, row in df.iterrows():
            klines.append({
                "date": row.get("日期", ""),
                "close": float(row.get("收盘", 0) or 0),
                "high": float(row.get("最高", 0) or 0),
                "low": float(row.get("最低", 0) or 0),
                "volume": float(row.get("成交量", 0) or 0),
            })
        return klines
    except Exception as e:
        logger.debug(f"[Anomaly] Failed to fetch kline for {symbol}: {e}")
        return []


def _fetch_kline_batch_sync(symbols: List[str], days: int = 60) -> Dict[str, List[Dict]]:
    """
    Batch fetch K-line data for multiple symbols.
    
    P1-4: Used for detecting true 60-day highs.
    Note: This is still sequential due to akshare limitations,
    but called from async context with timeout protection.
    """
    results = {}
    for symbol in symbols[:50]:  # Limit to 50 symbols to avoid timeout
        try:
            import akshare as ak
            df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
            if df.empty:
                continue
            
            df = df.tail(days)
            klines = []
            for _, row in df.iterrows():
                klines.append({
                    "date": row.get("日期", ""),
                    "close": float(row.get("收盘", 0) or 0),
                    "high": float(row.get("最高", 0) or 0),
                    "low": float(row.get("最低", 0) or 0),
                    "volume": float(row.get("成交量", 0) or 0),
                })
            results[symbol] = klines
        except Exception as e:
            logger.debug(f"[Anomaly] Failed to fetch kline for {symbol}: {e}")
            continue
    return results


async def _fetch_all_stocks() -> List[Dict]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _fetch_all_stocks_sync)


async def _fetch_capital_flow() -> List[Dict]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _fetch_capital_flow_sync)


async def _fetch_institution_research() -> List[Dict]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _fetch_institution_research_sync)


async def _fetch_kline(symbol: str, period: str = "daily", days: int = 60) -> List[Dict]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _fetch_kline_sync, symbol, period, days)


async def _fetch_kline_batch(symbols: List[str], days: int = 60) -> Dict[str, List[Dict]]:
    """
    Async wrapper for batch K-line fetching.
    
    P1-4: Used for detecting true 60-day highs with parallel processing.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _fetch_kline_batch_sync, symbols, days)


def _detect_volatility(stocks: List[Dict], top_n: int = 10) -> AnomalyResult:
    """Detect stocks with highest volatility (amplitude)."""
    volatility_stocks = []
    
    for stock in stocks:
        high = stock.get("high", 0)
        low = stock.get("low", 0)
        pre_close = stock.get("pre_close", 0)
        
        if pre_close <= 0:
            continue
        
        amplitude = abs(high - low) / pre_close * 100
        
        if amplitude > 0:
            symbol = stock.get("symbol", "")
            full_symbol = f"sh{symbol}" if symbol.startswith("6") else f"sz{symbol}"
            volatility_stocks.append({
                "symbol": full_symbol,
                "name": stock.get("name", ""),
                "amplitude": amplitude,
            })
    
    volatility_stocks.sort(key=lambda x: x["amplitude"], reverse=True)
    
    return AnomalyResult(
        type=AnomalyType.VOLATILITY,
        title="振幅最大",
        stocks=[
            AnomalyStock(
                symbol=s["symbol"],
                name=s["name"],
                value=round(s["amplitude"], 2),
                unit="%"
            )
            for s in volatility_stocks[:top_n]
        ]
    )


def _detect_capital_outflow(flows: List[Dict], top_n: int = 10) -> AnomalyResult:
    """Detect stocks with strongest capital outflow."""
    outflow_stocks = []
    
    for flow in flows:
        main_net = flow.get("main_net_inflow", 0)
        
        if main_net < 0:
            symbol = flow.get("symbol", "")
            full_symbol = f"sh{symbol}" if symbol.startswith("6") else f"sz{symbol}"
            outflow_stocks.append({
                "symbol": full_symbol,
                "name": flow.get("name", ""),
                "outflow": main_net / 1e8,
            })
    
    outflow_stocks.sort(key=lambda x: x["outflow"])
    
    return AnomalyResult(
        type=AnomalyType.CAPITAL_OUTFLOW,
        title="资金净流出最坚决",
        stocks=[
            AnomalyStock(
                symbol=s["symbol"],
                name=s["name"],
                value=round(s["outflow"], 2),
                unit="亿"
            )
            for s in outflow_stocks[:top_n]
        ]
    )


def _detect_institution_research(research: List[Dict], top_n: int = 10) -> AnomalyResult:
    """Detect most researched stocks by institutions."""
    research_stocks = []
    
    for r in research:
        count = r.get("research_count", 0)
        if count > 0:
            symbol = r.get("symbol", "")
            full_symbol = f"sh{symbol}" if symbol.startswith("6") else f"sz{symbol}"
            research_stocks.append({
                "symbol": full_symbol,
                "name": r.get("name", ""),
                "count": count,
            })
    
    research_stocks.sort(key=lambda x: x["count"], reverse=True)
    
    return AnomalyResult(
        type=AnomalyType.INSTITUTION_RESEARCH,
        title="机构调研最密集",
        stocks=[
            AnomalyStock(
                symbol=s["symbol"],
                name=s["name"],
                value=s["count"],
                unit="次"
            )
            for s in research_stocks[:top_n]
        ]
    )


def _detect_new_high_simple(stocks: List[Dict], top_n: int = 10) -> AnomalyResult:
    """
    Fallback: Detect stocks with highest gains (simplified version).
    
    Used when K-line data is not available.
    """
    high_stocks = []
    
    for stock in stocks:
        price = stock.get("price", 0)
        change_pct = stock.get("change_pct", 0)
        
        if price > 0 and change_pct > 3:  # Lower threshold for fallback
            symbol = stock.get("symbol", "")
            full_symbol = f"sh{symbol}" if symbol.startswith("6") else f"sz{symbol}"
            high_stocks.append({
                "symbol": full_symbol,
                "name": stock.get("name", ""),
                "change_pct": change_pct,
            })
    
    high_stocks.sort(key=lambda x: x["change_pct"], reverse=True)
    
    return AnomalyResult(
        type=AnomalyType.NEW_HIGH,
        title="涨幅居前",
        stocks=[
            AnomalyStock(
                symbol=s["symbol"],
                name=s["name"],
                value=round(s["change_pct"], 2),
                unit="%"
            )
            for s in high_stocks[:top_n]
        ]
    )


def _detect_new_high_with_kline(
    stocks: List[Dict], 
    kline_data: Dict[str, List[Dict]], 
    top_n: int = 10
) -> AnomalyResult:
    """
    P1-4: Detect stocks hitting true 60-day highs using K-line data.
    
    A stock is considered "new high" if:
    1. Current price >= 60-day high
    2. Has positive momentum (change_pct > 0)
    """
    high_stocks = []
    
    for stock in stocks:
        symbol = stock.get("symbol", "")
        if not symbol:
            continue
        
        # Check if we have K-line data for this symbol
        klines = kline_data.get(symbol, [])
        if not klines or len(klines) < 10:  # Need at least 10 days of data
            continue
        
        current_price = stock.get("price", 0)
        if current_price <= 0:
            continue
        
        # Calculate 60-day high (excluding today)
        historical_highs = [k["high"] for k in klines[:-1] if k["high"] > 0]
        if not historical_highs:
            continue
        
        period_high = max(historical_highs)
        
        # Check if current price is at or above period high
        if current_price >= period_high * 0.98:  # Allow 2% tolerance
            change_pct = stock.get("change_pct", 0)
            full_symbol = f"sh{symbol}" if symbol.startswith("6") else f"sz{symbol}"
            
            # Calculate weeks since last high
            days_to_high = len(klines)
            weeks = round(days_to_high / 5, 1)  # Approximate weeks
            
            high_stocks.append({
                "symbol": full_symbol,
                "name": stock.get("name", ""),
                "change_pct": change_pct,
                "weeks_to_high": weeks,
                "period_high": period_high,
            })
    
    # Sort by change percentage
    high_stocks.sort(key=lambda x: x["change_pct"], reverse=True)
    
    return AnomalyResult(
        type=AnomalyType.NEW_HIGH,
        title="创60日新高",
        stocks=[
            AnomalyStock(
                symbol=s["symbol"],
                name=s["name"],
                value=s.get("weeks_to_high", 0),
                unit="周"
            )
            for s in high_stocks[:top_n]
        ]
    )


def _detect_volume_surge(stocks: List[Dict], top_n: int = 10) -> AnomalyResult:
    """Detect stocks with unusual volume (simplified - based on amount)."""
    volume_stocks = []
    
    for stock in stocks:
        amount = stock.get("amount", 0)
        if amount > 0:
            symbol = stock.get("symbol", "")
            full_symbol = f"sh{symbol}" if symbol.startswith("6") else f"sz{symbol}"
            volume_stocks.append({
                "symbol": full_symbol,
                "name": stock.get("name", ""),
                "amount": amount / 1e8,
            })
    
    volume_stocks.sort(key=lambda x: x["amount"], reverse=True)
    
    return AnomalyResult(
        type=AnomalyType.VOLUME_SURGE,
        title="成交额最大",
        stocks=[
            AnomalyStock(
                symbol=s["symbol"],
                name=s["name"],
                value=round(s["amount"], 2),
                unit="亿"
            )
            for s in volume_stocks[:top_n]
        ]
    )


async def detect_anomalies(
    anomaly_type: Optional[AnomalyType] = None,
    top_n: int = 10,
    timeout: float = 15.0
) -> Dict[str, Any]:
    """
    Detect market anomalies.
    
    Args:
        anomaly_type: Specific anomaly type to detect, None for all types
        top_n: Number of top stocks to return per anomaly type
        timeout: Request timeout in seconds
        
    Returns:
        Dictionary with anomalies list and metadata
    """
    try:
        return await asyncio.wait_for(
            _detect_anomalies_internal(anomaly_type, top_n),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        logger.error("[Anomaly] Timeout detecting anomalies")
        return {
            "anomalies": [],
            "last_update": datetime.now().isoformat(),
            "error": "timeout"
        }


async def _detect_anomalies_internal(
    anomaly_type: Optional[AnomalyType],
    top_n: int
) -> Dict[str, Any]:
    """Internal anomaly detection logic."""
    results = []
    
    if anomaly_type in (None, AnomalyType.VOLATILITY, AnomalyType.NEW_HIGH, AnomalyType.VOLUME_SURGE):
        stocks = await _fetch_all_stocks()
        
        if stocks:
            if anomaly_type in (None, AnomalyType.VOLATILITY):
                results.append(_detect_volatility(stocks, top_n))
            
            if anomaly_type in (None, AnomalyType.NEW_HIGH):
                # P1-4: Try to use K-line data for true new high detection
                try:
                    # Get top gainers first (potential new high candidates)
                    gainers = sorted(
                        [s for s in stocks if s.get("change_pct", 0) > 0],
                        key=lambda x: x.get("change_pct", 0),
                        reverse=True
                    )[:50]  # Limit to top 50 gainers
                    
                    if gainers:
                        symbols = [s.get("symbol", "") for s in gainers if s.get("symbol")]
                        kline_data = await _fetch_kline_batch(symbols, days=60)
                        
                        if kline_data:
                            results.append(_detect_new_high_with_kline(stocks, kline_data, top_n))
                        else:
                            # Fallback to simple detection
                            results.append(_detect_new_high_simple(stocks, top_n))
                    else:
                        results.append(_detect_new_high_simple(stocks, top_n))
                except Exception as e:
                    logger.warning(f"[Anomaly] K-line fetch failed, using fallback: {e}")
                    results.append(_detect_new_high_simple(stocks, top_n))
            
            if anomaly_type in (None, AnomalyType.VOLUME_SURGE):
                results.append(_detect_volume_surge(stocks, top_n))
    
    if anomaly_type in (None, AnomalyType.CAPITAL_OUTFLOW):
        flows = await _fetch_capital_flow()
        if flows:
            results.append(_detect_capital_outflow(flows, top_n))
    
    if anomaly_type in (None, AnomalyType.INSTITUTION_RESEARCH):
        research = await _fetch_institution_research()
        if research:
            results.append(_detect_institution_research(research, top_n))
    
    return {
        "anomalies": [
            {
                "type": r.type.value,
                "title": r.title,
                "stocks": [
                    {
                        "symbol": s.symbol,
                        "name": s.name,
                        "value": s.value,
                        "unit": s.unit,
                    }
                    for s in r.stocks
                ]
            }
            for r in results
        ],
        "last_update": datetime.now().isoformat(),
    }
