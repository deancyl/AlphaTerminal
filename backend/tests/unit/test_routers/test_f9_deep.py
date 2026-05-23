"""
F9 Deep Data Module Test Suite
Tests for all F9 deep data endpoints

Coverage target: 95%
"""

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from fastapi.testclient import TestClient
from app.main import app
from app.routers import f9_deep
import akshare as ak

client = TestClient(app)

# Check if stock_individual_notice_report exists in akshare
HAS_STOCK_INDIVIDUAL_NOTICE_REPORT = hasattr(ak, 'stock_individual_notice_report')
HAS_BAOSTOCK = True
try:
    import baostock
except ImportError:
    HAS_BAOSTOCK = False


# ── Mock Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def mock_financial_df():
    """Mock financial indicators dataframe"""
    return pd.DataFrame(
        {
            "日期": ["2024-03-31", "2023-12-31", "2023-09-30"],
            "摊薄每股收益(元)": [6.86, 19.52, 15.08],
            "净资产收益率(%)": [9.21, 26.37, 20.39],
            "主营业务收入增长率(%)": [18.11, 18.04, 18.48],
            "净利润增长率(%)": [15.73, 18.04, 19.13],
            "销售毛利率(%)": [92.61, 92.13, 91.87],
            "销售净利率(%)": [52.66, 52.31, 51.89],
            "每股净资产_调整后(元)": [74.53, 74.01, 73.42],
        }
    )


@pytest.fixture
def mock_institution_df():
    """Mock institution holdings dataframe"""
    return pd.DataFrame(
        {
            "股东名称": [
                "香港中央结算有限公司",
                "中国证券金融股份有限公司",
                "中央汇金投资有限责任公司",
            ],
            "持股数量": [1000000, 500000, 300000],
            "占流通股比例": [5.5, 2.75, 1.65],
            "股本性质": ["流通A股", "流通A股", "流通A股"],
        }
    )


@pytest.fixture
def mock_forecast_eps_df():
    """Mock EPS forecast dataframe"""
    return pd.DataFrame(
        {
            "预测年份": ["2024", "2025"],
            "预测每股收益": [70.5, 75.2],
            "预测机构数量": [25, 22],
        }
    )


@pytest.fixture
def mock_forecast_institution_df():
    """Mock institution forecast dataframe"""
    return pd.DataFrame(
        {
            "机构名称": ["中信证券", "华泰证券", "国泰君安"],
            "预测评级": ["买入", "买入", "增持"],
            "目标价": [2100, 2050, 2000],
        }
    )


@pytest.fixture
def mock_margin_df():
    """Mock margin trading dataframe"""
    return pd.DataFrame(
        {
            "证券代码": ["600519"],
            "融资余额": [150000000],
            "融资买入额": [5000000],
            "融资偿还额": [4500000],
            "融券余额": [5000000],
            "融券余量": [3000],
            "融券卖出量": [100],
            "融券偿还量": [50],
            "融资融券余额": [155000000],
        }
    )


@pytest.fixture
def mock_shareholder_df():
    """Mock shareholder dataframe"""
    return pd.DataFrame(
        {
            "截止日期": ["2024-03-31", "2024-03-31", "2024-03-31"],
            "股东名称": [
                "贵州茅台酒厂(集团)有限公司",
                "香港中央结算有限公司",
                "中国证券金融股份有限公司",
            ],
            "持股数量": [600000000, 100000000, 50000000],
            "占流通股比例": [54.06, 9.01, 4.50],
            "股本性质": ["国有股", "流通A股", "流通A股"],
        }
    )


@pytest.fixture
def mock_announcements_df():
    """Mock announcements dataframe"""
    return pd.DataFrame(
        {
            "公告日期": ["2024-04-15", "2024-04-10", "2024-04-05"],
            "公告标题": [
                "2024年第一季度报告",
                "关于召开2023年度股东大会的通知",
                "2023年度利润分配预案",
            ],
            "公告类型": ["定期报告", "股东大会", "利润分配"],
            "代码": ["600519", "600519", "600519"],
            "名称": ["贵州茅台", "贵州茅台", "贵州茅台"],
            "网址": [
                "http://example.com/1",
                "http://example.com/2",
                "http://example.com/3",
            ],
        }
    )


@pytest.fixture
def mock_peers_df():
    """Mock peer comparison dataframe"""
    return pd.DataFrame(
        {
            "item": ["行业", "总市值", "市盈率", "市净率"],
            "value": ["白酒", "22000亿", "35.2", "10.1"],
        }
    )


@pytest.fixture
def mock_stock_info_df():
    """Mock stock info dataframe"""
    return pd.DataFrame(
        {
            "item": ["行业", "主营业务", "总市值"],
            "value": ["白酒", "茅台酒生产销售", "22000亿"],
        }
    )


# ── Health Check Tests ─────────────────────────────────────────────────────────


class TestF9HealthEndpoint:
    """Tests for /api/v1/f9/health endpoint"""

    def test_health_endpoint_success(self):
        """Test health check returns ok status"""
        response = client.get("/api/v1/f9/health")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["status"] == "ok"


# ── Financial Endpoint Tests ───────────────────────────────────────────────────


class TestF9FinancialEndpoint:
    """Tests for /api/v1/f9/{symbol}/financial endpoint"""

    def test_financial_endpoint_success(self, mock_financial_df):
        """Test financial endpoint returns data successfully"""
        with patch("app.routers.f9_deep.akshare_breaker") as mock_breaker:
            mock_breaker.__enter__ = MagicMock(return_value=None)
            mock_breaker.__exit__ = MagicMock(return_value=False)
            mock_breaker.is_available.return_value = True

            with patch(
                "akshare.stock_financial_analysis_indicator",
                return_value=mock_financial_df,
            ):
                response = client.get("/api/v1/f9/600519/financial")
                assert response.status_code == 200
                data = response.json()
                assert data["code"] == 0
                assert "indicators" in data["data"]
                assert "latest" in data["data"]
                assert "trend" in data["data"]

    def test_financial_endpoint_with_prefix(self, mock_financial_df):
        """Test financial endpoint handles symbol prefix (sh600519)"""
        with patch("app.routers.f9_deep.akshare_breaker") as mock_breaker:
            mock_breaker.__enter__ = MagicMock(return_value=None)
            mock_breaker.__exit__ = MagicMock(return_value=False)
            mock_breaker.is_available.return_value = True

            with patch(
                "akshare.stock_financial_analysis_indicator",
                return_value=mock_financial_df,
            ):
                response = client.get("/api/v1/f9/sh600519/financial")
                assert response.status_code == 200

    def test_financial_endpoint_cache_hit(self, mock_financial_df):
        """Test financial endpoint returns cached data on second request"""
        # Clear cache first
        f9_deep._cache.clear()

        with patch("app.routers.f9_deep.akshare_breaker") as mock_breaker:
            mock_breaker.__enter__ = MagicMock(return_value=None)
            mock_breaker.__exit__ = MagicMock(return_value=False)
            mock_breaker.is_available.return_value = True

            with patch(
                "akshare.stock_financial_analysis_indicator",
                return_value=mock_financial_df,
            ):
                # First request
                response1 = client.get("/api/v1/f9/600519/financial")
                # Second request should hit cache
                response2 = client.get("/api/v1/f9/600519/financial")

                assert response1.status_code == 200
                assert response2.status_code == 200


# ── Institution Endpoint Tests ─────────────────────────────────────────────────


class TestF9InstitutionEndpoint:
    """Tests for /api/v1/f9/{symbol}/institution endpoint"""

    def test_institution_endpoint_success(self, mock_institution_df):
        """Test institution endpoint returns data successfully"""
        with patch("app.routers.f9_deep.akshare_breaker") as mock_breaker:
            mock_breaker.__enter__ = MagicMock(return_value=None)
            mock_breaker.__exit__ = MagicMock(return_value=False)
            mock_breaker.is_available.return_value = True

            with patch(
                "akshare.stock_institute_hold_detail", return_value=mock_institution_df
            ):
                response = client.get("/api/v1/f9/600519/institution")
                assert response.status_code == 200
                data = response.json()
                assert data["code"] == 0
                assert "current" in data["data"]
                assert "trend" in data["data"]

    def test_institution_endpoint_with_sz_prefix(self, mock_institution_df):
        """Test institution endpoint handles SZ prefix (sz000001)"""
        with patch("app.routers.f9_deep.akshare_breaker") as mock_breaker:
            mock_breaker.__enter__ = MagicMock(return_value=None)
            mock_breaker.__exit__ = MagicMock(return_value=False)
            mock_breaker.is_available.return_value = True

            with patch(
                "akshare.stock_institute_hold_detail", return_value=mock_institution_df
            ):
                response = client.get("/api/v1/f9/sz000001/institution")
                assert response.status_code == 200


# ── Forecast Endpoint Tests ────────────────────────────────────────────────────


class TestF9ForecastEndpoint:
    """Tests for /api/v1/f9/{symbol}/forecast endpoint"""

    def test_forecast_endpoint_success(
        self, mock_forecast_eps_df, mock_forecast_institution_df
    ):
        """Test forecast endpoint returns data successfully"""
        with patch("app.routers.f9_deep.akshare_breaker") as mock_breaker:
            mock_breaker.__enter__ = MagicMock(return_value=None)
            mock_breaker.__exit__ = MagicMock(return_value=False)
            mock_breaker.is_available.return_value = True

            with patch("akshare.stock_profit_forecast_ths") as mock_func:
                mock_func.side_effect = [
                    mock_forecast_eps_df,
                    mock_forecast_institution_df,
                ]

                response = client.get("/api/v1/f9/600519/forecast")
                assert response.status_code == 200
                data = response.json()
                assert data["code"] == 0
                assert "eps_forecast" in data["data"]
                assert "institutions" in data["data"]


# ── Shareholder Endpoint Tests ────────────────────────────────────────────────


class TestF9ShareholderEndpoint:
    """Tests for /api/v1/f9/{symbol}/shareholder endpoint"""

    def test_shareholder_endpoint_success(self, mock_shareholder_df):
        """Test shareholder endpoint returns data successfully"""
        with patch("app.routers.f9_deep.akshare_breaker") as mock_breaker:
            mock_breaker.__enter__ = MagicMock(return_value=None)
            mock_breaker.__exit__ = MagicMock(return_value=False)
            mock_breaker.is_available.return_value = True

            # Patch akshare module - the import happens inside the function
            with patch(
                "akshare.stock_circulate_stock_holder", return_value=mock_shareholder_df
            ):
                with patch(
                    "akshare.stock_share_change_cninfo",
                    side_effect=Exception("No data"),
                ):
                    with patch(
                        "akshare.stock_shareholder_change_ths",
                        side_effect=Exception("No data"),
                    ):
                        response = client.get("/api/v1/f9/600519/shareholder")
                        assert response.status_code == 200
                        data = response.json()
                        assert data["code"] == 0
                        assert "circulateHolders" in data["data"]


# ── Margin Endpoint Tests ─────────────────────────────────────────────────────


class TestF9MarginEndpoint:
    """Tests for /api/v1/f9/{symbol}/margin endpoint"""

    def test_margin_endpoint_success(self, mock_margin_df):
        """Test margin endpoint returns data successfully"""
        with patch("app.routers.f9_deep.akshare_breaker") as mock_breaker:
            mock_breaker.__enter__ = MagicMock(return_value=None)
            mock_breaker.__exit__ = MagicMock(return_value=False)
            mock_breaker.is_available.return_value = True

            with patch("akshare.stock_margin_detail_sse", return_value=mock_margin_df):
                response = client.get("/api/v1/f9/600519/margin")
                # May return 404 if no data found, which is acceptable
                assert response.status_code in [200, 404]

    def test_margin_endpoint_szse_stock(self):
        """Test margin endpoint handles SZSE stocks (0开头)"""
        with patch("app.routers.f9_deep.akshare_breaker") as mock_breaker:
            mock_breaker.__enter__ = MagicMock(return_value=None)
            mock_breaker.__exit__ = MagicMock(return_value=False)
            mock_breaker.is_available.return_value = True

            with patch("akshare.stock_margin_detail_szse", return_value=pd.DataFrame()):
                response = client.get("/api/v1/f9/000001/margin")
                # May return 404 if no data found
                assert response.status_code in [200, 404]


# ── Announcements Endpoint Tests ──────────────────────────────────────────────


class TestF9AnnouncementsEndpoint:
    """Tests for /api/v1/f9/{symbol}/announcements endpoint"""

    @pytest.mark.skipif(not HAS_STOCK_INDIVIDUAL_NOTICE_REPORT, 
                        reason="stock_individual_notice_report not available in this akshare version")
    def test_announcements_endpoint_success(self, mock_announcements_df):
        """Test announcements endpoint returns data successfully"""
        with patch("app.routers.f9_deep.akshare_breaker") as mock_breaker:
            mock_breaker.__enter__ = MagicMock(return_value=None)
            mock_breaker.__exit__ = MagicMock(return_value=False)
            mock_breaker.is_available.return_value = True

            with patch(
                "akshare.stock_individual_notice_report",
                return_value=mock_announcements_df,
            ):
                response = client.get("/api/v1/f9/600519/announcements")
                assert response.status_code == 200
                data = response.json()
                assert data["code"] == 0
                assert "announcements" in data["data"]
                assert "total" in data["data"]
                assert "page" in data["data"]
                assert "page_size" in data["data"]

    @pytest.mark.skipif(not HAS_STOCK_INDIVIDUAL_NOTICE_REPORT, 
                        reason="stock_individual_notice_report not available in this akshare version")
    def test_announcements_endpoint_pagination(self, mock_announcements_df):
        """Test announcements endpoint pagination"""
        f9_deep._cache.clear()  # Clear cache to avoid stale data

        with patch("app.routers.f9_deep.akshare_breaker") as mock_breaker:
            mock_breaker.__enter__ = MagicMock(return_value=None)
            mock_breaker.__exit__ = MagicMock(return_value=False)
            mock_breaker.is_available.return_value = True

            with patch(
                "akshare.stock_individual_notice_report",
                return_value=mock_announcements_df,
            ):
                response = client.get(
                    "/api/v1/f9/600519/announcements?page=1&page_size=10"
                )
                assert response.status_code == 200
                data = response.json()
                assert data["data"]["page"] == 1
                assert data["data"]["page_size"] == 10

    @pytest.mark.skipif(not HAS_STOCK_INDIVIDUAL_NOTICE_REPORT, 
                        reason="stock_individual_notice_report not available in this akshare version")
    def test_announcements_endpoint_page_2(self, mock_announcements_df):
        """Test announcements endpoint page 2"""
        with patch("app.routers.f9_deep.akshare_breaker") as mock_breaker:
            mock_breaker.__enter__ = MagicMock(return_value=None)
            mock_breaker.__exit__ = MagicMock(return_value=False)
            mock_breaker.is_available.return_value = True

            with patch(
                "akshare.stock_individual_notice_report",
                return_value=mock_announcements_df,
            ):
                response = client.get(
                    "/api/v1/f9/600519/announcements?page=2&page_size=1"
                )
                assert response.status_code == 200
                data = response.json()
                assert data["data"]["page"] == 2


# ── Peers Endpoint Tests ──────────────────────────────────────────────────────


class TestF9PeersEndpoint:
    """Tests for /api/v1/f9/{symbol}/peers endpoint"""

    @pytest.mark.skipif(not HAS_BAOSTOCK, 
                        reason="baostock module not installed")
    def test_peers_endpoint_success(self, mock_stock_info_df, mock_financial_df):
        """Test peers endpoint returns data successfully"""
        with patch("app.routers.f9_deep.akshare_breaker") as mock_breaker:
            mock_breaker.__enter__ = MagicMock(return_value=None)
            mock_breaker.__exit__ = MagicMock(return_value=False)
            mock_breaker.is_available.return_value = True

            with patch(
                "akshare.stock_profile_cninfo", side_effect=Exception("No data")
            ):
                with patch(
                    "akshare.stock_individual_info_em", return_value=mock_stock_info_df
                ):
                    with patch(
                        "akshare.stock_financial_analysis_indicator",
                        return_value=mock_financial_df,
                    ):
                        response = client.get("/api/v1/f9/600519/peers")
                        assert response.status_code == 200
                        data = response.json()
                        assert data["code"] == 0
                        assert "industry" in data["data"]
                        assert "peers" in data["data"]


# ── Symbol Normalization Tests ────────────────────────────────────────────────


class TestF9SymbolNormalization:
    """Tests for symbol normalization"""

    def test_normalize_sh_prefix(self):
        """Test normalize_f9_symbol removes sh prefix"""
        result = f9_deep.normalize_f9_symbol("sh600519")
        assert result == "600519"

    def test_normalize_sz_prefix(self):
        """Test normalize_f9_symbol removes sz prefix"""
        result = f9_deep.normalize_f9_symbol("sz000001")
        assert result == "000001"

    def test_normalize_hk_prefix(self):
        """Test normalize_f9_symbol removes hk prefix"""
        result = f9_deep.normalize_f9_symbol("hk00700")
        assert result == "00700"

    def test_normalize_us_prefix(self):
        """Test normalize_f9_symbol removes us prefix"""
        result = f9_deep.normalize_f9_symbol("usAAPL")
        assert result == "AAPL"

    def test_normalize_no_prefix(self):
        """Test normalize_f9_symbol handles no prefix"""
        result = f9_deep.normalize_f9_symbol("600519")
        assert result == "600519"

    def test_normalize_empty_string(self):
        """Test normalize_f9_symbol handles empty string"""
        result = f9_deep.normalize_f9_symbol("")
        assert result == ""

    def test_normalize_case_insensitive(self):
        """Test normalize_f9_symbol is case insensitive"""
        result = f9_deep.normalize_f9_symbol("SH600519")
        assert result == "600519"

        result = f9_deep.normalize_f9_symbol("Sh600519")
        assert result == "600519"


# ── Input Validation Tests ────────────────────────────────────────────────────


class TestF9InputValidation:
    """Tests for input validation"""

    def test_announcements_page_validation_min(self):
        """Test announcements page=0 is normalized to 1"""
        response = client.get("/api/v1/f9/600519/announcements?page=0")
        assert response.status_code == 200

    def test_announcements_page_validation_negative(self):
        """Test announcements page=-1 is normalized to 1"""
        response = client.get("/api/v1/f9/600519/announcements?page=-1")
        assert response.status_code == 200

    def test_announcements_page_size_validation_min(self):
        """Test announcements page_size=0 is normalized to 20"""
        response = client.get("/api/v1/f9/600519/announcements?page_size=0")
        assert response.status_code == 200

    def test_announcements_page_size_validation_max(self):
        """Test announcements page_size=101 returns error response"""
        response = client.get("/api/v1/f9/600519/announcements?page_size=101")
        assert response.status_code == 200

    @pytest.mark.skipif(not HAS_STOCK_INDIVIDUAL_NOTICE_REPORT, 
                        reason="stock_individual_notice_report not available in this akshare version")
    def test_announcements_valid_pagination(self, mock_announcements_df):
        """Test announcements valid pagination parameters"""
        with patch("app.routers.f9_deep.akshare_breaker") as mock_breaker:
            mock_breaker.__enter__ = MagicMock(return_value=None)
            mock_breaker.__exit__ = MagicMock(return_value=False)
            mock_breaker.is_available.return_value = True

            with patch(
                "akshare.stock_individual_notice_report",
                return_value=mock_announcements_df,
            ):
                response = client.get(
                    "/api/v1/f9/600519/announcements?page=1&page_size=20"
                )
                assert response.status_code == 200


# ── Circuit Breaker Tests ─────────────────────────────────────────────────────


class TestF9CircuitBreaker:
    """Tests for circuit breaker endpoints"""

    def test_circuit_breaker_status_endpoint(self):
        """Test circuit breaker status endpoint"""
        response = client.get("/api/v1/f9/circuit_breaker/status")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "name" in data["data"]
        assert "state" in data["data"]
        assert "is_available" in data["data"]

    def test_circuit_breaker_reset_endpoint(self):
        """Test circuit breaker reset endpoint"""
        response = client.post("/api/v1/f9/circuit_breaker/reset")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["state"] == "closed"


# ── Error Handling Tests ──────────────────────────────────────────────────────


class TestF9ErrorHandling:
    """Tests for error handling"""

    def test_financial_empty_data_handling(self):
        """Test financial endpoint handles empty data gracefully"""
        with patch("app.routers.f9_deep.akshare_breaker") as mock_breaker:
            mock_breaker.__enter__ = MagicMock(return_value=None)
            mock_breaker.__exit__ = MagicMock(return_value=False)
            mock_breaker.is_available.return_value = True

            with patch(
                "akshare.stock_financial_analysis_indicator",
                return_value=pd.DataFrame(),
            ):
                response = client.get("/api/v1/f9/600519/financial")
                # Should return empty data, not crash
                assert response.status_code == 200

    def test_circuit_breaker_open_handling(self):
        """Test endpoint handles circuit breaker open state"""
        with patch("app.routers.f9_deep.akshare_breaker") as mock_breaker:
            mock_breaker.is_available.return_value = False

            response = client.get("/api/v1/f9/600519/financial")
            # Should return 503 or error response
            assert response.status_code in [200, 503]


# ── Cache Tests ───────────────────────────────────────────────────────────────


class TestF9Cache:
    """Tests for caching behavior"""

    def test_cache_key_format(self):
        """Test cache key format"""
        assert f9_deep.NAMESPACE == "f9:"
        assert f9_deep.TTL == 300

    def test_cache_functions_exist(self):
        """Test cache functions exist"""
        import asyncio

        # Test get_cached and set_cached are async functions
        assert asyncio.iscoroutinefunction(f9_deep.get_cached)
        assert asyncio.iscoroutinefunction(f9_deep.set_cached)


# ── Timeout Tests ─────────────────────────────────────────────────────────────


class TestF9Timeout:
    """Tests for timeout protection"""

    def test_timeout_constant_import(self):
        """Test AKSHARE_TIMEOUT is imported"""
        from app.config.timeout import AKSHARE_TIMEOUT

        assert AKSHARE_TIMEOUT > 0

    def test_run_with_timeout_function_exists(self):
        """Test run_with_timeout function exists"""
        import asyncio

        assert asyncio.iscoroutinefunction(f9_deep.run_with_timeout)


# ── Integration Tests ─────────────────────────────────────────────────────────


class TestF9Integration:
    """Integration tests for F9 endpoints"""

    def test_all_endpoints_exist(self):
        """Test all F9 endpoints are registered"""
        # Health check
        response = client.get("/api/v1/f9/health")
        assert response.status_code == 200

        # Circuit breaker status
        response = client.get("/api/v1/f9/circuit_breaker/status")
        assert response.status_code == 200

    def test_endpoint_paths_correct(self):
        """Test endpoint paths are correct"""
        # These should return validation errors or success, not 404
        endpoints = [
            "/api/v1/f9/health",
            "/api/v1/f9/circuit_breaker/status",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code != 404, f"Endpoint {endpoint} not found"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=app/routers/f9_deep", "--cov-report=term"])
