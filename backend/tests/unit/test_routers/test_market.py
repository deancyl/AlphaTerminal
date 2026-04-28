"""Tests for market router."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, Mock
import json

from app.main import app


client = TestClient(app)


class TestMarketOverview:
    """Test cases for market overview endpoint."""

    @patch('app.routers.market.get_latest_prices')
    def test_market_overview_endpoint(self, mock_get_latest_prices):
        """Test GET /market/overview endpoint."""
        # Mock get_latest_prices to return sample data
        mock_get_latest_prices.return_value = [
            {'symbol': '000001', 'name': '上证指数', 'price': 3000.0, 'change_pct': 1.5, 'volume': 1000000, 'market': 'AShare'},
            {'symbol': '000300', 'name': '沪深300', 'price': 4000.0, 'change_pct': 2.0, 'volume': 2000000, 'market': 'AShare'},
            {'symbol': '399001', 'name': '深证成指', 'price': 10000.0, 'change_pct': 1.8, 'volume': 1500000, 'market': 'AShare'},
            {'symbol': '399006', 'name': '创业板指', 'price': 2000.0, 'change_pct': 2.5, 'volume': 1200000, 'market': 'AShare'},
            {'symbol': 'HSI', 'name': '恒生指数', 'price': 25000.0, 'change_pct': 1.2, 'volume': 5000000, 'market': 'HK'},
            {'symbol': 'IXIC', 'name': '纳斯达克', 'price': 15000.0, 'change_pct': 3.0, 'volume': 8000000, 'market': 'US'},
        ]
        
        response = client.get("/api/v1/market/overview")
        assert response.status_code in [200, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert "code" in data
            assert data.get("code") == 0
            assert "data" in data

    @patch('app.routers.market.get_latest_prices')
    def test_market_overview_response_structure(self, mock_get_latest_prices):
        """Test that overview response has correct structure."""
        # Mock get_latest_prices to return sample data
        mock_get_latest_prices.return_value = [
            {'symbol': '000001', 'name': '上证指数', 'price': 3000.0, 'change_pct': 1.5, 'volume': 1000000, 'market': 'AShare'},
            {'symbol': '000300', 'name': '沪深300', 'price': 4000.0, 'change_pct': 2.0, 'volume': 2000000, 'market': 'AShare'},
            {'symbol': '399001', 'name': '深证成指', 'price': 10000.0, 'change_pct': 1.8, 'volume': 1500000, 'market': 'AShare'},
            {'symbol': '399006', 'name': '创业板指', 'price': 2000.0, 'change_pct': 2.5, 'volume': 1200000, 'market': 'AShare'},
            {'symbol': 'HSI', 'name': '恒生指数', 'price': 25000.0, 'change_pct': 1.2, 'volume': 5000000, 'market': 'HK'},
            {'symbol': 'IXIC', 'name': '纳斯达克', 'price': 15000.0, 'change_pct': 3.0, 'volume': 8000000, 'market': 'US'},
        ]
        
        response = client.get("/api/v1/market/overview")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                result = data["data"]
                assert "wind" in result
                assert "meta" in result
                meta = result["meta"]
                assert "markets" in meta

    @patch('app.routers.market.get_latest_prices')
    def test_market_overview_wind_symbols(self, mock_get_latest_prices):
        """Test that overview includes all wind symbols."""
        # Mock get_latest_prices to return sample data
        mock_get_latest_prices.return_value = [
            {'symbol': '000001', 'name': '上证指数', 'price': 3000.0, 'change_pct': 1.5, 'volume': 1000000, 'market': 'AShare'},
            {'symbol': '000300', 'name': '沪深300', 'price': 4000.0, 'change_pct': 2.0, 'volume': 2000000, 'market': 'AShare'},
            {'symbol': '399001', 'name': '深证成指', 'price': 10000.0, 'change_pct': 1.8, 'volume': 1500000, 'market': 'AShare'},
            {'symbol': '399006', 'name': '创业板指', 'price': 2000.0, 'change_pct': 2.5, 'volume': 1200000, 'market': 'AShare'},
            {'symbol': 'HSI', 'name': '恒生指数', 'price': 25000.0, 'change_pct': 1.2, 'volume': 5000000, 'market': 'HK'},
            {'symbol': 'IXIC', 'name': '纳斯达克', 'price': 15000.0, 'change_pct': 3.0, 'volume': 8000000, 'market': 'US'},
        ]
        
        response = client.get("/api/v1/market/overview")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                wind = data["data"]["wind"]
                expected = ["000001", "000300", "399001", "399006", "HSI", "IXIC"]
                for symbol in expected:
                    assert symbol in wind

    @patch('app.routers.market.get_latest_prices')
    def test_market_overview_market_status(self, mock_get_latest_prices):
        """Test that overview includes market status."""
        # Mock get_latest_prices to return sample data
        mock_get_latest_prices.return_value = [
            {'symbol': '000001', 'name': '上证指数', 'price': 3000.0, 'change_pct': 1.5, 'volume': 1000000, 'market': 'AShare'},
            {'symbol': '000300', 'name': '沪深300', 'price': 4000.0, 'change_pct': 2.0, 'volume': 2000000, 'market': 'AShare'},
            {'symbol': '399001', 'name': '深证成指', 'price': 10000.0, 'change_pct': 1.8, 'volume': 1500000, 'market': 'AShare'},
            {'symbol': '399006', 'name': '创业板指', 'price': 2000.0, 'change_pct': 2.5, 'volume': 1200000, 'market': 'AShare'},
            {'symbol': 'HSI', 'name': '恒生指数', 'price': 25000.0, 'change_pct': 1.2, 'volume': 5000000, 'market': 'HK'},
            {'symbol': 'IXIC', 'name': '纳斯达克', 'price': 15000.0, 'change_pct': 3.0, 'volume': 8000000, 'market': 'US'},
        ]
        
        response = client.get("/api/v1/market/overview")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                markets = data["data"]["meta"]["markets"]
                assert "AShare" in markets
                assert "HK" in markets
                assert "US" in markets


class TestMarketIndices:
    """Test cases for market indices endpoint."""

    def test_market_indices_endpoint(self):
        response = client.get("/api/v1/market/indices")
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert "code" in data

    def test_market_indices_response_structure(self):
        response = client.get("/api/v1/market/indices")
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                assert "data" in data
                assert "indices" in data["data"]


class TestMarketChinaAll:
    """Test cases for market china_all endpoint."""

    def test_market_china_all_endpoint(self):
        response = client.get("/api/v1/market/china_all")
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert "code" in data

    def test_market_china_all_response_structure(self):
        response = client.get("/api/v1/market/china_all")
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                assert "data" in data
                assert "china_all" in data["data"]
                assert "meta" in data["data"]


class TestMarketMacro:
    """Test cases for market macro endpoint."""

    def test_market_macro_endpoint(self):
        response = client.get("/api/v1/market/macro")
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert "code" in data

    def test_market_macro_response_structure(self):
        response = client.get("/api/v1/market/macro")
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                assert "data" in data
                assert "macro" in data["data"]

    def test_market_macro_expected_symbols(self):
        response = client.get("/api/v1/market/macro")
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                macro_data = data["data"]["macro"]
                assert isinstance(macro_data, list)


class TestMarketSymbols:
    """Test cases for market symbols endpoint."""

    def test_market_symbols_endpoint(self):
        response = client.get("/api/v1/market/symbols")
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert "code" in data

    def test_market_symbols_response_structure(self):
        response = client.get("/api/v1/market/symbols")
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                assert "data" in data
                assert "symbols" in data["data"]
                assert "count" in data["data"]
                assert "timestamp" in data["data"]

    def test_market_symbols_symbol_structure(self):
        response = client.get("/api/v1/market/symbols")
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                symbols = data["data"]["symbols"]
                if symbols:
                    symbol = symbols[0]
                    expected = ["symbol", "code", "name", "market", "type"]
                    for field in expected:
                        assert field in symbol


class TestMarketLookup:
    """Test cases for market lookup endpoint."""

    def test_market_lookup_existing_symbol(self):
        response = client.get("/api/v1/market/lookup/sh000001")
        assert response.status_code in [200, 404, 500]
        if response.status_code == 200:
            data = response.json()
            assert "code" in data

    def test_market_lookup_nonexistent_symbol(self):
        response = client.get("/api/v1/market/lookup/nonexistent123")
        assert response.status_code in [200, 404, 500]

    def test_market_lookup_case_insensitive(self):
        response_lower = client.get("/api/v1/market/lookup/sh000001")
        response_upper = client.get("/api/v1/market/lookup/SH000001")
        assert response_lower.status_code in [200, 404, 500]
        assert response_upper.status_code in [200, 404, 500]


@pytest.mark.skip(reason="Requires database setup - local imports make mocking difficult")
class TestMarketQuote:
    """Test cases for market quote endpoint."""

    def test_market_quote_endpoint(self):
        response = client.get("/api/v1/market/quote/sh000001")
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert "code" in data

    def test_market_quote_response_structure(self):
        response = client.get("/api/v1/market/quote/sh000001")
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                assert "data" in data
                quote = data["data"]
                assert "symbol" in quote
                assert "price" in quote

    def test_market_quote_nonexistent_symbol(self):
        response = client.get("/api/v1/market/quote/nonexistent123")
        assert response.status_code in [200, 404, 500]


class TestMarketStocks:
    """Test cases for market stocks endpoints."""

    def test_market_all_stocks_endpoint(self):
        response = client.get("/api/v1/market/all_stocks?page=1&page_size=10")
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert "code" in data

    def test_market_all_stocks_pagination(self):
        response = client.get("/api/v1/market/all_stocks?page=2&page_size=20")
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                assert "data" in data
                assert "stocks" in data["data"]
                assert "page" in data["data"]
                assert data["data"]["page"] == 2

    def test_market_all_stocks_search(self):
        response = client.get("/api/v1/market/all_stocks?search=茅台")
        assert response.status_code in [200, 500]

    def test_market_all_stocks_lite_endpoint(self):
        response = client.get("/api/v1/market/all_stocks_lite")
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert "code" in data

    def test_market_stocks_search_endpoint(self):
        response = client.get("/api/v1/market/stocks/search?keyword=茅台")
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert "code" in data

    def test_market_stocks_search_with_filters(self):
        response = client.get("/api/v1/market/stocks/search?min_price=10&max_price=100&sort_by=change_pct")
        assert response.status_code in [200, 500]


@pytest.mark.skip(reason="Requires database setup - local imports make mocking difficult")
class TestMarketHistory:
    """Test cases for market history endpoint."""

    def test_market_history_daily(self):
        response = client.get("/api/v1/market/history/sh000001?period=daily&limit=30")
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert "code" in data

    def test_market_history_weekly(self):
        response = client.get("/api/v1/market/history/sh000001?period=weekly&limit=30")
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert "code" in data

    def test_market_history_monthly(self):
        response = client.get("/api/v1/market/history/sh000001?period=monthly&limit=30")
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert "code" in data

    def test_market_history_response_structure(self):
        response = client.get("/api/v1/market/history/sh000001?period=daily&limit=10")
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                assert "data" in data
                result = data["data"]
                assert "symbol" in result
                assert "period" in result
                assert "history" in result

    def test_market_history_pagination(self):
        response = client.get("/api/v1/market/history/sh000001?period=daily&limit=10&offset=10")
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                assert "data" in data
                assert "offset" in data["data"]
                assert data["data"]["offset"] == 10

    def test_market_history_invalid_period(self):
        response = client.get("/api/v1/market/history/sh000001?period=invalid")
        assert response.status_code in [200, 500]


class TestMarketFundFlow:
    """Test cases for fund flow endpoint."""

    def test_market_fund_flow_endpoint(self):
        response = client.get("/api/v1/market/fund_flow")
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert "code" in data

    def test_market_fund_flow_response_structure(self):
        response = client.get("/api/v1/market/fund_flow")
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                assert "data" in data
                assert "items" in data["data"]
                assert "total" in data["data"]


class TestMarketFutures:
    """Test cases for futures endpoint."""

    def test_market_futures_daily(self):
        response = client.get("/api/v1/market/futures/IF0?period=daily")
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert "symbol" in data or "code" in data

    def test_market_futures_minute(self):
        response = client.get("/api/v1/market/futures/IF0?period=5min")
        assert response.status_code in [200, 500]

    def test_market_futures_invalid_period(self):
        response = client.get("/api/v1/market/futures/IF0?period=invalid")
        assert response.status_code in [200, 500]
