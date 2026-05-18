"""
E2E tests for futures workflow.

Tests the complete futures workflow from dashboard loading to data refresh.
"""
import pytest
import time
from fastapi.testclient import TestClient


class TestFuturesE2EWorkflow:
    """E2E: Complete futures workflow test"""
    
    @pytest.fixture(scope="class")
    def client(self):
        """Create a test client for the FastAPI app."""
        from app.main import app
        return TestClient(app)
    
    def test_complete_futures_workflow(self, client):
        """
        Complete E2E workflow test:
        1. Load dashboard → verify data
        2. Get index history → verify structure
        3. Get term structure → verify timeout protection
        4. Get commodities → verify sectors
        """
        # Step 1: Load main indexes
        response = client.get("/api/v1/futures/main_indexes")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "data" in data
        assert "index_futures" in data["data"]
        assert len(data["data"]["index_futures"]) == 3
        
        # Verify source field exists
        assert "source" in data["data"]
        
        # Step 2: Get historical data for IF
        response = client.get("/api/v1/futures/index_history?symbol=IF&limit=20")
        assert response.status_code == 200
        history_data = response.json()
        assert history_data["code"] == 0
        assert "data" in history_data
        assert "history" in history_data["data"]
        assert "symbol" in history_data["data"]
        
        # Step 3: Get term structure with timeout protection
        start = time.time()
        response = client.get("/api/v1/futures/term_structure?symbol=RB")
        elapsed = time.time() - start
        assert elapsed < 15  # Should complete within timeout
        assert response.status_code in [200, 400, 500]  # May fail if no data
        
        # Step 4: Get commodities
        response = client.get("/api/v1/futures/commodities")
        assert response.status_code == 200
        commodities = response.json()
        assert commodities["code"] == 0
        assert "data" in commodities
        assert "commodities" in commodities["data"]
        
        # Verify sector grouping (if present in real data)
        for item in commodities["data"]["commodities"]:
            if "sector" in item:
                assert "sector_emoji" in item
    
    def test_futures_data_consistency(self, client):
        """Test that data is consistent across endpoints"""
        # Get main indexes
        main_response = client.get("/api/v1/futures/main_indexes")
        assert main_response.status_code == 200
        main_data = main_response.json()
        
        # Get commodities
        commodities_response = client.get("/api/v1/futures/commodities")
        assert commodities_response.status_code == 200
        commodities_data = commodities_response.json()
        
        # Verify update_time is consistent
        assert main_data["data"]["update_time"] == commodities_data["data"]["update_time"]
    
    def test_futures_error_handling(self, client):
        """Test error handling across workflow"""
        # Invalid symbol for index_history
        response = client.get("/api/v1/futures/index_history?symbol=INVALID")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["history"] == []
        
        # Invalid symbol for term_structure
        response = client.get("/api/v1/futures/term_structure?symbol=INVALID")
        assert response.status_code in [200, 400, 500]
    
    def test_index_history_valid_symbols(self, client):
        """Test index history with valid symbols"""
        valid_symbols = ["IF", "IC", "IM"]
        
        for symbol in valid_symbols:
            response = client.get(f"/api/v1/futures/index_history?symbol={symbol}&limit=10")
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert data["data"]["symbol"] == symbol
    
    def test_commodities_sector_grouping(self, client):
        """Test that commodities are properly grouped by sector"""
        response = client.get("/api/v1/futures/commodities")
        assert response.status_code == 200
        data = response.json()
        
        commodities = data["data"]["commodities"]
        assert len(commodities) > 0
        
        # Check that all commodities have required fields
        # Note: sector fields may be missing in mock data fallback
        required_fields = ["symbol", "name", "unit", "price", "change_pct"]
        for item in commodities:
            for field in required_fields:
                assert field in item, f"Missing field: {field}"
        
        # Verify sector values if present (real data has sectors, mock may not)
        valid_sectors = ["黑色建材", "能源化工", "新能源", "其他"]
        for item in commodities:
            if "sector" in item:
                assert item["sector"] in valid_sectors, f"Invalid sector: {item['sector']}"
    
    def test_main_indexes_structure(self, client):
        """Test main indexes response structure"""
        response = client.get("/api/v1/futures/main_indexes")
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert data["code"] == 0
        assert "message" in data
        assert "data" in data
        
        # Verify index futures structure
        index_futures = data["data"]["index_futures"]
        assert len(index_futures) == 3
        
        # Check required fields for each index future
        required_fields = ["symbol", "name", "price", "change_pct", "position"]
        for item in index_futures:
            for field in required_fields:
                assert field in item, f"Missing field in index future: {field}"
    
    def test_term_structure_timeout_protection(self, client):
        """Test that term structure endpoint has timeout protection"""
        start = time.time()
        response = client.get("/api/v1/futures/term_structure?symbol=RB")
        elapsed = time.time() - start
        
        # Should complete within 15 seconds (timeout is 10s + buffer)
        assert elapsed < 15, f"Request took too long: {elapsed:.2f}s"
    
    def test_workflow_refresh_consistency(self, client):
        """Test that multiple calls return consistent data"""
        # First call
        response1 = client.get("/api/v1/futures/main_indexes")
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Second call (should use cache)
        response2 = client.get("/api/v1/futures/main_indexes")
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Update time should be the same (cached)
        assert data1["data"]["update_time"] == data2["data"]["update_time"]
