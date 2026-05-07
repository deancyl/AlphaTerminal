"""AlphaTerminal MCP Server - AI Agent 工具接口"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class Tool:
    """MCP 工具定义"""

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        handler: callable,
        required_scope: str = "R",
    ):
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.handler = handler
        self.required_scope = required_scope

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "required_scope": self.required_scope,
        }


class MCPServer:
    """
    AlphaTerminal MCP Server

    提供 AI Agent 可调用的标准化工具接口。
    基于 Model Context Protocol (MCP) 设计。
    """

    _instance: Optional["MCPServer"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools: Dict[str, Tool] = {}
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._tools: Dict[str, Tool] = {}
        self._register_tools()
        self._initialized = True
        logger.info(f"[MCP] Server initialized with {len(self._tools)} tools")

    def _register_tools(self):
        """注册所有可用工具"""
        # ── Market Data Tools ────────────────────────────────────────────────

        self._tools["get_klines"] = Tool(
            name="get_klines",
            description="获取 K 线数据（支持 A股、港股、美股）",
            input_schema={
                "type": "object",
                "properties": {
                    "market": {
                        "type": "string",
                        "enum": ["AStock", "HKStock", "USStock"],
                        "description": "市场代码",
                    },
                    "symbol": {"type": "string", "description": "股票代码"},
                    "timeframe": {
                        "type": "string",
                        "enum": ["1m", "5m", "15m", "1H", "4H", "1D", "1W"],
                        "description": "时间周期",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 100,
                        "description": "数据条数限制",
                    },
                },
                "required": ["market", "symbol", "timeframe"],
            },
            handler=self._get_klines,
            required_scope="R",
        )

        self._tools["get_realtime_quote"] = Tool(
            name="get_realtime_quote",
            description="获取实时行情报价（价格、涨跌幅、成交量等）",
            input_schema={
                "type": "object",
                "properties": {
                    "market": {
                        "type": "string",
                        "enum": ["AStock", "HKStock", "USStock"],
                        "description": "市场代码",
                    },
                    "symbol": {"type": "string", "description": "股票代码"},
                },
                "required": ["market", "symbol"],
            },
            handler=self._get_realtime_quote,
            required_scope="R",
        )

        self._tools["search_symbols"] = Tool(
            name="search_symbols",
            description="搜索股票代码和名称",
            input_schema={
                "type": "object",
                "properties": {
                    "market": {
                        "type": "string",
                        "enum": ["AStock", "HKStock", "USStock"],
                        "description": "市场代码",
                    },
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词（代码或名称）",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 20,
                        "description": "返回数量限制",
                    },
                },
                "required": ["market", "keyword"],
            },
            handler=self._search_symbols,
            required_scope="R",
        )

        # ── Portfolio Tools ──────────────────────────────────────────────────

        self._tools["get_portfolio"] = Tool(
            name="get_portfolio",
            description="获取组合持仓信息",
            input_schema={
                "type": "object",
                "properties": {
                    "portfolio_id": {
                        "type": "string",
                        "description": "组合 ID（不填则返回主组合）",
                    }
                },
                "required": [],
            },
            handler=self._get_portfolio,
            required_scope="R",
        )

        self._tools["get_account_info"] = Tool(
            name="get_account_info",
            description="获取账户资金信息",
            input_schema={
                "type": "object",
                "properties": {},
                "required": [],
            },
            handler=self._get_account_info,
            required_scope="R",
        )

        # ── Trading Tools ───────────────────────────────────────────────────

        self._tools["submit_order"] = Tool(
            name="submit_order",
            description="提交模拟交易订单（仅 Paper Trading）",
            input_schema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "股票代码"},
                    "side": {
                        "type": "string",
                        "enum": ["BUY", "SELL"],
                        "description": "买卖方向",
                    },
                    "quantity": {
                        "type": "number",
                        "description": "交易数量",
                    },
                    "price": {"type": "number", "description": "委托价格"},
                },
                "required": ["symbol", "side", "quantity", "price"],
            },
            handler=self._submit_order,
            required_scope="T",
        )

        self._tools["list_orders"] = Tool(
            name="list_orders",
            description="列出所有模拟交易订单",
            input_schema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "过滤指定股票",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["pending", "filled", "cancelled", "rejected"],
                        "description": "过滤订单状态",
                    },
                },
                "required": [],
            },
            handler=self._list_orders,
            required_scope="R",
        )

        self._tools["cancel_order"] = Tool(
            name="cancel_order",
            description="取消模拟交易订单",
            input_schema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "订单 ID"},
                },
                "required": ["order_id"],
            },
            handler=self._cancel_order,
            required_scope="T",
        )

    # ── Tool Handlers ─────────────────────────────────────────────────────────

    def _get_klines(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """获取 K 线数据"""
        from app.routers.market import get_periodic_history
        from app.db import get_periodic_history as db_get_history

        market = arguments["market"]
        symbol = arguments["symbol"]
        timeframe = arguments.get("timeframe", "1D")
        limit = min(arguments.get("limit", 100), 1000)

        # 转换市场代码
        sym = symbol
        if market == "AStock":
            if not symbol.startswith(("sh", "sz")):
                sym = f"sh{symbol}" if symbol.startswith("6") else f"sz{symbol}"
        elif market == "HKStock":
            sym = f"hk{symbol}"
        elif market == "USStock":
            sym = f"us{symbol}"

        # period 映射
        period_map = {
            "1m": "1min",
            "5m": "5min",
            "15m": "15min",
            "30m": "30min",
            "1H": "60min",
            "4H": "60min",
            "1D": "daily",
            "1W": "weekly",
        }
        period = period_map.get(timeframe, "daily")

        try:
            rows = db_get_history(sym, period=period, limit=limit)
            data = [
                {
                    "timestamp": row.get("trade_date", ""),
                    "open": float(row.get("open", 0)),
                    "high": float(row.get("high", 0)),
                    "low": float(row.get("low", 0)),
                    "close": float(row.get("close", 0)),
                    "volume": float(row.get("volume", 0)),
                }
                for row in rows
            ]
            return {"success": True, "data": data, "count": len(data)}
        except Exception as e:
            logger.warning(f"[MCP] get_klines failed: {e}")
            return {"success": False, "error": str(e), "data": []}

    def _get_realtime_quote(
        self, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """获取实时行情"""
        import asyncio

        market = arguments["market"]
        symbol = arguments["symbol"]

        sym = symbol
        if market == "AStock":
            if not symbol.startswith(("sh", "sz")):
                sym = f"sh{symbol}" if symbol.startswith("6") else f"sz{symbol}"
        elif market == "HKStock":
            sym = f"hk{symbol}"
        elif market == "USStock":
            sym = f"us{symbol}"

        try:
            from app.routers.market import market_quote

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                quote = loop.run_until_complete(market_quote(sym))
            finally:
                loop.close()

            if "data" in quote:
                data = quote["data"]
                return {
                    "success": True,
                    "data": {
                        "symbol": symbol,
                        "market": market,
                        "price": data.get("price", 0),
                        "change": data.get("price_change", 0),
                        "change_pct": data.get("pct_change", 0),
                        "volume": data.get("volume", 0),
                        "timestamp": data.get("timestamp", ""),
                    },
                }
            return {"success": False, "error": "No data", "data": None}
        except Exception as e:
            logger.warning(f"[MCP] get_realtime_quote failed: {e}")
            return {"success": False, "error": str(e), "data": None}

    def _search_symbols(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """搜索股票代码"""
        market = arguments["market"]
        keyword = arguments.get("keyword", "")
        limit = arguments.get("limit", 20)

        try:
            from app.routers.stocks import search_stocks
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(search_stocks(q=keyword))
            finally:
                loop.close()

            symbols = results.get("data", {}).get("stocks", [])[:limit]

            # 市场前缀过滤
            market_prefix_map = {
                "AStock": ("sh", "sz"),
                "HKStock": ("hk",),
                "USStock": ("us",),
            }
            prefixes = market_prefix_map.get(market, ())

            filtered = []
            for item in symbols:
                code = item.get("code", "")
                if prefixes:
                    if any(code.startswith(p) for p in prefixes):
                        filtered.append(
                            {
                                "symbol": code.lstrip("shszHKus")
                                .lstrip("0")
                                .lstrip("hk")
                                .lstrip("us")
                                or code,
                                "name": item.get("name", ""),
                                "code": code,
                            }
                        )
                else:
                    filtered.append(
                        {
                            "symbol": code,
                            "name": item.get("name", ""),
                            "code": code,
                        }
                    )

            return {"success": True, "data": filtered, "count": len(filtered)}
        except Exception as e:
            logger.warning(f"[MCP] search_symbols failed: {e}")
            return {"success": False, "error": str(e), "data": []}

    def _get_portfolio(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """获取组合持仓"""
        try:
            from app.routers.portfolio import portfolio_detail
            import asyncio

            portfolio_id = arguments.get("portfolio_id")

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                if portfolio_id:
                    result = loop.run_until_complete(
                        portfolio_detail(portfolio_id)
                    )
                else:
                    result = loop.run_until_complete(portfolio_detail(None))
            finally:
                loop.close()

            return {"success": True, "data": result}
        except Exception as e:
            logger.warning(f"[MCP] get_portfolio failed: {e}")
            return {"success": False, "error": str(e), "data": None}

    def _get_account_info(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """获取账户资金信息"""
        try:
            from app.routers.portfolio import portfolio_summary
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(portfolio_summary())
            finally:
                loop.close()

            return {"success": True, "data": result}
        except Exception as e:
            logger.warning(f"[MCP] get_account_info failed: {e}")
            return {"success": False, "error": str(e), "data": None}

    def _submit_order(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """提交模拟订单"""
        try:
            from app.services.agent.paper_trading import (
                PaperTradingService,
                OrderSide,
            )

            service = PaperTradingService.get_instance()
            order = service.submit_order(
                symbol=arguments["symbol"],
                side=arguments["side"],
                quantity=float(arguments["quantity"]),
                price=float(arguments["price"]),
            )

            return {
                "success": True,
                "data": {
                    "id": order.id,
                    "symbol": order.symbol,
                    "side": order.side.value,
                    "quantity": order.quantity,
                    "price": order.price,
                    "status": order.status.value,
                    "created_at": order.created_at.isoformat(),
                },
            }
        except Exception as e:
            logger.warning(f"[MCP] submit_order failed: {e}")
            return {"success": False, "error": str(e)}

    def _list_orders(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """列出订单"""
        try:
            from app.services.agent.paper_trading import PaperTradingService

            service = PaperTradingService.get_instance()
            symbol = arguments.get("symbol")
            status = arguments.get("status")

            orders = service.list_orders(symbol=symbol, status=status)

            return {
                "success": True,
                "data": [
                    {
                        "id": o.id,
                        "symbol": o.symbol,
                        "side": o.side.value,
                        "quantity": o.quantity,
                        "price": o.price,
                        "status": o.status.value,
                        "created_at": o.created_at.isoformat(),
                        "filled_at": o.filled_at.isoformat()
                        if o.filled_at
                        else None,
                    }
                    for o in orders
                ],
                "count": len(orders),
            }
        except Exception as e:
            logger.warning(f"[MCP] list_orders failed: {e}")
            return {"success": False, "error": str(e), "data": []}

    def _cancel_order(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """取消订单"""
        try:
            from app.services.agent.paper_trading import PaperTradingService

            service = PaperTradingService.get_instance()
            success = service.cancel_order(arguments["order_id"])

            if success:
                return {"success": True, "message": "Order cancelled"}
            else:
                return {"success": False, "error": "Order not found or cannot be cancelled"}
        except Exception as e:
            logger.warning(f"[MCP] cancel_order failed: {e}")
            return {"success": False, "error": str(e)}

    # ── Public API ────────────────────────────────────────────────────────────

    def list_tools(self) -> List[Dict[str, Any]]:
        """返回所有工具的元信息"""
        return [tool.to_dict() for tool in self._tools.values()]

    def call_tool(
        self, name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """调用指定工具"""
        if name not in self._tools:
            return {"success": False, "error": f"Unknown tool: {name}"}

        tool = self._tools[name]
        logger.debug(f"[MCP] call_tool: {name} with args: {arguments}")

        try:
            result = tool.handler(arguments)
            return result
        except Exception as e:
            logger.error(f"[MCP] call_tool {name} failed: {e}")
            return {"success": False, "error": str(e)}

    def get_tool(self, name: str) -> Optional[Tool]:
        """获取指定工具"""
        return self._tools.get(name)


def get_mcp_server() -> MCPServer:
    """获取 MCP Server 单例"""
    return MCPServer()
