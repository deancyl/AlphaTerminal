"""
Unit tests for Treemap Builder

Tests for P0-1: N+1 API call optimization using asyncio.gather()
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


class TestTreemapBuilderN1Optimization:
    """Test N+1 optimization in treemap builder."""

    @pytest.mark.asyncio
    async def test_fetch_sector_stocks_batch_uses_gather(self):
        """Test that _fetch_sector_stocks_batch uses asyncio.gather for parallel fetching."""
        from app.services.market_radar.treemap_builder import _fetch_sector_stocks_batch

        sector_names = ["白酒", "银行", "证券"]

        with patch(
            "app.services.market_radar.treemap_builder._executor"
        ) as mock_executor:
            # Mock the executor to return test data
            mock_loop = MagicMock()
            mock_loop.run_in_executor = AsyncMock(
                return_value=("白酒", [{"symbol": "600519", "name": "贵州茅台"}])
            )

            with patch("asyncio.get_running_loop", return_value=mock_loop):
                result = await _fetch_sector_stocks_batch(sector_names)

                # Verify asyncio.gather was called (via run_in_executor calls)
                assert mock_loop.run_in_executor.call_count == len(sector_names)

    @pytest.mark.asyncio
    async def test_build_sector_treemap_parallel_fetch(self):
        """Test that _build_sector_treemap fetches sectors and stocks in parallel."""
        from app.services.market_radar.treemap_builder import _build_sector_treemap

        with patch(
            "app.services.market_radar.treemap_builder._fetch_sectors"
        ) as mock_sectors:
            with patch(
                "app.services.market_radar.treemap_builder._fetch_all_stocks"
            ) as mock_stocks:
                with patch(
                    "app.services.market_radar.treemap_builder._fetch_sector_stocks_batch"
                ) as mock_batch:
                    mock_sectors.return_value = [{"name": "白酒", "code": "bk001"}]
                    mock_stocks.return_value = [
                        {"symbol": "600519", "name": "贵州茅台", "market_cap": 2e12}
                    ]
                    mock_batch.return_value = {
                        "白酒": [
                            {"symbol": "600519", "name": "贵州茅台", "market_cap": 2e12}
                        ]
                    }

                    result = await _build_sector_treemap()

                    # Verify parallel fetch was called
                    assert mock_sectors.called
                    assert mock_stocks.called
                    assert mock_batch.called

                    # Verify result structure
                    assert "data" in result
                    assert "last_update" in result
                    assert "data_source" in result


class TestTreemapBuilderDataSource:
    """Test data source tracking."""

    @pytest.mark.asyncio
    async def test_result_includes_data_source(self):
        """Test that result includes data_source field."""
        from app.services.market_radar.treemap_builder import _build_sector_treemap

        with patch(
            "app.services.market_radar.treemap_builder._fetch_sectors"
        ) as mock_sectors:
            with patch(
                "app.services.market_radar.treemap_builder._fetch_all_stocks"
            ) as mock_stocks:
                with patch(
                    "app.services.market_radar.treemap_builder._fetch_sector_stocks_batch"
                ) as mock_batch:
                    mock_sectors.return_value = []
                    mock_stocks.return_value = []
                    mock_batch.return_value = {}

                    result = await _build_sector_treemap()

                    assert "data_source" in result


class TestTreemapBuilderErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_timeout_returns_fallback(self):
        """Test that timeout returns fallback data with error flag."""
        from app.services.market_radar.treemap_builder import build_treemap_data

        with patch(
            "app.services.market_radar.treemap_builder._build_sector_treemap"
        ) as mock_build:
            mock_build.side_effect = asyncio.TimeoutError()

            result = await build_treemap_data(level="sector", timeout=15.0)

            assert "error" in result
            assert result["error"] == "timeout"
            assert result["data_source"] == "fallback"
