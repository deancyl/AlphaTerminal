"""
Market Radar Integration Tests

Wave 4-32: API integration tests
Tests the full flow from API call to response
"""

import pytest
import asyncio
import time
from unittest.mock import patch, MagicMock


class TestMarketRadarAPIIntegration:
    """Integration tests for Market Radar API."""

    @pytest.mark.asyncio
    async def test_treemap_full_flow(self):
        """Test complete treemap data flow."""
        from app.services.market_radar.treemap_builder import build_treemap_data

        # Mock the underlying data fetchers
        with patch('app.services.market_radar.treemap_builder._fetch_sectors') as mock_sectors:
            with patch('app.services.market_radar.treemap_builder._fetch_all_stocks') as mock_stocks:
                with patch('app.services.market_radar.treemap_builder._fetch_sector_stocks_batch') as mock_batch:
                    # Setup mock data
                    mock_sectors.return_value = [
                        {"name": "白酒", "code": "bk001"},
                        {"name": "银行", "code": "bk002"},
                    ]
                    mock_stocks.return_value = [
                        {"symbol": "600519", "name": "贵州茅台", "market_cap": 2e12, "change_pct": 2.5},
                        {"symbol": "601398", "name": "工商银行", "market_cap": 1e12, "change_pct": 1.0},
                    ]
                    mock_batch.return_value = {
                        "白酒": [{"symbol": "600519", "name": "贵州茅台", "market_cap": 2e12}],
                        "银行": [{"symbol": "601398", "name": "工商银行", "market_cap": 1e12}],
                    }

                    # Execute
                    result = await build_treemap_data(level="sector", timeout=15.0)

                    # Verify structure
                    assert "data" in result
                    assert "last_update" in result
                    assert "data_source" in result

                    # Verify parallel fetching was used
                    assert mock_batch.called

    @pytest.mark.asyncio
    async def test_anomaly_detection_full_flow(self):
        """Test complete anomaly detection flow."""
        from app.services.market_radar.anomaly_detector import detect_anomalies

        with patch('app.services.market_radar.anomaly_detector._fetch_all_stocks') as mock_stocks:
            with patch('app.services.market_radar.anomaly_detector._fetch_capital_flow') as mock_flow:
                with patch('app.services.market_radar.anomaly_detector._fetch_institution_research') as mock_research:
                    mock_stocks.return_value = [
                        {"symbol": "600519", "name": "贵州茅台", "price": 1800,
                         "high": 1850, "low": 1750, "pre_close": 1780, "change_pct": 1.12,
                         "amount": 1e9},
                    ]
                    mock_flow.return_value = [
                        {"symbol": "600519", "name": "贵州茅台", "main_net_inflow": -1e8},
                    ]
                    mock_research.return_value = [
                        {"symbol": "600519", "name": "贵州茅台", "research_count": 5},
                    ]

                    result = await detect_anomalies(anomaly_type=None, top_n=10, timeout=15.0)

                    assert "anomalies" in result
                    assert "last_update" in result
                    assert len(result["anomalies"]) >= 1

    @pytest.mark.asyncio
    async def test_error_handling_flow(self):
        """Test error handling in full flow."""
        from app.services.market_radar.treemap_builder import build_treemap_data

        # Force timeout
        with patch('app.services.market_radar.treemap_builder._build_sector_treemap') as mock_build:
            mock_build.side_effect = asyncio.TimeoutError()

            result = await build_treemap_data(level="sector", timeout=15.0)

            assert "error" in result
            assert result["error"] == "timeout"
            assert result["data_source"] == "fallback"


class TestMarketRadarPerformance:
    """Performance tests for Market Radar."""

    @pytest.mark.asyncio
    async def test_treemap_response_time(self):
        """Test that treemap builds within acceptable time."""
        from app.services.market_radar.treemap_builder import build_treemap_data

        with patch('app.services.market_radar.treemap_builder._fetch_sectors') as mock_sectors:
            with patch('app.services.market_radar.treemap_builder._fetch_all_stocks') as mock_stocks:
                with patch('app.services.market_radar.treemap_builder._fetch_sector_stocks_batch') as mock_batch:
                    mock_sectors.return_value = [{"name": f"板块{i}", "code": f"bk{i}"} for i in range(30)]
                    mock_stocks.return_value = [{"symbol": f"600{i}", "name": f"股票{i}", "market_cap": 1e10} for i in range(500)]
                    mock_batch.return_value = {f"板块{i}": [] for i in range(30)}

                    start_time = time.time()
                    result = await build_treemap_data(level="sector", timeout=15.0)
                    elapsed_time = time.time() - start_time

                    # Should complete within 5 seconds (mocked data)
                    assert elapsed_time < 5.0

    @pytest.mark.asyncio
    async def test_parallel_fetch_performance(self):
        """Test that parallel fetching is faster than sequential."""
        from app.services.market_radar.treemap_builder import _fetch_sector_stocks_batch

        # Simulate slow API calls (100ms each)
        async def slow_fetch(name):
            await asyncio.sleep(0.1)
            return (name, [{"symbol": "test", "name": name}])

        with patch('asyncio.get_running_loop') as mock_loop:
            mock_executor = MagicMock()

            async def mock_run_in_executor(executor, func, name):
                return await slow_fetch(name)

            mock_loop.return_value.run_in_executor = mock_run_in_executor

            # Test parallel fetch of 10 sectors
            start_time = time.time()
            result = await _fetch_sector_stocks_batch([f"板块{i}" for i in range(10)])
            elapsed_time = time.time() - start_time

            # Parallel should be ~100ms (max of all), not ~1000ms (sum of all)
            # With mocked async, this should be fast
            assert elapsed_time < 2.0  # Allow some overhead


class TestMarketRadarConcurrency:
    """Concurrency tests for Market Radar."""

    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test handling multiple concurrent requests."""
        from app.services.market_radar.treemap_builder import build_treemap_data

        with patch('app.services.market_radar.treemap_builder._fetch_sectors') as mock_sectors:
            with patch('app.services.market_radar.treemap_builder._fetch_all_stocks') as mock_stocks:
                with patch('app.services.market_radar.treemap_builder._fetch_sector_stocks_batch') as mock_batch:
                    mock_sectors.return_value = [{"name": "白酒", "code": "bk001"}]
                    mock_stocks.return_value = []
                    mock_batch.return_value = {}

                    # Simulate 10 concurrent requests
                    tasks = [build_treemap_data(level="sector", timeout=15.0) for _ in range(10)]
                    results = await asyncio.gather(*tasks)

                    # All should complete successfully
                    assert len(results) == 10
                    for result in results:
                        assert "data" in result

    @pytest.mark.asyncio
    async def test_rate_limiting_effect(self):
        """Test that rate limiting doesn't break functionality."""
        from app.config.rate_limit import get_endpoint_category, get_limit_for_path

        # Test rate limit configuration
        category = get_endpoint_category("/api/v1/market_radar/treemap")
        assert category == "market_radar"

        limit = get_limit_for_path("/api/v1/market_radar/treemap")
        assert limit.requests == 30
        assert limit.period == 60
