"""
Unit tests for WebSocket streaming module.

Tests:
    - BaseStreamer state machine
    - SinaStreamer message parsing
    - MockSinaStreamer tick generation
    - StreamingManager circuit breaker
    - StreamingManager HTTP fallback
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import time

from app.services.streaming.base_streamer import BaseStreamer, StreamerState
from app.services.streaming.sina_streamer import SinaStreamer, MockSinaStreamer
from app.services.streaming.streaming_manager import StreamingManager, StreamingMode


class TestBaseStreamer:
    """Test BaseStreamer abstract class."""
    
    def test_streamer_state_enum(self):
        assert StreamerState.DISCONNECTED.value == "disconnected"
        assert StreamerState.CONNECTING.value == "connecting"
        assert StreamerState.CONNECTED.value == "connected"
        assert StreamerState.RECONNECTING.value == "reconnecting"
        assert StreamerState.FAILED.value == "failed"
    
    def test_streamer_initial_state(self):
        streamer = MockSinaStreamer()
        assert streamer.state == StreamerState.DISCONNECTED
        assert not streamer.is_connected
        assert not streamer.is_failed
    
    def test_streamer_stats(self):
        streamer = MockSinaStreamer()
        stats = streamer.stats
        
        assert stats["name"] == "mock_sina"
        assert stats["state"] == "disconnected"
        assert stats["subscribed_symbols"] == 0
        assert stats["message_count"] == 0


class TestMockSinaStreamer:
    """Test MockSinaStreamer for testing/fallback."""
    
    @pytest.mark.asyncio
    async def test_mock_streamer_lifecycle(self):
        ticks_received = []
        
        def on_tick(symbol, tick):
            ticks_received.append((symbol, tick))
        
        streamer = MockSinaStreamer(on_tick=on_tick)
        
        await streamer.start(symbols=["sh600519", "sz000001"])
        
        await asyncio.sleep(1.5)
        
        await streamer.stop()
        
        assert len(ticks_received) >= 2
        
        symbol, tick = ticks_received[0]
        assert symbol in ["sh600519", "sz000001"]
        assert tick["type"] == "tick"
        assert tick["price"] > 0
        assert tick["source"] == "mock"
    
    @pytest.mark.asyncio
    async def test_mock_streamer_add_remove_symbols(self):
        streamer = MockSinaStreamer()
        
        await streamer.start(symbols=["sh600519"])
        await asyncio.sleep(0.1)
        
        assert "sh600519" in streamer._subscribed_symbols
        
        await streamer.add_symbols(["sz000001"])
        assert "sz000001" in streamer._subscribed_symbols
        
        await streamer.remove_symbols(["sh600519"])
        assert "sh600519" not in streamer._subscribed_symbols
        
        await streamer.stop()


class TestSinaStreamer:
    """Test SinaStreamer message parsing."""
    
    def test_parse_tick_valid(self):
        streamer = SinaStreamer()
        
        data = {
            "symbol": "sh600519",
            "name": "贵州茅台",
            "price": 1800.50,
            "open": 1790.00,
            "high": 1810.00,
            "low": 1785.00,
            "prev_close": 1785.00,
            "volume": 1000000,
            "amount": 1800000000,
            "turnover": 0.5,
        }
        
        tick = streamer._parse_tick(data)
        
        assert tick is not None
        assert tick["symbol"] == "sh600519"
        assert tick["name"] == "贵州茅台"
        assert tick["price"] == 1800.50
        assert tick["source"] == "sina_ws"
    
    def test_parse_tick_invalid_price(self):
        streamer = SinaStreamer()
        
        data = {
            "symbol": "sh600519",
            "price": 0,
        }
        
        tick = streamer._parse_tick(data)
        
        assert tick is None
    
    def test_parse_tick_missing_symbol(self):
        streamer = SinaStreamer()
        
        data = {
            "price": 1800.50,
        }
        
        tick = streamer._parse_tick(data)
        
        assert tick is None


class TestStreamingManager:
    """Test StreamingManager with circuit breaker and HTTP fallback."""
    
    @pytest.mark.asyncio
    async def test_streaming_manager_initial_state(self):
        manager = StreamingManager(enable_mock=True)
        
        assert manager.mode == StreamingMode.HTTP_FALLBACK
        assert not manager.is_streaming
        assert manager.is_http_fallback
    
    @pytest.mark.asyncio
    async def test_streaming_manager_mock_mode(self):
        ticks_received = []
        
        def on_tick(symbol, tick):
            ticks_received.append((symbol, tick))
        
        manager = StreamingManager(enable_mock=True)
        
        await manager.start(symbols=["sh600519"])
        
        await asyncio.sleep(1.5)
        
        assert manager.mode == StreamingMode.MOCK
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_streaming_manager_circuit_breaker(self):
        manager = StreamingManager(enable_mock=False)
        
        for _ in range(5):
            manager._record_failure()
        
        assert manager._circuit_breaker_open
        assert manager._circuit_breaker_failures == 5
    
    @pytest.mark.asyncio
    async def test_streaming_manager_force_failover(self):
        manager = StreamingManager(enable_mock=True)
        
        await manager.start(symbols=["sh600519"])
        await asyncio.sleep(0.5)
        
        await manager.force_failover()
        
        assert manager.mode == StreamingMode.HTTP_FALLBACK
        assert manager._circuit_breaker_open
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_streaming_manager_reset_circuit_breaker(self):
        manager = StreamingManager(enable_mock=True)
        
        manager._circuit_breaker_open = True
        manager._circuit_breaker_failures = 5
        
        await manager.reset_circuit_breaker()
        
        assert not manager._circuit_breaker_open
        assert manager.mode == StreamingMode.MOCK
    
    @pytest.mark.asyncio
    async def test_streaming_manager_add_remove_symbols(self):
        manager = StreamingManager(enable_mock=True)
        
        await manager.start(symbols=["sh600519"])
        await asyncio.sleep(0.1)
        
        assert "sh600519" in manager._subscribed_symbols
        
        await manager.add_symbols(["sz000001"])
        assert "sz000001" in manager._subscribed_symbols
        
        await manager.remove_symbols(["sh600519"])
        assert "sh600519" not in manager._subscribed_symbols
        
        await manager.stop()
    
    def test_streaming_manager_get_status(self):
        manager = StreamingManager(enable_mock=True)
        
        status = manager.get_status()
        
        assert "mode" in status
        assert "circuit_breaker" in status
        assert "streamers" in status
        assert "total_symbols" in status


class TestStreamingManagerIntegration:
    """Integration tests for StreamingManager with ws_manager."""
    
    @pytest.mark.asyncio
    async def test_streaming_manager_broadcasts_to_ws_manager(self):
        from app.services.ws_manager import ws_manager
        
        broadcast_calls = []
        
        original_broadcast = ws_manager.broadcast_tick
        
        async def mock_broadcast(symbol, tick):
            broadcast_calls.append((symbol, tick))
        
        ws_manager.broadcast_tick = mock_broadcast
        
        try:
            manager = StreamingManager(ws_manager=ws_manager, enable_mock=True)
            
            await manager.start(symbols=["sh600519"])
            
            await asyncio.sleep(1.5)
            
            assert len(broadcast_calls) >= 1
            
            await manager.stop()
        finally:
            ws_manager.broadcast_tick = original_broadcast


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
