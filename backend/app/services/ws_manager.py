"""
WebSocket 连接管理器
支持按股票代码订阅，后台 scheduler 广播增量 tick
"""
import asyncio
import json
import logging
from collections import defaultdict
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # symbol -> [WebSocket connections]
        self._conns: dict[str, list[WebSocket]] = defaultdict(list)
        # 防止并发写
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, symbol: str):
        """客户端订阅某只股票"""
        await ws.accept()
        async with self._lock:
            if ws not in self._conns[symbol]:
                self._conns[symbol].append(ws)
        logger.info(f"[WS] client connected: symbol={symbol}, total={len(self._conns[symbol])}")

    async def disconnect(self, ws: WebSocket, symbol: str):
        """客户端取消订阅"""
        async with self._lock:
            if ws in self._conns.get(symbol, []):
                self._conns[symbol].remove(ws)
                if not self._conns[symbol]:
                    del self._conns[symbol]
        logger.info(f"[WS] client disconnected: symbol={symbol}")

    async def broadcast_tick(self, symbol: str, tick: dict):
        """
        广播 tick 给所有订阅了该股票的客户端
        tick 格式: {"symbol":"600519","price":1680.5,"chg_pct":1.23,...}
        """
        async with self._lock:
            conns = list(self._conns.get(symbol, []))
        if not conns:
            return
        dead = []
        data = json.dumps(tick, ensure_ascii=False)
        for ws in conns:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        # 清理断开的连接
        if dead:
            async with self._lock:
                for ws in dead:
                    if ws in self._conns.get(symbol, []):
                        self._conns[symbol].remove(ws)

    def subscriber_count(self, symbol: str) -> int:
        return len(self._conns.get(symbol, []))

    def total_subscribers(self) -> int:
        return sum(len(v) for v in self._conns.values())


# 全局单例
ws_manager = ConnectionManager()
