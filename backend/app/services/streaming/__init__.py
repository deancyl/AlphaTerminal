"""
WebSocket Streaming Source Layer

Provides real-time tick data streaming from external WebSocket APIs
with Pub/Sub broadcast to connected clients.

Architecture:
    External WS (Sina/Eastmoney) → BaseStreamer → StreamingManager → ws_manager.broadcast_tick()

Features:
    - <1s latency real-time tick data
    - Circuit breaker for connection failures
    - HTTP polling fallback when streaming unavailable
    - Automatic reconnect with exponential backoff
"""

from .base_streamer import BaseStreamer, StreamerState
from .sina_streamer import SinaStreamer, MockSinaStreamer
from .streaming_manager import StreamingManager, get_streaming_manager

__all__ = [
    'BaseStreamer',
    'StreamerState',
    'SinaStreamer',
    'MockSinaStreamer',
    'StreamingManager',
    'get_streaming_manager',
]