"""
Treemap Builder - Build ECharts treemap data from market data.

Uses akshare to fetch sector and stock data, then formats for ECharts treemap series.

OPTIMIZED: Uses asyncio.gather() for parallel fetching to avoid N+1 API calls.
"""

import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="treemap_")

# Data source tracking
DATA_SOURCE_AKSHARE = "akshare"
DATA_SOURCE_CACHE = "cache"
DATA_SOURCE_FALLBACK = "fallback"


def _fetch_sectors_sync() -> List[Dict]:
    """Fetch all sector names from akshare."""
    try:
        import akshare as ak
        df = ak.stock_board_industry_name_em()
        sectors = []
        for _, row in df.iterrows():
            sectors.append({
                "name": row["板块名称"],
                "code": row["板块代码"],
            })
        return sectors
    except Exception as e:
        logger.error(f"[Treemap] Failed to fetch sectors: {e}")
        return []


def _fetch_sector_stocks_sync(sector_name: str) -> tuple:
    """Fetch stocks in a specific sector. Returns (sector_name, stocks_list) for parallel processing."""
    try:
        import akshare as ak
        df = ak.stock_board_industry_cons_em(symbol=sector_name)
        stocks = []
        for _, row in df.iterrows():
            stocks.append({
                "symbol": row.get("代码", ""),
                "name": row.get("名称", ""),
                "price": float(row.get("最新价", 0) or 0),
                "change_pct": float(row.get("涨跌幅", 0) or 0),
                "volume": float(row.get("成交量", 0) or 0),
                "amount": float(row.get("成交额", 0) or 0),
                "market_cap": float(row.get("总市值", 0) or 0),
            })
        return (sector_name, stocks)
    except Exception as e:
        logger.warning(f"[Treemap] Failed to fetch stocks for {sector_name}: {e}")
        return (sector_name, [])


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
                    "market_cap": float(row.get("总市值", 0) or 0),
                    "high": float(row.get("最高", 0) or 0),
                    "low": float(row.get("最低", 0) or 0),
                    "pre_close": float(row.get("昨收", 0) or 0),
                })
            except (ValueError, TypeError):
                continue
        return stocks
    except Exception as e:
        logger.error(f"[Treemap] Failed to fetch all stocks: {e}")
        return []


async def _fetch_sectors() -> List[Dict]:
    """Async wrapper for sector fetching."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _fetch_sectors_sync)


async def _fetch_sector_stocks_batch(sector_names: List[str]) -> Dict[str, List[Dict]]:
    """
    Batch fetch stocks for multiple sectors using asyncio.gather().
    
    OPTIMIZATION: Instead of N sequential API calls, use parallel fetching.
    This reduces total time from N * T to max(T) where T is single API call time.
    
    Args:
        sector_names: List of sector names to fetch
        
    Returns:
        Dictionary mapping sector_name to list of stocks
    """
    loop = asyncio.get_running_loop()
    
    # Create parallel tasks for all sectors
    tasks = [
        loop.run_in_executor(_executor, _fetch_sector_stocks_sync, name)
        for name in sector_names
    ]
    
    # Execute all tasks in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Build result dictionary
    sector_stocks_map = {}
    for result in results:
        if isinstance(result, Exception):
            logger.warning(f"[Treemap] Parallel fetch error: {result}")
            continue
        if isinstance(result, tuple) and len(result) == 2:
            sector_name, stocks = result
            if stocks:
                sector_stocks_map[sector_name] = stocks
    
    return sector_stocks_map


async def _fetch_all_stocks() -> List[Dict]:
    """Async wrapper for all stocks fetching."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _fetch_all_stocks_sync)


async def get_sector_stocks(sector_name: str, timeout: float = 15.0) -> List[Dict]:
    """
    Get stocks in a specific sector.
    
    Args:
        sector_name: Sector name (e.g., "白酒")
        timeout: Request timeout in seconds
        
    Returns:
        List of stock dictionaries
    """
    try:
        result = await _fetch_sector_stocks_batch([sector_name])
        return result.get(sector_name, [])
    except asyncio.TimeoutError:
        logger.warning(f"[Treemap] Timeout fetching stocks for {sector_name}")
        return []


async def build_treemap_data(
    level: str = "sector",
    timeout: float = 15.0
) -> Dict[str, Any]:
    """
    Build treemap data for ECharts visualization.
    
    Args:
        level: "sector" for sector aggregation, "stock" for individual stocks
        timeout: Request timeout in seconds
        
    Returns:
        Dictionary with treemap data and metadata including data_source info
    """
    try:
        if level == "sector":
            return await asyncio.wait_for(_build_sector_treemap(), timeout=timeout)
        else:
            return await asyncio.wait_for(_build_stock_treemap(), timeout=timeout)
    except asyncio.TimeoutError:
        logger.error("[Treemap] Timeout building treemap data")
        return {
            "data": [],
            "last_update": datetime.now().isoformat(),
            "data_source": DATA_SOURCE_FALLBACK,
            "error": "timeout"
        }


async def _build_sector_treemap() -> Dict[str, Any]:
    """
    Build treemap with sector aggregation.
    
    OPTIMIZED: Uses asyncio.gather() for parallel sector stock fetching.
    """
    # Fetch sectors and all stocks in parallel
    sectors, all_stocks = await asyncio.gather(
        _fetch_sectors(),
        _fetch_all_stocks()
    )
    
    if not sectors:
        logger.warning("[Treemap] No sectors fetched")
        return {
            "data": [],
            "last_update": datetime.now().isoformat(),
            "data_source": DATA_SOURCE_FALLBACK
        }
    
    if not all_stocks:
        logger.warning("[Treemap] No stocks fetched")
        return {
            "data": [],
            "last_update": datetime.now().isoformat(),
            "data_source": DATA_SOURCE_FALLBACK
        }
    
    stock_by_symbol = {s["symbol"]: s for s in all_stocks}
    
    # OPTIMIZATION: Batch fetch all sector stocks in parallel
    # Instead of 30 sequential calls, use single parallel batch
    sector_names = [s["name"] for s in sectors[:30]]
    sector_stocks_map = await _fetch_sector_stocks_batch(sector_names)
    
    treemap_data = []
    
    for sector_name in sector_names:
        sector_stocks = sector_stocks_map.get(sector_name, [])
        
        if not sector_stocks:
            continue
        
        children = []
        sector_market_cap = 0
        sector_change_sum = 0
        valid_stocks = 0
        
        for stock in sector_stocks[:20]:
            symbol = stock.get("symbol", "")
            if not symbol:
                continue
            
            full_symbol = f"sh{symbol}" if symbol.startswith("6") else f"sz{symbol}"
            market_stock = stock_by_symbol.get(symbol, stock)
            
            market_cap = market_stock.get("market_cap", 0) or stock.get("market_cap", 0)
            change_pct = market_stock.get("change_pct", 0) or stock.get("change_pct", 0)
            
            if market_cap > 0:
                children.append({
                    "name": stock.get("name", symbol),
                    "value": round(market_cap / 1e8, 2),
                    "change_pct": round(change_pct, 2),
                    "symbol": full_symbol,
                })
                sector_market_cap += market_cap
                sector_change_sum += change_pct
                valid_stocks += 1
        
        if valid_stocks > 0 and sector_market_cap > 0:
            avg_change = sector_change_sum / valid_stocks
            treemap_data.append({
                "name": sector_name,
                "value": round(sector_market_cap / 1e8, 2),
                "change_pct": round(avg_change, 2),
                "children": children,
            })
    
    treemap_data.sort(key=lambda x: x["value"], reverse=True)
    
    return {
        "data": treemap_data,
        "last_update": datetime.now().isoformat(),
        "data_source": DATA_SOURCE_AKSHARE,
        "source_detail": {
            "name": "东方财富",
            "type": "实时",
            "api": "akshare.stock_board_industry_name_em"
        }
    }


async def _build_stock_treemap() -> Dict[str, Any]:
    """Build treemap with individual stocks (no sector grouping)."""
    all_stocks = await _fetch_all_stocks()
    
    if not all_stocks:
        logger.warning("[Treemap] No stocks fetched for stock-level treemap")
        return {
            "data": [],
            "last_update": datetime.now().isoformat(),
            "data_source": DATA_SOURCE_FALLBACK
        }
    
    treemap_data = []
    
    for stock in all_stocks[:500]:
        symbol = stock.get("symbol", "")
        if not symbol:
            continue
        
        market_cap = stock.get("market_cap", 0)
        if market_cap <= 0:
            continue
        
        full_symbol = f"sh{symbol}" if symbol.startswith("6") else f"sz{symbol}"
        
        treemap_data.append({
            "name": stock.get("name", symbol),
            "value": round(market_cap / 1e8, 2),
            "change_pct": round(stock.get("change_pct", 0) or 0, 2),
            "symbol": full_symbol,
        })
    
    treemap_data.sort(key=lambda x: x["value"], reverse=True)
    
    return {
        "data": treemap_data,
        "last_update": datetime.now().isoformat(),
        "data_source": DATA_SOURCE_AKSHARE,
        "source_detail": {
            "name": "东方财富",
            "type": "实时",
            "api": "akshare.stock_zh_a_spot_em"
        }
    }
