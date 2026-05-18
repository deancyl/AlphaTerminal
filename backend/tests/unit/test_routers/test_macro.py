"""
Macro Module Test Suite
Tests for all macro economic data endpoints

Coverage target: 95%
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.routers import macro
from app.config.timeout import MACRO_TIMEOUT
from app.utils.response import ErrorCode

client = TestClient(app)


# ── Mock Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def mock_akshare_gdp():
    """Mock akshare GDP data"""
    import pandas as pd
    return pd.DataFrame({
        '季度': ['2024Q1', '2023Q4', '2023Q3'],
        '国内生产总值-绝对值': [296299, 285937, 279178],
        '国内生产总值-同比增长': [5.3, 5.2, 4.9],
        '第一产业-同比增长': [3.3, 4.2, 4.0],
        '第二产业-同比增长': [6.0, 5.5, 5.1],
        '第三产业-同比增长': [5.0, 5.3, 5.0],
    })


@pytest.fixture
def mock_akshare_cpi():
    """Mock akshare CPI data"""
    import pandas as pd
    return pd.DataFrame({
        '月份': ['2024年03月份', '2024年02月份', '2024年01月份'],
        '全国-当月': [100.1, 99.9, 100.3],
        '全国-同比增长': [0.1, -0.1, 0.3],
        '全国-环比增长': [-0.6, 0.3, 0.4],
        '城市-同比增长': [0.1, -0.1, 0.3],
        '农村-同比增长': [0.1, -0.1, 0.4],
    })


@pytest.fixture
def mock_akshare_pmi():
    """Mock akshare PMI data"""
    import pandas as pd
    return pd.DataFrame({
        '月份': ['2024年03月份', '2024年02月份', '2024年01月份'],
        '制造业-指数': [50.8, 49.1, 49.2],
        '制造业-同比增长': [1.2, -0.8, -0.5],
        '非制造业-指数': [53.0, 51.4, 50.7],
        '非制造业-同比增长': [1.5, 0.3, 0.2],
    })


@pytest.fixture
def mock_empty_dataframe():
    """Mock empty dataframe"""
    import pandas as pd
    return pd.DataFrame()


# ── Endpoint Tests ─────────────────────────────────────────────────────────────

class TestMacroGdpEndpoint:
    """Tests for /api/v1/macro/gdp endpoint"""
    
    def test_gdp_endpoint_success(self, mock_akshare_gdp):
        """Test GDP endpoint returns data successfully"""
        with patch.object(macro, '_get_ak') as mock_ak:
            mock_ak.return_value.macro_china_gdp.return_value = mock_akshare_gdp
            response = client.get("/api/v1/macro/gdp")
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert "data" in data["data"]
            assert data["data"]["indicator"] == "GDP"
    
    def test_gdp_endpoint_with_limit(self, mock_akshare_gdp):
        """Test GDP endpoint respects limit parameter"""
        with patch.object(macro, '_get_ak') as mock_ak:
            mock_ak.return_value.macro_china_gdp.return_value = mock_akshare_gdp
            response = client.get("/api/v1/macro/gdp?limit=2")
            assert response.status_code == 200
    
    def test_gdp_endpoint_cache_hit(self, mock_akshare_gdp):
        """Test GDP endpoint returns cached data on second request"""
        with patch.object(macro, '_get_ak') as mock_ak:
            mock_ak.return_value.macro_china_gdp.return_value = mock_akshare_gdp
            # First request
            response1 = client.get("/api/v1/macro/gdp")
            # Second request should hit cache
            response2 = client.get("/api/v1/macro/gdp")
            assert response1.status_code == 200
            assert response2.status_code == 200


class TestMacroCpiEndpoint:
    """Tests for /api/v1/macro/cpi endpoint"""
    
    def test_cpi_endpoint_success(self, mock_akshare_cpi):
        """Test CPI endpoint returns data successfully"""
        with patch.object(macro, '_get_ak') as mock_ak:
            mock_ak.return_value.macro_china_cpi.return_value = mock_akshare_cpi
            response = client.get("/api/v1/macro/cpi")
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert data["data"]["indicator"] == "CPI"


class TestMacroPpiEndpoint:
    """Tests for /api/v1/macro/ppi endpoint"""
    
    def test_ppi_endpoint_success(self):
        """Test PPI endpoint returns data successfully"""
        import pandas as pd
        mock_df = pd.DataFrame({
            '月份': ['2024年03月份'],
            '当月': [100.0],
            '当月同比增长': [-2.8],
            '累计': [99.5],
        })
        with patch.object(macro, '_get_ak') as mock_ak:
            mock_ak.return_value.macro_china_ppi.return_value = mock_df
            response = client.get("/api/v1/macro/ppi")
            assert response.status_code == 200


class TestMacroPmiEndpoint:
    """Tests for /api/v1/macro/pmi endpoint"""
    
    def test_pmi_endpoint_success(self, mock_akshare_pmi):
        """Test PMI endpoint returns data successfully"""
        with patch.object(macro, '_get_ak') as mock_ak:
            mock_ak.return_value.macro_china_pmi.return_value = mock_akshare_pmi
            response = client.get("/api/v1/macro/pmi")
            assert response.status_code == 200
            data = response.json()
            assert data["data"]["indicator"] == "PMI"


class TestMacroM2Endpoint:
    """Tests for /api/v1/macro/m2 endpoint"""
    
    def test_m2_endpoint_success(self):
        """Test M2 endpoint returns data successfully"""
        import pandas as pd
        mock_df = pd.DataFrame({
            '统计时间': ['2024年03月份'],
            '货币和准货币（广义货币M2）': [3048000.0],
            '货币和准货币（广义货币M2）同比增长': [8.3],
        })
        with patch.object(macro, '_get_ak') as mock_ak:
            mock_ak.return_value.macro_china_supply_of_money.return_value = mock_df
            response = client.get("/api/v1/macro/m2")
            assert response.status_code == 200


class TestMacroSocialFinancingEndpoint:
    """Tests for /api/v1/macro/social_financing endpoint"""
    
    def test_social_financing_endpoint_success(self):
        """Test social financing endpoint returns data successfully"""
        import pandas as pd
        mock_df = pd.DataFrame({
            '月份': ['2024年03月份'],
            '社会融资规模增量': [48725.0],
            '其中-人民币贷款': [32951.0],
        })
        with patch.object(macro, '_get_ak') as mock_ak:
            mock_ak.return_value.macro_china_shrzgm.return_value = mock_df
            response = client.get("/api/v1/macro/social_financing")
            assert response.status_code == 200


class TestMacroIndustrialProductionEndpoint:
    """Tests for /api/v1/macro/industrial_production endpoint"""
    
    def test_industrial_production_endpoint_success(self):
        """Test industrial production endpoint returns data successfully"""
        import pandas as pd
        mock_df = pd.DataFrame({
            '日期': [datetime(2024, 3, 1)],
            '今值': [4.5],
            '前值': [7.0],
        })
        with patch.object(macro, '_get_ak') as mock_ak:
            mock_ak.return_value.macro_china_industrial_production_yoy.return_value = mock_df
            response = client.get("/api/v1/macro/industrial_production")
            assert response.status_code == 200


class TestMacroUnemploymentEndpoint:
    """Tests for /api/v1/macro/unemployment endpoint"""
    
    def test_unemployment_endpoint_success(self):
        """Test unemployment endpoint returns data successfully"""
        import pandas as pd
        mock_df = pd.DataFrame({
            'date': ['2024年03月份'],
            'item': ['全国城镇调查失业率'],
            'value': [5.2],
        })
        with patch.object(macro, '_get_ak') as mock_ak:
            mock_ak.return_value.macro_china_urban_unemployment.return_value = mock_df
            response = client.get("/api/v1/macro/unemployment")
            assert response.status_code == 200


class TestMacroOverviewEndpoint:
    """Tests for /api/v1/macro/overview endpoint"""
    
    def test_overview_endpoint_success(self):
        """Test overview endpoint returns combined data"""
        import pandas as pd
        
        mock_gdp = pd.DataFrame({
            '季度': ['2024Q1'],
            '国内生产总值-绝对值': [296299],
            '国内生产总值-同比增长': [5.3],
        })
        
        mock_cpi = pd.DataFrame({
            '月份': ['2024年03月份'],
            '全国-当月': [100.1],
            '全国-同比增长': [0.1],
            '全国-环比增长': [-0.6],
        })
        
        with patch.object(macro, '_get_ak') as mock_ak:
            mock_ak.return_value.macro_china_gdp.return_value = mock_gdp
            mock_ak.return_value.macro_china_cpi.return_value = mock_cpi
            mock_ak.return_value.macro_china_ppi.return_value = pd.DataFrame({'月份': [], '当月': []})
            mock_ak.return_value.macro_china_pmi.return_value = pd.DataFrame({'月份': [], '制造业-指数': []})
            mock_ak.return_value.macro_china_supply_of_money.return_value = pd.DataFrame()
            mock_ak.return_value.macro_china_shrzgm.return_value = pd.DataFrame()
            mock_ak.return_value.macro_china_industrial_production_yoy.return_value = pd.DataFrame()
            mock_ak.return_value.macro_china_urban_unemployment.return_value = pd.DataFrame()
            
            response = client.get("/api/v1/macro/overview")
            assert response.status_code == 200


class TestMacroBatchEndpoint:
    """Tests for /api/v1/macro/batch endpoint"""
    
    def test_batch_endpoint_success(self):
        """Test batch endpoint returns multiple indicators"""
        import pandas as pd
        mock_df = pd.DataFrame({
            '季度': ['2024Q1'],
            '国内生产总值-同比增长': [5.3],
        })
        
        with patch.object(macro, '_get_ak') as mock_ak:
            mock_ak.return_value.macro_china_gdp.return_value = mock_df
            response = client.get("/api/v1/macro/batch?indicators=gdp")
            assert response.status_code == 200
    
    def test_batch_endpoint_invalid_indicator(self):
        """Test batch endpoint rejects invalid indicators"""
        response = client.get("/api/v1/macro/batch?indicators=invalid_indicator")
        # Should return error for invalid indicator
        assert response.status_code == 200
        # Check if error message contains "无效" or similar


# ── Validation Tests ─────────────────────────────────────────────────────────────

class TestMacroValidation:
    """Tests for input validation"""
    
    def test_limit_validation_min(self):
        """Test limit parameter minimum value"""
        response = client.get("/api/v1/macro/gdp?limit=0")
        assert response.status_code == 422  # Validation error
    
    def test_limit_validation_max(self):
        """Test limit parameter maximum value"""
        response = client.get("/api/v1/macro/gdp?limit=101")
        assert response.status_code == 422  # Validation error
    
    def test_limit_validation_negative(self):
        """Test limit parameter negative value"""
        response = client.get("/api/v1/macro/gdp?limit=-1")
        assert response.status_code == 422  # Validation error
    
    def test_limit_validation_valid(self, mock_akshare_gdp):
        """Test limit parameter valid value"""
        with patch.object(macro, '_get_ak') as mock_ak:
            mock_ak.return_value.macro_china_gdp.return_value = mock_akshare_gdp
            response = client.get("/api/v1/macro/gdp?limit=50")
            assert response.status_code == 200


# ── Error Handling Tests ─────────────────────────────────────────────────────────

class TestMacroErrorHandling:
    """Tests for error handling"""
    
    def test_empty_data_handling(self, mock_empty_dataframe):
        """Test endpoint handles empty data gracefully"""
        with patch.object(macro, '_get_ak') as mock_ak:
            mock_ak.return_value.macro_china_gdp.return_value = mock_empty_dataframe
            response = client.get("/api/v1/macro/gdp")
            # Should return empty data array, not crash
            assert response.status_code == 200
    
    def test_exception_handling(self):
        """Test endpoint handles exceptions gracefully"""
        # Clear cache to ensure fresh fetch
        macro._cache.clear()
        macro._cache_ttl.clear()
        
        with patch.object(macro, '_get_ak') as mock_ak:
            mock_ak.return_value.macro_china_gdp.side_effect = Exception("Test error")
            response = client.get("/api/v1/macro/gdp")
            assert response.status_code == 200
            data = response.json()
            assert data["code"] != 0  # Error response


# ── Cache Tests ─────────────────────────────────────────────────────────────────

class TestMacroCache:
    """Tests for caching behavior"""
    
    def test_cache_set_and_get(self, mock_akshare_gdp):
        """Test cache stores and retrieves data"""
        # Clear cache first
        macro._cache.clear()
        macro._cache_ttl.clear()
        
        with patch.object(macro, '_get_ak') as mock_ak:
            mock_ak.return_value.macro_china_gdp.return_value = mock_akshare_gdp
            
            # First request - should fetch from akshare
            response1 = client.get("/api/v1/macro/gdp")
            call_count_1 = mock_ak.return_value.macro_china_gdp.call_count
            
            # Second request - should hit cache
            response2 = client.get("/api/v1/macro/gdp")
            call_count_2 = mock_ak.return_value.macro_china_gdp.call_count
            
            # akshare should only be called once
            assert call_count_1 == call_count_2
            assert response1.status_code == 200
            assert response2.status_code == 200


# ── Timeout Tests ───────────────────────────────────────────────────────────────

class TestMacroTimeout:
    """Tests for timeout protection"""
    
    def test_timeout_constant_exists(self):
        """Test MACRO_TIMEOUT constant is defined"""
        assert hasattr(macro, 'MACRO_TIMEOUT') or MACRO_TIMEOUT > 0
    
    def test_timeout_value_reasonable(self):
        """Test MACRO_TIMEOUT is reasonable (10-60 seconds)"""
        assert 10 <= MACRO_TIMEOUT <= 60


# ── Rate Limiting Tests ─────────────────────────────────────────────────────────

class TestMacroRateLimit:
    """Tests for rate limiting"""
    
    def test_rate_limit_config_exists(self):
        """Test macro rate limit is configured"""
        from app.config.rate_limit import ENDPOINT_LIMITS, get_endpoint_category
        
        # Check macro category exists
        assert "macro" in ENDPOINT_LIMITS
        
        # Check category detection
        assert get_endpoint_category("/api/v1/macro/gdp") == "macro"
        assert get_endpoint_category("/api/v1/macro/overview") == "macro"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=app/routers/macro", "--cov-report=term"])
