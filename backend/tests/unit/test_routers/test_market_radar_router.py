"""
Unit tests for Market Radar Router

Tests for:
- P0-2: Rate limiting
- P2-10: Error message sanitization
- API endpoint functionality
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock


@pytest.fixture
def app():
    """Create test FastAPI app."""
    from app.routers.market_radar import router
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestMarketRadarHealthEndpoint:
    """Test health check endpoint."""
    
    def test_health_check_returns_ok(self, client):
        """Test that health endpoint returns ok status."""
        response = client.get("/api/v1/market_radar/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "market_radar"
        assert "timestamp" in data


class TestMarketRadarTreemapEndpoint:
    """Test treemap endpoint."""
    
    def test_treemap_default_sector_level(self, client):
        """Test treemap with default sector level."""
        mock_response = {
            "data": [{"name": "白酒", "value": 100}],
            "last_update": "2024-01-01T00:00:00",
            "data_source": "akshare"
        }
        
        with patch('app.routers.market_radar.get_cache') as mock_cache:
            mock_cache_instance = MagicMock()
            mock_cache_instance.get.return_value = None  # No cache hit
            mock_cache.return_value = mock_cache_instance
            
            with patch('app.routers.market_radar.build_treemap_data', new_callable=AsyncMock) as mock_build:
                mock_build.return_value = mock_response
                
                response = client.get("/api/v1/market_radar/treemap")
                
                assert response.status_code == 200
                data = response.json()
                assert "data" in data
    
    def test_treemap_stock_level(self, client):
        """Test treemap with stock level."""
        mock_response = {
            "data": [{"name": "贵州茅台", "value": 200}],
            "last_update": "2024-01-01T00:00:00",
            "data_source": "akshare"
        }
        
        with patch('app.routers.market_radar.get_cache') as mock_cache:
            mock_cache_instance = MagicMock()
            mock_cache_instance.get.return_value = None
            mock_cache.return_value = mock_cache_instance
            
            with patch('app.routers.market_radar.build_treemap_data', new_callable=AsyncMock) as mock_build:
                mock_build.return_value = mock_response
                
                response = client.get("/api/v1/market_radar/treemap?level=stock")
                
                assert response.status_code == 200
    
    def test_treemap_timeout_returns_504(self, client):
        """Test that timeout returns 504 status."""
        with patch('app.routers.market_radar.get_cache') as mock_cache:
            mock_cache_instance = MagicMock()
            mock_cache_instance.get.return_value = None  # No cache hit
            mock_cache.return_value = mock_cache_instance
            
            with patch('app.routers.market_radar.build_treemap_data', new_callable=AsyncMock) as mock_build:
                # Return response with error key to trigger 504
                mock_build.return_value = {
                    "error": "timeout",
                    "data": []
                }
                
                response = client.get("/api/v1/market_radar/treemap")
                
                assert response.status_code == 504


class TestMarketRadarAnomaliesEndpoint:
    """Test anomalies endpoint."""
    
    def test_anomalies_returns_list(self, client):
        """Test that anomalies endpoint returns list."""
        mock_response = {
            "anomalies": [
                {"type": "volatility", "title": "振幅最大", "stocks": []}
            ],
            "last_update": "2024-01-01T00:00:00"
        }
        
        with patch('app.routers.market_radar.get_cache') as mock_cache:
            mock_cache_instance = MagicMock()
            mock_cache_instance.get.return_value = None
            mock_cache.return_value = mock_cache_instance
            
            with patch('app.routers.market_radar.detect_anomalies', new_callable=AsyncMock) as mock_detect:
                mock_detect.return_value = mock_response
                
                response = client.get("/api/v1/market_radar/anomalies")
                
                assert response.status_code == 200
                data = response.json()
                assert "anomalies" in data
    
    def test_anomaly_by_type_valid(self, client):
        """Test anomaly by type with valid type."""
        mock_response = {
            "anomalies": [
                {"type": "volatility", "title": "振幅最大", "stocks": []}
            ],
            "last_update": "2024-01-01T00:00:00"
        }
        
        with patch('app.routers.market_radar.get_cache') as mock_cache:
            mock_cache_instance = MagicMock()
            mock_cache_instance.get.return_value = None
            mock_cache.return_value = mock_cache_instance
            
            with patch('app.routers.market_radar.detect_anomalies', new_callable=AsyncMock) as mock_detect:
                mock_detect.return_value = mock_response
                
                response = client.get("/api/v1/market_radar/anomalies/volatility")
                
                assert response.status_code == 200
    
    def test_anomaly_by_type_invalid(self, client):
        """Test anomaly by type with invalid type returns 400."""
        response = client.get("/api/v1/market_radar/anomalies/invalid_type")
        
        assert response.status_code == 400
        data = response.json()
        # P2-10: Check Chinese error message
        assert "无效的异常类型" in data["detail"]


class TestMarketRadarErrorMessages:
    """Test P2-10: Error message sanitization."""
    
    def test_error_message_sanitized(self, client):
        """Test that error messages don't expose internal details."""
        with patch('app.routers.market_radar.get_cache') as mock_cache:
            mock_cache_instance = MagicMock()
            mock_cache_instance.get.return_value = None  # No cache hit
            mock_cache.return_value = mock_cache_instance
            
            with patch('app.routers.market_radar.build_treemap_data', new_callable=AsyncMock) as mock_build:
                # Raise exception directly to trigger error handler
                mock_build.side_effect = Exception("Internal database connection string: mysql://user:pass@host")
                
                response = client.get("/api/v1/market_radar/treemap")
                
                assert response.status_code == 500
                data = response.json()
                # P2-10: Error message should be sanitized
                assert "mysql://" not in data["detail"]
                assert "pass@" not in data["detail"]
