"""
Test fixtures for AlphaTerminal backend tests.

This package provides reusable mock objects and test utilities:

MockWebSocket - Mock WebSocket for testing WebSocket endpoints
MockAkshareData - Mock data provider for Akshare API responses
MockAkshareClient - Mock Akshare client with configurable behavior
"""
from .mock_ws import (
    MockWebSocket,
    MockWebSocketWithHeartbeat,
    MockWebSocketFactory,
    create_mock_websocket,
    create_mock_websocket_batch,
)
from .mock_akshare import (
    MockAkshareData,
    MockAkshareClient,
    create_mock_akshare_client,
    create_sample_stock_quote,
    create_sample_index_quote,
)

__all__ = [
    # WebSocket mocks
    'MockWebSocket',
    'MockWebSocketWithHeartbeat',
    'MockWebSocketFactory',
    'create_mock_websocket',
    'create_mock_websocket_batch',
    # Akshare mocks
    'MockAkshareData',
    'MockAkshareClient',
    'create_mock_akshare_client',
    'create_sample_stock_quote',
    'create_sample_index_quote',
]