"""
Integration tests for ML API endpoints.

Tests cover:
- Model management (CRUD)
- Training and prediction
- Portfolio optimization
- Factor analysis
"""
import pytest
from fastapi.testclient import TestClient


class TestMLHealthEndpoint:
    """Tests for ML health check endpoint."""
    
    def test_health_check_returns_200(self, client: TestClient):
        """Test GET /api/v1/ml/health returns healthy status."""
        response = client.get("/api/v1/ml/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "data" in data
        assert "status" in data["data"]
        assert data["data"]["status"] == "healthy"


class TestMLModelManagement:
    """Tests for model CRUD operations."""
    
    def test_list_models_returns_200(self, client: TestClient):
        """Test GET /api/v1/ml/models returns model list."""
        response = client.get("/api/v1/ml/models")
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "models" in data["data"]
        assert "total" in data["data"]
    
    def test_get_model_not_found_returns_404(self, client: TestClient):
        """Test GET /api/v1/ml/models/{nonexistent} returns 404."""
        response = client.get("/api/v1/ml/models/nonexistent_model_xyz")
        
        # Should return error response with NOT_FOUND code
        data = response.json()
        assert data["code"] != 0  # Error code


class TestMLTraining:
    """Tests for model training endpoint."""
    
    def test_train_model_missing_fields_returns_422(self, client: TestClient):
        """Test POST /api/v1/ml/train with missing fields returns validation error."""
        response = client.post("/api/v1/ml/train", json={})
        
        assert response.status_code == 422  # Validation error
    
    def test_train_model_invalid_symbol_returns_422(self, client: TestClient):
        """Test POST /api/v1/ml/train with invalid symbol format."""
        response = client.post("/api/v1/ml/train", json={
            "model_id": "test_model",
            "symbol": "invalid_symbol",
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
        })
        
        # Should return validation error or bad request
        assert response.status_code in [400, 422]


class TestMLPrediction:
    """Tests for prediction endpoint."""
    
    def test_predict_model_not_found(self, client: TestClient):
        """Test POST /api/v1/ml/predict with nonexistent model."""
        response = client.post("/api/v1/ml/predict", json={
            "model_id": "nonexistent_model",
            "symbol": "sh600519",
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
        })
        
        # Should return error (model not found)
        data = response.json()
        assert data["code"] != 0


class TestMLPortfolioOptimization:
    """Tests for portfolio optimization endpoint."""
    
    def test_optimize_missing_fields_returns_422(self, client: TestClient):
        """Test POST /api/v1/ml/optimize with missing fields."""
        response = client.post("/api/v1/ml/optimize", json={})
        
        assert response.status_code == 422
    
    def test_optimize_invalid_method_returns_422(self, client: TestClient):
        """Test POST /api/v1/ml/optimize with invalid method."""
        response = client.post("/api/v1/ml/optimize", json={
            "symbols": ["sh600519", "sh600036"],
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "method": "invalid_method",
        })
        
        assert response.status_code == 422
    
    def test_optimize_valid_request_structure(self, client: TestClient):
        """Test POST /api/v1/ml/optimize with valid request structure."""
        response = client.post("/api/v1/ml/optimize", json={
            "symbols": ["sh600519", "sh600036"],
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "method": "mvo",
            "risk_aversion": 1.0,
            "max_weight": 0.3,
        })
        
        # Should return 200 or 401 (if API key required)
        assert response.status_code in [200, 401]


class TestMLFactorAnalysis:
    """Tests for factor analysis endpoint."""
    
    def test_factors_missing_fields_returns_422(self, client: TestClient):
        """Test POST /api/v1/ml/factors with missing fields."""
        response = client.post("/api/v1/ml/factors", json={})
        
        assert response.status_code == 422
    
    def test_factors_invalid_symbol_returns_422(self, client: TestClient):
        """Test POST /api/v1/ml/factors with invalid symbol format."""
        response = client.post("/api/v1/ml/factors", json={
            "symbol": "invalid",
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
        })
        
        assert response.status_code == 422
    
    def test_factors_valid_request_structure(self, client: TestClient):
        """Test POST /api/v1/ml/factors with valid request structure."""
        response = client.post("/api/v1/ml/factors", json={
            "symbol": "sh600519",
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "factors": ["momentum", "value"],
        })
        
        # Should return 200 or 401 (if API key required)
        assert response.status_code in [200, 401]


class TestMLRiskMetrics:
    """Tests for risk metrics endpoint."""
    
    def test_risk_metrics_missing_fields_returns_422(self, client: TestClient):
        """Test POST /api/v1/ml/risk-metrics with missing fields."""
        response = client.post("/api/v1/ml/risk-metrics", json={})
        
        assert response.status_code == 422
    
    def test_risk_metrics_valid_request(self, client: TestClient):
        """Test POST /api/v1/ml/risk-metrics with valid returns."""
        response = client.post("/api/v1/ml/risk-metrics", json={
            "daily_returns": [0.01, -0.02, 0.03, 0.01, -0.01, 0.02, 0.01, -0.03, 0.02, 0.01],
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "annualized_return" in data["data"]
        assert "sharpe_ratio" in data["data"]


class TestMLOptimizationMethods:
    """Tests for listing optimization methods."""
    
    def test_methods_returns_200(self, client: TestClient):
        """Test GET /api/v1/ml/methods returns available methods."""
        response = client.get("/api/v1/ml/methods")
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "methods" in data["data"]
        assert "factors" in data["data"]
        
        # Check methods
        methods = data["data"]["methods"]
        method_ids = [m["id"] for m in methods]
        assert "gmv" in method_ids
        assert "mvo" in method_ids
        assert "rp" in method_ids
        assert "inv" in method_ids


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def client():
    """Create test client."""
    from app.main import app
    return TestClient(app)
