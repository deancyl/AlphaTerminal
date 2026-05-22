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
                assert data["code"] == 0
                assert "anomalies" in data["data"]
    
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


class TestMarketRadarCircuitBreaker:
    """Test Circuit Breaker integration."""
    
    def test_circuit_breaker_reset_endpoint(self, client):
        """Test that circuit breaker reset endpoint works."""
        response = client.post("/api/v1/market_radar/circuit_breaker/reset")
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "treemap" in data["data"]
        assert "anomaly" in data["data"]
    
    def test_health_includes_circuit_breaker_status(self, client):
        """Test that health endpoint includes circuit breaker status."""
        response = client.get("/api/v1/market_radar/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "circuit_breakers" in data
        assert "treemap" in data["circuit_breakers"]
        assert "anomaly" in data["circuit_breakers"]
        assert "state" in data["circuit_breakers"]["treemap"]
        assert "failure_count" in data["circuit_breakers"]["treemap"]


class TestMarketRadarFallback:
    """Test fallback data source functionality."""
    
    def test_treemap_returns_fallback_data(self, client):
        """Test that treemap returns fallback data when primary source fails."""
        mock_response = {
            "data": [{"name": "热门股票", "value": 100, "children": []}],
            "last_update": "2024-01-01T00:00:00",
            "data_source": "fallback",
            "source_detail": {
                "name": "热门股票 (市值排名)",
                "type": "实时",
                "api": "top_stocks_by_market_cap"
            }
        }
        
        with patch('app.routers.market_radar.get_cache') as mock_cache:
            mock_cache_instance = MagicMock()
            mock_cache_instance.get.return_value = None
            mock_cache.return_value = mock_cache_instance
            
            with patch('app.routers.market_radar.build_treemap_data', new_callable=AsyncMock) as mock_build:
                mock_build.return_value = mock_response
                
                response = client.get("/api/v1/market_radar/treemap")
                
                assert response.status_code == 200
                data = response.json()
                assert data["code"] == 0
                assert data["data"]["data_source"] == "fallback"
    
    def test_treemap_includes_circuit_breaker_info(self, client):
        """Test that treemap response includes circuit breaker info."""
        mock_response = {
            "data": [{"name": "热门股票", "value": 100}],
            "last_update": "2024-01-01T00:00:00",
            "data_source": "fallback"
        }
        
        with patch('app.routers.market_radar.get_cache') as mock_cache:
            mock_cache_instance = MagicMock()
            mock_cache_instance.get.return_value = None
            mock_cache.return_value = mock_cache_instance
            
            with patch('app.routers.market_radar.build_treemap_data', new_callable=AsyncMock) as mock_build:
                mock_build.return_value = mock_response
                
                response = client.get("/api/v1/market_radar/treemap")
                
                assert response.status_code == 200
                data = response.json()
                assert "circuit_breaker" in data["data"]
                assert "state" in data["data"]["circuit_breaker"]


class TestMarketRadarCacheFormat:
    """Test that cached responses have correct format."""
    
    def test_cached_response_has_code_and_message(self, client):
        """Test that cached response includes code and message fields."""
        cached_response = {
            "code": 0,
            "message": "success",
            "data": {
                "data": [{"name": "白酒", "value": 100}],
                "last_update": "2024-01-01T00:00:00",
                "data_source": "akshare"
            }
        }
        
        with patch('app.routers.market_radar.get_cache') as mock_cache:
            mock_cache_instance = MagicMock()
            mock_cache_instance.get.return_value = cached_response
            mock_cache.return_value = mock_cache_instance
            
            response = client.get("/api/v1/market_radar/treemap")
            
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert data["message"] == "success"


class TestMarketRadarTemperature:
    """Test market temperature endpoint."""
    
    def test_temperature_returns_score(self, client):
        """Test that temperature endpoint returns a score."""
        with patch('app.services.sentiment_engine.get_histogram') as mock_histogram:
            mock_histogram.return_value = {
                "advance": 100,
                "decline": 50,
                "limit_up": 10,
                "limit_down": 5,
                "unchanged": 20,
                "timestamp": "2024-01-01T00:00:00"
            }
            
            response = client.get("/api/v1/market_radar/temperature")
            
            assert response.status_code == 200
            data = response.json()
            assert "score" in data
            assert "label" in data
            assert "color" in data
            assert 0 <= data["score"] <= 100
