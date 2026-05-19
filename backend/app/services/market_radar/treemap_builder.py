"""
Treemap Builder - Build ECharts treemap data from market data.

Uses akshare to fetch sector and stock data, then formats for ECharts treemap series.
"""

import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="treemap_")


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


def _fetch_sector_stocks_sync(sector_name: str) -> List[Dict]:
    """Fetch stocks in a specific sector."""
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
        return stocks
    except Exception as e:
        logger.warning(f"[Treemap] Failed to fetch stocks for {sector_name}: {e}")
        return []


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


async def _fetch_sector_stocks(sector_name: str) -> List[Dict]:
    """Async wrapper for sector stocks fetching."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _fetch_sector_stocks_sync, sector_name)


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
        return await asyncio.wait_for(_fetch_sector_stocks(sector_name), timeout=timeout)
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
        Dictionary with treemap data and metadata
    """
    try:
        if level == "sector":
            return await asyncio.wait_for(_build_sector_treemap(), timeout=timeout)
        else:
            return await asyncio.wait_for(_build_stock_treemap(), timeout=timeout)
    except asyncio.TimeoutError:
        logger.error("[Treemap] Timeout building treemap data")
        return {"data": [], "last_update": datetime.now().isoformat(), "error": "timeout"}


async def _build_sector_treemap() -> Dict[str, Any]:
    """Build treemap with sector aggregation."""
    sectors = await _fetch_sectors()
    if not sectors:
        logger.warning("[Treemap] No sectors fetched")
        return {"data": [], "last_update": datetime.now().isoformat()}
    
    all_stocks = await _fetch_all_stocks()
    if not all_stocks:
        logger.warning("[Treemap] No stocks fetched")
        return {"data": [], "last_update": datetime.now().isoformat()}
    
    stock_by_symbol = {s["symbol"]: s for s in all_stocks}
    
    treemap_data = []
    
    for sector in sectors[:30]:
        sector_name = sector["name"]
        sector_stocks = await _fetch_sector_stocks(sector_name)
        
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
    }


async def _build_stock_treemap() -> Dict[str, Any]:
    """Build treemap with individual stocks (no sector grouping)."""
    all_stocks = await _fetch_all_stocks()
    
    if not all_stocks:
        logger.warning("[Treemap] No stocks fetched for stock-level treemap")
        return {"data": [], "last_update": datetime.now().isoformat()}
    
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
    }
