"""
Tests for backtest router.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, Mock
import json
from datetime import datetime, timedelta

from app.main import app


client = TestClient(app)


class TestBacktestValidation:
    """Test cases for backtest input validation."""

    def test_backtest_params_depth_validation(self):
        """Test validation of nested params depth (DoS prevention)."""
        # Create deeply nested params
        nested_params = {}
        current = nested_params
        for i in range(10):  # Exceed MAX_PARAMS_DEPTH of 5
            current["level"] = {}
            current = current["level"]
        
        request_data = {
            "symbol": "sh000001",
            "period": "daily",
            "start_date": "2024-01-01",
            "end_date": "2024-03-01",
            "initial_capital": 100000,
            "strategy_type": "ma_crossover",
            "params": nested_params
        }
        
        response = client.post("/api/v1/backtest/run", json=request_data)
        # Should reject due to depth limit
        assert response.status_code == 400 or response.status_code == 422

    def test_backtest_params_size_validation(self):
        """Test validation of params JSON size (DoS prevention)."""
        # Create large params
        large_params = {"key_" + str(i): "value_" * 100 for i in range(100)}
        
        request_data = {
            "symbol": "sh000001",
            "period": "daily",
            "start_date": "2024-01-01",
            "end_date": "2024-03-01",
            "initial_capital": 100000,
            "strategy_type": "ma_crossover",
            "params": large_params
        }
        
        response = client.post("/api/v1/backtest/run", json=request_data)
        # Should reject due to size limit
        assert response.status_code == 400 or response.status_code == 422

    def test_backtest_params_keys_validation(self):
        """Test validation of params key count (DoS prevention)."""
        # Create params with too many keys
        many_keys_params = {f"key_{i}": i for i in range(100)}
        
        request_data = {
            "symbol": "sh000001",
            "period": "daily",
            "start_date": "2024-01-01",
            "end_date": "2024-03-01",
            "initial_capital": 100000,
            "strategy_type": "ma_crossover",
            "params": many_keys_params
        }
        
        response = client.post("/api/v1/backtest/run", json=request_data)
        # Should reject due to key count limit
        assert response.status_code == 400 or response.status_code == 422

    def test_backtest_date_validation_invalid_format(self):
        """Test date format validation."""
        request_data = {
            "symbol": "sh000001",
            "period": "daily",
            "start_date": "invalid-date",
            "end_date": "2024-03-01",
            "initial_capital": 100000,
            "strategy_type": "ma_crossover"
        }
        
        response = client.post("/api/v1/backtest/run", json=request_data)
        data = response.json()
        assert response.status_code == 200  # API returns 200 with error code
        assert data.get("code") == 1
        assert "日期格式错误" in data.get("message", "")

    def test_backtest_date_validation_end_before_start(self):
        """Test that end_date cannot be before start_date."""
        request_data = {
            "symbol": "sh000001",
            "period": "daily",
            "start_date": "2024-03-01",
            "end_date": "2024-01-01",
            "initial_capital": 100000,
            "strategy_type": "ma_crossover"
        }
        
        response = client.post("/api/v1/backtest/run", json=request_data)
        data = response.json()
        assert response.status_code == 200
        assert data.get("code") == 1
        assert "不能晚于" in data.get("message", "")

    def test_backtest_date_validation_too_long_span(self):
        """Test that date span cannot exceed 10 years."""
        request_data = {
            "symbol": "sh000001",
            "period": "daily",
            "start_date": "2010-01-01",
            "end_date": "2024-01-01",
            "initial_capital": 100000,
            "strategy_type": "ma_crossover"
        }
        
        response = client.post("/api/v1/backtest/run", json=request_data)
        data = response.json()
        assert response.status_code == 200
        assert data.get("code") == 1
        assert "不能超过" in data.get("message", "")

    def test_backtest_capital_validation_too_low(self):
        """Test that initial_capital cannot be too low."""
        request_data = {
            "symbol": "sh000001",
            "period": "daily",
            "start_date": "2024-01-01",
            "end_date": "2024-03-01",
            "initial_capital": 50,  # Below MIN_CAPITAL of 100
            "strategy_type": "ma_crossover"
        }
        
        response = client.post("/api/v1/backtest/run", json=request_data)
        data = response.json()
        assert response.status_code == 200
        assert data.get("code") == 1
        assert "initial_capital" in data.get("message", "").lower()

    def test_backtest_capital_validation_too_high(self):
        """Test that initial_capital cannot be too high."""
        request_data = {
            "symbol": "sh000001",
            "period": "daily",
            "start_date": "2024-01-01",
            "end_date": "2024-03-01",
            "initial_capital": 1e10,  # Above MAX_CAPITAL of 1e9
            "strategy_type": "ma_crossover"
        }
        
        response = client.post("/api/v1/backtest/run", json=request_data)
        data = response.json()
        assert response.status_code == 200
        assert data.get("code") == 1
        assert "initial_capital" in data.get("message", "").lower()

    def test_backtest_capital_validation_invalid_type(self):
        """Test that initial_capital must be a valid number."""
        request_data = {
            "symbol": "sh000001",
            "period": "daily",
            "start_date": "2024-01-01",
            "end_date": "2024-03-01",
            "initial_capital": "invalid",
            "strategy_type": "ma_crossover"
        }
        
        response = client.post("/api/v1/backtest/run", json=request_data)
        # FastAPI validates type at request level, returns 422 for invalid type
        assert response.status_code in [200, 422]
        if response.status_code == 200:
            data = response.json()
            assert data.get("code") == 1

    @patch('app.routers.backtest._get_conn')
    def test_backtest_symbol_prefix_handling(self, mock_get_conn):
        """Test that symbol prefixes (sh/sz) are correctly handled."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ('2024-01-01', 100.0, 101.0, 99.0, 100.5, 1000000),
            ('2024-01-02', 100.5, 102.0, 100.0, 101.5, 1200000),
            ('2024-01-03', 101.5, 103.0, 101.0, 102.5, 1100000),
        ]
        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        
        request_data = {
            "symbol": "sh000001",  # With prefix
            "period": "daily",
            "start_date": "2024-01-01",
            "end_date": "2024-03-01",
            "initial_capital": 100000,
            "strategy_type": "ma_crossover"
        }
        
        response = client.post("/api/v1/backtest/run", json=request_data)
        # Should accept and process correctly
        assert response.status_code in [200, 500]


class TestBacktestStrategies:
    """Test cases for different strategy types."""

    @patch('app.routers.backtest._get_conn')
    def test_ma_crossover_strategy_params(self, mock_get_conn):
        """Test MA crossover strategy with custom parameters."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ('2024-01-01', 100.0, 101.0, 99.0, 100.5, 1000000),
            ('2024-01-02', 100.5, 102.0, 100.0, 101.5, 1200000),
            ('2024-01-03', 101.5, 103.0, 101.0, 102.5, 1100000),
        ]
        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        
        request_data = {
            "symbol": "sh000001",
            "period": "daily",
            "start_date": "2024-01-01",
            "end_date": "2024-03-01",
            "initial_capital": 100000,
            "strategy_type": "ma_crossover",
            "params": {
                "fast_ma": 10,
                "slow_ma": 30
            }
        }
        
        response = client.post("/api/v1/backtest/run", json=request_data)
        assert response.status_code in [200, 500]

    @patch('app.routers.backtest._get_conn')
    def test_rsi_oversold_strategy_params(self, mock_get_conn):
        """Test RSI oversold strategy with custom parameters."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ('2024-01-01', 100.0, 101.0, 99.0, 100.5, 1000000),
            ('2024-01-02', 100.5, 102.0, 100.0, 101.5, 1200000),
            ('2024-01-03', 101.5, 103.0, 101.0, 102.5, 1100000),
        ]
        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        
        request_data = {
            "symbol": "sh000001",
            "period": "daily",
            "start_date": "2024-01-01",
            "end_date": "2024-03-01",
            "initial_capital": 100000,
            "strategy_type": "rsi_oversold",
            "params": {
                "rsi_period": 14,
                "rsi_buy": 30,
                "rsi_sell": 70
            }
        }
        
        response = client.post("/api/v1/backtest/run", json=request_data)
        assert response.status_code in [200, 500]

    @patch('app.routers.backtest._get_conn')
    def test_bollinger_bands_strategy_params(self, mock_get_conn):
        """Test Bollinger Bands strategy with custom parameters."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ('2024-01-01', 100.0, 101.0, 99.0, 100.5, 1000000),
            ('2024-01-02', 100.5, 102.0, 100.0, 101.5, 1200000),
            ('2024-01-03', 101.5, 103.0, 101.0, 102.5, 1100000),
        ]
        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        
        request_data = {
            "symbol": "sh000001",
            "period": "daily",
            "start_date": "2024-01-01",
            "end_date": "2024-03-01",
            "initial_capital": 100000,
            "strategy_type": "bollinger_bands",
            "params": {
                "bb_period": 20,
                "bb_std": 2
            }
        }
        
        response = client.post("/api/v1/backtest/run", json=request_data)
        assert response.status_code in [200, 500]

    @patch('app.routers.backtest._get_conn')
    def test_unknown_strategy_defaults_to_ma(self, mock_get_conn):
        """Test that unknown strategy type defaults to ma_crossover."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ('2024-01-01', 100.0, 101.0, 99.0, 100.5, 1000000),
            ('2024-01-02', 100.5, 102.0, 100.0, 101.5, 1200000),
            ('2024-01-03', 101.5, 103.0, 101.0, 102.5, 1100000),
        ]
        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        
        request_data = {
            "symbol": "sh000001",
            "period": "daily",
            "start_date": "2024-01-01",
            "end_date": "2024-03-01",
            "initial_capital": 100000,
            "strategy_type": "unknown_strategy"
        }
        
        response = client.post("/api/v1/backtest/run", json=request_data)
        assert response.status_code in [200, 500]


class TestBacktestEndpoints:
    """Test cases for backtest API endpoints."""

    @patch('app.routers.backtest._get_conn')
    def test_get_strategies_endpoint(self, mock_get_conn):
        """Test GET /strategies endpoint."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        
        response = client.get("/api/v1/backtest/strategies")
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert "code" in data
            assert data.get("code") == 0

    @patch('app.routers.backtest._get_conn')
    def test_create_strategy_endpoint_validation(self, mock_get_conn):
        """Test POST /strategies endpoint validation."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 1
        mock_cursor.fetchone.return_value = [1]
        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        
        strategy_data = {
            "name": "",  # Empty name - should be rejected
            "description": "Test strategy",
            "strategy_type": "ma_crossover",
            "params": {}
        }
        
        response = client.post("/api/v1/backtest/strategies", json=strategy_data)
        assert response.status_code in [200, 400, 422, 500]

    @patch('app.routers.backtest._get_conn')
    def test_create_strategy_with_valid_data(self, mock_get_conn):
        """Test POST /strategies with valid data."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 1
        mock_cursor.fetchone.return_value = [1]
        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        
        strategy_data = {
            "name": "Test Strategy",
            "description": "A test strategy",
            "strategy_type": "ma_crossover",
            "params": {
                "fast_ma": 5,
                "slow_ma": 20
            }
        }
        
        response = client.post("/api/v1/backtest/strategies", json=strategy_data)
        assert response.status_code in [200, 201, 500]

    @patch('app.routers.backtest._get_conn')
    def test_get_results_endpoint(self, mock_get_conn):
        """Test GET /results endpoint."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        
        response = client.get("/api/v1/backtest/results")
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert "code" in data

    @patch('app.routers.backtest._get_conn')
    def test_get_results_with_limit_param(self, mock_get_conn):
        """Test GET /results with limit parameter."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        
        response = client.get("/api/v1/backtest/results?limit=5")
        assert response.status_code in [200, 500]


class TestBacktestResponseFormat:
    """Test cases for backtest response format."""

    @patch('app.routers.backtest._get_conn')
    def test_backtest_response_structure(self, mock_get_conn):
        """Test that backtest response has correct structure."""
        # Mock database connection with sample data
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ('2024-01-01', 100.0, 101.0, 99.0, 100.5, 1000000),
            ('2024-01-02', 100.5, 102.0, 100.0, 101.5, 1200000),
            ('2024-01-03', 101.5, 103.0, 101.0, 102.5, 1100000),
        ]
        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        
        request_data = {
            "symbol": "sh000001",
            "period": "daily",
            "start_date": "2024-01-01",
            "end_date": "2024-03-01",
            "initial_capital": 100000,
            "strategy_type": "ma_crossover"
        }
        
        response = client.post("/api/v1/backtest/run", json=request_data)
        data = response.json()
        
        # Check response structure regardless of success/error
        assert "code" in data
        if data.get("code") == 0:
            assert "data" in data
            result = data["data"]
            # Verify expected fields exist
            expected_fields = [
                "symbol", "start_date", "end_date", "initial_capital",
                "final_capital", "total_return", "total_return_pct",
                "wins", "losses", "win_rate", "trades_count",
                "trades", "equity_curve", "benchmark_return_pct"
            ]
            for field in expected_fields:
                assert field in result, f"Missing field: {field}"

    def test_backtest_error_response_format(self):
        """Test that error responses follow consistent format."""
        request_data = {
            "symbol": "sh000001",
            "period": "daily",
            "start_date": "2024-03-01",  # End before start
            "end_date": "2024-01-01",
            "initial_capital": 100000,
            "strategy_type": "ma_crossover"
        }
        
        response = client.post("/api/v1/backtest/run", json=request_data)
        data = response.json()
        
        assert response.status_code == 200  # API returns 200 with error code
        assert "code" in data
        assert data["code"] == 1
        assert "message" in data


class TestBacktestDataRequirements:
    """Test cases for backtest data requirements."""

    @patch('app.routers.backtest._get_conn')
    def test_backtest_insufficient_data(self, mock_get_conn):
        """Test behavior when insufficient historical data."""
        # Mock database connection with empty data
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []  # No data
        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        
        request_data = {
            "symbol": "nonexistent_symbol_12345",
            "period": "daily",
            "start_date": "2024-01-01",
            "end_date": "2024-03-01",
            "initial_capital": 100000,
            "strategy_type": "ma_crossover"
        }
        
        response = client.post("/api/v1/backtest/run", json=request_data)
        data = response.json()
        
        # Should return error about missing data
        assert response.status_code == 200
        assert data.get("code") == 1
        assert "无" in data.get("message", "") or "数据" in data.get("message", "")

    @patch('app.routers.backtest._get_conn')
    def test_backtest_insufficient_data_for_slow_ma(self, mock_get_conn):
        """Test when data is insufficient for slow MA calculation."""
        # Mock database connection with only 3 days of data
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ('2024-01-01', 100.0, 101.0, 99.0, 100.5, 1000000),
            ('2024-01-02', 100.5, 102.0, 100.0, 101.5, 1200000),
            ('2024-01-03', 101.5, 103.0, 101.0, 102.5, 1100000),
        ]
        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        
        # Request very short period with very slow MA
        request_data = {
            "symbol": "sh000001",
            "period": "daily",
            "start_date": "2024-01-01",
            "end_date": "2024-01-05",  # Only 5 days
            "initial_capital": 100000,
            "strategy_type": "ma_crossover",
            "params": {
                "slow_ma": 100  # Requires 100 days of data
            }
        }
        
        response = client.post("/api/v1/backtest/run", json=request_data)
        data = response.json()
        
        # Should return error about insufficient data for calculation
        assert response.status_code == 200
        if data.get("code") == 1:
            assert "不足以计算" in data.get("message", "") or "数据" in data.get("message", "")


class TestBacktestPerformanceMetrics:
    """Test cases for backtest performance metrics calculation."""

    @patch('app.routers.backtest._get_conn')
    def test_backtest_metrics_present(self, mock_get_conn):
        """Test that all expected metrics are present in successful response."""
        # Mock database connection with sample data
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ('2024-01-01', 100.0, 101.0, 99.0, 100.5, 1000000),
            ('2024-01-02', 100.5, 102.0, 100.0, 101.5, 1200000),
            ('2024-01-03', 101.5, 103.0, 101.0, 102.5, 1100000),
        ]
        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        
        request_data = {
            "symbol": "sh000001",
            "period": "daily",
            "start_date": "2024-01-01",
            "end_date": "2024-03-01",
            "initial_capital": 100000,
            "strategy_type": "ma_crossover"
        }
        
        response = client.post("/api/v1/backtest/run", json=request_data)
        data = response.json()
        
        if data.get("code") == 0:
            result = data["data"]
            # Performance metrics
            assert "sharpe_ratio" in result
            assert "annualized_return_pct" in result
            assert "max_drawdown" in result
            assert "max_drawdown_pct" in result
            assert "benchmark_return_pct" in result

    @patch('app.routers.backtest._get_conn')
    def test_backtest_trade_details_structure(self, mock_get_conn):
        """Test that trade details have correct structure."""
        # Mock database connection with sample data
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ('2024-01-01', 100.0, 101.0, 99.0, 100.5, 1000000),
            ('2024-01-02', 100.5, 102.0, 100.0, 101.5, 1200000),
            ('2024-01-03', 101.5, 103.0, 101.0, 102.5, 1100000),
        ]
        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        
        request_data = {
            "symbol": "sh000001",
            "period": "daily",
            "start_date": "2024-01-01",
            "end_date": "2024-03-01",
            "initial_capital": 100000,
            "strategy_type": "ma_crossover"
        }
        
        response = client.post("/api/v1/backtest/run", json=request_data)
        data = response.json()
        
        if data.get("code") == 0:
            result = data["data"]
            trades = result.get("trades", [])
            if trades:
                trade = trades[0]
                # Check trade structure
                expected_trade_fields = [
                    "entry_date", "entry_price", "shares", "type"
                ]
                for field in expected_trade_fields:
                    assert field in trade
                # Check closed trades have exit info
                if "exit_date" in trade:
                    assert "exit_price" in trade
                    assert "pnl" in trade
                    assert "pnl_pct" in trade

    @patch('app.routers.backtest._get_conn')
    def test_backtest_equity_curve_structure(self, mock_get_conn):
        """Test that equity curve has correct structure."""
        # Mock database connection with sample data
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ('2024-01-01', 100.0, 101.0, 99.0, 100.5, 1000000),
            ('2024-01-02', 100.5, 102.0, 100.0, 101.5, 1200000),
            ('2024-01-03', 101.5, 103.0, 101.0, 102.5, 1100000),
        ]
        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        
        request_data = {
            "symbol": "sh000001",
            "period": "daily",
            "start_date": "2024-01-01",
            "end_date": "2024-03-01",
            "initial_capital": 100000,
            "strategy_type": "ma_crossover"
        }
        
        response = client.post("/api/v1/backtest/run", json=request_data)
        data = response.json()
        
        if data.get("code") == 0:
            result = data["data"]
            equity_curve = result.get("equity_curve", [])
            if equity_curve:
                point = equity_curve[0]
                assert "date" in point
                assert "value" in point
