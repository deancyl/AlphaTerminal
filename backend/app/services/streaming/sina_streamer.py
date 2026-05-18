"""
Sina WebSocket Streamer.

Connects to Sina's real-time quote WebSocket API and broadcasts
tick updates to subscribers via the ws_manager.

Protocol:
    - Connect: wss://hq.sinajs.cn/ws
    - Subscribe: {"action":"subscribe","symbols":["sh600519","sz000001"]}
    - Message: JSON tick with OHLCV data
"""
import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Any, Union

try:
    import websockets
    from websockets.client import ClientConnection
except ImportError:
    websockets = None
    ClientConnection = None

from .base_streamer import BaseStreamer, StreamerState

logger = logging.getLogger(__name__)


class SinaStreamer(BaseStreamer):
    """
    Sina WebSocket real-time quote streamer.
    
    Connects to Sina's WebSocket API and parses tick messages
    for broadcasting to connected clients.
    """
    
    name = "sina"
    ws_url = "wss://hq.sinajs.cn/ws"
    
    PING_INTERVAL = 30
    MESSAGE_TIMEOUT = 60
    
    def __init__(self, on_tick=None, proxy: Optional[str] = None):
        super().__init__(on_tick=on_tick)
        self._proxy = proxy
        self._ws: Optional[Any] = None
        self._ping_task = None
        self._last_ping_time = 0.0
    
    async def connect(self):
        if websockets is None:
            raise ImportError("websockets library not installed. Run: pip install websockets")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Origin": "https://finance.sina.com.cn",
        }
        
        self._ws = await websockets.connect(
            self.ws_url,
            additional_headers=headers,
            ping_interval=self.PING_INTERVAL,
            ping_timeout=10,
            close_timeout=5,
        )
        
        logger.info(f"[{self.name}] WebSocket connected to {self.ws_url}")
    
    async def subscribe(self, symbols: List[str]):
        if not self._ws or not symbols:
            return
        
        msg = json.dumps({
            "action": "subscribe",
            "symbols": symbols
        }, ensure_ascii=False)
        
        await self._ws.send(msg)
        logger.debug(f"[{self.name}] Subscribed to {len(symbols)} symbols")
    
    async def unsubscribe(self, symbols: List[str]):
        if not self._ws or not symbols:
            return
        
        msg = json.dumps({
            "action": "unsubscribe",
            "symbols": symbols
        }, ensure_ascii=False)
        
        await self._ws.send(msg)
        logger.debug(f"[{self.name}] Unsubscribed from {len(symbols)} symbols")
    
    async def disconnect(self):
        ping_task: Optional[asyncio.Task] = self._ping_task
        self._ping_task = None
        
        if ping_task is not None:
            ping_task.cancel()
            try:
                await ping_task
            except asyncio.CancelledError:
                pass
        
        ws = self._ws
        self._ws = None
        
        if ws is not None:
            try:
                await ws.close()
            except Exception:
                pass
        
        logger.info(f"[{self.name}] Disconnected")
    
    async def _message_loop(self):
        while self._running and self._ws:
            try:
                raw = await asyncio.wait_for(
                    self._ws.recv(),
                    timeout=self.MESSAGE_TIMEOUT
                )
                
                await self._handle_message(raw)
                
            except asyncio.TimeoutError:
                logger.warning(f"[{self.name}] Message timeout, sending ping")
                await self._send_ping()
                
            except Exception as e:
                if websockets and isinstance(e, websockets.exceptions.ConnectionClosed):
                    logger.warning(f"[{self.name}] Connection closed: {e}")
                    raise
                logger.error(f"[{self.name}] Message loop error: {e}")
                raise
    
    async def _handle_message(self, raw: Union[str, bytes]):
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        try:
            data = json.loads(raw)
            
            if data.get("type") == "pong":
                logger.debug(f"[{self.name}] Received pong")
                return
            
            if data.get("type") == "tick":
                tick = self._parse_tick(data)
                if tick and tick.get("symbol"):
                    self._emit_tick(tick["symbol"], tick)
                    
        except json.JSONDecodeError:
            logger.warning(f"[{self.name}] Invalid JSON: {raw[:100]}")
        except Exception as e:
            logger.error(f"[{self.name}] Handle message error: {e}")
    
    def _parse_tick(self, data: Dict) -> Optional[Dict[str, Any]]:
        symbol = data.get("symbol", "")
        if not symbol:
            return None
        
        symbol = symbol.lower().strip()
        
        price = float(data.get("price", 0) or 0)
        prev_close = float(data.get("prev_close", 0) or 0)
        
        if price <= 0:
            return None
        
        change_pct = ((price - prev_close) / prev_close * 100) if prev_close > 0 else 0.0
        change = round(price - prev_close, 3) if prev_close > 0 else 0.0
        
        return {
            "type": "tick",
            "symbol": symbol,
            "name": data.get("name", ""),
            "price": price,
            "open": float(data.get("open", 0) or 0),
            "high": float(data.get("high", 0) or 0),
            "low": float(data.get("low", 0) or 0),
            "prev_close": prev_close,
            "chg": change,
            "chg_pct": round(change_pct, 4),
            "volume": float(data.get("volume", 0) or 0),
            "amount": float(data.get("amount", 0) or 0),
            "turnover": float(data.get("turnover", 0) or 0),
            "timestamp": int(time.time()),
            "source": "sina_ws",
        }
    
    async def _send_ping(self):
        if self._ws:
            try:
                await self._ws.send(json.dumps({"action": "ping"}))
                self._last_ping_time = time.time()
            except Exception as e:
                logger.warning(f"[{self.name}] Ping failed: {e}")


class MockSinaStreamer(BaseStreamer):
    """
    Mock Sina streamer for testing/fallback.
    
    Generates simulated tick data at regular intervals.
    """
    
    name = "mock_sina"
    ws_url = "mock://localhost"
    
    TICK_INTERVAL = 1.0
    
    MOCK_PRICES = {
        "sh600519": {"name": "贵州茅台", "base": 1800.0},
        "sz000001": {"name": "平安银行", "base": 12.0},
        "sh000001": {"name": "上证指数", "base": 3200.0},
        "sh000300": {"name": "沪深300", "base": 3800.0},
        "sz399001": {"name": "深证成指", "base": 10500.0},
        "sz399006": {"name": "创业板指", "base": 2100.0},
    }
    
    async def connect(self):
        logger.info(f"[{self.name}] Mock connection established")
    
    async def subscribe(self, symbols: List[str]):
        logger.info(f"[{self.name}] Mock subscribed to {symbols}")
    
    async def unsubscribe(self, symbols: List[str]):
        logger.info(f"[{self.name}] Mock unsubscribed from {symbols}")
    
    async def disconnect(self):
        logger.info(f"[{self.name}] Mock disconnected")
    
    async def _message_loop(self):
        import random
        
        while self._running:
            for symbol in self._subscribed_symbols:
                mock_data = self.MOCK_PRICES.get(symbol, {"name": symbol, "base": 100.0})
                base_price = mock_data["base"]
                
                variation = random.uniform(-0.02, 0.02)
                price = base_price * (1 + variation)
                prev_close = base_price
                change_pct = (price - prev_close) / prev_close * 100
                
                tick = {
                    "type": "tick",
                    "symbol": symbol,
                    "name": mock_data["name"],
                    "price": round(price, 2),
                    "open": round(base_price * 1.001, 2),
                    "high": round(price * 1.005, 2),
                    "low": round(price * 0.995, 2),
                    "prev_close": prev_close,
                    "chg": round(price - prev_close, 3),
                    "chg_pct": round(change_pct, 4),
                    "volume": random.randint(100000, 10000000),
                    "amount": random.uniform(10000000, 1000000000),
                    "turnover": random.uniform(0.1, 5.0),
                    "timestamp": int(time.time()),
                    "source": "mock",
                }
                
                self._emit_tick(symbol, tick)
            
            await asyncio.sleep(self.TICK_INTERVAL)
