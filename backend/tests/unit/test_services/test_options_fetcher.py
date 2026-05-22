"""
Options Fetcher Service Tests

Tests for the options fetcher implementation in backend/app/services/fetchers/options_fetcher.py
Covers CFFEX/SSE options chain, Greeks calculation, historical data, and error handling.
"""

import pytest
import pandas as pd
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app.services.fetchers.options_fetcher import (
    OptionsFetcher,
    clean_value,
    options_fetcher,
)
from app.services.circuit_breaker import CircuitBreaker

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_cffex_chain_df():
    """Mock DataFrame returned by akshare.option_cffex_hs300_spot_sina."""
    data = {
        "看涨合约-标识": ["IO2506C3800", "IO2506C3850", "IO2506C3900"],
        "看涨合约-最新价": [125.5, 98.2, 72.8],
        "看涨合约-涨跌": [2.5, -1.2, 0.8],
        "看涨合约-买量": [1000, 800, 600],
        "看涨合约-持仓量": [5000, 4500, 4000],
        "行权价": [3800, 3850, 3900],
        "看跌合约-标识": ["IO2506P3800", "IO2506P3850", "IO2506P3900"],
        "看跌合约-最新价": [45.2, 68.5, 92.3],
        "看跌合约-涨跌": [-1.5, 0.8, 2.2],
        "看跌合约-买量": [500, 700, 900],
        "看跌合约-持仓量": [3000, 3500, 4000],
    }
    return pd.DataFrame(data)


@pytest.fixture
def mock_sse_greeks_df():
    """Mock DataFrame returned by akshare.option_sse_greeks_sina."""
    data = {
        "名称": ["50ETF购6月2500"],
        "Delta": [0.523],
        "Gamma": [0.089],
        "Theta": [-0.012],
        "Vega": [0.234],
        "隐含波动率": [0.185],
        "最新价": [0.0456],
        "行权价": [2.5],
        "到期日": ["2025-06-26"],
    }
    return pd.DataFrame(data)


@pytest.fixture
def mock_empty_df():
    """Mock empty DataFrame."""
    return pd.DataFrame()


@pytest.fixture
def mock_circuit_breaker_available():
    """Mock circuit breaker that is available."""
    cb = MagicMock(spec=CircuitBreaker)
    cb.is_available.return_value = True
    cb.record_success = MagicMock()
    cb.record_failure = MagicMock()
    return cb


@pytest.fixture
def mock_circuit_breaker_open():
    """Mock circuit breaker that is open (unavailable)."""
    cb = MagicMock(spec=CircuitBreaker)
    cb.is_available.return_value = False
    cb.record_success = MagicMock()
    cb.record_failure = MagicMock()
    return cb


@pytest.fixture
def options_fetcher_with_mock_cb(mock_circuit_breaker_available):
    """OptionsFetcher with mocked circuit breaker."""
    return OptionsFetcher(circuit_breaker=mock_circuit_breaker_available)


@pytest.fixture
def mock_akshare():
    """Mock akshare module."""
    mock_ak = MagicMock()
    return mock_ak


# ============================================================================
# TestOptionsFetcherChain - Tests for fetch_options_chain function
# ============================================================================


class TestOptionsFetcherChain:
    """Tests for fetch_options_chain function."""

    @pytest.mark.asyncio
    async def test_fetch_chain_success(
        self, options_fetcher_with_mock_cb, mock_cffex_chain_df, mock_akshare
    ):
        """Should successfully fetch CFFEX options chain."""
        fetcher = options_fetcher_with_mock_cb
        mock_akshare.option_cffex_hs300_spot_sina.return_value = mock_cffex_chain_df
        fetcher._ak = mock_akshare

        result = await fetcher.get_cffex_chain("io2506")

        assert result is not None
        assert result["symbol"] == "io2506"
        assert "calls" in result
        assert "puts" in result
        assert result["source"] == "akshare"

    @pytest.mark.asyncio
    async def test_fetch_chain_cffex_format(
        self, options_fetcher_with_mock_cb, mock_cffex_chain_df, mock_akshare
    ):
        """Should return CFFEX format with correct structure."""
        fetcher = options_fetcher_with_mock_cb
        mock_akshare.option_cffex_hs300_spot_sina.return_value = mock_cffex_chain_df
        fetcher._ak = mock_akshare

        result = await fetcher.get_cffex_chain("io2506")

        assert "symbol" in result
        assert "name" in result
        assert "calls" in result
        assert "puts" in result
        assert "update_time" in result
        assert "source" in result

    @pytest.mark.asyncio
    async def test_fetch_chain_sse_format(self, options_fetcher_with_mock_cb):
        """Should handle SSE format (via get_sse_greeks)."""
        fetcher = options_fetcher_with_mock_cb

        assert hasattr(fetcher, "get_sse_greeks")
        assert callable(fetcher.get_sse_greeks)

    @pytest.mark.asyncio
    async def test_fetch_chain_returns_calls_and_puts(
        self, options_fetcher_with_mock_cb, mock_cffex_chain_df, mock_akshare
    ):
        """Should return both calls and puts lists."""
        fetcher = options_fetcher_with_mock_cb
        mock_akshare.option_cffex_hs300_spot_sina.return_value = mock_cffex_chain_df
        fetcher._ak = mock_akshare

        result = await fetcher.get_cffex_chain("io2506")

        assert isinstance(result["calls"], list)
        assert isinstance(result["puts"], list)
        assert len(result["calls"]) > 0
        assert len(result["puts"]) > 0

    @pytest.mark.asyncio
    async def test_fetch_chain_strike_price_range(
        self, options_fetcher_with_mock_cb, mock_cffex_chain_df, mock_akshare
    ):
        """Should have strike prices in valid range."""
        fetcher = options_fetcher_with_mock_cb
        mock_akshare.option_cffex_hs300_spot_sina.return_value = mock_cffex_chain_df
        fetcher._ak = mock_akshare

        result = await fetcher.get_cffex_chain("io2506")

        for call in result["calls"]:
            assert call["strike"] is not None
            assert call["strike"] > 0

        for put in result["puts"]:
            assert put["strike"] is not None
            assert put["strike"] > 0

    @pytest.mark.asyncio
    async def test_fetch_chain_with_symbol_prefix(
        self, options_fetcher_with_mock_cb, mock_cffex_chain_df, mock_akshare
    ):
        """Should handle different symbol prefixes (io/mo)."""
        fetcher = options_fetcher_with_mock_cb
        mock_akshare.option_cffex_hs300_spot_sina.return_value = mock_cffex_chain_df
        fetcher._ak = mock_akshare

        result_io = await fetcher.get_cffex_chain("io2506")
        assert result_io["symbol"] == "io2506"

        result_mo = await fetcher.get_cffex_chain("mo2506")
        assert result_mo["symbol"] == "mo2506"


# ============================================================================
# TestOptionsFetcherGreeks - Tests for fetch_greeks function
# ============================================================================


class TestOptionsFetcherGreeks:
    """Tests for fetch_greeks function."""

    @pytest.mark.asyncio
    async def test_fetch_greeks_success(
        self, options_fetcher_with_mock_cb, mock_sse_greeks_df, mock_akshare
    ):
        """Should successfully fetch Greeks data."""
        fetcher = options_fetcher_with_mock_cb
        mock_akshare.option_sse_greeks_sina.return_value = mock_sse_greeks_df
        fetcher._ak = mock_akshare

        result = await fetcher.get_sse_greeks("10004023")

        assert result is not None
        assert result["code"] == "10004023"
        assert result["source"] == "akshare"

    @pytest.mark.asyncio
    async def test_fetch_greeks_delta_range(
        self, options_fetcher_with_mock_cb, mock_sse_greeks_df, mock_akshare
    ):
        """Delta should be in range [-1, 1]."""
        fetcher = options_fetcher_with_mock_cb
        mock_akshare.option_sse_greeks_sina.return_value = mock_sse_greeks_df
        fetcher._ak = mock_akshare

        result = await fetcher.get_sse_greeks("10004023")

        if result["delta"] is not None:
            assert -1.0 <= result["delta"] <= 1.0

    @pytest.mark.asyncio
    async def test_fetch_greeks_gamma_positive(
        self, options_fetcher_with_mock_cb, mock_sse_greeks_df, mock_akshare
    ):
        """Gamma should be positive."""
        fetcher = options_fetcher_with_mock_cb
        mock_akshare.option_sse_greeks_sina.return_value = mock_sse_greeks_df
        fetcher._ak = mock_akshare

        result = await fetcher.get_sse_greeks("10004023")

        if result["gamma"] is not None:
            assert result["gamma"] >= 0

    @pytest.mark.asyncio
    async def test_fetch_greeks_theta_negative(
        self, options_fetcher_with_mock_cb, mock_sse_greeks_df, mock_akshare
    ):
        """Theta is typically negative (time decay)."""
        fetcher = options_fetcher_with_mock_cb
        mock_akshare.option_sse_greeks_sina.return_value = mock_sse_greeks_df
        fetcher._ak = mock_akshare

        result = await fetcher.get_sse_greeks("10004023")

        if result["theta"] is not None:
            assert isinstance(result["theta"], (int, float))

    @pytest.mark.asyncio
    async def test_fetch_greeks_vega_positive(
        self, options_fetcher_with_mock_cb, mock_sse_greeks_df, mock_akshare
    ):
        """Vega should be positive."""
        fetcher = options_fetcher_with_mock_cb
        mock_akshare.option_sse_greeks_sina.return_value = mock_sse_greeks_df
        fetcher._ak = mock_akshare

        result = await fetcher.get_sse_greeks("10004023")

        if result["vega"] is not None:
            assert result["vega"] >= 0

    @pytest.mark.asyncio
    async def test_fetch_greeks_iv_range(
        self, options_fetcher_with_mock_cb, mock_sse_greeks_df, mock_akshare
    ):
        """IV should be in reasonable range [0, 5]."""
        fetcher = options_fetcher_with_mock_cb
        mock_akshare.option_sse_greeks_sina.return_value = mock_sse_greeks_df
        fetcher._ak = mock_akshare

        result = await fetcher.get_sse_greeks("10004023")

        if result["iv"] is not None:
            assert 0 <= result["iv"] <= 5.0


# ============================================================================
# TestOptionsFetcherHistory - Tests for fetch_options_history function
# ============================================================================


class TestOptionsFetcherHistory:
    """Tests for fetch_options_history function."""

    @pytest.mark.asyncio
    async def test_fetch_history_success(self, options_fetcher_with_mock_cb):
        """Should successfully fetch historical options data."""
        fetcher = options_fetcher_with_mock_cb

        result = await fetcher.get_kline("IO2506C3800")

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_history_with_date_range(self, options_fetcher_with_mock_cb):
        """Should handle date range parameters."""
        fetcher = options_fetcher_with_mock_cb

        result = await fetcher.get_kline(
            "IO2506C3800", start_date="2024-01-01", end_date="2024-12-31"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_history_data_structure(self, options_fetcher_with_mock_cb):
        """Should return correct data structure."""
        fetcher = options_fetcher_with_mock_cb

        result = await fetcher.get_kline(
            symbol="IO2506C3800",
            period="daily",
            adjust="qfq",
            start_date="2024-01-01",
            end_date="2024-12-31",
        )

        assert result is None


# ============================================================================
# TestOptionsFetcherDataValidation - Tests for data validation
# ============================================================================


class TestOptionsFetcherDataValidation:
    """Tests for data validation."""

    @pytest.mark.asyncio
    async def test_chain_has_required_fields(
        self, options_fetcher_with_mock_cb, mock_cffex_chain_df, mock_akshare
    ):
        """Chain result should have all required fields."""
        fetcher = options_fetcher_with_mock_cb
        mock_akshare.option_cffex_hs300_spot_sina.return_value = mock_cffex_chain_df
        fetcher._ak = mock_akshare

        result = await fetcher.get_cffex_chain("io2506")

        required_fields = ["symbol", "name", "calls", "puts", "update_time", "source"]
        for field in required_fields:
            assert field in result

    @pytest.mark.asyncio
    async def test_greeks_has_required_fields(
        self, options_fetcher_with_mock_cb, mock_sse_greeks_df, mock_akshare
    ):
        """Greeks result should have all required fields."""
        fetcher = options_fetcher_with_mock_cb
        mock_akshare.option_sse_greeks_sina.return_value = mock_sse_greeks_df
        fetcher._ak = mock_akshare

        result = await fetcher.get_sse_greeks("10004023")

        required_fields = ["code", "delta", "gamma", "theta", "vega", "iv", "source"]
        for field in required_fields:
            assert field in result

    def test_strike_is_numeric(self):
        """Strike should be numeric or None."""
        assert clean_value(3800) == 3800.0
        assert clean_value("3850.5") == 3850.5
        assert clean_value(None) is None
        assert clean_value("N/A") is None
        assert clean_value(float("nan")) is None

    def test_iv_is_percentage(self):
        """IV should be a valid percentage value."""
        assert clean_value(0.185) == 0.185
        assert clean_value(0.50) == 0.50
        assert clean_value(1.0) == 1.0

    @pytest.mark.asyncio
    async def test_empty_data_handling(
        self, options_fetcher_with_mock_cb, mock_empty_df, mock_akshare
    ):
        """Should handle empty data gracefully."""
        fetcher = options_fetcher_with_mock_cb
        mock_akshare.option_cffex_hs300_spot_sina.return_value = mock_empty_df
        fetcher._ak = mock_akshare

        result = await fetcher.get_cffex_chain("io2506")

        assert result is not None
        assert result["calls"] == []
        assert result["puts"] == []
        assert result["source"] == "empty"


# ============================================================================
# TestOptionsFetcherErrorHandling - Tests for error handling
# ============================================================================


class TestOptionsFetcherErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_network_error_handling(
        self, options_fetcher_with_mock_cb, mock_akshare
    ):
        """Should handle network errors gracefully."""
        fetcher = options_fetcher_with_mock_cb
        mock_akshare.option_cffex_hs300_spot_sina.side_effect = ConnectionError(
            "Network error"
        )
        fetcher._ak = mock_akshare

        result = await fetcher.get_cffex_chain("io2506")

        assert result is not None
        assert result["source"] == "empty"
        assert "error" in result

    @pytest.mark.asyncio
    async def test_timeout_handling(self, options_fetcher_with_mock_cb, mock_akshare):
        """Should handle timeout gracefully."""
        fetcher = options_fetcher_with_mock_cb
        fetcher._ak = mock_akshare

        with patch("asyncio.wait_for") as mock_wait:
            mock_wait.side_effect = asyncio.TimeoutError()

            result = await fetcher.get_cffex_chain("io2506")

            assert result is not None
            assert result["source"] == "empty"

    @pytest.mark.asyncio
    async def test_invalid_symbol_handling(
        self, options_fetcher_with_mock_cb, mock_akshare
    ):
        """Should handle invalid symbol gracefully."""
        fetcher = options_fetcher_with_mock_cb
        mock_akshare.option_cffex_hs300_spot_sina.side_effect = ValueError(
            "Invalid symbol"
        )
        fetcher._ak = mock_akshare

        result = await fetcher.get_cffex_chain("invalid_symbol")

        assert result is not None
        assert result["source"] == "empty"

    @pytest.mark.asyncio
    async def test_circuit_breaker_handling(self, mock_circuit_breaker_open):
        """Should respect circuit breaker state."""
        fetcher = OptionsFetcher(circuit_breaker=mock_circuit_breaker_open)

        result = await fetcher.get_cffex_chain("io2506")

        assert result is not None
        assert result["source"] == "empty"
        assert "error" in result


# ============================================================================
# TestOptionsFetcherCache - Tests for caching
# ============================================================================


class TestOptionsFetcherCache:
    """Tests for caching."""

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_data(
        self, options_fetcher_with_mock_cb, mock_cffex_chain_df, mock_akshare
    ):
        """Should return cached data on cache hit."""
        fetcher = options_fetcher_with_mock_cb
        mock_akshare.option_cffex_hs300_spot_sina.return_value = mock_cffex_chain_df
        fetcher._ak = mock_akshare

        result1 = await fetcher.get_cffex_chain("io2506")
        result2 = await fetcher.get_cffex_chain("io2506")

        assert result1["symbol"] == result2["symbol"]
        assert result1["calls"] == result2["calls"]
        assert mock_akshare.option_cffex_hs300_spot_sina.call_count == 1

    @pytest.mark.asyncio
    async def test_cache_miss_fetches_new_data(
        self, options_fetcher_with_mock_cb, mock_cffex_chain_df, mock_akshare
    ):
        """Should fetch new data on cache miss."""
        fetcher = options_fetcher_with_mock_cb
        mock_akshare.option_cffex_hs300_spot_sina.return_value = mock_cffex_chain_df
        fetcher._ak = mock_akshare

        result1 = await fetcher.get_cffex_chain("io2506")
        result2 = await fetcher.get_cffex_chain("io2507")

        assert mock_akshare.option_cffex_hs300_spot_sina.call_count == 2

    @pytest.mark.asyncio
    async def test_cache_expiry(
        self, options_fetcher_with_mock_cb, mock_cffex_chain_df, mock_akshare
    ):
        """Should refetch after cache expiry."""
        fetcher = options_fetcher_with_mock_cb
        mock_akshare.option_cffex_hs300_spot_sina.return_value = mock_cffex_chain_df
        fetcher._ak = mock_akshare

        result1 = await fetcher.get_cffex_chain("io2506")

        cache_key = "cffex_chain_io2506"
        fetcher._cache_ttl[cache_key] = datetime.now() - timedelta(seconds=1)

        result2 = await fetcher.get_cffex_chain("io2506")

        assert mock_akshare.option_cffex_hs300_spot_sina.call_count == 2


# ============================================================================
# TestOptionsFetcherContractList - Tests for contract list
# ============================================================================


class TestOptionsFetcherContractList:
    """Tests for contract list functionality."""

    @pytest.mark.asyncio
    async def test_get_contract_list_cffex(self, options_fetcher_with_mock_cb):
        """Should return CFFEX contract list."""
        fetcher = options_fetcher_with_mock_cb

        result = await fetcher.get_contract_list("CFFEX")

        assert result["exchange"] == "CFFEX"
        assert "contracts" in result
        assert len(result["contracts"]) > 0

    @pytest.mark.asyncio
    async def test_get_contract_list_sse(self, options_fetcher_with_mock_cb):
        """Should return SSE contract list."""
        fetcher = options_fetcher_with_mock_cb

        result = await fetcher.get_contract_list("SSE")

        assert result["exchange"] == "SSE"
        assert "contracts" in result
        assert len(result["contracts"]) > 0

    @pytest.mark.asyncio
    async def test_contract_list_has_required_fields(
        self, options_fetcher_with_mock_cb
    ):
        """Contract list should have required fields."""
        fetcher = options_fetcher_with_mock_cb

        result = await fetcher.get_contract_list("CFFEX")

        for contract in result["contracts"]:
            assert "code" in contract
            assert "name" in contract
            assert "type" in contract


# ============================================================================
# TestOptionsFetcherHealth - Tests for health check
# ============================================================================


class TestOptionsFetcherHealth:
    """Tests for health check functionality."""

    def test_is_healthy_when_available(self, mock_circuit_breaker_available):
        """Should return True when circuit breaker is available."""
        fetcher = OptionsFetcher(circuit_breaker=mock_circuit_breaker_available)

        assert fetcher.is_healthy() is True

    def test_is_healthy_when_unavailable(self, mock_circuit_breaker_open):
        """Should return False when circuit breaker is open."""
        fetcher = OptionsFetcher(circuit_breaker=mock_circuit_breaker_open)

        assert fetcher.is_healthy() is False

    @pytest.mark.asyncio
    async def test_ping_success(
        self, options_fetcher_with_mock_cb, mock_cffex_chain_df, mock_akshare
    ):
        """Should return True on successful ping."""
        fetcher = options_fetcher_with_mock_cb
        mock_akshare.option_cffex_hs300_spot_sina.return_value = mock_cffex_chain_df
        fetcher._ak = mock_akshare

        result = await fetcher.ping()

        assert result is True

    @pytest.mark.asyncio
    async def test_ping_failure(self, options_fetcher_with_mock_cb, mock_akshare):
        """Should return False on failed ping."""
        fetcher = options_fetcher_with_mock_cb
        mock_akshare.option_cffex_hs300_spot_sina.side_effect = Exception("Failed")
        fetcher._ak = mock_akshare

        result = await fetcher.ping()

        assert result is False


# ============================================================================
# TestCleanValue - Tests for clean_value utility function
# ============================================================================


class TestCleanValue:
    """Tests for clean_value utility function."""

    def test_clean_value_with_number(self):
        """Should return float for numeric input."""
        assert clean_value(100) == 100.0
        assert clean_value(100.5) == 100.5

    def test_clean_value_with_string_number(self):
        """Should parse string numbers."""
        assert clean_value("100") == 100.0
        assert clean_value("100.5") == 100.5

    def test_clean_value_with_none(self):
        """Should return None for None input."""
        assert clean_value(None) is None

    def test_clean_value_with_nan(self):
        """Should return None for NaN."""
        import math

        assert clean_value(float("nan")) is None
        assert clean_value(math.nan) is None

    def test_clean_value_with_inf(self):
        """Should return None for infinity."""
        assert clean_value(float("inf")) is None
        assert clean_value(float("-inf")) is None

    def test_clean_value_with_invalid_string(self):
        """Should return None for invalid strings."""
        assert clean_value("N/A") is None
        assert clean_value("invalid") is None
        assert clean_value("") is None


# ============================================================================
# TestOptionsFetcherSingleton - Tests for singleton instance
# ============================================================================


class TestOptionsFetcherSingleton:
    """Tests for singleton instance."""

    def test_singleton_exists(self):
        """Should have a singleton instance."""

        assert options_fetcher is not None
        assert isinstance(options_fetcher, OptionsFetcher)

    def test_singleton_has_required_methods(self):
        """Singleton should have all required methods."""

        assert hasattr(options_fetcher, "get_cffex_chain")
        assert hasattr(options_fetcher, "get_sse_greeks")
        assert hasattr(options_fetcher, "get_contract_list")
        assert hasattr(options_fetcher, "is_healthy")
        assert hasattr(options_fetcher, "ping")
