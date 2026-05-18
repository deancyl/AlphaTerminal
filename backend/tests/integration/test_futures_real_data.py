"""
P0 Integration Tests for Futures Real Data
Tests critical paths for real data API and historical endpoint.
"""
import pytest
import time
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


class TestFuturesRealData:
    """P0: Real data integration tests"""

    def test_main_indexes_returns_data(self):
        """Test that main_indexes endpoint returns data"""
        response = client.get("/api/v1/futures/main_indexes")
        assert response.status_code == 200

        data = response.json()
        assert data["code"] == 0
        assert "index_futures" in data["data"]
        assert len(data["data"]["index_futures"]) == 3

        # Check structure
        for fut in data["data"]["index_futures"]:
            assert "symbol" in fut
            assert "name" in fut
            assert "price" in fut
            assert "change_pct" in fut
            assert fut["symbol"] in ["IF", "IC", "IM"]

    def test_main_indexes_has_source_field(self):
        """Test that source field is present (real or mock)"""
        response = client.get("/api/v1/futures/main_indexes")
        assert response.status_code == 200

        data = response.json()
        assert "source" in data["data"]
        assert data["data"]["source"] in ["real", "mock"]

    def test_index_history_endpoint_exists(self):
        """Test that index_history endpoint exists"""
        response = client.get("/api/v1/futures/index_history?symbol=IF&limit=10")
        assert response.status_code == 200

        data = response.json()
        assert data["code"] == 0
        assert "history" in data["data"]

    def test_index_history_invalid_symbol(self):
        """Test that invalid symbol returns empty history"""
        response = client.get("/api/v1/futures/index_history?symbol=INVALID")
        assert response.status_code == 200

        data = response.json()
        assert data["data"]["history"] == []

    def test_term_structure_timeout(self):
        """Test that term_structure has timeout protection"""
        start = time.time()
        response = client.get("/api/v1/futures/term_structure?symbol=RB")
        elapsed = time.time() - start

        # Should complete within 15 seconds (10s timeout + buffer)
        assert elapsed < 15, f"Request took {elapsed}s, should timeout at 10s"
        assert response.status_code in [200, 500]


class TestFuturesMainIndexesExtended:
    """Extended tests for main_indexes endpoint"""

    def test_main_indexes_response_structure(self):
        """Test complete response structure"""
        response = client.get("/api/v1/futures/main_indexes")
        assert response.status_code == 200

        data = response.json()
        # Check top-level structure
        assert "code" in data
        assert "data" in data
        assert data["code"] == 0

        # Check data structure
        result = data["data"]
        assert "index_futures" in result
        assert "update_time" in result
        assert "source" in result

    def test_main_indexes_index_futures_fields(self):
        """Test that each index future has all required fields"""
        response = client.get("/api/v1/futures/main_indexes")
        assert response.status_code == 200

        data = response.json()
        index_futures = data["data"]["index_futures"]

        required_fields = ["symbol", "name", "price", "change_pct", "position", "note"]
        for fut in index_futures:
            for field in required_fields:
                assert field in fut, f"Missing field '{field}' in {fut}"

    def test_main_indexes_symbols_correct(self):
        """Test that correct symbols are returned"""
        response = client.get("/api/v1/futures/main_indexes")
        assert response.status_code == 200

        data = response.json()
        symbols = [fut["symbol"] for fut in data["data"]["index_futures"]]

        assert "IF" in symbols
        assert "IC" in symbols
        assert "IM" in symbols
        assert len(symbols) == 3


class TestFuturesIndexHistoryExtended:
    """Extended tests for index_history endpoint"""

    def test_index_history_with_period_daily(self):
        """Test index_history with daily period"""
        response = client.get("/api/v1/futures/index_history?symbol=IF&period=daily&limit=10")
        assert response.status_code == 200

        data = response.json()
        assert data["code"] == 0
        assert "symbol" in data["data"]
        assert "period" in data["data"]
        assert "history" in data["data"]

    def test_index_history_with_period_minute(self):
        """Test index_history with minute period"""
        response = client.get("/api/v1/futures/index_history?symbol=IC&period=5min&limit=10")
        assert response.status_code == 200

        data = response.json()
        assert data["code"] == 0

    def test_index_history_all_valid_symbols(self):
        """Test index_history for all valid symbols"""
        valid_symbols = ["IF", "IC", "IM"]

        for symbol in valid_symbols:
            response = client.get(f"/api/v1/futures/index_history?symbol={symbol}&limit=5")
            assert response.status_code == 200

            data = response.json()
            assert data["code"] == 0
            assert data["data"]["symbol"] == symbol

    def test_index_history_history_item_structure(self):
        """Test structure of history items when data is available"""
        response = client.get("/api/v1/futures/index_history?symbol=IF&limit=10")
        assert response.status_code == 200

        data = response.json()
        history = data["data"]["history"]

        if len(history) > 0:
            # Check first item has required fields
            item = history[0]
            expected_fields = ["date", "open", "close", "high", "low", "volume", "hold"]
            for field in expected_fields:
                assert field in item, f"Missing field '{field}' in history item"

    def test_index_history_limit_parameter(self):
        """Test that limit parameter is respected"""
        response = client.get("/api/v1/futures/index_history?symbol=IF&limit=5")
        assert response.status_code == 200

        data = response.json()
        history = data["data"]["history"]

        # History should have at most 5 items (or less if not enough data)
        assert len(history) <= 5


class TestFuturesTermStructureExtended:
    """Extended tests for term_structure endpoint"""

    def test_term_structure_response_structure(self):
        """Test term_structure response structure"""
        response = client.get("/api/v1/futures/term_structure?symbol=RB")
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            # Should have code and data fields
            assert "code" in data

    def test_term_structure_with_different_symbols(self):
        """Test term_structure with different commodity symbols"""
        symbols = ["RB", "I", "HC"]

        for symbol in symbols:
            response = client.get(f"/api/v1/futures/term_structure?symbol={symbol}")
            # Should complete within timeout
            assert response.status_code in [200, 500]

    def test_term_structure_invalid_symbol(self):
        """Test term_structure with invalid symbol"""
        response = client.get("/api/v1/futures/term_structure?symbol=INVALID")
        # Should return error response, not crash
        assert response.status_code in [200, 400, 500]


class TestFuturesCommodities:
    """Tests for commodities endpoint"""

    def test_commodities_endpoint_exists(self):
        """Test that commodities endpoint exists and returns data"""
        response = client.get("/api/v1/futures/commodities")
        assert response.status_code == 200

        data = response.json()
        assert data["code"] == 0
        assert "commodities" in data["data"]

    def test_commodities_response_structure(self):
        """Test commodities response structure"""
        response = client.get("/api/v1/futures/commodities")
        assert response.status_code == 200

        data = response.json()
        result = data["data"]

        assert "commodities" in result
        assert "update_time" in result

    def test_commodities_item_structure(self):
        """Test structure of commodity items"""
        response = client.get("/api/v1/futures/commodities")
        assert response.status_code == 200

        data = response.json()
        commodities = data["data"]["commodities"]

        if len(commodities) > 0:
            item = commodities[0]
            expected_fields = ["symbol", "name", "unit", "price", "change_pct"]
            for field in expected_fields:
                assert field in item, f"Missing field '{field}' in commodity item"

    def test_commodities_has_expected_symbols(self):
        """Test that expected commodity symbols are present"""
        response = client.get("/api/v1/futures/commodities")
        assert response.status_code == 200

        data = response.json()
        symbols = [c["symbol"] for c in data["data"]["commodities"]]

        # Check for some key commodities
        expected_symbols = ["RB0", "HC0", "I0"]  # 螺纹钢, 热卷, 铁矿石
        for expected in expected_symbols:
            assert expected in symbols, f"Missing expected symbol {expected}"


class TestFuturesCacheBehavior:
    """Tests for cache behavior"""

    def test_main_indexes_cache_consistency(self):
        """Test that multiple calls return consistent data"""
        response1 = client.get("/api/v1/futures/main_indexes")
        response2 = client.get("/api/v1/futures/main_indexes")

        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        # Both should have same structure
        assert data1["code"] == data2["code"]
        assert len(data1["data"]["index_futures"]) == len(data2["data"]["index_futures"])

    def test_commodities_cache_consistency(self):
        """Test that commodities cache is consistent"""
        response1 = client.get("/api/v1/futures/commodities")
        response2 = client.get("/api/v1/futures/commodities")

        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        # Both should have same number of commodities
        assert len(data1["data"]["commodities"]) == len(data2["data"]["commodities"])
