"""
WebSocket 连接管理器 — 优化版本
使用 Dict[symbol, Set[WSConnection]] 实现 O(1) 广播查找
支持心跳检测、死连接清理、消息批量和速率限制
"""
import asyncio
import json
import logging
import time
from collections import defaultdict
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

# 心跳配置
PING_INTERVAL = 25  # 发送 ping 间隔（秒）
PONG_TIMEOUT = 10     # 等待 pong 响应超时（秒）
CLEANUP_INTERVAL = 30  # 死连接清理间隔（秒）
LOCK_TIMEOUT = 5.0  # Async lock timeout (seconds)

# 批量和速率限制配置
BATCH_INTERVAL = 0.05  # 50ms 批量发送间隔
MAX_SUBSCRIPTIONS = 50  # 每个连接最大订阅数
MAX_MSG_PER_SECOND = 100  # 每秒最大消息数


class WSConnection:
    """单个 WebSocket 连接及其订阅状态"""
    def __init__(self, ws: WebSocket):
        self._ws         = ws
        self._symbols    = set()
        self._lock       = asyncio.Lock()
        self._last_pong  = time.time()
        self._latency    = None
        self._msg_times  = []  # 速率限制：记录消息发送时间戳

    @property
    def ws(self) -> WebSocket:
        return self._ws

    @property
    def latency(self) -> float | None:
        return self._latency

    def update_pong(self, latency: float):
        """更新 pong 响应时间"""
        self._last_pong = time.time()
        self._latency = latency

    def is_alive(self) -> bool:
        """检查连接是否还活着（pong 未超时）"""
        return (time.time() - self._last_pong) < PONG_TIMEOUT

    def _check_rate_limit(self) -> bool:
        """检查是否超过速率限制，返回 True 表示允许发送"""
        now = time.time()
        self._msg_times = [t for t in self._msg_times if now - t < 1.0]
        if len(self._msg_times) >= MAX_MSG_PER_SECOND:
            return False
        self._msg_times.append(now)
        return True

    async def subscribe(self, symbols: list[str]) -> tuple[bool, str]:
        """
        追加订阅 symbols
        返回: (成功与否, 错误消息)
        """
        async with self._lock:
            new_symbols = [s.strip().lower() for s in symbols if s.strip().lower() not in self._symbols]
            if len(self._symbols) + len(new_symbols) > MAX_SUBSCRIPTIONS:
                return False, f"订阅数量超过限制（最大 {MAX_SUBSCRIPTIONS} 个）"
            for s in new_symbols:
                self._symbols.add(s)
            logger.debug(f"[WS] subs updated: {self._symbols}")
            return True, ""

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
    - 支持心跳检测、死连接自动清理、消息批量和速率限制
    """
    def __init__(self):
        self._conns: list[WSConnection] = []
        self._symbol_map: dict[str, set] = {}
        self._conn_lock  = asyncio.Lock()
        self._map_lock   = asyncio.Lock()
        self._heartbeat_task = None
        self._cleanup_task = None
        self._batch_task = None
        self._running = False
        self._latencies: list[float] = []
        self._batch_queue: dict[str, dict] = {}
        self._batch_lock = asyncio.Lock()

    async def start(self):
        """启动心跳、清理和批量任务"""
        if self._running:
            return
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self._batch_task = asyncio.create_task(self._batch_loop())
        logger.info("[WS] heartbeat, cleanup and batch tasks started")

    async def stop(self):
        """停止心跳、清理和批量任务"""
        self._running = False
        for task in [self._heartbeat_task, self._cleanup_task, self._batch_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        logger.info("[WS] heartbeat, cleanup and batch tasks stopped")

    async def _heartbeat_loop(self):
        """心跳循环：定期发送 ping 并检查响应"""
        while self._running:
            await asyncio.sleep(PING_INTERVAL)
            if not self._running:
                break

            async with self._conn_lock:
                conns_copy = list(self._conns)

            for conn in conns_copy:
                try:
                    await conn.ws.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    pass

    async def _cleanup_loop(self):
        """清理循环：移除死连接"""
        while self._running:
            await asyncio.sleep(CLEANUP_INTERVAL)
            if not self._running:
                break

            dead = []
            async with self._conn_lock:
                for conn in self._conns:
                    if not conn.is_alive():
                        dead.append(conn)

            for conn in dead:
                logger.warning(f"[WS] removing dead connection (pong timeout)")
                await self.disconnect(conn)

    async def _batch_loop(self):
        """批量发送循环：每 50ms 发送累积的消息"""
        while self._running:
            await asyncio.sleep(BATCH_INTERVAL)
            if not self._running:
                break

            async with self._batch_lock:
                if not self._batch_queue:
                    continue
                batch = self._batch_queue.copy()
                self._batch_queue.clear()

            if batch:
                await self._send_batch(batch)

    async def _send_batch(self, batch: dict[str, dict]):
        """发送批量消息给订阅者"""
        for symbol, tick in batch.items():
            sym_lower = symbol.strip().lower()
            data = json.dumps(tick, ensure_ascii=False)

            async with self._map_lock:
                subscribers = self._symbol_map.get(sym_lower, set()).copy()

            if not subscribers:
                continue

            dead = []
            for conn in subscribers:
                if not conn._check_rate_limit():
                    logger.warning(f"[WS] rate limit exceeded for connection, dropping message")
                    continue
                try:
                    await conn.ws.send_text(data)
                except Exception:
                    dead.append(conn)

            if dead:
                await self._remove_dead_connections(dead, sym_lower)

    async def _remove_dead_connections(self, dead: list[WSConnection], symbol: str):
        """移除死连接"""
        async with self._map_lock:
            for conn in dead:
                if conn in self._symbol_map.get(symbol, set()):
                    self._symbol_map[symbol].discard(conn)

        async with self._conn_lock:
            for conn in dead:
                if conn in self._conns:
                    self._conns.remove(conn)

        logger.warning(f"[WS] removed {len(dead)} dead connections")

    async def connect(self, ws: WebSocket) -> WSConnection:
        """注册新连接，返回 WSConnection 对象"""
        conn = WSConnection(ws)
        async with self._conn_lock:
            self._conns.append(conn)
        logger.info(f"[WS] client connected, total={len(self._conns)}")
        if not self._running:
            await self.start()
        return conn

    async def disconnect(self, conn: WSConnection):
        """注销连接"""
        symbols = await conn.get_symbols()

        async with self._conn_lock:
            if conn in self._conns:
                self._conns.remove(conn)

        async with self._map_lock:
            for sym in symbols:
                if sym in self._symbol_map:
                    self._symbol_map[sym].discard(conn)
                    if not self._symbol_map[sym]:
                        del self._symbol_map[sym]

        logger.info(f"[WS] client disconnected, total={len(self._conns)}")
        if not self._conns:
            await self.stop()

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

    async def subscribe(self, conn: WSConnection, symbols: list[str]) -> tuple[bool, str]:
        """
        连接订阅 symbols
        返回: (成功与否, 错误消息)
        """
        success, error = await conn.subscribe(symbols)
        if not success:
            logger.warning(f"[WS] subscription limit reached: {error}")
            return False, error
        sym_set = set(s.strip().lower() for s in symbols)
        async with self._map_lock:
            await self._update_symbol_map(conn, sym_set, is_add=True)
        return True, ""

    async def unsubscribe(self, conn: WSConnection, symbols: list[str]):
        """连接取消订阅 symbols"""
        await conn.unsubscribe(symbols)
        sym_set = set(s.strip().lower() for s in symbols)
        async with self._map_lock:
            await self._update_symbol_map(conn, sym_set, is_add=False)

    async def broadcast_tick(self, symbol: str, tick: dict):
        """
        广播 tick 给所有订阅了该 symbol 的连接（使用批量发送）
        消息会累积在队列中，每 50ms 批量发送
        """
        sym_lower = symbol.strip().lower()
        async with self._batch_lock:
            self._batch_queue[sym_lower] = tick

    async def broadcast_to_subscribers(self, symbol: str, tick: dict):
        """broadcast_tick 的别名，保持 API 兼容"""
        await self.broadcast_tick(symbol, tick)

    def total(self) -> int:
        return len(self._conns)

    async def get_metrics(self) -> dict:
        """获取 WebSocket 连接指标"""
        async with self._conn_lock:
            latencies = [c.latency for c in self._conns if c.latency is not None]
        async with self._batch_lock:
            batch_queue_size = len(self._batch_queue)
        return {
            "active_connections": len(self._conns),
            "latency_avg": sum(latencies) / len(latencies) if latencies else None,
            "latency_min": min(latencies) if latencies else None,
            "latency_max": max(latencies) if latencies else None,
            "subscribed_symbols": len(self._symbol_map),
            "batch_queue_size": batch_queue_size,
            "max_subscriptions": MAX_SUBSCRIPTIONS,
            "max_msg_per_second": MAX_MSG_PER_SECOND,
        }


ws_manager = ConnectionManager()
