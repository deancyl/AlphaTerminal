#!/usr/bin/env python3
"""
AlphaTerminal MCP Server - CLI Entry Point

Usage:
    python -m app.mcp.server_main

Environment Variables:
    ALPHATERMINAL_BASE_URL: Backend API URL (default: http://localhost:8002)
    ALPHATERMINAL_AGENT_TOKEN: Agent token for authentication
    ALPHATERMINAL_TRANSPORT: stdio | sse | streamable-http (default: stdio)
    ALPHATERMINAL_HOST: Server bind host (default: 0.0.0.0)
    ALPHATERMINAL_PORT: Server port (default: 7800)
"""

import os
import sys
import json
import logging
from typing import Any, Dict, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = os.environ.get('ALPHATERMINAL_BASE_URL', 'http://localhost:8002')
AGENT_TOKEN = os.environ.get('ALPHATERMINAL_AGENT_TOKEN', '')
TRANSPORT = os.environ.get('ALPHATERMINAL_TRANSPORT', 'stdio')


def get_tools() -> list:
    """Get list of available MCP tools"""
    return [
        {
            "name": "get_market_data",
            "description": "获取市场K线数据",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "market": {"type": "string", "enum": ["AStock", "HKStock", "USStock"]},
                    "symbol": {"type": "string"},
                    "timeframe": {"type": "string", "enum": ["1m", "5m", "15m", "1H", "4H", "1D", "1W"]},
                    "limit": {"type": "integer", "default": 100}
                },
                "required": ["market", "symbol", "timeframe"]
            }
        },
        {
            "name": "get_realtime_quote",
            "description": "获取实时行情报价",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "market": {"type": "string", "enum": ["AStock", "HKStock", "USStock"]},
                    "symbol": {"type": "string"}
                },
                "required": ["market", "symbol"]
            }
        },
        {
            "name": "search_symbols",
            "description": "搜索股票代码和名称",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "market": {"type": "string", "enum": ["AStock", "HKStock", "USStock"]},
                    "keyword": {"type": "string"},
                    "limit": {"type": "integer", "default": 20}
                },
                "required": ["market", "keyword"]
            }
        },
        {
            "name": "get_portfolio",
            "description": "获取组合持仓信息",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "portfolio_id": {"type": "string"}
                }
            }
        },
        {
            "name": "submit_order",
            "description": "提交模拟交易订单（仅Paper Trading）",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "side": {"type": "string", "enum": ["BUY", "SELL"]},
                    "quantity": {"type": "number"},
                    "price": {"type": "number"}
                },
                "required": ["symbol", "side", "quantity", "price"]
            }
        },
        {
            "name": "list_orders",
            "description": "列出所有模拟交易订单",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "status": {"type": "string", "enum": ["pending", "filled", "cancelled", "rejected"]}
                }
            }
        }
    ]


async def call_api(endpoint: str, method: str = "GET", data: Optional[Dict] = None) -> Dict[str, Any]:
    """Call AlphaTerminal API"""
    import urllib.request
    import urllib.error

    url = f"{BASE_URL}{endpoint}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AGENT_TOKEN}"
    }

    try:
        if method == "GET":
            req = urllib.request.Request(url, headers=headers)
        else:
            req = urllib.request.Request(url, data=json.dumps(data or {}).encode(), headers=headers)
            req.get_method = lambda: method

        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


def handle_request(request: Dict[str, Any]) -> Dict[str, Any]:
    """Handle MCP request"""
    method = request.get("method", "")
    params = request.get("params", {})
    request_id = request.get("id")

    if method == "initialize":
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "AlphaTerminal MCP", "version": "1.0.0"},
            "id": request_id
        }

    if method == "tools/list":
        return {
            "tools": get_tools(),
            "id": request_id
        }

    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if tool_name == "get_market_data":
            endpoint = "/api/v1/agent/v1/klines"
            response = call_api(endpoint, "POST", {
                "market": arguments.get("market"),
                "symbol": arguments.get("symbol"),
                "timeframe": arguments.get("timeframe", "1D"),
                "limit": arguments.get("limit", 100)
            })
            return {"content": [{"type": "text", "text": json.dumps(response)}], "id": request_id}

        elif tool_name == "get_realtime_quote":
            endpoint = f"/api/v1/agent/v1/price?market={arguments.get('market')}&symbol={arguments.get('symbol')}"
            response = call_api(endpoint)
            return {"content": [{"type": "text", "text": json.dumps(response)}], "id": request_id}

        elif tool_name == "search_symbols":
            endpoint = f"/api/v1/agent/v1/markets/{arguments.get('market')}/symbols?keyword={arguments.get('keyword', '')}&limit={arguments.get('limit', 20)}"
            response = call_api(endpoint)
            return {"content": [{"type": "text", "text": json.dumps(response)}], "id": request_id}

        elif tool_name == "get_portfolio":
            endpoint = "/api/v1/agent/v1/portfolio"
            response = call_api(endpoint)
            return {"content": [{"type": "text", "text": json.dumps(response)}], "id": request_id}

        elif tool_name == "submit_order":
            endpoint = "/api/v1/agent/v1/orders"
            response = call_api(endpoint, "POST", {
                "symbol": arguments.get("symbol"),
                "side": arguments.get("side"),
                "quantity": arguments.get("quantity"),
                "price": arguments.get("price")
            })
            return {"content": [{"type": "text", "text": json.dumps(response)}], "id": request_id}

        elif tool_name == "list_orders":
            endpoint = "/api/v1/agent/v1/orders"
            response = call_api(endpoint)
            return {"content": [{"type": "text", "text": json.dumps(response)}], "id": request_id}

        else:
            return {"error": f"Unknown tool: {tool_name}", "id": request_id}

    return {"error": f"Unknown method: {method}", "id": request_id}


def run_stdio():
    """Run MCP server in stdio mode"""
    logger.info("Starting AlphaTerminal MCP Server in stdio mode")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
            response = handle_request(request)
            print(json.dumps(response), flush=True)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            print(json.dumps({"error": f"Invalid JSON: {e}"}), flush=True)


def run_http():
    """Run MCP server in HTTP mode"""
    import urllib.request
    from http.server import HTTPServer, BaseHTTPRequestHandler

    host = os.environ.get('ALPHATERMINAL_HOST', '0.0.0.0')
    port = int(os.environ.get('ALPHATERMINAL_PORT', '7800'))

    class MCPHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode()

            try:
                request = json.loads(body)
                response = handle_request(request)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                logger.error(f"Error: {e}")
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())

        def do_GET(self):
            if self.path == '/tools':
                response = {"tools": get_tools()}
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            else:
                self.send_response(404)
                self.end_headers()

    server = HTTPServer((host, port), MCPHandler)
    logger.info(f"Starting MCP Server on {host}:{port}")
    server.serve_forever()


def main():
    """Main entry point"""
    if TRANSPORT == "stdio":
        run_stdio()
    else:
        run_http()


if __name__ == "__main__":
    main()
