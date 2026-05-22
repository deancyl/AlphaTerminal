"""
Tests for forex_fetcher service.

Covers:
1. ForexFetcher methods (get_spot_quotes, get_history, get_cfets_spot, etc.)
2. Fallback chain (EastMoney -> CFETS -> BOC -> Static)
3. Circuit breaker integration
4. Data validation and error handling
5. Cache operations
"""

import pytest
import asyncio
import sys
import os
import pandas as pd
from typing import Any, cast
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from app.services.fetchers.forex_fetcher import (
    ForexFetcher,
    clean_value,
    get_circuit_breaker_status,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_akshare():
    """Mock akshare module."""
    mock_ak = MagicMock()
    return mock_ak


@pytest.fixture
def sample_spot_dataframe():
    """Sample DataFrame for forex_spot_em."""
    return pd.DataFrame(
        {
            "代码": ["USDCNY", "EURCNY", "GBPCNY"],
            "名称": ["美元/人民币", "欧元/人民币", "英镑/人民币"],
            "最新价": [7.2450, 7.8900, 9.1200],
            "涨跌额": [0.0050, 0.0100, 0.0200],
            "涨跌幅": [0.069, 0.127, 0.219],
            "今开": [7.2400, 7.8800, 9.1000],
            "最高": [7.2500, 7.9000, 9.1500],
            "最低": [7.2350, 7.8700, 9.0900],
            "昨收": [7.2400, 7.8800, 9.1000],
        }
    )


@pytest.fixture
def sample_history_dataframe():
    """Sample DataFrame for forex_hist_em."""
    return pd.DataFrame(
        {
            "日期": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "今开": [7.2400, 7.2450, 7.2500],
            "最新价": [7.2450, 7.2500, 7.2550],
            "最高": [7.2500, 7.2550, 7.2600],
            "最低": [7.2350, 7.2400, 7.2450],
            "振幅": [0.15, 0.15, 0.15],
        }
    )


@pytest.fixture
def sample_cfets_dataframe():
    """Sample DataFrame for fx_spot_quote."""
    return pd.DataFrame(
        {
            "货币对": ["USD/CNY", "EUR/CNY", "GBP/CNY"],
            "买报价": [7.2440, 7.8890, 9.1190],
            "卖报价": [7.2460, 7.8910, 9.1210],
            "中间价": [7.2450, 7.8900, 9.1200],
        }
    )


@pytest.fixture
def sample_boc_dataframe():
    """Sample DataFrame for currency_boc_safe."""
    return pd.DataFrame(
        {
            "日期": ["2024-01-01", "2024-01-02"],
            "美元": [7.2450, 7.2500],
            "欧元": [7.8900, 7.8950],
            "日元": [0.0486, 0.0487],
            "英镑": [9.1200, 9.1250],
            "港币": [0.9290, 0.9295],
            "澳大利亚元": [4.7200, 4.7250],
            "加拿大元": [5.3800, 5.3850],
            "瑞士法郎": [8.2500, 8.2550],
        }
    )


def _create_mock_akshare(
    spot_df=None,
    history_df=None,
    cfets_df=None,
    boc_df=None,
    spot_error=None,
    cfets_error=None,
    boc_error=None,
):
    """Helper to create a mock akshare object with configurable behavior."""
    mock_ak = MagicMock()

    if spot_error:
        mock_ak.forex_spot_em = Mock(side_effect=spot_error)
    elif spot_df is not None:
        mock_ak.forex_spot_em = Mock(return_value=spot_df)
    else:
        mock_ak.forex_spot_em = Mock(return_value=pd.DataFrame())

    if history_df is not None:
        mock_ak.forex_hist_em = Mock(return_value=history_df)
    else:
        mock_ak.forex_hist_em = Mock(return_value=pd.DataFrame())

    if cfets_error:
        mock_ak.fx_spot_quote = Mock(side_effect=cfets_error)
        mock_ak.fx_pair_quote = Mock(side_effect=cfets_error)
    elif cfets_df is not None:
        mock_ak.fx_spot_quote = Mock(return_value=cfets_df)
        mock_ak.fx_pair_quote = Mock(return_value=pd.DataFrame())
    else:
        mock_ak.fx_spot_quote = Mock(return_value=pd.DataFrame())
        mock_ak.fx_pair_quote = Mock(return_value=pd.DataFrame())

    if boc_error:
        mock_ak.currency_boc_safe = Mock(side_effect=boc_error)
    elif boc_df is not None:
        mock_ak.currency_boc_safe = Mock(return_value=boc_df)
    else:
        mock_ak.currency_boc_safe = Mock(return_value=pd.DataFrame())

    return mock_ak


def _set_fetcher_ak(fetcher: ForexFetcher, mock_ak: MagicMock) -> None:
    """Helper to set mocked akshare on fetcher with proper type handling."""
    # Use cast to tell type checker this is intentional for testing
    fetcher._ak = cast(Any, mock_ak)


# ============================================================================
# TestForexFetcherSpot - Tests for fetch_forex_spot function
# ============================================================================


class TestForexFetcherSpot:
    """Tests for fetch_forex_spot function."""

    @pytest.mark.asyncio
    async def test_fetch_spot_success(self, sample_spot_dataframe):
        """Test successful spot quotes fetch."""
        fetcher = ForexFetcher()
        mock_ak = _create_mock_akshare(spot_df=sample_spot_dataframe)
        _set_fetcher_ak(fetcher, mock_ak)

        result = await fetcher.get_spot_quotes()

        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_fetch_spot_returns_quotes_list(self, sample_spot_dataframe):
        """Test that spot quotes returns a list of quotes."""
        fetcher = ForexFetcher()
        mock_ak = _create_mock_akshare(spot_df=sample_spot_dataframe)
        _set_fetcher_ak(fetcher, mock_ak)

        result = await fetcher.get_spot_quotes()

        assert isinstance(result, list)
        for quote in result:
            assert isinstance(quote, dict)

    @pytest.mark.asyncio
    async def test_fetch_spot_quote_structure(self, sample_spot_dataframe):
        """Test that each quote has required fields."""
        fetcher = ForexFetcher()
        mock_ak = _create_mock_akshare(spot_df=sample_spot_dataframe)
        _set_fetcher_ak(fetcher, mock_ak)

        result = await fetcher.get_spot_quotes()

        required_fields = ["symbol", "name", "latest", "source", "timestamp"]
        for quote in result:
            for field in required_fields:
                assert field in quote, f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_fetch_spot_with_cny_pairs(self, sample_spot_dataframe):
        """Test that CNY-based pairs are included."""
        fetcher = ForexFetcher()
        mock_ak = _create_mock_akshare(spot_df=sample_spot_dataframe)
        _set_fetcher_ak(fetcher, mock_ak)

        result = await fetcher.get_spot_quotes()

        symbols = [q["symbol"] for q in result]
        assert "USDCNY" in symbols
        assert "EURCNY" in symbols
        assert "GBPCNY" in symbols

    @pytest.mark.asyncio
    async def test_fetch_spot_with_cross_pairs(self, sample_spot_dataframe):
        """Test that cross pairs can be processed."""
        cross_df = pd.concat(
            [
                sample_spot_dataframe,
                pd.DataFrame(
                    {
                        "代码": ["EURUSD", "GBPUSD"],
                        "名称": ["欧元/美元", "英镑/美元"],
                        "最新价": [1.0850, 1.2650],
                        "涨跌额": [0.0010, 0.0020],
                        "涨跌幅": [0.092, 0.158],
                        "今开": [1.0840, 1.2630],
                        "最高": [1.0860, 1.2660],
                        "最低": [1.0830, 1.2620],
                        "昨收": [1.0840, 1.2630],
                    }
                ),
            ],
            ignore_index=True,
        )

        fetcher = ForexFetcher()
        mock_ak = _create_mock_akshare(spot_df=cross_df)
        _set_fetcher_ak(fetcher, mock_ak)

        result = await fetcher.get_spot_quotes()

        symbols = [q["symbol"] for q in result]
        assert "EURUSD" in symbols
        assert "GBPUSD" in symbols


# ============================================================================
# TestForexFetcherHistory - Tests for fetch_forex_history function
# ============================================================================


class TestForexFetcherHistory:
    """Tests for fetch_forex_history function."""

    @pytest.mark.asyncio
    async def test_fetch_history_success(self, sample_history_dataframe):
        """Test successful history fetch."""
        fetcher = ForexFetcher()
        mock_ak = _create_mock_akshare(history_df=sample_history_dataframe)
        _set_fetcher_ak(fetcher, mock_ak)

        result = await fetcher.get_history("USDCNH")

        assert result is not None
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_fetch_history_returns_list(self, sample_history_dataframe):
        """Test that history returns a list of klines."""
        fetcher = ForexFetcher()
        mock_ak = _create_mock_akshare(history_df=sample_history_dataframe)
        _set_fetcher_ak(fetcher, mock_ak)

        result = await fetcher.get_history("USDCNH")

        assert isinstance(result, list)
        for kline in result:
            assert isinstance(kline, dict)

    @pytest.mark.asyncio
    async def test_fetch_history_with_symbol(self, sample_history_dataframe):
        """Test that history fetch uses the correct symbol."""
        fetcher = ForexFetcher()
        mock_ak = MagicMock()
        mock_ak.forex_hist_em = Mock(return_value=sample_history_dataframe)
        _set_fetcher_ak(fetcher, mock_ak)

        await fetcher.get_history("USDCNH")

        mock_ak.forex_hist_em.assert_called_once()
        call_kwargs = mock_ak.forex_hist_em.call_args[1]
        assert call_kwargs["symbol"] == "USDCNH"

    @pytest.mark.asyncio
    async def test_fetch_history_with_date_range(self, sample_history_dataframe):
        """Test history fetch with date range filtering."""
        fetcher = ForexFetcher()
        mock_ak = _create_mock_akshare(history_df=sample_history_dataframe)
        _set_fetcher_ak(fetcher, mock_ak)

        result = await fetcher.get_history(
            "USDCNH", start_date="2024-01-01", end_date="2024-01-02"
        )

        assert result is not None
        for kline in result:
            assert kline["date"] >= "2024-01-01"
            assert kline["date"] <= "2024-01-02"

    @pytest.mark.asyncio
    async def test_fetch_history_data_structure(self, sample_history_dataframe):
        """Test that each kline has required fields."""
        fetcher = ForexFetcher()
        mock_ak = _create_mock_akshare(history_df=sample_history_dataframe)
        _set_fetcher_ak(fetcher, mock_ak)

        result = await fetcher.get_history("USDCNH")

        required_fields = ["date", "open", "close", "high", "low"]
        for kline in result:
            for field in required_fields:
                assert field in kline, f"Missing field: {field}"


# ============================================================================
# TestForexFetcherFallback - Tests for fallback chain
# ============================================================================


class TestForexFetcherFallback:
    """Tests for fallback chain."""

    @pytest.mark.asyncio
    async def test_fallback_to_cfets_on_eastmoney_failure(self, sample_cfets_dataframe):
        """Test fallback to CFETS when EastMoney fails."""
        fetcher = ForexFetcher()
        mock_ak = MagicMock()
        mock_ak.forex_spot_em = Mock(side_effect=Exception("Network error"))
        mock_ak.fx_spot_quote = Mock(return_value=sample_cfets_dataframe)
        mock_ak.fx_pair_quote = Mock(return_value=pd.DataFrame())
        mock_ak.currency_boc_safe = Mock(return_value=pd.DataFrame())
        _set_fetcher_ak(fetcher, mock_ak)

        result = await fetcher.get_spot_quotes()

        assert result is not None
        assert len(result) > 0
        assert any(q.get("source") == "cfets" for q in result)

    @pytest.mark.asyncio
    async def test_fallback_to_boc_on_cfets_failure(self, sample_boc_dataframe):
        """Test fallback to BOC when CFETS fails."""
        fetcher = ForexFetcher()
        mock_ak = MagicMock()
        mock_ak.forex_spot_em = Mock(side_effect=Exception("Network error"))
        mock_ak.fx_spot_quote = Mock(side_effect=Exception("CFETS error"))
        mock_ak.fx_pair_quote = Mock(side_effect=Exception("CFETS pair error"))
        mock_ak.currency_boc_safe = Mock(return_value=sample_boc_dataframe)
        _set_fetcher_ak(fetcher, mock_ak)

        with patch(
            "app.services.fetchers.forex_fetcher._get_akshare", return_value=mock_ak
        ):
            result = await fetcher.get_spot_quotes()

        assert result is not None
        assert len(result) > 0
        assert any(q.get("source") == "boc" for q in result)

    @pytest.mark.asyncio
    async def test_fallback_to_static_on_all_failure(self):
        """Test fallback to static data when all sources fail."""
        fetcher = ForexFetcher()
        mock_ak = MagicMock()
        mock_ak.forex_spot_em = Mock(side_effect=Exception("Network error"))
        mock_ak.fx_spot_quote = Mock(side_effect=Exception("CFETS error"))
        mock_ak.fx_pair_quote = Mock(side_effect=Exception("CFETS pair error"))
        mock_ak.currency_boc_safe = Mock(side_effect=Exception("BOC error"))
        _set_fetcher_ak(fetcher, mock_ak)

        with patch(
            "app.services.fetchers.forex_fetcher._get_akshare", return_value=mock_ak
        ):
            result = await fetcher.get_spot_quotes()

        assert result is not None
        assert len(result) == 10
        assert all(q.get("source") == "static" for q in result)
        assert all(q.get("is_demo") is True for q in result)

    @pytest.mark.asyncio
    async def test_fallback_preserves_quote_structure(self):
        """Test that fallback data maintains quote structure."""
        fetcher = ForexFetcher()

        result = fetcher._get_minimal_static_fallback()

        required_fields = [
            "symbol",
            "name",
            "latest",
            "bid",
            "ask",
            "spread",
            "change",
            "change_pct",
            "open",
            "high",
            "low",
            "prev_close",
            "source",
            "is_demo",
            "timestamp",
        ]

        for quote in result:
            for field in required_fields:
                assert field in quote, f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_fallback_logs_warning(self, caplog):
        """Test that fallback logs warning messages."""
        fetcher = ForexFetcher()
        mock_ak = MagicMock()
        mock_ak.forex_spot_em = Mock(side_effect=Exception("Network error"))
        mock_ak.fx_spot_quote = Mock(side_effect=Exception("CFETS error"))
        mock_ak.fx_pair_quote = Mock(side_effect=Exception("CFETS pair error"))
        mock_ak.currency_boc_safe = Mock(side_effect=Exception("BOC error"))
        _set_fetcher_ak(fetcher, mock_ak)

        with caplog.at_level("WARNING"):
            await fetcher.get_spot_quotes()

        assert any(
            "失败" in record.message or "error" in record.message.lower()
            for record in caplog.records
        )


# ============================================================================
# TestForexFetcherCircuitBreaker - Tests for circuit breaker integration
# ============================================================================


class TestForexFetcherCircuitBreaker:
    """Tests for circuit breaker integration."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_on_failures(self):
        """Test that circuit breaker blocks requests after failures."""
        fetcher = ForexFetcher()

        for _ in range(5):
            fetcher.cb.record_failure()

        assert not fetcher.cb.is_available()

        result = await fetcher.get_spot_quotes()

        assert result is not None
        assert any(q.get("source") in ("cfets", "boc", "static") for q in result)

    @pytest.mark.asyncio
    async def test_circuit_breaker_allows_on_success(self, sample_spot_dataframe):
        """Test that circuit breaker allows requests after success."""
        fetcher = ForexFetcher()
        mock_ak = _create_mock_akshare(spot_df=sample_spot_dataframe)
        _set_fetcher_ak(fetcher, mock_ak)

        fetcher.cb.record_failure()
        fetcher.cb.record_failure()
        fetcher.cb.record_success()

        assert fetcher.cb.is_available()

        result = await fetcher.get_spot_quotes()

        assert result is not None
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_circuit_breaker_reset(self):
        """Test manual circuit breaker reset."""
        fetcher = ForexFetcher()

        for _ in range(5):
            fetcher.cb.record_failure()

        assert not fetcher.cb.is_available()

        result = await fetcher.reset_circuit_breaker()

        assert result["success"] is True
        assert result["state"] == "closed"
        assert fetcher.cb.is_available()


# ============================================================================
# TestForexFetcherDataValidation - Tests for data validation
# ============================================================================


class TestForexFetcherDataValidation:
    """Tests for data validation."""

    def test_quote_has_required_fields(self):
        """Test that quote has all required fields."""
        fetcher = ForexFetcher()
        quotes = fetcher._get_minimal_static_fallback()

        required_fields = ["symbol", "name", "latest", "bid", "ask", "timestamp"]

        for quote in quotes:
            for field in required_fields:
                assert field in quote

    def test_quote_price_is_numeric(self):
        """Test that quote prices are numeric."""
        fetcher = ForexFetcher()
        quotes = fetcher._get_minimal_static_fallback()

        for quote in quotes:
            assert isinstance(quote["latest"], (int, float))
            assert isinstance(quote["bid"], (int, float))
            assert isinstance(quote["ask"], (int, float))

    def test_quote_timestamp_is_valid(self):
        """Test that quote timestamp is valid."""
        fetcher = ForexFetcher()
        quotes = fetcher._get_minimal_static_fallback()

        for quote in quotes:
            ts = quote["timestamp"]
            assert isinstance(ts, int)
            assert ts > 1577836800

    @pytest.mark.asyncio
    async def test_empty_data_handling(self):
        """Test handling of empty data from API."""
        fetcher = ForexFetcher()
        mock_ak = MagicMock()
        mock_ak.forex_spot_em = Mock(return_value=pd.DataFrame())
        mock_ak.fx_spot_quote = Mock(return_value=pd.DataFrame())
        mock_ak.fx_pair_quote = Mock(return_value=pd.DataFrame())
        mock_ak.currency_boc_safe = Mock(return_value=pd.DataFrame())
        _set_fetcher_ak(fetcher, mock_ak)

        result = await fetcher.get_spot_quotes()

        assert result is not None
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_malformed_data_handling(self):
        """Test handling of malformed data."""
        fetcher = ForexFetcher()
        malformed_df = pd.DataFrame(
            {
                "wrong_column": [1, 2, 3],
            }
        )
        mock_ak = MagicMock()
        mock_ak.forex_spot_em = Mock(return_value=malformed_df)
        mock_ak.fx_spot_quote = Mock(return_value=pd.DataFrame())
        mock_ak.fx_pair_quote = Mock(return_value=pd.DataFrame())
        mock_ak.currency_boc_safe = Mock(return_value=pd.DataFrame())
        _set_fetcher_ak(fetcher, mock_ak)

        result = await fetcher.get_spot_quotes()

        assert result is not None


# ============================================================================
# TestForexFetcherErrorHandling - Tests for error handling
# ============================================================================


class TestForexFetcherErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_network_error_handling(self):
        """Test handling of network errors."""
        fetcher = ForexFetcher()
        mock_ak = MagicMock()
        mock_ak.forex_spot_em = Mock(side_effect=ConnectionError("Network error"))
        mock_ak.fx_spot_quote = Mock(side_effect=ConnectionError("Network error"))
        mock_ak.fx_pair_quote = Mock(side_effect=ConnectionError("Network error"))
        mock_ak.currency_boc_safe = Mock(side_effect=ConnectionError("Network error"))
        _set_fetcher_ak(fetcher, mock_ak)

        result = await fetcher.get_spot_quotes()

        assert result is not None
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test handling of timeout errors."""
        fetcher = ForexFetcher()
        mock_ak = MagicMock()
        mock_ak.forex_spot_em = Mock(side_effect=asyncio.TimeoutError())
        mock_ak.fx_spot_quote = Mock(side_effect=asyncio.TimeoutError())
        mock_ak.fx_pair_quote = Mock(side_effect=asyncio.TimeoutError())
        mock_ak.currency_boc_safe = Mock(side_effect=asyncio.TimeoutError())
        _set_fetcher_ak(fetcher, mock_ak)

        result = await fetcher.get_spot_quotes()

        assert result is not None

    @pytest.mark.asyncio
    async def test_rate_limit_handling(self):
        """Test handling of rate limit errors."""
        fetcher = ForexFetcher()
        mock_ak = MagicMock()
        mock_ak.forex_spot_em = Mock(side_effect=Exception("Rate limit exceeded"))
        mock_ak.fx_spot_quote = Mock(side_effect=Exception("Rate limit exceeded"))
        mock_ak.fx_pair_quote = Mock(side_effect=Exception("Rate limit exceeded"))
        mock_ak.currency_boc_safe = Mock(side_effect=Exception("Rate limit exceeded"))
        _set_fetcher_ak(fetcher, mock_ak)

        result = await fetcher.get_spot_quotes()

        assert result is not None

    @pytest.mark.asyncio
    async def test_invalid_symbol_handling(self):
        """Test handling of invalid symbol in history."""
        fetcher = ForexFetcher()
        mock_ak = MagicMock()
        mock_ak.forex_hist_em = Mock(side_effect=Exception("Invalid symbol"))
        _set_fetcher_ak(fetcher, mock_ak)

        result = await fetcher.get_history("INVALID")

        assert result == []


# ============================================================================
# TestForexFetcherCache - Tests for caching
# ============================================================================


class TestForexFetcherCache:
    """Tests for caching."""

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_data(self, sample_spot_dataframe):
        """Test that cache hit returns cached data."""
        fetcher = ForexFetcher()
        mock_ak = _create_mock_akshare(spot_df=sample_spot_dataframe)
        _set_fetcher_ak(fetcher, mock_ak)

        result1 = await fetcher.get_spot_quotes()
        result2 = await fetcher.get_spot_quotes()

        assert result1 == result2
        mock_ak.forex_spot_em.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_miss_fetches_new_data(self, sample_spot_dataframe):
        """Test that cache miss fetches new data."""
        fetcher = ForexFetcher()
        fetcher._cache = {}
        mock_ak = _create_mock_akshare(spot_df=sample_spot_dataframe)
        _set_fetcher_ak(fetcher, mock_ak)

        result = await fetcher.get_spot_quotes()

        assert result is not None
        mock_ak.forex_spot_em.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_expiry(self, sample_spot_dataframe):
        """Test that cache expires after TTL."""
        fetcher = ForexFetcher()
        mock_ak = _create_mock_akshare(spot_df=sample_spot_dataframe)
        _set_fetcher_ak(fetcher, mock_ak)

        await fetcher.get_spot_quotes()

        fetcher._cache_ttl["spot_quotes"] = datetime.now() - timedelta(seconds=1)

        await fetcher.get_spot_quotes()

        assert mock_ak.forex_spot_em.call_count == 2


# ============================================================================
# TestCleanValue - Tests for clean_value function
# ============================================================================


class TestCleanValue:
    """Tests for clean_value function."""

    def test_clean_none(self):
        """Test cleaning None value."""
        assert clean_value(None) is None

    def test_clean_nan(self):
        """Test cleaning NaN value."""
        import math

        assert clean_value(float("nan")) is None
        assert clean_value(math.nan) is None

    def test_clean_infinity(self):
        """Test cleaning infinity values."""
        assert clean_value(float("inf")) is None
        assert clean_value(float("-inf")) is None

    def test_clean_valid_number(self):
        """Test cleaning valid numbers."""
        assert clean_value(123) == 123.0
        assert clean_value(45.67) == 45.67
        assert clean_value("100") == 100.0

    def test_clean_invalid_string(self):
        """Test cleaning invalid string."""
        assert clean_value("not a number") is None

    def test_clean_pandas_na(self):
        """Test cleaning pandas NA values."""
        assert clean_value(pd.NA) is None
        assert clean_value(pd.NaT) is None


# ============================================================================
# TestCrossRateCalculation - Tests for cross rate calculation
# ============================================================================


class TestCrossRateCalculation:
    """Tests for cross rate calculation."""

    def test_same_currency(self):
        """Test cross rate for same currency."""
        fetcher = ForexFetcher()
        from decimal import Decimal

        result = fetcher.calculate_cross_rate("USD", "USD", {})
        assert result == Decimal("1.0")

    def test_direct_rate(self):
        """Test direct rate lookup."""
        fetcher = ForexFetcher()
        from decimal import Decimal

        rates = {"EUR/USD": Decimal("1.0850")}
        result = fetcher.calculate_cross_rate("EUR", "USD", rates)
        assert result == Decimal("1.0850")

    def test_inverse_rate(self):
        """Test inverse rate calculation."""
        fetcher = ForexFetcher()
        from decimal import Decimal

        rates = {"USD/EUR": Decimal("0.9217")}
        result = fetcher.calculate_cross_rate("EUR", "USD", rates)
        assert result is not None
        assert abs(float(result) - 1.0850) < 0.01

    def test_cross_via_usd(self):
        """Test cross rate calculation via USD."""
        fetcher = ForexFetcher()
        from decimal import Decimal

        rates = {
            "EUR/USD": Decimal("1.0850"),
            "GBP/USD": Decimal("1.2650"),
        }
        result = fetcher.calculate_cross_rate("EUR", "GBP", rates)
        assert result is not None
        assert abs(float(result) - 0.8577) < 0.01

    def test_no_rate_available(self):
        """Test when no rate is available."""
        fetcher = ForexFetcher()

        result = fetcher.calculate_cross_rate("XXX", "YYY", {})
        assert result is None


# ============================================================================
# TestGetCircuitBreakerStatus - Tests for circuit breaker status function
# ============================================================================


class TestGetCircuitBreakerStatus:
    """Tests for get_circuit_breaker_status function."""

    def test_returns_dict(self):
        """Test that function returns a dictionary."""
        result = get_circuit_breaker_status()
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        """Test that result has required keys."""
        result = get_circuit_breaker_status()

        required_keys = ["is_open", "failure_count", "is_available", "state"]
        for key in required_keys:
            assert key in result

    def test_is_available_matches_is_open(self):
        """Test that is_available is opposite of is_open."""
        result = get_circuit_breaker_status()
        assert result["is_available"] == (not result["is_open"])


# ============================================================================
# TestCFETSParsing - Tests for CFETS data parsing
# ============================================================================


class TestCFETSParsing:
    """Tests for CFETS data parsing methods."""

    def test_parse_cfets_to_quotes(self, sample_cfets_dataframe):
        """Test parsing CFETS data to quotes."""
        fetcher = ForexFetcher()
        ts = int(datetime.now().timestamp())

        result = fetcher._parse_cfets_to_quotes(sample_cfets_dataframe, ts)

        assert len(result) == 3
        assert result[0]["symbol"] == "USDCNY"
        assert result[0]["source"] == "cfets"

    def test_parse_cfets_pair_to_quotes(self):
        """Test parsing CFETS cross pairs to quotes."""
        fetcher = ForexFetcher()
        ts = int(datetime.now().timestamp())

        df = pd.DataFrame(
            {
                "货币对": ["EUR/USD", "GBP/USD"],
                "买报价": [1.0845, 1.2645],
                "卖报价": [1.0855, 1.2655],
            }
        )

        result = fetcher._parse_cfets_pair_to_quotes(df, ts)

        assert len(result) == 2
        symbols = [q["symbol"] for q in result]
        assert "EURUSD" in symbols
        assert "GBPUSD" in symbols

    def test_parse_boc_to_quotes(self, sample_boc_dataframe):
        """Test parsing BOC data to quotes."""
        fetcher = ForexFetcher()
        ts = int(datetime.now().timestamp())

        result = fetcher._parse_boc_to_quotes(sample_boc_dataframe, ts)

        assert len(result) > 0
        symbols = [q["symbol"] for q in result]
        assert "USDCNY" in symbols
        assert "EURCNY" in symbols
        assert all(q["source"] == "boc" for q in result)


# ============================================================================
# TestGetCurrencyName - Tests for currency name lookup
# ============================================================================


class TestGetCurrencyName:
    """Tests for _get_currency_name method."""

    def test_known_currency(self):
        """Test known currency pair."""
        fetcher = ForexFetcher()

        assert fetcher._get_currency_name("USDCNY") == "美元/人民币"
        assert fetcher._get_currency_name("EURUSD") == "欧元/美元"

    def test_unknown_currency(self):
        """Test unknown currency pair returns symbol."""
        fetcher = ForexFetcher()

        assert fetcher._get_currency_name("XXXYYY") == "XXXYYY"


# ============================================================================
# TestIsHealthy - Tests for health check
# ============================================================================


class TestIsHealthy:
    """Tests for is_healthy method."""

    def test_healthy_when_circuit_closed(self):
        """Test is_healthy returns True when circuit breaker is closed."""
        fetcher = ForexFetcher()
        fetcher.cb.record_success()

        assert fetcher.is_healthy() is True

    def test_unhealthy_when_circuit_open(self):
        """Test is_healthy returns False when circuit breaker is open."""
        fetcher = ForexFetcher()

        for _ in range(5):
            fetcher.cb.record_failure()

        assert fetcher.is_healthy() is False


# ============================================================================
# TestPing - Tests for connectivity check
# ============================================================================


class TestPing:
    """Tests for ping method."""

    @pytest.mark.asyncio
    async def test_ping_success(self, sample_spot_dataframe):
        """Test ping returns True when data available."""
        fetcher = ForexFetcher()
        mock_ak = _create_mock_akshare(spot_df=sample_spot_dataframe)
        _set_fetcher_ak(fetcher, mock_ak)

        result = await fetcher.ping()

        assert result is True

    @pytest.mark.asyncio
    async def test_ping_returns_true_with_fallback(self):
        """Test ping returns True even with fallback data (service is available)."""
        fetcher = ForexFetcher()
        mock_ak = MagicMock()
        mock_ak.forex_spot_em = Mock(side_effect=Exception("Error"))
        mock_ak.fx_spot_quote = Mock(side_effect=Exception("Error"))
        mock_ak.fx_pair_quote = Mock(side_effect=Exception("Error"))
        mock_ak.currency_boc_safe = Mock(side_effect=Exception("Error"))
        _set_fetcher_ak(fetcher, mock_ak)

        with patch(
            "app.services.fetchers.forex_fetcher._get_akshare", return_value=mock_ak
        ):
            result = await fetcher.ping()

        # Ping returns True because fallback data is available
        assert result is True
