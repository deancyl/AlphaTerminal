"""
Abstract base class for WebSocket streamers.

All streamers (Sina, Eastmoney, etc.) inherit from this base class
and implement the abstract methods for their specific protocols.
"""
import asyncio
import logging
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Callable, Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class StreamerState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


class BaseStreamer(ABC):
    """
    Abstract base class for WebSocket streamers.
    
    Lifecycle:
        connect() → subscribe() → [on_message loop] → disconnect()
        
    Features:
        - Automatic reconnection with exponential backoff
        - State machine for connection management
        - Callback-based tick delivery
        - Graceful shutdown
    """
    
    name: str = "base"
    ws_url: str = ""
    
    RECONNECT_BASE_DELAY = 1.0
    RECONNECT_MAX_DELAY = 60.0
    RECONNECT_MULTIPLIER = 2.0
    MAX_CONSECUTIVE_FAILURES = 5
    
    def __init__(self, on_tick: Optional[Callable[[str, Dict], None]] = None):
        self._state = StreamerState.DISCONNECTED
        self._ws = None
        self._subscribed_symbols: set[str] = set()
        self._on_tick = on_tick
        self._running = False
        self._reconnect_delay = self.RECONNECT_BASE_DELAY
        self._consecutive_failures = 0
        self._last_message_time = 0.0
        self._connect_time = 0.0
        self._message_count = 0
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
    
    @property
    def state(self) -> StreamerState:
        return self._state
    
    @property
    def is_connected(self) -> bool:
        return self._state == StreamerState.CONNECTED
    
    @property
    def is_failed(self) -> bool:
        return self._state == StreamerState.FAILED
    
    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "state": self._state.value,
            "subscribed_symbols": len(self._subscribed_symbols),
            "consecutive_failures": self._consecutive_failures,
            "reconnect_delay": self._reconnect_delay,
            "last_message_time": self._last_message_time,
            "connect_time": self._connect_time,
            "uptime": time.time() - self._connect_time if self._connect_time > 0 else 0,
            "message_count": self._message_count,
        }
    
    def set_tick_callback(self, callback: Callable[[str, Dict], None]):
        self._on_tick = callback
    
    async def start(self, symbols: Optional[List[str]] = None):
        if self._running:
            logger.warning(f"[{self.name}] Already running")
            return
        
        self._running = True
        if symbols:
            self._subscribed_symbols = set(s.lower() for s in symbols)
        
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"[{self.name}] Started with {len(self._subscribed_symbols)} symbols")
    
    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        
        await self.disconnect()
        logger.info(f"[{self.name}] Stopped")
    
    async def _run_loop(self):
        while self._running:
            try:
                await self._connect_and_stream()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self.name}] Stream error: {e}")
                self._consecutive_failures += 1
                
                if self._consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                    self._state = StreamerState.FAILED
                    logger.error(f"[{self.name}] Max failures reached, entering FAILED state")
                    break
                
                self._state = StreamerState.RECONNECTING
                delay = min(
                    self.RECONNECT_BASE_DELAY * (self.RECONNECT_MULTIPLIER ** self._consecutive_failures),
                    self.RECONNECT_MAX_DELAY
                )
                self._reconnect_delay = delay
                logger.info(f"[{self.name}] Reconnecting in {delay:.1f}s (failure {self._consecutive_failures})")
                await asyncio.sleep(delay)
    
    async def _connect_and_stream(self):
        self._state = StreamerState.CONNECTING
        
        await self.connect()
        
        self._state = StreamerState.CONNECTED
        self._connect_time = time.time()
        self._consecutive_failures = 0
        self._reconnect_delay = self.RECONNECT_BASE_DELAY
        
        logger.info(f"[{self.name}] Connected to {self.ws_url}")
        
        if self._subscribed_symbols:
            await self.subscribe(list(self._subscribed_symbols))
        
        await self._message_loop()
    
    @abstractmethod
    async def connect(self):
        pass
    
    @abstractmethod
    async def subscribe(self, symbols: List[str]):
        pass
    
    @abstractmethod
    async def unsubscribe(self, symbols: List[str]):
        pass
    
    @abstractmethod
    async def disconnect(self):
        pass
    
    @abstractmethod
    async def _message_loop(self):
        pass
    
    def _emit_tick(self, symbol: str, tick: Dict):
        self._last_message_time = time.time()
        self._message_count += 1
        
        if self._on_tick:
            try:
                self._on_tick(symbol, tick)
            except Exception as e:
                logger.error(f"[{self.name}] Tick callback error: {e}")
    
    async def add_symbols(self, symbols: List[str]):
        async with self._lock:
            new_symbols = [s.lower() for s in symbols if s.lower() not in self._subscribed_symbols]
            if not new_symbols:
                return
            
            self._subscribed_symbols.update(new_symbols)
            
            if self.is_connected:
                await self.subscribe(new_symbols)
                logger.info(f"[{self.name}] Added {len(new_symbols)} symbols: {new_symbols[:5]}...")
    
    async def remove_symbols(self, symbols: List[str]):
        async with self._lock:
            to_remove = [s.lower() for s in symbols if s.lower() in self._subscribed_symbols]
            if not to_remove:
                return
            
            self._subscribed_symbols.difference_update(to_remove)
            
            if self.is_connected:
                await self.unsubscribe(to_remove)
                logger.info(f"[{self.name}] Removed {len(to_remove)} symbols")
