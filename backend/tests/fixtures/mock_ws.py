"""
Mock WebSocket fixtures for testing.

Provides reusable MockWebSocket classes for testing WebSocket-related functionality
without requiring actual network connections.
"""
import json
from typing import List, Dict, Any, Optional, Callable
from unittest.mock import AsyncMock


class MockWebSocket:
    """
    Mock WebSocket for testing WebSocket endpoints.
    
    Simulates the FastAPI WebSocket interface for testing:
    - accept() - connection acceptance
    - send_text() - message sending
    - receive_text() - message receiving
    - close() - connection closing
    
    Usage:
        mock_ws = MockWebSocket()
        await mock_ws.accept()
        await mock_ws.send_text(json.dumps({"type": "ping"}))
        assert len(mock_ws.sent_messages) == 1
    """
    
    def __init__(
        self,
        receive_messages: Optional[List[str]] = None,
        auto_accept: bool = True,
        raise_on_send: Optional[Exception] = None
    ):
        """
        Initialize MockWebSocket.
        
        Args:
            receive_messages: Pre-populated messages to receive (for testing receive loop)
            auto_accept: Automatically accept connection on accept() call
            raise_on_send: Exception to raise on send_text (for testing error handling)
        """
        self.closed = False
        self.close_code: Optional[int] = None
        self.close_reason: Optional[str] = None
        self.sent_messages: List[Dict[str, Any]] = []
        self._receive_messages = receive_messages or []
        self._receive_index = 0
        self._auto_accept = auto_accept
        self._raise_on_send = raise_on_send
        self.accepted = False
    
    async def accept(self) -> None:
        """Accept WebSocket connection."""
        if self._auto_accept:
            self.accepted = True
    
    async def send_text(self, data: str) -> None:
        """
        Send text message through WebSocket.
        
        Args:
            data: JSON string or plain text to send
        
        Raises:
            Exception: If raise_on_send is configured
        """
        if self._raise_on_send:
            raise self._raise_on_send
        
        if self.closed:
            raise RuntimeError("WebSocket is closed")
        
        # Parse JSON if possible, store both raw and parsed
        try:
            parsed = json.loads(data) if isinstance(data, str) else data
            self.sent_messages.append(parsed)
        except json.JSONDecodeError:
            self.sent_messages.append({"raw": data})
    
    async def receive_text(self) -> str:
        """
        Receive text message from WebSocket.
        
        Returns:
            Next message from receive_messages queue
            
        Raises:
            RuntimeError: If no more messages available
        """
        if self._receive_index >= len(self._receive_messages):
            raise RuntimeError("No more messages to receive")
        
        msg = self._receive_messages[self._receive_index]
        self._receive_index += 1
        return msg
    
    async def close(self, code: int = 1000, reason: str = "") -> None:
        """
        Close WebSocket connection.
        
        Args:
            code: WebSocket close code
            reason: Close reason string
        """
        self.closed = True
        self.close_code = code
        self.close_reason = reason
    
    def add_receive_message(self, message: str) -> None:
        """Add a message to the receive queue."""
        self._receive_messages.append(message)
    
    def clear_sent_messages(self) -> None:
        """Clear sent messages history."""
        self.sent_messages.clear()
    
    def get_last_sent_message(self) -> Optional[Dict[str, Any]]:
        """Get the last sent message."""
        return self.sent_messages[-1] if self.sent_messages else None


class MockWebSocketWithHeartbeat(MockWebSocket):
    """
    Mock WebSocket with heartbeat support.
    
    Automatically responds to ping messages with pong.
    
    Usage:
        mock_ws = MockWebSocketWithHeartbeat()
        await mock_ws.send_text(json.dumps({"type": "ping"}))
        # Automatically sends {"type": "pong"} back
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ping_count = 0
        self.pong_count = 0
        self._last_ping_time: Optional[float] = None
    
    async def send_text(self, data: str) -> None:
        """Send text and auto-respond to ping."""
        await super().send_text(data)
        
        # Check if this is a ping message
        try:
            parsed = json.loads(data) if isinstance(data, str) else data
            if parsed.get("type") == "ping":
                self.ping_count += 1
                self._last_ping_time = parsed.get("timestamp")
                # Auto-send pong response
                pong_msg = json.dumps({"type": "pong", "timestamp": self._last_ping_time})
                await super().send_text(pong_msg)
                self.pong_count += 1
        except (json.JSONDecodeError, TypeError):
            pass


class MockWebSocketFactory:
    """
    Factory for creating multiple MockWebSocket instances.
    
    Useful for testing multiple concurrent connections.
    
    Usage:
        factory = MockWebSocketFactory()
        connections = factory.create_batch(5)
        for ws in connections:
            await manager.connect(ws)
    """
    
    def __init__(
        self,
        default_receive_messages: Optional[List[str]] = None,
        default_raise_on_send: Optional[Exception] = None
    ):
        self._default_receive_messages = default_receive_messages
        self._default_raise_on_send = default_raise_on_send
        self._created: List[MockWebSocket] = []
    
    def create(
        self,
        receive_messages: Optional[List[str]] = None,
        raise_on_send: Optional[Exception] = None
    ) -> MockWebSocket:
        """Create a single MockWebSocket instance."""
        ws = MockWebSocket(
            receive_messages=receive_messages or self._default_receive_messages,
            raise_on_send=raise_on_send or self._default_raise_on_send
        )
        self._created.append(ws)
        return ws
    
    def create_batch(self, count: int) -> List[MockWebSocket]:
        """Create multiple MockWebSocket instances."""
        return [self.create() for _ in range(count)]
    
    def create_with_heartbeat(self, **kwargs) -> MockWebSocketWithHeartbeat:
        """Create a MockWebSocket with heartbeat support."""
        ws = MockWebSocketWithHeartbeat(**kwargs)
        self._created.append(ws)
        return ws
    
    def get_all_created(self) -> List[MockWebSocket]:
        """Get all created WebSocket instances."""
        return self._created
    
    def clear(self) -> None:
        """Clear all created instances."""
        self._created.clear()


# Convenience fixtures for pytest
def create_mock_websocket(
    receive_messages: Optional[List[str]] = None,
    raise_on_send: Optional[Exception] = None
) -> MockWebSocket:
    """Convenience function to create a MockWebSocket."""
    return MockWebSocket(
        receive_messages=receive_messages,
        raise_on_send=raise_on_send
    )


def create_mock_websocket_batch(count: int) -> List[MockWebSocket]:
    """Convenience function to create multiple MockWebSocket instances."""
    factory = MockWebSocketFactory()
    return factory.create_batch(count)