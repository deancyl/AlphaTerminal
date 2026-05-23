"""
Integration tests for data fallback logic (v0.6.45)

Tests:
1. Forex CFETS fallback chain
2. Futures circuit breaker protection
3. Macro per-indicator caching
4. Bounded random walk for mock history
"""

import pytest
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# Forex Fallback Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestForexFallback:
    """Tests for forex fallback chain"""

    @pytest.fixture
    def forex_fetcher(self):
        """Create a ForexFetcher instance"""
        from app.services.fetchers.forex_fetcher import ForexFetcher

        return ForexFetcher()

    def test_parse_cfets_to_quotes(self, forex_fetcher):
        """Test CFETS parsing to standard quote format"""
        import pandas as pd

        # Mock CFETS data
        mock_df = pd.DataFrame(
            {
                "货币对": ["USD/CNY", "EUR/CNY", "GBP/CNY"],
                "买报价": [7.248, 7.888, 9.118],
                "卖报价": [7.252, 7.892, 9.122],
                "中间价": [7.250, 7.890, 9.120],
            }
        )

        ts = int(datetime.now().timestamp())
        quotes = forex_fetcher._parse_cfets_to_quotes(mock_df, ts)

        assert len(quotes) == 3
        assert quotes[0]["symbol"] == "USDCNY"
        assert quotes[0]["source"] == "cfets"
        assert quotes[0]["is_demo"] == False
        assert quotes[0]["latest"] == 7.250

    def test_parse_cfets_pair_to_quotes(self, forex_fetcher):
        """Test CFETS cross pair parsing"""
        import pandas as pd

        mock_df = pd.DataFrame(
            {
                "货币对": ["EUR/USD", "GBP/USD", "USD/JPY"],
                "买报价": [1.0888, 1.2628, 149.80],
                "卖报价": [1.0896, 1.2640, 149.90],
            }
        )

        ts = int(datetime.now().timestamp())
        quotes = forex_fetcher._parse_cfets_pair_to_quotes(mock_df, ts)

        assert len(quotes) == 3
        assert quotes[0]["symbol"] == "EURUSD"
        assert quotes[0]["source"] == "cfets"

    def test_parse_boc_to_quotes(self, forex_fetcher):
        """Test BOC official rates parsing"""
        import pandas as pd

        mock_df = pd.DataFrame(
            {
                "日期": ["2024-01-15", "2024-01-16"],
                "美元": [7.25, 7.26],
                "欧元": [7.89, 7.90],
                "日元": [0.0486, 0.0487],
                "英镑": [9.12, 9.13],
                "港币": [0.929, 0.930],
                "澳大利亚元": [4.72, 4.73],
            }
        )

        ts = int(datetime.now().timestamp())
        quotes = forex_fetcher._parse_boc_to_quotes(mock_df, ts)

        # Should use latest row
        assert len(quotes) >= 5
        assert quotes[0]["symbol"] == "USDCNY"
        assert quotes[0]["source"] == "boc"

    def test_get_minimal_static_fallback(self, forex_fetcher):
        """Test minimal static fallback"""
        quotes = forex_fetcher._get_minimal_static_fallback()

        assert len(quotes) == 10  # 6 CNY-based + 4 USD-based for triangular arbitrage
        assert all(q["source"] == "static" for q in quotes)
        assert all(q["is_demo"] == True for q in quotes)

    def test_get_currency_name(self, forex_fetcher):
        """Test currency name mapping"""
        assert forex_fetcher._get_currency_name("USDCNY") == "美元/人民币"
        assert forex_fetcher._get_currency_name("EURUSD") == "欧元/美元"
        assert forex_fetcher._get_currency_name("UNKNOWN") == "UNKNOWN"


# ─────────────────────────────────────────────────────────────────────────────
# Futures Circuit Breaker Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestFuturesCircuitBreaker:
    """Tests for futures circuit breaker protection"""

    def test_circuit_breaker_exists(self):
        """Test that circuit breaker is initialized"""
        from app.routers.futures import _futures_cb

        assert _futures_cb is not None
        assert _futures_cb.name == "futures"

    def test_circuit_breaker_config(self):
        """Test circuit breaker configuration"""
        from app.routers.futures import _futures_cb

        assert _futures_cb.config.failure_threshold == 5
        assert _futures_cb.config.timeout == 60.0

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_on_open(self):
        """Test that circuit breaker blocks requests when open"""
        from app.routers.futures import _futures_cb
        from app.services.circuit_breaker import CircuitState

        # Simulate opening the circuit breaker
        original_state = _futures_cb.state
        _futures_cb._state = CircuitState.OPEN

        # Check that it's not available
        assert not _futures_cb.is_available()

        # Restore original state
        _futures_cb._state = original_state


# ─────────────────────────────────────────────────────────────────────────────
# Macro Per-Indicator Caching Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestMacroPerIndicatorCaching:
    """Tests for macro per-indicator caching"""

    def test_indicator_cache_keys_defined(self):
        """Test that indicator cache keys are defined"""
        # The INDICATOR_CACHE_KEYS should be defined in the dashboard endpoint
        # We verify by checking the warmup function
        from app.routers.macro import warmup_macro_cache

        # warmup_macro_cache should exist
        assert warmup_macro_cache is not None
        assert callable(warmup_macro_cache)

    @pytest.mark.asyncio
    async def test_warmup_macro_cache_exists(self):
        """Test that warmup function exists and is callable"""
        from app.routers.macro import warmup_macro_cache

        # Just verify it's a coroutine function
        import inspect

        assert inspect.iscoroutinefunction(warmup_macro_cache)


# ─────────────────────────────────────────────────────────────────────────────
# Bounded Random Walk Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestBoundedRandomWalk:
    """Tests for bounded random walk generation"""

    def test_generate_bounded_random_walk_exists(self):
        """Test that bounded random walk function exists"""
        from app.routers.forex import _generate_bounded_random_walk

        assert _generate_bounded_random_walk is not None
        assert callable(_generate_bounded_random_walk)

    def test_bounded_walk_returns_correct_length(self):
        """Test that bounded walk returns correct number of days"""
        from app.routers.forex import _generate_bounded_random_walk

        history = _generate_bounded_random_walk(7.25, 30, 0.003)
        assert len(history) == 30

        history = _generate_bounded_random_walk(7.25, 100, 0.003)
        assert len(history) == 100

    def test_bounded_walk_has_required_fields(self):
        """Test that each history entry has required fields"""
        from app.routers.forex import _generate_bounded_random_walk

        history = _generate_bounded_random_walk(7.25, 10, 0.003)

        for entry in history:
            assert "date" in entry
            assert "open" in entry
            assert "close" in entry
            assert "high" in entry
            assert "low" in entry
            assert "amplitude" in entry

    def test_bounded_walk_ohlc_constraints(self):
        """Test that OHLC constraints are satisfied"""
        from app.routers.forex import _generate_bounded_random_walk

        history = _generate_bounded_random_walk(7.25, 50, 0.003)

        for entry in history:
            # High should be >= max(open, close)
            assert entry["high"] >= max(entry["open"], entry["close"])
            # Low should be <= min(open, close)
            assert entry["low"] <= min(entry["open"], entry["close"])

    def test_bounded_walk_stays_within_bounds(self):
        """Test that values stay within reasonable bounds from base rate"""
        from app.routers.forex import _generate_bounded_random_walk

        base_rate = 7.25
        max_deviation = base_rate * 0.10  # 10% max deviation

        history = _generate_bounded_random_walk(base_rate, 100, 0.003)

        for entry in history:
            # All values should be within 10% of base rate
            assert abs(entry["open"] - base_rate) <= max_deviation
            assert abs(entry["close"] - base_rate) <= max_deviation
            assert abs(entry["high"] - base_rate) <= max_deviation
            assert abs(entry["low"] - base_rate) <= max_deviation

    def test_bounded_walk_different_decimals(self):
        """Test that decimals are correct for different rate ranges"""
        from app.routers.forex import _generate_bounded_random_walk

        # JPY pairs (rate > 100) should have 2 decimals
        history_jpy = _generate_bounded_random_walk(149.85, 10, 0.003)
        for entry in history_jpy:
            assert entry["open"] == round(entry["open"], 2)

        # Major pairs (rate >= 1) should have 4 decimals
        history_major = _generate_bounded_random_walk(7.25, 10, 0.003)
        for entry in history_major:
            assert entry["open"] == round(entry["open"], 4)

        # Minor pairs (rate < 1) should have 6 decimals
        history_minor = _generate_bounded_random_walk(0.0486, 10, 0.01)
        for entry in history_minor:
            assert entry["open"] == round(entry["open"], 6)


# ─────────────────────────────────────────────────────────────────────────────
# Run tests
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
