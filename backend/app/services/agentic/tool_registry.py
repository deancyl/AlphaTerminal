"""
Tool Registry for Agentic Workflow

Provides a registry of tools that can be invoked by the workflow engine.
Each tool wraps an existing data fetching service.
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="agentic_tool_")


@dataclass
class ToolParameter:
    """Parameter definition for a tool"""
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None


@dataclass
class Tool:
    """Tool definition with metadata and execution function"""
    name: str
    description: str
    parameters: List[ToolParameter] = field(default_factory=list)
    execute_func: Optional[Callable] = None
    category: str = "data"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default
                }
                for p in self.parameters
            ],
            "category": self.category
        }


class ToolRegistry:
    """
    Registry of available tools for workflow execution.
    
    Tools are registered with metadata and execution functions.
    The registry provides lookup and execution capabilities.
    """
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._register_builtin_tools()
        logger.info(f"[ToolRegistry] Initialized with {len(self._tools)} builtin tools")
    
    def register(self, tool: Tool) -> None:
        """Register a tool"""
        self._tools[tool.name] = tool
        logger.debug(f"[ToolRegistry] Registered tool: {tool.name}")
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a tool by name"""
        return self._tools.get(name)
    
    def list_tools(self) -> List[Tool]:
        """List all registered tools"""
        return list(self._tools.values())
    
    def list_tools_by_category(self, category: str) -> List[Tool]:
        """List tools by category"""
        return [t for t in self._tools.values() if t.category == category]
    
    async def execute(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool with given parameters.
        
        Args:
            tool_name: Name of the tool to execute
            params: Parameters to pass to the tool
            
        Returns:
            Execution result with data and metadata
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return {
                "success": False,
                "error": f"Tool not found: {tool_name}",
                "data": None
            }
        
        if not tool.execute_func:
            return {
                "success": False,
                "error": f"Tool has no execution function: {tool_name}",
                "data": None
            }
        
        try:
            start_time = datetime.now()
            
            if asyncio.iscoroutinefunction(tool.execute_func):
                result = await tool.execute_func(**params)
            else:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    _executor, 
                    lambda: tool.execute_func(**params)
                )
            
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            return {
                "success": True,
                "data": result,
                "elapsed_ms": elapsed_ms,
                "tool": tool_name
            }
        except Exception as e:
            logger.error(f"[ToolRegistry] Tool execution failed: {tool_name}, {e}")
            return {
                "success": False,
                "error": str(e),
                "data": None,
                "tool": tool_name
            }
    
    def _register_builtin_tools(self) -> None:
        """Register built-in data fetching tools"""
        
        self.register(Tool(
            name="get_quote",
            description="获取股票实时行情数据",
            parameters=[
                ToolParameter("symbol", "string", "股票代码（如 600519 或 sh600519）", required=True)
            ],
            execute_func=self._get_quote,
            category="market"
        ))
        
        self.register(Tool(
            name="get_news",
            description="获取股票相关新闻",
            parameters=[
                ToolParameter("symbol", "string", "股票代码", required=False),
                ToolParameter("limit", "integer", "返回条数", required=False, default=10)
            ],
            execute_func=self._get_news,
            category="news"
        ))
        
        self.register(Tool(
            name="get_financial",
            description="获取股票财务数据",
            parameters=[
                ToolParameter("symbol", "string", "股票代码", required=True)
            ],
            execute_func=self._get_financial,
            category="financial"
        ))
        
        self.register(Tool(
            name="get_kline",
            description="获取股票K线历史数据",
            parameters=[
                ToolParameter("symbol", "string", "股票代码", required=True),
                ToolParameter("period", "string", "周期（daily/weekly/monthly）", required=False, default="daily"),
                ToolParameter("limit", "integer", "返回条数", required=False, default=60)
            ],
            execute_func=self._get_kline,
            category="market"
        ))
        
        self.register(Tool(
            name="search_stocks",
            description="搜索股票",
            parameters=[
                ToolParameter("keyword", "string", "搜索关键词", required=True),
                ToolParameter("limit", "integer", "返回条数", required=False, default=10)
            ],
            execute_func=self._search_stocks,
            category="market"
        ))
        
        self.register(Tool(
            name="get_sector_stocks",
            description="获取板块成分股",
            parameters=[
                ToolParameter("sector", "string", "板块名称（如 半导体、白酒）", required=True)
            ],
            execute_func=self._get_sector_stocks,
            category="market"
        ))
        
        self.register(Tool(
            name="get_macro_data",
            description="获取宏观经济数据",
            parameters=[
                ToolParameter("indicator", "string", "指标名称（GDP/CPI/PPI/PMI/M2）", required=True)
            ],
            execute_func=self._get_macro_data,
            category="macro"
        ))
    
    def _get_quote(self, symbol: str) -> Dict[str, Any]:
        """Fetch real-time quote data"""
        try:
            from app.services.quote_source import get_quote_with_fallback
            
            sym = symbol.lower()
            if not sym.startswith(("sh", "sz", "hk", "us")):
                if sym.startswith("6"):
                    sym = f"sh{sym}"
                elif sym.startswith(("0", "3")):
                    sym = f"sz{sym}"
            
            quote = get_quote_with_fallback(sym)
            
            if not quote:
                return {"error": f"No quote data for {symbol}"}
            
            return {
                "symbol": sym,
                "name": quote.get("name", ""),
                "price": quote.get("price", 0),
                "change": quote.get("change", 0),
                "change_pct": quote.get("change_pct", 0),
                "volume": quote.get("volume", 0),
                "amount": quote.get("amount", 0),
                "high": quote.get("high", 0),
                "low": quote.get("low", 0),
                "open": quote.get("open", 0),
                "prev_close": quote.get("prev_close", 0),
                "pe_ttm": quote.get("pe_ttm"),
                "pb": quote.get("pb"),
                "market_cap": quote.get("market_cap"),
            }
        except Exception as e:
            logger.error(f"[ToolRegistry] get_quote error: {e}")
            return {"error": str(e)}
    
    def _get_news(self, symbol: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
        """Fetch news data"""
        try:
            from app.db.database import _get_conn
            
            conn = _get_conn()
            
            if symbol:
                rows = conn.execute(
                    """SELECT title, content, ctime, tag, source 
                       FROM news_cache 
                       WHERE title LIKE ? OR content LIKE ?
                       ORDER BY ctime DESC 
                       LIMIT ?""",
                    (f"%{symbol}%", f"%{symbol}%", limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT title, content, ctime, tag, source 
                       FROM news_cache 
                       ORDER BY ctime DESC 
                       LIMIT ?""",
                    (limit,)
                ).fetchall()
            
            conn.close()
            
            news_list = []
            for row in rows:
                news_list.append({
                    "title": row[0],
                    "content": row[1][:200] if row[1] else "",
                    "time": row[2],
                    "tag": row[3],
                    "source": row[4]
                })
            
            return {
                "count": len(news_list),
                "news": news_list
            }
        except Exception as e:
            logger.error(f"[ToolRegistry] get_news error: {e}")
            return {"error": str(e), "count": 0, "news": []}
    
    def _get_financial(self, symbol: str) -> Dict[str, Any]:
        """Fetch financial data"""
        try:
            from app.services.fetchers.akshare_fetcher import AkShareFetcher
            
            fetcher = AkShareFetcher()
            
            sym = symbol.lower().replace("sh", "").replace("sz", "")
            
            try:
                import akshare as ak
                df = ak.stock_financial_analysis_indicator(symbol=sym)
                
                if df is not None and not df.empty:
                    latest = df.iloc[-1].to_dict() if len(df) > 0 else {}
                    return {
                        "symbol": symbol,
                        "data": latest,
                        "history": df.tail(8).to_dict(orient="records") if len(df) >= 8 else df.to_dict(orient="records")
                    }
            except Exception:
                pass
            
            return {
                "symbol": symbol,
                "data": {},
                "history": []
            }
        except Exception as e:
            logger.error(f"[ToolRegistry] get_financial error: {e}")
            return {"error": str(e), "symbol": symbol, "data": {}, "history": []}
    
    def _get_kline(self, symbol: str, period: str = "daily", limit: int = 60) -> Dict[str, Any]:
        """Fetch K-line data"""
        try:
            from app.db import get_daily_history
            
            sym = symbol.lower().replace("sh", "").replace("sz", "")
            
            rows = get_daily_history(sym, limit=limit)
            
            if rows:
                kline_data = []
                for row in rows:
                    kline_data.append({
                        "date": row[0] if len(row) > 0 else "",
                        "open": float(row[1]) if len(row) > 1 and row[1] else 0,
                        "high": float(row[2]) if len(row) > 2 and row[2] else 0,
                        "low": float(row[3]) if len(row) > 3 and row[3] else 0,
                        "close": float(row[4]) if len(row) > 4 and row[4] else 0,
                        "volume": float(row[5]) if len(row) > 5 and row[5] else 0,
                    })
                
                return {
                    "symbol": symbol,
                    "period": period,
                    "count": len(kline_data),
                    "data": kline_data
                }
            
            return {
                "symbol": symbol,
                "period": period,
                "count": 0,
                "data": []
            }
        except Exception as e:
            logger.error(f"[ToolRegistry] get_kline error: {e}")
            return {"error": str(e), "symbol": symbol, "count": 0, "data": []}
    
    def _search_stocks(self, keyword: str, limit: int = 10) -> Dict[str, Any]:
        """Search stocks by keyword"""
        try:
            from app.db.database import _get_conn
            
            conn = _get_conn()
            rows = conn.execute(
                """SELECT symbol, name, price, change_pct 
                   FROM market_all_stocks 
                   WHERE symbol LIKE ? OR name LIKE ?
                   LIMIT ?""",
                (f"%{keyword}%", f"%{keyword}%", limit)
            ).fetchall()
            conn.close()
            
            stocks = []
            for row in rows:
                stocks.append({
                    "symbol": row[0],
                    "name": row[1],
                    "price": float(row[2]) if row[2] else 0,
                    "change_pct": float(row[3]) if row[3] else 0
                })
            
            return {
                "keyword": keyword,
                "count": len(stocks),
                "stocks": stocks
            }
        except Exception as e:
            logger.error(f"[ToolRegistry] search_stocks error: {e}")
            return {"error": str(e), "keyword": keyword, "count": 0, "stocks": []}
    
    def _get_sector_stocks(self, sector: str) -> Dict[str, Any]:
        """Get stocks in a sector"""
        try:
            from app.services.sectors_cache import get_sectors
            
            sectors = get_sectors()
            
            for s in sectors:
                if sector in s.get("name", "") or s.get("name", "") in sector:
                    return {
                        "sector": s.get("name"),
                        "count": len(s.get("stocks", [])),
                        "stocks": s.get("stocks", [])[:20],
                        "change_pct": s.get("change_pct", 0)
                    }
            
            return {
                "sector": sector,
                "count": 0,
                "stocks": [],
                "error": f"Sector not found: {sector}"
            }
        except Exception as e:
            logger.error(f"[ToolRegistry] get_sector_stocks error: {e}")
            return {"error": str(e), "sector": sector, "count": 0, "stocks": []}
    
    def _get_macro_data(self, indicator: str) -> Dict[str, Any]:
        """Get macro economic data"""
        try:
            import akshare as ak
            
            indicator_map = {
                "GDP": ("macro_china_gdp", "国内生产总值"),
                "CPI": ("macro_china_cpi_yearly", "居民消费价格指数"),
                "PPI": ("macro_china_ppi_yearly", "工业生产者出厂价格指数"),
                "PMI": ("macro_china_pmi_yearly", "采购经理指数"),
                "M2": ("macro_china_m2_yearly", "广义货币供应量"),
            }
            
            if indicator.upper() not in indicator_map:
                return {"error": f"Unknown indicator: {indicator}"}
            
            func_name, name = indicator_map[indicator.upper()]
            
            try:
                func = getattr(ak, func_name)
                df = func()
                
                if df is not None and not df.empty:
                    return {
                        "indicator": indicator,
                        "name": name,
                        "latest": df.iloc[-1].to_dict() if len(df) > 0 else {},
                        "history": df.tail(12).to_dict(orient="records")
                    }
            except Exception:
                pass
            
            return {
                "indicator": indicator,
                "name": name,
                "latest": {},
                "history": []
            }
        except Exception as e:
            logger.error(f"[ToolRegistry] get_macro_data error: {e}")
            return {"error": str(e), "indicator": indicator}


_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get singleton ToolRegistry instance"""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
