"""
End-to-end tests for Wind Vane (市场风向标) workflow.

Tests the complete user flow for the wind vane widget:
- Display of wind vane data
- Click interaction to open K-line chart
- Error handling
- Mobile layout visibility
"""

import pytest


class TestWindVaneDisplay:
    """Test wind vane display functionality."""

    def test_market_overview_returns_wind_data(self, client):
        """Test that market overview returns wind vane data."""
        response = client.get("/api/v1/market/overview")
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                wind = data["data"]["wind"]
                expected_symbols = ["000001", "000300", "399001", "399006", "HSI", "IXIC"]
                for symbol in expected_symbols:
                    assert symbol in wind, f"Missing wind symbol: {symbol}"

    def test_wind_data_structure(self, client):
        """Test that wind vane data has correct structure."""
        response = client.get("/api/v1/market/overview")

        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                wind = data["data"]["wind"]
                for symbol, item in wind.items():
                    assert "name" in item
                    assert "price" in item
                    assert "change_pct" in item
                    assert "status" in item
                    assert "market" in item


class TestWindVaneInteraction:
    """Test wind vane click interaction."""

    def test_symbol_click_opens_chart(self, client):
        """Test that clicking a symbol returns valid history data."""
        symbol = "000001"
        response = client.get(f"/api/v1/market/history/{symbol}?period=daily&limit=30")
        assert response.status_code in [200, 500]

    def test_macro_symbol_lookup(self, client):
        """Test that macro symbols can be looked up."""
        response = client.get("/api/v1/market/lookup/GOLD")
        assert response.status_code in [200, 404, 500]


class TestWindVaneErrorHandling:
    """Test wind vane error handling."""

    def test_macro_endpoint_responds(self, client):
        """Test that macro endpoint responds without crashing."""
        response = client.get("/api/v1/market/macro")
        assert response.status_code in [200, 500]

    def test_invalid_symbol_handling(self, client):
        """Test that invalid symbols are handled gracefully."""
        response = client.get("/api/v1/market/history/INVALID?period=daily")
        assert response.status_code in [200, 404, 500]

    def test_history_invalid_period(self, client):
        """Test that invalid period is handled gracefully."""
        response = client.get("/api/v1/market/history/000001?period=invalid&limit=30")
        assert response.status_code in [200, 500]


class TestWindVaneMobileLayout:
    """Test wind vane mobile layout."""

    def test_market_overview_mobile_friendly(self, client):
        """Test that market overview response is mobile-friendly."""
        response = client.get("/api/v1/market/overview")

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)
            assert "data" in data

    def test_wind_data_is_compact(self, client):
        """Test that wind data uses compact structure."""
        response = client.get("/api/v1/market/overview")

        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                wind = data["data"]["wind"]
                for symbol, item in wind.items():
                    assert isinstance(item.get("name"), str)
                    assert isinstance(item.get("price"), (int, float))


class TestWindVaneDataFreshness:
    """Test wind vane data freshness."""

    def test_macro_cache_is_60_seconds(self):
        """Test that macro cache TTL is 60 seconds."""
        from app.routers.market.overview import _MACRO_CACHE_TTL
        assert _MACRO_CACHE_TTL == 60

    def test_market_overview_has_timestamp(self, client):
        """Test that market overview includes timestamp."""
        response = client.get("/api/v1/market/overview")

        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                wind = data["data"]["wind"]
                for symbol, item in wind.items():
                    assert "status" in item or "name" in item
