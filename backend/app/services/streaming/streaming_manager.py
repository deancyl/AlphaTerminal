"""
Streaming Manager with Circuit Breaker and HTTP Fallback.

Manages multiple WebSocket streamers and provides:
    - Circuit breaker for connection failures
    - HTTP polling fallback when streaming unavailable
    - Automatic failover between streaming and polling
    - Unified tick broadcast to ws_manager
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Any, Set

from .base_streamer import BaseStreamer, StreamerState
from .sina_streamer import SinaStreamer, MockSinaStreamer

logger = logging.getLogger(__name__)


class StreamingMode(Enum):
    STREAMING = "streaming"
    HTTP_FALLBACK = "http_fallback"
    MOCK = "mock"


@dataclass
class StreamingStats:
    mode: StreamingMode = StreamingMode.HTTP_FALLBACK
    active_streamers: int = 0
    total_symbols: int = 0
    ticks_received: int = 0
    ticks_broadcast: int = 0
    last_tick_time: float = 0.0
    uptime_seconds: float = 0.0
    circuit_breaker_trips: int = 0
    http_fallback_activations: int = 0


class StreamingManager:
    """
    Manages WebSocket streaming with circuit breaker and HTTP fallback.
    
    Features:
        - Automatic failover to HTTP polling when streaming fails
        - Circuit breaker prevents cascading failures
        - Unified tick broadcast to ws_manager
        - Graceful degradation with mock data for testing
    """
    
    CIRCUIT_BREAKER_THRESHOLD = 5
    CIRCUIT_BREAKER_RESET_DELAY = 60.0
    HTTP_POLL_INTERVAL = 10.0
    HEALTH_CHECK_INTERVAL = 30.0
    
    def __init__(
        self,
        ws_manager=None,
        http_fetcher=None,
        proxy: Optional[str] = None,
        enable_mock: bool = False,
    ):
        self._ws_manager = ws_manager
        self._http_fetcher = http_fetcher
        self._proxy = proxy
        self._enable_mock = enable_mock
        
        self._streamers: Dict[str, BaseStreamer] = {}
        self._mode = StreamingMode.HTTP_FALLBACK
        self._running = False
        self._start_time = 0.0
        
        self._circuit_breaker_failures = 0
        self._circuit_breaker_open = False
        self._circuit_breaker_open_time = 0.0
        
        self._stats = StreamingStats()
        self._subscribed_symbols: Set[str] = set()
        
        self._http_poll_task: Optional[asyncio.Task] = None
        self._health_check_task: Optional[asyncio.Task] = None
        
        self._lock = asyncio.Lock()
    
    @property
    def mode(self) -> StreamingMode:
        return self._mode
    
    @property
    def stats(self) -> StreamingStats:
        self._stats.mode = self._mode
        self._stats.active_streamers = sum(1 for s in self._streamers.values() if s.is_connected)
        self._stats.total_symbols = len(self._subscribed_symbols)
        self._stats.uptime_seconds = time.time() - self._start_time if self._start_time > 0 else 0
        return self._stats
    
    @property
    def is_streaming(self) -> bool:
        return self._mode == StreamingMode.STREAMING
    
    @property
    def is_http_fallback(self) -> bool:
        return self._mode == StreamingMode.HTTP_FALLBACK
    
    def set_ws_manager(self, ws_manager):
        self._ws_manager = ws_manager
    
    def set_http_fetcher(self, fetcher):
        self._http_fetcher = fetcher
    
    async def start(self, symbols: Optional[List[str]] = None):
        if self._running:
            logger.warning("[StreamingManager] Already running")
            return
        
        self._running = True
        self._start_time = time.time()
        
        if symbols:
            self._subscribed_symbols = set(s.lower() for s in symbols)
        
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        
        await self._try_start_streaming()
        
        logger.info(f"[StreamingManager] Started with mode={self._mode.value}, symbols={len(self._subscribed_symbols)}")
    
    async def stop(self):
        self._running = False
        
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        if self._http_poll_task:
            self._http_poll_task.cancel()
            try:
                await self._http_poll_task
            except asyncio.CancelledError:
                pass
        
        for streamer in self._streamers.values():
            await streamer.stop()
        
        self._streamers.clear()
        logger.info("[StreamingManager] Stopped")
    
    async def _try_start_streaming(self):
        if self._circuit_breaker_open:
            elapsed = time.time() - self._circuit_breaker_open_time
            if elapsed < self.CIRCUIT_BREAKER_RESET_DELAY:
                logger.info(f"[StreamingManager] Circuit breaker open, using HTTP fallback ({elapsed:.0f}s remaining)")
                await self._start_http_fallback()
                return
            else:
                logger.info("[StreamingManager] Circuit breaker reset delay elapsed, attempting streaming")
                self._circuit_breaker_open = False
                self._circuit_breaker_failures = 0
        
        if self._enable_mock:
            await self._start_mock_streaming()
            return
        
        try:
            streamer = SinaStreamer(
                on_tick=self._on_tick,
                proxy=self._proxy
            )
            
            await streamer.start(list(self._subscribed_symbols))
            
            await asyncio.sleep(2.0)
            
            if streamer.is_connected:
                self._streamers["sina"] = streamer
                self._mode = StreamingMode.STREAMING
                logger.info("[StreamingManager] Streaming mode active (Sina WebSocket)")
            else:
                raise Exception("Streamer failed to connect")
                
        except Exception as e:
            logger.error(f"[StreamingManager] Streaming failed: {e}")
            self._record_failure()
            await self._start_http_fallback()
    
    async def _start_http_fallback(self):
        self._mode = StreamingMode.HTTP_FALLBACK
        self._stats.http_fallback_activations += 1
        
        logger.info(f"[StreamingManager] HTTP fallback mode active (polling every {self.HTTP_POLL_INTERVAL}s)")
        
        if self._http_poll_task:
            self._http_poll_task.cancel()
        
        self._http_poll_task = asyncio.create_task(self._http_poll_loop())
    
    async def _start_mock_streaming(self):
        self._mode = StreamingMode.MOCK
        
        streamer = MockSinaStreamer(on_tick=self._on_tick)
        await streamer.start(list(self._subscribed_symbols))
        self._streamers["mock"] = streamer
        
        logger.info("[StreamingManager] Mock streaming mode active")
    
    async def _http_poll_loop(self):
        while self._running:
            try:
                await self._poll_http_quotes()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[StreamingManager] HTTP poll error: {e}")
            
            await asyncio.sleep(self.HTTP_POLL_INTERVAL)
    
    async def _poll_http_quotes(self):
        if not self._http_fetcher or not self._subscribed_symbols:
            return
        
        try:
            symbols = list(self._subscribed_symbols)
            quotes = await self._http_fetcher.get_quotes_batch(symbols)
            
            for quote in quotes:
                tick = {
                    "type": "tick",
                    "symbol": quote.symbol.lower(),
                    "name": quote.name,
                    "price": quote.price,
                    "open": quote.open,
                    "high": quote.high,
                    "low": quote.low,
                    "prev_close": quote.prev_close,
                    "chg": quote.change,
                    "chg_pct": quote.change_pct,
                    "volume": quote.volume,
                    "amount": getattr(quote, 'amount', 0),
                    "turnover": getattr(quote, 'turnover', 0),
                    "timestamp": int(time.time()),
                    "source": "http_poll",
                }
                self._on_tick(quote.symbol.lower(), tick)
            
            logger.debug(f"[StreamingManager] HTTP polled {len(quotes)} quotes")
            
        except Exception as e:
            logger.error(f"[StreamingManager] HTTP poll failed: {e}")
    
    async def _health_check_loop(self):
        while self._running:
            await asyncio.sleep(self.HEALTH_CHECK_INTERVAL)
            
            if self._mode == StreamingMode.STREAMING:
                await self._check_streaming_health()
            elif self._mode == StreamingMode.HTTP_FALLBACK:
                await self._try_resume_streaming()
    
    async def _check_streaming_health(self):
        for name, streamer in list(self._streamers.items()):
            if streamer.is_failed:
                logger.warning(f"[StreamingManager] Streamer {name} failed, recording failure")
                self._record_failure()
                await streamer.stop()
                del self._streamers[name]
        
        if not self._streamers and self._mode == StreamingMode.STREAMING:
            logger.warning("[StreamingManager] No active streamers, switching to HTTP fallback")
            await self._start_http_fallback()
    
    async def _try_resume_streaming(self):
        if self._circuit_breaker_open:
            elapsed = time.time() - self._circuit_breaker_open_time
            if elapsed >= self.CIRCUIT_BREAKER_RESET_DELAY:
                logger.info("[StreamingManager] Attempting to resume streaming")
                await self._try_start_streaming()
    
    def _record_failure(self):
        self._circuit_breaker_failures += 1
        self._stats.circuit_breaker_trips += 1
        
        if self._circuit_breaker_failures >= self.CIRCUIT_BREAKER_THRESHOLD:
            self._circuit_breaker_open = True
            self._circuit_breaker_open_time = time.time()
            logger.warning(
                f"[StreamingManager] Circuit breaker OPEN after {self._circuit_breaker_failures} failures"
            )
    
    def _on_tick(self, symbol: str, tick: Dict):
        self._stats.ticks_received += 1
        self._stats.last_tick_time = time.time()
        
        if self._ws_manager:
            try:
                asyncio.create_task(self._ws_manager.broadcast_tick(symbol, tick))
                self._stats.ticks_broadcast += 1
            except Exception as e:
                logger.error(f"[StreamingManager] Broadcast error: {e}")
    
    async def add_symbols(self, symbols: List[str]):
        async with self._lock:
            new_symbols = [s.lower() for s in symbols if s.lower() not in self._subscribed_symbols]
            if not new_symbols:
                return
            
            self._subscribed_symbols.update(new_symbols)
            
            for streamer in self._streamers.values():
                await streamer.add_symbols(new_symbols)
            
            logger.info(f"[StreamingManager] Added {len(new_symbols)} symbols")
    
    async def remove_symbols(self, symbols: List[str]):
        async with self._lock:
            to_remove = [s.lower() for s in symbols if s.lower() in self._subscribed_symbols]
            if not to_remove:
                return
            
            self._subscribed_symbols.difference_update(to_remove)
            
            for streamer in self._streamers.values():
                await streamer.remove_symbols(to_remove)
            
            logger.info(f"[StreamingManager] Removed {len(to_remove)} symbols")
    
    async def force_failover(self):
        logger.info("[StreamingManager] Force failover triggered")
        
        for streamer in self._streamers.values():
            await streamer.stop()
        self._streamers.clear()
        
        self._circuit_breaker_open = True
        self._circuit_breaker_open_time = time.time()
        
        await self._start_http_fallback()
    
    async def reset_circuit_breaker(self):
        self._circuit_breaker_open = False
        self._circuit_breaker_failures = 0
        logger.info("[StreamingManager] Circuit breaker reset")
        
        await self._try_start_streaming()
    
    def get_status(self) -> Dict[str, Any]:
        stats = self.stats
        return {
            "mode": stats.mode.value,
            "active_streamers": stats.active_streamers,
            "total_symbols": stats.total_symbols,
            "ticks_received": stats.ticks_received,
            "ticks_broadcast": stats.ticks_broadcast,
            "last_tick_time": stats.last_tick_time,
            "uptime_seconds": stats.uptime_seconds,
            "circuit_breaker": {
                "open": self._circuit_breaker_open,
                "failures": self._circuit_breaker_failures,
                "threshold": self.CIRCUIT_BREAKER_THRESHOLD,
                "trips": stats.circuit_breaker_trips,
            },
            "http_fallback_activations": stats.http_fallback_activations,
            "streamers": {
                name: streamer.stats for name, streamer in self._streamers.items()
            },
        }


_streaming_manager: Optional[StreamingManager] = None


def get_streaming_manager() -> StreamingManager:
    global _streaming_manager
    if _streaming_manager is None:
        _streaming_manager = StreamingManager()
    return _streaming_manager
