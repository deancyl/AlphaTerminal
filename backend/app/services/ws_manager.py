"""
WebSocket 连接管理器 — 优化版本
使用 Dict[symbol, Set[WSConnection]] 实现 O(1) 广播查找
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
            logger.debug(f"[WS] subs updated: {self._symbols}")

    async def unsubscribe(self, symbols: list[str]):
        """取消订阅 symbols"""
        async with self._lock:
            for s in symbols:
                self._symbols.discard(s.strip().lower())
            logger.debug(f"[WS] subs updated: {self._symbols}")

    async def get_symbols(self) -> set:
        async with self._lock:
            return set(self._symbols)


class ConnectionManager:
    """
    优化后的连接管理器：
    - 使用 _symbol_map: Dict[symbol, Set[WSConnection]] 实现 O(1) 查找
    - 广播时直接通过 symbol 获取订阅者，避免遍历所有连接
    """
    def __init__(self):
        self._conns: list[WSConnection] = []   # 所有活跃连接
        self._symbol_map: dict[str, set] = {}  # symbol -> 订阅该symbol的连接集合（O(1)查找）
        self._conn_lock  = asyncio.Lock()       # 保护 _conns
        self._map_lock   = asyncio.Lock()       # 保护 _symbol_map

    async def connect(self, ws: WebSocket) -> WSConnection:
        """注册新连接，返回 WSConnection 对象"""
        conn = WSConnection(ws)
        async with self._conn_lock:
            self._conns.append(conn)
        logger.info(f"[WS] client connected, total={len(self._conns)}")
        return conn

    async def disconnect(self, conn: WSConnection):
        """注销连接"""
        # 先获取连接的订阅列表
        symbols = await conn.get_symbols()
        
        async with self._conn_lock:
            if conn in self._conns:
                self._conns.remove(conn)
        
        # 从 symbol_map 中移除
        async with self._map_lock:
            for sym in symbols:
                if sym in self._symbol_map:
                    self._symbol_map[sym].discard(conn)
                    if not self._symbol_map[sym]:
                        del self._symbol_map[sym]
        
        logger.info(f"[WS] client disconnected, total={len(self._conns)}")

    async def _update_symbol_map(self, conn: WSConnection, symbols: set, is_add: bool):
        """更新 symbol_map（内部方法，需持有 _map_lock）"""
        for sym in symbols:
            if is_add:
                if sym not in self._symbol_map:
                    self._symbol_map[sym] = set()
                self._symbol_map[sym].add(conn)
            else:
                if sym in self._symbol_map:
                    self._symbol_map[sym].discard(conn)
                    if not self._symbol_map[sym]:
                        del self._symbol_map[sym]

    async def subscribe(self, conn: WSConnection, symbols: list[str]):
        """连接订阅 symbols"""
        sym_set = set(s.strip().lower() for s in symbols)
        async with self._map_lock:
            await self._update_symbol_map(conn, sym_set, is_add=True)

    async def unsubscribe(self, conn: WSConnection, symbols: list[str]):
        """连接取消订阅 symbols"""
        sym_set = set(s.strip().lower() for s in symbols)
        async with self._map_lock:
            await self._update_symbol_map(conn, sym_set, is_add=False)

    async def broadcast_tick(self, symbol: str, tick: dict):
        """
        广播 tick 给所有订阅了该 symbol 的连接
        使用 O(1) 查找：直接从 _symbol_map 获取订阅者
        
        消息格式（WebSocket 协议）：
        - tick 消息必须包含 "type": "tick" 字段
        - symbol 字段保持原始格式（不强制小写）
        - 示例：{"type": "tick", "symbol": "600519", "price": 1680.5, ...}
        
        订阅匹配规则：
        - 订阅时 symbol 统一转为小写存储（subscribe/unsubscribe 方法）
        - 广播时 symbol 转为小写进行匹配
        - 这确保了 "600519" 和 "SH600519" 等不同大小写形式能正确匹配
        """
        sym_lower = symbol.strip().lower()
        data = json.dumps(tick, ensure_ascii=False)
        
        # O(1) 获取订阅者
        async with self._map_lock:
            subscribers = self._symbol_map.get(sym_lower, set()).copy()

        if not subscribers:
            return

        dead = []
        for conn in subscribers:
            try:
                await conn.ws.send_text(data)
            except Exception:
                dead.append(conn)

        # 清理死连接
        if dead:
            async with self._map_lock:
                for conn in dead:
                    if conn in self._symbol_map.get(sym_lower, set()):
                        self._symbol_map[sym_lower].discard(conn)
            
            async with self._conn_lock:
                for conn in dead:
                    if conn in self._conns:
                        self._conns.remove(conn)
            
            logger.warning(f"[WS] removed {len(dead)} dead connections")

    async def broadcast_to_subscribers(self, symbol: str, tick: dict):
        """broadcast_tick 的别名，保持 API 兼容"""
        await self.broadcast_tick(symbol, tick)

    def total(self) -> int:
        return len(self._conns)


ws_manager = ConnectionManager()
