"""
Tests for fund router.

Covers the following endpoints:
- GET /fund/etf/info - ETF实时行情
- GET /fund/etf/history - ETF历史K线
- GET /fund/open/info - 场外公募基金信息
- GET /fund/open/rank - 场外基金排行
- GET /fund/portfolio/{code} - 基金投资组合
- GET /fund/open/nav/{code} - 场外基金净值历史
- GET /fund/open/returns/{code} - 基金阶段收益
- GET /fund/open/risk/{code} - 基金风险指标
- GET /fund/open/full/{code} - 并发完整数据
- GET /fund/money/rank - 货币基金排行
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock

from app.main import app


client = TestClient(app)


class TestETFEndpoints:
    """Test cases for ETF endpoints."""

    @patch('app.routers.fund.fetcher.get_etf_info', new_callable=AsyncMock)
    def test_etf_info_endpoint(self, mock_get_etf_info):
        """Test GET /fund/etf/info endpoint."""
        mock_get_etf_info.return_value = {
            'source': 'mock',
            'code': '510300',
            'name': '沪深300ETF',
            'price': 4.123,
            'change_pct': 1.5,
            'volume': 1000000,
        }

        response = client.get("/api/v1/fund/etf/info?code=510300")
        assert response.status_code == 200
        data = response.json()
        assert data.get("code") == 0
        assert "data" in data
        assert data["data"]["code"] == "510300"

    @patch('app.routers.fund.fetcher.get_etf_info', new_callable=AsyncMock)
    def test_etf_info_not_found(self, mock_get_etf_info):
        """Test ETF info endpoint with invalid code."""
        mock_get_etf_info.return_value = None

        response = client.get("/api/v1/fund/etf/info?code=000000")
        assert response.status_code == 400

    def test_etf_info_missing_code(self):
        """Test ETF info endpoint without code parameter."""
        response = client.get("/api/v1/fund/etf/info")
        assert response.status_code == 422

    @patch('app.routers.fund.fetcher.get_etf_history', new_callable=AsyncMock)
    def test_etf_history_endpoint(self, mock_get_etf_history):
        """Test GET /fund/etf/history endpoint."""
        mock_get_etf_history.return_value = [
            {'date': '2024-01-01', 'open': 4.0, 'close': 4.1, 'high': 4.2, 'low': 3.9, 'volume': 1000000},
            {'date': '2024-01-02', 'open': 4.1, 'close': 4.2, 'high': 4.3, 'low': 4.0, 'volume': 1200000},
        ]

        response = client.get("/api/v1/fund/etf/history?code=510300&period=daily&limit=300")
        assert response.status_code == 200
        data = response.json()
        assert data.get("code") == 0
        assert "data" in data
        assert isinstance(data["data"], list)

    @patch('app.routers.fund.fetcher.get_etf_history', new_callable=AsyncMock)
    def test_etf_history_empty(self, mock_get_etf_history):
        """Test ETF history endpoint with empty result."""
        mock_get_etf_history.return_value = []

        response = client.get("/api/v1/fund/etf/history?code=510300")
        assert response.status_code == 200
        data = response.json()
        assert data.get("code") == 0
        assert data["data"] == []


class TestOpenFundEndpoints:
    """Test cases for open fund endpoints."""

    @patch('app.routers.fund.fetcher.get_fund_info', new_callable=AsyncMock)
    def test_open_fund_info_endpoint(self, mock_get_fund_info):
        """Test GET /fund/open/info endpoint."""
        mock_get_fund_info.return_value = {
            'source': 'mock',
            'code': '110011',
            'name': '易方达中小盘',
            'nav': 5.6789,
            'nav_change_pct': 2.34,
            'type': '混合型',
        }

        response = client.get("/api/v1/fund/open/info?code=110011")
        assert response.status_code == 200
        data = response.json()
        assert data.get("code") == 0
        assert data["data"]["code"] == "110011"
        assert data["data"]["name"] == "易方达中小盘"

    @patch('app.routers.fund.fetcher.get_fund_info', new_callable=AsyncMock)
    def test_open_fund_info_not_found(self, mock_get_fund_info):
        """Test open fund info endpoint with invalid code."""
        mock_get_fund_info.return_value = None

        response = client.get("/api/v1/fund/open/info?code=000000")
        assert response.status_code == 400

    @patch('app.routers.fund.fetcher.get_fund_rank', new_callable=AsyncMock)
    def test_open_fund_rank_endpoint(self, mock_get_fund_rank):
        """Test GET /fund/open/rank endpoint."""
        mock_get_fund_rank.return_value = [
            {'code': '110011', 'name': '易方达中小盘', 'nav': 5.6789, 'nav_growthrate': 2.34},
            {'code': '000001', 'name': '华夏成长', 'nav': 1.2345, 'nav_growthrate': 1.56},
        ]

        response = client.get("/api/v1/fund/open/rank?type=股票型&limit=100")
        assert response.status_code == 200
        data = response.json()
        assert data.get("code") == 0
        assert isinstance(data["data"], list)
        assert len(data["data"]) == 2

    @patch('app.routers.fund.fetcher.get_fund_rank', new_callable=AsyncMock)
    def test_open_fund_rank_empty(self, mock_get_fund_rank):
        """Test open fund rank endpoint with empty result."""
        mock_get_fund_rank.return_value = []

        response = client.get("/api/v1/fund/open/rank")
        assert response.status_code == 200
        data = response.json()
        assert data.get("code") == 0
        assert data["data"] == []


class TestFundPortfolioEndpoint:
    """Test cases for fund portfolio endpoint."""

    @patch('app.routers.fund.fetcher.get_fund_portfolio', new_callable=AsyncMock)
    def test_fund_portfolio_endpoint(self, mock_get_fund_portfolio):
        """Test GET /fund/portfolio/{code} endpoint."""
        mock_get_fund_portfolio.return_value = {
            'source': 'mock',
            'code': '110011',
            'quarter': '2024年1季度',
            'stocks': [
                {'code': '600519', 'name': '贵州茅台', 'ratio': 5.89},
                {'code': '300750', 'name': '宁德时代', 'ratio': 2.78},
            ],
            'assets': [
                {'name': '股票', 'ratio': 85.5},
                {'name': '债券', 'ratio': 5.2},
            ],
        }

        response = client.get("/api/v1/fund/portfolio/110011")
        assert response.status_code == 200
        data = response.json()
        assert data.get("code") == 0
        assert "stocks" in data["data"]
        assert "assets" in data["data"]
        assert len(data["data"]["stocks"]) == 2

    @patch('app.routers.fund.fetcher.get_fund_portfolio', new_callable=AsyncMock)
    def test_fund_portfolio_empty(self, mock_get_fund_portfolio):
        """Test fund portfolio endpoint with empty result."""
        mock_get_fund_portfolio.return_value = None

        response = client.get("/api/v1/fund/portfolio/110011")
        assert response.status_code == 200
        data = response.json()
        assert data.get("code") == 0
        assert data["data"]["stocks"] == []
        assert data["data"]["assets"] == []


class TestFundNAVEndpoint:
    """Test cases for fund NAV history endpoint."""

    @patch('app.routers.fund.fetcher.get_fund_nav_history', new_callable=AsyncMock)
    def test_fund_nav_history_endpoint(self, mock_get_fund_nav_history):
        """Test GET /fund/open/nav/{code} endpoint."""
        mock_get_fund_nav_history.return_value = [
            {'date': '2024-01-01', 'nav': 5.0, 'accumulated_nav': 5.5},
            {'date': '2024-01-02', 'nav': 5.1, 'accumulated_nav': 5.6},
        ]

        response = client.get("/api/v1/fund/open/nav/110011?period=6m")
        assert response.status_code == 200
        data = response.json()
        assert data.get("code") == 0
        assert isinstance(data["data"], list)
        assert len(data["data"]) == 2
        assert "nav" in data["data"][0]

    @patch('app.routers.fund.fetcher.get_fund_nav_history', new_callable=AsyncMock)
    def test_fund_nav_history_empty(self, mock_get_fund_nav_history):
        """Test fund NAV history endpoint with empty result."""
        mock_get_fund_nav_history.return_value = []

        response = client.get("/api/v1/fund/open/nav/110011")
        assert response.status_code == 200
        data = response.json()
        assert data.get("code") == 0
        assert data["data"] == []


class TestFundReturnsEndpoint:
    """Test cases for fund returns endpoint."""

    @patch('app.routers.fund.fetcher.get_fund_returns', new_callable=AsyncMock)
    def test_fund_returns_endpoint(self, mock_get_fund_returns):
        """Test GET /fund/open/returns/{code} endpoint."""
        mock_get_fund_returns.return_value = {
            'source': 'mock',
            'code': '110011',
            'name': '易方达中小盘',
            'returns': {
                '1w': 1.23,
                '1m': 3.45,
                '3m': 8.90,
                '6m': 12.34,
                '1y': 25.67,
            },
        }

        response = client.get("/api/v1/fund/open/returns/110011")
        assert response.status_code == 200
        data = response.json()
        assert data.get("code") == 0
        assert "returns" in data["data"]
        assert "1w" in data["data"]["returns"]
        assert "1y" in data["data"]["returns"]

    @patch('app.routers.fund.fetcher.get_fund_returns', new_callable=AsyncMock)
    def test_fund_returns_structure(self, mock_get_fund_returns):
        """Test fund returns response structure."""
        mock_get_fund_returns.return_value = {
            'source': 'mock',
            'code': '110011',
            'returns': {
                '1w': 1.0,
                '1m': 2.0,
                '3m': 3.0,
                '6m': 5.0,
                '1y': 10.0,
                '2y': 20.0,
                '3y': 30.0,
                'ytd': 8.0,
                'since_inception': 150.0,
            },
        }

        response = client.get("/api/v1/fund/open/returns/110011")
        assert response.status_code == 200
        data = response.json()
        returns = data["data"]["returns"]
        expected_keys = ['1w', '1m', '3m', '6m', '1y', '2y', '3y', 'ytd', 'since_inception']
        for key in expected_keys:
            assert key in returns


class TestFundRiskEndpoint:
    """Test cases for fund risk metrics endpoint."""

    @patch('app.routers.fund.fetcher.get_fund_risk_metrics', new_callable=AsyncMock)
    def test_fund_risk_endpoint(self, mock_get_fund_risk_metrics):
        """Test GET /fund/open/risk/{code} endpoint."""
        mock_get_fund_risk_metrics.return_value = {
            'source': 'mock',
            'code': '110011',
            'sharpe': 1.25,
            'max_drawdown': -15.5,
            'alpha': 3.5,
            'beta': 0.85,
            'volatility': 18.5,
        }

        response = client.get("/api/v1/fund/open/risk/110011")
        assert response.status_code == 200
        data = response.json()
        assert data.get("code") == 0
        assert "sharpe" in data["data"]
        assert "max_drawdown" in data["data"]
        assert "alpha" in data["data"]
        assert "beta" in data["data"]
        assert "volatility" in data["data"]

    @patch('app.routers.fund.fetcher.get_fund_risk_metrics', new_callable=AsyncMock)
    def test_fund_risk_values(self, mock_get_fund_risk_metrics):
        """Test fund risk metrics values are numeric."""
        mock_get_fund_risk_metrics.return_value = {
            'source': 'mock',
            'code': '110011',
            'sharpe': 1.25,
            'max_drawdown': -15.5,
            'alpha': 3.5,
            'beta': 0.85,
            'volatility': 18.5,
        }

        response = client.get("/api/v1/fund/open/risk/110011")
        assert response.status_code == 200
        data = response.json()
        metrics = data["data"]
        assert isinstance(metrics["sharpe"], (int, float))
        assert isinstance(metrics["max_drawdown"], (int, float))
        assert isinstance(metrics["alpha"], (int, float))
        assert isinstance(metrics["beta"], (int, float))
        assert isinstance(metrics["volatility"], (int, float))


class TestFundFullDataEndpoint:
    """Test cases for fund full data endpoint."""

    @patch('app.routers.fund.fetcher.get_fund_full_data', new_callable=AsyncMock)
    def test_fund_full_data_endpoint(self, mock_get_fund_full_data):
        """Test GET /fund/open/full/{code} endpoint."""
        mock_get_fund_full_data.return_value = {
            'info': {'code': '110011', 'name': '易方达中小盘', 'nav': 5.6789},
            'nav_history': [
                {'date': '2024-01-01', 'nav': 5.0},
                {'date': '2024-01-02', 'nav': 5.1},
            ],
            'portfolio': {
                'stocks': [{'code': '600519', 'name': '贵州茅台'}],
                'assets': [{'name': '股票', 'ratio': 85.5}],
            },
        }

        response = client.get("/api/v1/fund/open/full/110011?period=6m")
        assert response.status_code == 200
        data = response.json()
        assert data.get("code") == 0
        assert "info" in data["data"]
        assert "nav_history" in data["data"]
        assert "portfolio" in data["data"]

    @patch('app.routers.fund.fetcher.get_fund_full_data', new_callable=AsyncMock)
    def test_fund_full_data_partial(self, mock_get_fund_full_data):
        """Test fund full data with partial results."""
        mock_get_fund_full_data.return_value = {
            'info': None,
            'nav_history': [],
            'portfolio': None,
        }

        response = client.get("/api/v1/fund/open/full/110011")
        assert response.status_code == 200
        data = response.json()
        assert data.get("code") == 0


class TestMoneyFundRankEndpoint:
    """Test cases for money fund rank endpoint."""

    def test_money_fund_rank_endpoint(self):
        """Test GET /fund/money/rank endpoint."""
        response = client.get("/api/v1/fund/money/rank?limit=50")
        assert response.status_code == 200
        data = response.json()
        assert data.get("code") == 0
        assert "data" in data
        assert isinstance(data["data"], list)

    def test_money_fund_rank_pagination(self):
        """Test money fund rank with different limits."""
        response = client.get("/api/v1/fund/money/rank?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data.get("code") == 0
        assert isinstance(data["data"], list)


class TestFundResponseStructure:
    """Test cases for response structure consistency."""

    @patch('app.routers.fund.fetcher.get_etf_info', new_callable=AsyncMock)
    def test_response_has_timestamp(self, mock_get_etf_info):
        """Test that responses include timestamp."""
        mock_get_etf_info.return_value = {
            'source': 'mock',
            'code': '510300',
            'name': '沪深300ETF',
        }

        response = client.get("/api/v1/fund/etf/info?code=510300")
        assert response.status_code == 200
        data = response.json()
        assert "timestamp" in data

    @patch('app.routers.fund.fetcher.get_etf_info', new_callable=AsyncMock)
    def test_response_has_perf(self, mock_get_etf_info):
        """Test that responses include performance metrics."""
        mock_get_etf_info.return_value = {
            'source': 'mock',
            'code': '510300',
            'name': '沪深300ETF',
        }

        response = client.get("/api/v1/fund/etf/info?code=510300")
        assert response.status_code == 200
        data = response.json()
        assert "_perf" in data
        assert "elapsed_s" in data["_perf"]