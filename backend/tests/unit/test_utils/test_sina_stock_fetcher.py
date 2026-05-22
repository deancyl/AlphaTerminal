"""
Unit tests for Sina stock fetcher utility.
"""

import pytest
from unittest.mock import patch, MagicMock
import json

from app.utils.sina_stock_fetcher import (
    fetch_all_stocks_sina,
    _get_proxies,
    _SINA_STOCK_CB,
)
from app.services.circuit_breaker import CircuitState


class TestGetProxies:
    """Tests for _get_proxies function."""

    def test_no_proxy_settings(self):
        """Test when no proxy is configured."""
        with patch('app.config.settings.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(HTTP_PROXY=None, http_proxy=None)
            result = _get_proxies()
            assert result is None

    def test_with_http_proxy(self):
        """Test when HTTP_PROXY is configured."""
        with patch('app.config.settings.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                HTTP_PROXY="http://192.168.1.50:7897",
                http_proxy=None
            )
            result = _get_proxies()
            assert result == {
                "http": "http://192.168.1.50:7897",
                "https": "http://192.168.1.50:7897"
            }

    def test_with_lowercase_proxy(self):
        """Test when http_proxy (lowercase) is configured."""
        with patch('app.config.settings.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                HTTP_PROXY=None,
                http_proxy="http://proxy.example.com:8080"
            )
            result = _get_proxies()
            assert result == {
                "http": "http://proxy.example.com:8080",
                "https": "http://proxy.example.com:8080"
            }


class TestFetchAllStocksSina:
    """Tests for fetch_all_stocks_sina function."""

    def test_fetch_all_stocks_success(self):
        """Test fetching all stocks successfully."""
        mock_sh_stocks = [
            {
                "symbol": "sh600519",
                "code": "600519",
                "name": "贵州茅台",
                "trade": "1299.18",
                "changepercent": "-0.902",
                "per": "19.786",
                "pb": "6.006",
                "mktcap": "163000000",
                "nmc": "163000000",
                "volume": "1588706",
                "amount": "2067373353",
                "turnoverratio": "0.12687",
                "high": "1311.91",
                "low": "1296.6",
                "settlement": "1311"
            }
        ]
        mock_sz_stocks = [
            {
                "symbol": "sz000001",
                "code": "000001",
                "name": "平安银行",
                "trade": "10.7",
                "changepercent": "0",
                "per": "5.169",
                "pb": "0.448",
                "mktcap": "2076433",
                "nmc": "2076433",
                "volume": "25917101",
                "amount": "276564267",
                "turnoverratio": "0.13355",
                "high": "10.71",
                "low": "10.65",
                "settlement": "10.7"
            }
        ]

        with patch('app.utils.sina_stock_fetcher.curl_requests') as mock_requests:
            call_count = [0]
            def get_side_effect(*args, **kwargs):
                call_count[0] += 1
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                url = args[0] if args else ""
                if "node=sh_a" in url:
                    if "page=1" in url:
                        mock_resp.text = json.dumps(mock_sh_stocks)
                    else:
                        mock_resp.text = "[]"
                elif "node=sz_a" in url:
                    if "page=1" in url:
                        mock_resp.text = json.dumps(mock_sz_stocks)
                    else:
                        mock_resp.text = "[]"
                else:
                    mock_resp.text = "[]"
                return mock_resp

            mock_requests.get.side_effect = get_side_effect

            _SINA_STOCK_CB._state = CircuitState.CLOSED
            _SINA_STOCK_CB._stats.consecutive_failures = 0

            result = fetch_all_stocks_sina(max_pages=2, delay=0)

            assert len(result) == 2
            assert result[0]["symbol"] == "sh600519"
            assert result[1]["symbol"] == "sz000001"

    def test_fetch_all_stocks_empty_response(self):
        """Test handling empty response from API."""
        with patch('app.utils.sina_stock_fetcher.curl_requests') as mock_requests:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "[]"
            mock_requests.get.return_value = mock_response

            _SINA_STOCK_CB._state = CircuitState.CLOSED
            _SINA_STOCK_CB._stats.consecutive_failures = 0

            result = fetch_all_stocks_sina(max_pages=1, delay=0)
            assert result == []

    def test_fetch_all_stocks_api_error(self):
        """Test handling API error."""
        with patch('app.utils.sina_stock_fetcher.curl_requests') as mock_requests:
            mock_requests.get.side_effect = Exception("Network error")

            _SINA_STOCK_CB._state = CircuitState.CLOSED
            _SINA_STOCK_CB._stats.consecutive_failures = 0

            result = fetch_all_stocks_sina(max_pages=1, delay=0)
            assert result == []

    def test_fetch_all_stocks_excludes_beijing(self):
        """Test Beijing Stock Exchange stocks are excluded."""
        mock_stocks = [
            {
                "symbol": "bj830799",
                "code": "830799",
                "name": "北京股票",
                "trade": "10.0",
                "changepercent": "0",
                "per": "10",
                "pb": "1",
                "mktcap": "1000000",
                "nmc": "1000000",
                "volume": "1000",
                "amount": "10000",
                "turnoverratio": "0.1",
                "high": "10.5",
                "low": "9.5",
                "settlement": "10"
            },
            {
                "symbol": "sh600519",
                "code": "600519",
                "name": "贵州茅台",
                "trade": "1299.18",
                "changepercent": "-0.902",
                "per": "19.786",
                "pb": "6.006",
                "mktcap": "163000000",
                "nmc": "163000000",
                "volume": "1588706",
                "amount": "2067373353",
                "turnoverratio": "0.12687",
                "high": "1311.91",
                "low": "1296.6",
                "settlement": "1311"
            }
        ]

        with patch('app.utils.sina_stock_fetcher.curl_requests') as mock_requests:
            call_count = [0]
            def get_side_effect(*args, **kwargs):
                call_count[0] += 1
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                if call_count[0] <= 2:
                    mock_resp.text = json.dumps(mock_stocks)
                else:
                    mock_resp.text = "[]"
                return mock_resp

            mock_requests.get.side_effect = get_side_effect

            _SINA_STOCK_CB._state = CircuitState.CLOSED
            _SINA_STOCK_CB._stats.consecutive_failures = 0

            result = fetch_all_stocks_sina(max_pages=1, delay=0, exclude_bj=True)

            assert len(result) == 2  # Both sh and sz have 1 valid stock each
            for stock in result:
                assert not stock["symbol"].startswith("bj")


class TestCircuitBreaker:
    """Tests for circuit breaker integration."""

    def test_circuit_breaker_initial_state(self):
        """Test circuit breaker starts in closed state."""
        assert _SINA_STOCK_CB.state.value == "closed"

    def test_circuit_breaker_config(self):
        """Test circuit breaker configuration."""
        assert _SINA_STOCK_CB.config.failure_threshold == 5
        assert _SINA_STOCK_CB.config.timeout == 60.0


class TestDataTransformation:
    """Tests for data transformation in fetch_all_stocks_sina."""

    def test_numeric_fields_conversion(self):
        """Test numeric fields are properly converted."""
        mock_stocks = [
            {
                "symbol": "sh600519",
                "code": "600519",
                "name": "贵州茅台",
                "trade": "1299.18",
                "changepercent": "-0.902",
                "per": "19.786",
                "pb": "6.006",
                "mktcap": "163000000",
                "nmc": "163000000",
                "volume": "1588706",
                "amount": "2067373353",
                "turnoverratio": "0.12687",
                "high": "1311.91",
                "low": "1296.6",
                "settlement": "1311"
            }
        ]

        with patch('app.utils.sina_stock_fetcher.curl_requests') as mock_requests:
            call_count = [0]
            def get_side_effect(*args, **kwargs):
                call_count[0] += 1
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                if call_count[0] <= 2:
                    mock_resp.text = json.dumps(mock_stocks)
                else:
                    mock_resp.text = "[]"
                return mock_resp

            mock_requests.get.side_effect = get_side_effect

            _SINA_STOCK_CB._state = CircuitState.CLOSED
            _SINA_STOCK_CB._stats.consecutive_failures = 0

            result = fetch_all_stocks_sina(max_pages=1, delay=0)

            assert len(result) >= 1
            stock = result[0]
            assert isinstance(stock["price"], float)
            assert isinstance(stock["change_pct"], float)
            assert isinstance(stock["volume"], float)
            assert isinstance(stock["amount"], float)

    def test_null_values_handling(self):
        """Test handling of null/empty values."""
        mock_stocks = [
            {
                "symbol": "sh600519",
                "code": "600519",
                "name": "贵州茅台",
                "trade": "",
                "changepercent": "",
                "per": None,
                "pb": None,
                "mktcap": "",
                "nmc": "",
                "volume": "",
                "amount": "",
                "turnoverratio": "",
                "high": "",
                "low": "",
                "settlement": ""
            }
        ]

        with patch('app.utils.sina_stock_fetcher.curl_requests') as mock_requests:
            call_count = [0]
            def get_side_effect(*args, **kwargs):
                call_count[0] += 1
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                if call_count[0] <= 2:
                    mock_resp.text = json.dumps(mock_stocks)
                else:
                    mock_resp.text = "[]"
                return mock_resp

            mock_requests.get.side_effect = get_side_effect

            _SINA_STOCK_CB._state = CircuitState.CLOSED
            _SINA_STOCK_CB._stats.consecutive_failures = 0

            result = fetch_all_stocks_sina(max_pages=1, delay=0)

            assert len(result) >= 1
            stock = result[0]
            assert stock["price"] == 0.0
            assert stock["change_pct"] == 0.0
            assert stock["pe"] is None
            assert stock["pb"] is None
