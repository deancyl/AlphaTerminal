import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio


@pytest.mark.asyncio
async def test_broadcast_performance_metrics():
    """Test performance metrics broadcast function"""
    from app.services.scheduler import broadcast_performance_metrics

    with patch('app.db.metrics_db.get_endpoint_stats') as mock_stats:
        with patch('app.services.ws_manager.ws_manager') as mock_ws:
            # Mock data
            mock_stats.return_value = [
                {'endpoint': '/api/v1/market/quote', 'avg_ms': 35.5, 'request_count': 100, 'max_ms': 150},
                {'endpoint': '/api/v1/macro/overview', 'avg_ms': 120.3, 'request_count': 50, 'max_ms': 300},
            ]

            # Mock broadcast
            mock_ws.broadcast_performance_metrics = AsyncMock()

            # Run function
            broadcast_performance_metrics()

            # Verify broadcast called
            assert mock_ws.broadcast_performance_metrics.called

            # Verify message structure
            call_args = mock_ws.broadcast_performance_metrics.call_args[0][0]
            assert 'stats' in call_args
            assert 'top_endpoints' in call_args
            assert call_args['stats']['total_requests'] == 150


def test_broadcast_performance_metrics_empty():
    """Test broadcast with no metrics"""
    from app.services.scheduler import broadcast_performance_metrics

    with patch('app.db.metrics_db.get_endpoint_stats') as mock_stats:
        with patch('app.services.ws_manager.ws_manager') as mock_ws:
            mock_stats.return_value = []
            mock_ws.broadcast_performance_metrics = AsyncMock()

            broadcast_performance_metrics()

            # Should still call broadcast (with zeros)
            assert mock_ws.broadcast_performance_metrics.called
            call_args = mock_ws.broadcast_performance_metrics.call_args[0][0]
            assert call_args['stats']['total_requests'] == 0
            assert call_args['stats']['avg_latency_ms'] == 0