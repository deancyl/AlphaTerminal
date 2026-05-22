"""
Market Radar Performance Tests

Wave 4-33: Performance benchmark tests
Wave 4-34: Memory leak tests
Wave 4-35: Concurrent stress tests
"""

import pytest
import asyncio
import time
from unittest.mock import patch


class TestPerformanceBenchmarks:
    """Wave 4-33: Performance benchmark tests."""

    @pytest.mark.asyncio
    async def test_treemap_build_benchmark(self):
        """Benchmark treemap building time."""
        from app.services.market_radar.treemap_builder import build_treemap_data

        sectors = [{"name": f"板块{i}", "code": f"bk{i}"} for i in range(30)]
        stocks = [
            {
                "symbol": f"{600000+i}",
                "name": f"股票{i}",
                "market_cap": 1e10 + i * 1e8,
                "change_pct": i % 10 - 5,
            }
            for i in range(500)
        ]
        sector_stocks = {
            f"板块{i}": [
                {"symbol": f"{600000+i}", "name": f"股票{i}", "market_cap": 1e10}
                for i in range(20)
            ]
            for i in range(30)
        }

        with patch(
            "app.services.market_radar.treemap_builder._fetch_sectors",
            return_value=sectors,
        ):
            with patch(
                "app.services.market_radar.treemap_builder._fetch_all_stocks",
                return_value=stocks,
            ):
                with patch(
                    "app.services.market_radar.treemap_builder._fetch_sector_stocks_batch",
                    return_value=sector_stocks,
                ):

                    times = []
                    for _ in range(5):
                        start = time.perf_counter()
                        await build_treemap_data(level="sector", timeout=15.0)
                        elapsed = time.perf_counter() - start
                        times.append(elapsed)

                    avg_time = sum(times) / len(times)
                    assert avg_time < 1.0, f"Average time {avg_time}s exceeds threshold"


class TestConcurrentStress:
    """Wave 4-35: Concurrent stress tests."""

    @pytest.mark.asyncio
    async def test_concurrent_treemap_requests(self):
        """Test handling 100 concurrent treemap requests."""
        from app.services.market_radar.treemap_builder import build_treemap_data

        sectors = [{"name": "白酒", "code": "bk001"}]
        stocks = [{"symbol": "600519", "name": "贵州茅台", "market_cap": 2e12}]

        with patch(
            "app.services.market_radar.treemap_builder._fetch_sectors",
            return_value=sectors,
        ):
            with patch(
                "app.services.market_radar.treemap_builder._fetch_all_stocks",
                return_value=stocks,
            ):
                with patch(
                    "app.services.market_radar.treemap_builder._fetch_sector_stocks_batch",
                    return_value={},
                ):

                    tasks = [
                        build_treemap_data(level="sector", timeout=15.0)
                        for _ in range(100)
                    ]

                    start = time.perf_counter()
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    elapsed = time.perf_counter() - start

                    success_count = sum(
                        1
                        for r in results
                        if not isinstance(r, Exception) and "data" in r
                    )
                    assert (
                        success_count >= 95
                    ), f"Only {success_count}/100 requests succeeded"
                    assert elapsed < 5.0, f"100 requests took {elapsed}s"


class TestRateLimitUnderLoad:
    """Test rate limiting behavior under load."""

    def test_rate_limit_config_under_load(self):
        """Test rate limit configuration handles load correctly."""
        from app.config.rate_limit import get_limit_for_path, get_endpoint_category

        paths = [
            "/api/v1/market_radar/treemap",
            "/api/v1/market_radar/anomalies",
            "/api/v1/market_radar/health",
        ] * 100

        start = time.perf_counter()
        for path in paths:
            category = get_endpoint_category(path)
            limit = get_limit_for_path(path)
        elapsed = time.perf_counter() - start

        assert elapsed < 0.01, f"Path categorization took {elapsed}s"
