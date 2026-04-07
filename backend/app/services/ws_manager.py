"""
WebSocket 连接管理器 — 动态多路复用版本
每个连接独立订阅 symbol 集合，广播时按需过滤
"""
import asyncio
import json
import logging
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class WSConnection:
    """单个 WebSocket 连接及其订阅状态"""
    def __init__(self, ws: WebSocket):
        self._ws         = ws
        self._symbols    = set()        # 该连接订阅的 symbol 集合
        self._lock       = asyncio.Lock()

    @property
    def ws(self) -> WebSocket:
        return self._ws

    async def subscribe(self, symbols: list[str]):
        """追加订阅 symbols"""
        async with self._lock:
            for s in symbols:
                self._symbols.add(s.strip().lower())
            logger.info(f"[WS] subs updated: {self._symbols}")

    async def unsubscribe(self, symbols: list[str]):
        """取消订阅 symbols"""
        async with self._lock:
            for s in symbols:
                self._symbols.discard(s.strip().lower())
            logger.info(f"[WS] subs updated: {self._symbols}")

    async def get_symbols(self) -> set:
        async with self._lock:
            return set(self._symbols)


class ConnectionManager:
    def __init__(self):
        self._conns: list[WSConnection] = []   # 所有活跃连接（注册后端推送时会遍历全部）
        self._lock   = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> WSConnection:
        """注册新连接，返回 WSConnection 对象"""
        conn = WSConnection(ws)
        async with self._lock:
            self._conns.append(conn)
        logger.info(f"[WS] client connected, total={len(self._conns)}")
        return conn

    async def disconnect(self, conn: WSConnection):
        """注销连接"""
        async with self._lock:
            if conn in self._conns:
                self._conns.remove(conn)
        logger.info(f"[WS] client disconnected, total={len(self._conns)}")

    async def broadcast_tick(self, symbol: str, tick: dict):
        """
        广播 tick 给所有订阅了该 symbol 的连接
        """
        async with self._lock:
            active = list(self._conns)

        dead = []
        data = json.dumps(tick, ensure_ascii=False)
        sym_lower = symbol.strip().lower()

        for conn in active:
            subs = await conn.get_symbols()
            if sym_lower not in subs:
                continue
            try:
                await conn.ws.send_text(data)
            except Exception:
                dead.append(conn)

        if dead:
            async with self._lock:
                for conn in dead:
                    if conn in self._conns:
                        self._conns.remove(conn)

    async def broadcast_to_subscribers(self, symbol: str, tick: dict):
        """broadcast_tick 的别名，保持 API 兼容"""
        await self.broadcast_tick(symbol, tick)

    def total(self) -> int:
        return len(self._conns)


ws_manager = ConnectionManager()
