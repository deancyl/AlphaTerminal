"""
Unit Tests for PerformanceMetricsCalculator

Tests cover all 10 debug cycles:
- Cycle 1: Input validation
- Cycle 2: Returns calculation
- Cycle 3: Sharpe ratio calculation
- Cycle 4: Sortino ratio calculation
- Cycle 5: Drawdown calculation
- Cycle 6: Win rate calculation
- Cycle 7: Profit factor calculation
- Cycle 8: VaR/CVaR calculation
- Cycle 9: Trade analysis
- Cycle 10: Metrics aggregation
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.DEBUG)

from app.services.performance_analyzer import PerformanceMetricsCalculator


class TestPerformanceMetricsCalculator:
    """Tests for PerformanceMetricsCalculator class"""
    
    @pytest.fixture
    def calculator(self):
        """Create calculator instance"""
        return PerformanceMetricsCalculator(risk_free_rate=0.02, trading_days=252)
    
    @pytest.fixture
    def sample_equity_curve(self):
        """Create sample equity curve with known properties"""
        dates = pd.date_range(start='2023-01-01', periods=252, freq='D')
        # Simulate 10% annual return with 15% volatility
        np.random.seed(42)
        returns = np.random.normal(0.10/252, 0.15/np.sqrt(252), 252)
        equity = 100000 * (1 + returns).cumprod()
        return pd.Series(equity, index=dates)
    
    @pytest.fixture
    def sample_trades(self):
        """Create sample trade list"""
        return [
            {"entry_date": "2023-01-05", "exit_date": "2023-01-10", "pnl": 1000, "pnl_pct": 0.02},
            {"entry_date": "2023-01-15", "exit_date": "2023-01-20", "pnl": -500, "pnl_pct": -0.01},
            {"entry_date": "2023-01-25", "exit_date": "2023-01-30", "pnl": 1500, "pnl_pct": 0.03},
            {"entry_date": "2023-02-05", "exit_date": "2023-02-10", "pnl": -750, "pnl_pct": -0.015},
            {"entry_date": "2023-02-15", "exit_date": "2023-02-20", "pnl": 2000, "pnl_pct": 0.04},
        ]
    
    # ==================== Cycle 1: Input Validation ====================
    
    def test_cycle1_validate_valid_inputs(self, calculator, sample_equity_curve):
        """Test Cycle 1: Valid inputs should pass validation"""
        is_valid, error = calculator._validate_inputs(sample_equity_curve)
        assert is_valid is True
        assert error == ""
    
    def test_cycle1_validate_empty_equity_curve(self, calculator):
        """Test Cycle 1: Empty equity curve should fail validation"""
        empty_curve = pd.Series([], dtype=float)
        is_valid, error = calculator._validate_inputs(empty_curve)
        assert is_valid is False
        assert "empty" in error.lower()
    
    def test_cycle1_validate_none_equity_curve(self, calculator):
        """Test Cycle 1: None equity curve should fail validation"""
        is_valid, error = calculator._validate_inputs(None)
        assert is_valid is False
        assert "empty" in error.lower() or "none" in error.lower()
    
    def test_cycle1_validate_single_point(self, calculator):
        """Test Cycle 1: Single point should fail validation"""
        single_point = pd.Series([100000], index=pd.date_range(start='2023-01-01', periods=1, freq='D'))
        is_valid, error = calculator._validate_inputs(single_point)
        assert is_valid is False
        assert "insufficient" in error.lower()
    
    def test_cycle1_validate_inf_values(self, calculator):
        """Test Cycle 1: Infinite values should fail validation"""
        dates = pd.date_range(start='2023-01-01', periods=10, freq='D')
        equity = pd.Series([100000, np.inf, 101000, 102000, 103000, 104000, 105000, 106000, 107000, 108000], index=dates)
        is_valid, error = calculator._validate_inputs(equity)
        assert is_valid is False
        assert "infinite" in error.lower()
    
    def test_cycle1_validate_with_trades(self, calculator, sample_equity_curve, sample_trades):
        """Test Cycle 1: Validation should accept valid trades"""
        is_valid, error = calculator._validate_inputs(sample_equity_curve, sample_trades)
        assert is_valid is True
    
    def test_cycle1_validate_invalid_trades_type(self, calculator, sample_equity_curve):
        """Test Cycle 1: Invalid trades type should fail"""
        is_valid, error = calculator._validate_inputs(sample_equity_curve, trades="not_a_list")
        assert is_valid is False
        assert "list" in error.lower()
    
    # ==================== Cycle 2: Returns Calculation ====================
    
    def test_cycle2_calculate_returns_basic(self, calculator):
        """Test Cycle 2: Basic returns calculation"""
        equity = pd.Series([100, 101, 102, 101.5, 103], 
                          index=pd.date_range(start='2023-01-01', periods=5, freq='D'))
        returns = calculator.calculate_returns(equity)
        
        assert len(returns) == 4
        assert abs(returns.iloc[0] - 0.01) < 0.0001  # (101-100)/100
        assert abs(returns.iloc[1] - 0.0099) < 0.0001  # (102-101)/101
        assert abs(returns.iloc[2] - (-0.0049)) < 0.0001  # (101.5-102)/102
        assert abs(returns.iloc[3] - 0.0148) < 0.0001  # (103-101.5)/101.5
    
    def test_cycle2_calculate_returns_empty(self, calculator):
        """Test Cycle 2: Empty equity should return empty returns"""
        returns = calculator.calculate_returns(pd.Series([], dtype=float))
        assert len(returns) == 0
    
    def test_cycle2_calculate_returns_with_nan(self, calculator):
        """Test Cycle 2: NaN values should be handled"""
        equity = pd.Series([100, np.nan, 102, 103], 
                          index=pd.date_range(start='2023-01-01', periods=4, freq='D'))
        returns = calculator.calculate_returns(equity)
        
        assert len(returns) > 0
        assert not returns.isna().any()
    
    def test_cycle2_calculate_returns_constant_equity(self, calculator):
        """Test Cycle 2: Constant equity should return zero returns"""
        equity = pd.Series([100, 100, 100, 100], 
                          index=pd.date_range(start='2023-01-01', periods=4, freq='D'))
        returns = calculator.calculate_returns(equity)
        
        assert all(returns == 0)
    
    # ==================== Cycle 3: Sharpe Ratio ====================
    
    def test_cycle3_sharpe_ratio_positive(self, calculator):
        """Test Cycle 3: Positive Sharpe ratio"""
        # Create returns with positive mean
        returns = pd.Series([0.01, 0.02, 0.015, 0.01, 0.02])
        sharpe = calculator.calculate_sharpe_ratio(returns)
        
        assert sharpe > 0
    
    def test_cycle3_sharpe_ratio_negative(self, calculator):
        """Test Cycle 3: Negative Sharpe ratio"""
        # Create returns with negative mean
        returns = pd.Series([-0.01, -0.02, -0.015, -0.01, -0.02])
        sharpe = calculator.calculate_sharpe_ratio(returns)
        
        assert sharpe < 0
    
    def test_cycle3_sharpe_ratio_zero_volatility(self, calculator):
        """Test Cycle 3: Zero volatility should return 0"""
        returns = pd.Series([0.01, 0.01, 0.01, 0.01])
        sharpe = calculator.calculate_sharpe_ratio(returns)
        
        assert sharpe == 0.0
    
    def test_cycle3_sharpe_ratio_empty_returns(self, calculator):
        """Test Cycle 3: Empty returns should return 0"""
        returns = pd.Series([], dtype=float)
        sharpe = calculator.calculate_sharpe_ratio(returns)
        
        assert sharpe == 0.0
    
    def test_cycle3_sharpe_ratio_formula(self, calculator):
        """Test Cycle 3: Verify Sharpe ratio formula"""
        # Known values: mean=0.01, std=0.005
        returns = pd.Series([0.01, 0.015, 0.005, 0.01, 0.01])
        sharpe = calculator.calculate_sharpe_ratio(returns)
        
        # Expected: (mean * 252 - 0.02) / (std * sqrt(252))
        expected_return = returns.mean() * 252
        expected_vol = returns.std() * np.sqrt(252)
        expected_sharpe = (expected_return - 0.02) / expected_vol
        
        assert abs(sharpe - expected_sharpe) < 0.01
    
    # ==================== Cycle 4: Sortino Ratio ====================
    
    def test_cycle4_sortino_ratio_positive(self, calculator):
        """Test Cycle 4: Positive Sortino ratio"""
        # More positive returns than negative
        returns = pd.Series([0.02, 0.01, -0.005, 0.02, 0.01, -0.003, 0.015])
        sortino = calculator.calculate_sortino_ratio(returns)
        
        # Should be positive (more upside than downside)
        assert sortino > 0 or np.isnan(sortino)  # Allow NaN for edge cases
    
    def test_cycle4_sortino_ratio_no_negative_returns(self, calculator):
        """Test Cycle 4: No negative returns should return high value"""
        returns = pd.Series([0.01, 0.02, 0.015, 0.01])
        sortino = calculator.calculate_sortino_ratio(returns)
        
        assert sortino == 100.0  # Very high Sortino for no losses
    
    def test_cycle4_sortino_ratio_all_negative(self, calculator):
        """Test Cycle 4: All negative returns"""
        returns = pd.Series([-0.01, -0.02, -0.015, -0.01])
        sortino = calculator.calculate_sortino_ratio(returns)
        
        assert sortino < 0
    
    def test_cycle4_sortino_ratio_empty(self, calculator):
        """Test Cycle 4: Empty returns should return 0"""
        returns = pd.Series([], dtype=float)
        sortino = calculator.calculate_sortino_ratio(returns)
        
        assert sortino == 0.0
    
    def test_cycle4_sortino_vs_sharpe(self, calculator):
        """Test Cycle 4: Sortino should be higher than Sharpe for asymmetric returns"""
        # Returns with positive skew (more upside)
        returns = pd.Series([0.01, 0.02, -0.01, 0.03, -0.005, 0.02])
        sharpe = calculator.calculate_sharpe_ratio(returns)
        sortino = calculator.calculate_sortino_ratio(returns)
        
        # Sortino should be higher when there are fewer downside deviations
        assert sortino > sharpe
    
    # ==================== Cycle 5: Drawdown Calculation ====================
    
    def test_cycle5_max_drawdown_basic(self, calculator):
        """Test Cycle 5: Basic drawdown calculation"""
        # Equity curve: 100 -> 110 -> 105 -> 115 -> 110
        equity = pd.Series([100, 110, 105, 115, 110],
                         index=pd.date_range(start='2023-01-01', periods=5, freq='D'))
        dd_metrics = calculator.calculate_max_drawdown(equity)
        
        # Max drawdown should be from 110 to 105 = -4.55%
        assert dd_metrics["max_drawdown"] < 0
        assert abs(dd_metrics["max_drawdown"] - (-0.0455)) < 0.01
    
    def test_cycle5_max_drawdown_no_drawdown(self, calculator):
        """Test Cycle 5: Monotonically increasing equity"""
        equity = pd.Series([100, 101, 102, 103, 104],
                         index=pd.date_range(start='2023-01-01', periods=5, freq='D'))
        dd_metrics = calculator.calculate_max_drawdown(equity)
        
        assert dd_metrics["max_drawdown"] == 0.0
    
    def test_cycle5_max_drawdown_large(self, calculator):
        """Test Cycle 5: Large drawdown scenario"""
        # Equity drops from 100 to 50 (50% drawdown from peak)
        equity = pd.Series([100, 90, 80, 70, 50],
                         index=pd.date_range(start='2023-01-01', periods=5, freq='D'))
        dd_metrics = calculator.calculate_max_drawdown(equity)
        
        # Max drawdown should be -50% (from 100 to 50)
        assert dd_metrics["max_drawdown"] < -0.4  # At least 40% drawdown
    
    def test_cycle5_drawdown_duration(self, calculator):
        """Test Cycle 5: Drawdown duration calculation"""
        # Create equity with known drawdown period
        equity = pd.Series([100, 110, 100, 105, 115, 120],
                         index=pd.date_range(start='2023-01-01', periods=6, freq='D'))
        dd_metrics = calculator.calculate_max_drawdown(equity)
        
        assert dd_metrics["drawdown_duration"] >= 0
    
    def test_cycle5_empty_equity(self, calculator):
        """Test Cycle 5: Empty equity should return zero drawdown"""
        dd_metrics = calculator.calculate_max_drawdown(pd.Series([], dtype=float))
        
        assert dd_metrics["max_drawdown"] == 0.0
        assert dd_metrics["drawdown_duration"] == 0
    
    # ==================== Cycle 6: Win Rate Calculation ====================
    
    def test_cycle6_win_rate_basic(self, calculator, sample_trades):
        """Test Cycle 6: Basic win rate calculation"""
        win_rate = calculator.calculate_win_rate(sample_trades)
        
        # 3 wins out of 5 trades
        assert abs(win_rate - 0.6) < 0.01
    
    def test_cycle6_win_rate_all_wins(self, calculator):
        """Test Cycle 6: All winning trades"""
        trades = [
            {"pnl": 100},
            {"pnl": 200},
            {"pnl": 150},
        ]
        win_rate = calculator.calculate_win_rate(trades)
        
        assert win_rate == 1.0
    
    def test_cycle6_win_rate_all_losses(self, calculator):
        """Test Cycle 6: All losing trades"""
        trades = [
            {"pnl": -100},
            {"pnl": -200},
            {"pnl": -150},
        ]
        win_rate = calculator.calculate_win_rate(trades)
        
        assert win_rate == 0.0
    
    def test_cycle6_win_rate_empty_trades(self, calculator):
        """Test Cycle 6: Empty trades should return 0"""
        win_rate = calculator.calculate_win_rate([])
        
        assert win_rate == 0.0
    
    def test_cycle6_win_rate_no_pnl_field(self, calculator):
        """Test Cycle 6: Trades without PnL field"""
        trades = [
            {"entry": "2023-01-01"},
            {"entry": "2023-01-02"},
        ]
        win_rate = calculator.calculate_win_rate(trades)
        
        assert win_rate == 0.0
    
    def test_cycle6_win_rate_mixed(self, calculator):
        """Test Cycle 6: Mixed wins and losses"""
        trades = [
            {"pnl": 100},
            {"pnl": -50},
            {"pnl": 0},  # Break-even
            {"pnl": 75},
        ]
        win_rate = calculator.calculate_win_rate(trades)
        
        # 2 wins out of 4 trades (break-even is not a win)
        assert abs(win_rate - 0.5) < 0.01
    
    # ==================== Cycle 7: Profit Factor ====================
    
    def test_cycle7_profit_factor_basic(self, calculator, sample_trades):
        """Test Cycle 7: Basic profit factor calculation"""
        profit_factor = calculator.calculate_profit_factor(sample_trades)
        
        # Gross profit = 4500, Gross loss = 1250
        # Profit factor = 4500 / 1250 = 3.6
        assert profit_factor > 1
        assert abs(profit_factor - 3.6) < 0.1
    
    def test_cycle7_profit_factor_no_losses(self, calculator):
        """Test Cycle 7: No losses should return infinity"""
        trades = [
            {"pnl": 100},
            {"pnl": 200},
            {"pnl": 150},
        ]
        profit_factor = calculator.calculate_profit_factor(trades)
        
        assert profit_factor == float('inf')
    
    def test_cycle7_profit_factor_no_profits(self, calculator):
        """Test Cycle 7: No profits should return 0"""
        trades = [
            {"pnl": -100},
            {"pnl": -200},
        ]
        profit_factor = calculator.calculate_profit_factor(trades)
        
        assert profit_factor == 0.0
    
    def test_cycle7_profit_factor_empty(self, calculator):
        """Test Cycle 7: Empty trades should return 0"""
        profit_factor = calculator.calculate_profit_factor([])
        
        assert profit_factor == 0.0
    
    def test_cycle7_profit_factor_equal(self, calculator):
        """Test Cycle 7: Equal profits and losses"""
        trades = [
            {"pnl": 100},
            {"pnl": -100},
        ]
        profit_factor = calculator.calculate_profit_factor(trades)
        
        assert abs(profit_factor - 1.0) < 0.01
    
    # ==================== Cycle 8: VaR/CVaR Calculation ====================
    
    def test_cycle8_var_basic(self, calculator):
        """Test Cycle 8: Basic VaR calculation"""
        # Normal distribution of returns
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0.001, 0.02, 252))
        
        var_95 = calculator.calculate_var(returns, 0.95)
        var_99 = calculator.calculate_var(returns, 0.99)
        
        # VaR should be negative (potential loss)
        assert var_95 < 0
        assert var_99 < 0
        
        # VaR 99% should be more extreme than VaR 95%
        assert var_99 < var_95
    
    def test_cycle8_var_empty(self, calculator):
        """Test Cycle 8: Empty returns should return 0"""
        var = calculator.calculate_var(pd.Series([], dtype=float))
        
        assert var == 0.0
    
    def test_cycle8_cvar_basic(self, calculator):
        """Test Cycle 8: Basic CVaR calculation"""
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0.001, 0.02, 252))
        
        cvar_95 = calculator.calculate_cvar(returns, 0.95)
        cvar_99 = calculator.calculate_cvar(returns, 0.99)
        
        # CVaR should be negative (expected loss)
        assert cvar_95 < 0
        assert cvar_99 < 0
        
        # CVaR should be more extreme than VaR
        var_95 = calculator.calculate_var(returns, 0.95)
        assert cvar_95 <= var_95
    
    def test_cycle8_cvar_empty(self, calculator):
        """Test Cycle 8: Empty returns CVaR"""
        cvar = calculator.calculate_cvar(pd.Series([], dtype=float))
        
        assert cvar == 0.0
    
    def test_cycle8_var_known_distribution(self, calculator):
        """Test Cycle 8: VaR with known distribution"""
        # Create returns with clear tail risk
        np.random.seed(42)
        returns = pd.Series(np.random.normal(-0.001, 0.02, 252))
        
        var_95 = calculator.calculate_var(returns, 0.95)
        var_99 = calculator.calculate_var(returns, 0.99)
        
        # VaR should be negative (representing potential loss)
        assert var_95 < 0
        # VaR 99% should be more extreme than VaR 95%
        assert var_99 < var_95
    
    # ==================== Cycle 9: Trade Analysis ====================
    
    def test_cycle9_trade_analysis_basic(self, calculator, sample_trades):
        """Test Cycle 9: Basic trade analysis"""
        analysis = calculator.analyze_trades(sample_trades)
        
        assert analysis["total_trades"] == 5
        assert analysis["winning_trades"] == 3
        assert analysis["losing_trades"] == 2
        assert analysis["largest_win"] == 2000
        assert analysis["largest_loss"] == -750
    
    def test_cycle9_trade_analysis_empty(self, calculator):
        """Test Cycle 9: Empty trades analysis"""
        analysis = calculator.analyze_trades([])
        
        assert analysis["total_trades"] == 0
        assert analysis["winning_trades"] == 0
        assert analysis["losing_trades"] == 0
    
    def test_cycle9_consecutive_wins(self, calculator):
        """Test Cycle 9: Consecutive wins calculation"""
        trades = [
            {"pnl": 100},
            {"pnl": 200},
            {"pnl": 150},
            {"pnl": -50},
            {"pnl": 100},
        ]
        analysis = calculator.analyze_trades(trades)
        
        assert analysis["max_consecutive_wins"] == 3
    
    def test_cycle9_consecutive_losses(self, calculator):
        """Test Cycle 9: Consecutive losses calculation"""
        trades = [
            {"pnl": -100},
            {"pnl": -200},
            {"pnl": 150},
            {"pnl": -50},
            {"pnl": -75},
            {"pnl": -25},
        ]
        analysis = calculator.analyze_trades(trades)
        
        # Should have consecutive losses (2 at start, 3 at end)
        assert analysis["max_consecutive_losses"] >= 2
    
    def test_cycle9_trade_duration(self, calculator):
        """Test Cycle 9: Average trade duration"""
        trades = [
            {"entry_date": "2023-01-01", "exit_date": "2023-01-10", "pnl": 100},
            {"entry_date": "2023-01-15", "exit_date": "2023-01-20", "pnl": -50},
        ]
        analysis = calculator.analyze_trades(trades)
        
        # Average duration: (9 + 5) / 2 = 7 days
        assert analysis["avg_trade_duration_days"] > 0
    
    def test_cycle9_trade_distribution(self, calculator):
        """Test Cycle 9: Trade distribution analysis"""
        trades = [
            {"pnl": 1000},  # Large win
            {"pnl": 100},   # Small win
            {"pnl": -100},  # Small loss
            {"pnl": -1000}, # Large loss
        ]
        analysis = calculator.analyze_trades(trades)
        
        assert "trade_distribution" in analysis
        assert isinstance(analysis["trade_distribution"], dict)
    
    # ==================== Cycle 10: Metrics Aggregation ====================
    
    def test_cycle10_calculate_all_metrics(self, calculator, sample_equity_curve, sample_trades):
        """Test Cycle 10: Full metrics calculation"""
        metrics = calculator.calculate_all_metrics(sample_equity_curve, sample_trades)
        
        # Check all metric categories exist
        assert "total_return" in metrics
        assert "annual_return" in metrics
        assert "sharpe_ratio" in metrics
        assert "sortino_ratio" in metrics
        assert "calmar_ratio" in metrics
        assert "max_drawdown" in metrics
        assert "win_rate" in metrics
        assert "profit_factor" in metrics
        assert "var_95" in metrics
        assert "cvar_95" in metrics
        assert "trade_analysis" in metrics
    
    def test_cycle10_metrics_without_trades(self, calculator, sample_equity_curve):
        """Test Cycle 10: Metrics calculation without trades"""
        metrics = calculator.calculate_all_metrics(sample_equity_curve)
        
        assert metrics["win_rate"] == 0.0
        assert metrics["profit_factor"] == 0.0
        assert "trade_analysis" in metrics
    
    def test_cycle10_metrics_invalid_inputs(self, calculator):
        """Test Cycle 10: Invalid inputs should return empty metrics"""
        metrics = calculator.calculate_all_metrics(pd.Series([], dtype=float))
        
        assert "error" in metrics
        assert metrics["sharpe_ratio"] == 0.0
    
    def test_cycle10_metrics_values_reasonable(self, calculator, sample_equity_curve, sample_trades):
        """Test Cycle 10: All metrics should have reasonable values"""
        metrics = calculator.calculate_all_metrics(sample_equity_curve, sample_trades)
        
        # Sharpe ratio should be reasonable
        assert -10 < metrics["sharpe_ratio"] < 10
        
        # Win rate should be between 0 and 1
        assert 0 <= metrics["win_rate"] <= 1
        
        # Max drawdown should be negative or zero
        assert metrics["max_drawdown"] <= 0
        
        # Volatility should be positive
        assert metrics["annual_volatility"] >= 0
    
    def test_cycle10_calmar_ratio(self, calculator, sample_equity_curve):
        """Test Cycle 10: Calmar ratio calculation"""
        returns = calculator.calculate_returns(sample_equity_curve)
        calmar = calculator.calculate_calmar_ratio(returns)
        
        # Calmar should be reasonable
        assert -100 < calmar < 100
    
    # ==================== Edge Cases ====================
    
    def test_edge_case_zero_equity(self, calculator):
        """Test edge case: Zero equity values"""
        equity = pd.Series([100, 0, 100, 100],
                         index=pd.date_range(start='2023-01-01', periods=4, freq='D'))
        
        # Should handle gracefully
        is_valid, _ = calculator._validate_inputs(equity)
        assert is_valid is True  # Should pass validation but warn
    
    def test_edge_case_very_small_returns(self, calculator):
        """Test edge case: Very small returns"""
        equity = pd.Series([100.0, 100.0001, 100.0002, 100.0003],
                         index=pd.date_range(start='2023-01-01', periods=4, freq='D'))
        returns = calculator.calculate_returns(equity)
        
        # Should handle very small returns
        assert len(returns) > 0
    
    def test_edge_case_large_numbers(self, calculator):
        """Test edge case: Large equity values"""
        equity = pd.Series([1e9, 1.1e9, 1.05e9, 1.2e9],
                         index=pd.date_range(start='2023-01-01', periods=4, freq='D'))
        metrics = calculator.calculate_all_metrics(equity)
        
        # Should handle large numbers without overflow
        assert not np.isnan(metrics["sharpe_ratio"])
        assert not np.isinf(metrics["sharpe_ratio"])
    
    def test_edge_case_single_trade(self, calculator):
        """Test edge case: Single trade"""
        trades = [{"pnl": 100}]
        
        win_rate = calculator.calculate_win_rate(trades)
        profit_factor = calculator.calculate_profit_factor(trades)
        
        assert win_rate == 1.0
        assert profit_factor == float('inf')
    
    def test_edge_case_break_even_trades(self, calculator):
        """Test edge case: Break-even trades"""
        trades = [
            {"pnl": 0},
            {"pnl": 0},
            {"pnl": 0},
        ]
        
        win_rate = calculator.calculate_win_rate(trades)
        profit_factor = calculator.calculate_profit_factor(trades)
        
        # Break-even trades are not wins
        assert win_rate == 0.0
        assert profit_factor == 0.0


class TestPerformanceMetricsCalculatorIntegration:
    """Integration tests for PerformanceMetricsCalculator"""
    
    @pytest.fixture
    def calculator(self):
        return PerformanceMetricsCalculator()
    
    def test_full_workflow(self, calculator):
        """Test complete workflow with realistic data"""
        # Generate realistic equity curve
        np.random.seed(42)
        dates = pd.date_range(start='2023-01-01', periods=252, freq='D')
        returns = np.random.normal(0.0004, 0.02, 252)  # ~10% annual return, 32% vol
        equity = 100000 * (1 + returns).cumprod()
        equity_curve = pd.Series(equity, index=dates)
        
        # Generate realistic trades
        trades = []
        for i in range(50):
            pnl = np.random.choice([np.random.normal(500, 200), np.random.normal(-300, 150)])
            trades.append({
                "entry_date": f"2023-{(i // 4) + 1:02d}-{(i % 28) + 1:02d}",
                "exit_date": f"2023-{(i // 4) + 1:02d}-{(i % 28) + 5:02d}",
                "pnl": pnl
            })
        
        # Calculate all metrics
        metrics = calculator.calculate_all_metrics(equity_curve, trades)
        
        # Verify all metrics are present and reasonable
        assert metrics["total_days"] == 251  # 252 - 1 for returns calculation
        assert -1 < metrics["total_return"] < 2  # Reasonable total return
        assert -5 < metrics["sharpe_ratio"] < 5  # Reasonable Sharpe
        assert metrics["max_drawdown"] <= 0  # Drawdown is negative
    
    def test_comparison_with_known_values(self, calculator):
        """Test against known metric values"""
        # Create equity curve with known properties
        equity = pd.Series([100, 102, 101, 103, 102, 104, 103, 105],
                         index=pd.date_range(start='2023-01-01', periods=8, freq='D'))
        
        returns = calculator.calculate_returns(equity)
        
        # Verify returns are calculated correctly
        assert len(returns) == 7
        assert abs(returns.iloc[0] - 0.02) < 0.0001  # (102-100)/100
    
    def test_debug_logging_all_cycles(self, calculator, caplog):
        """Test that all 10 debug cycles produce logging output"""
        import logging
        caplog.set_level(logging.DEBUG)
        
        # Create sample data inline
        np.random.seed(42)
        dates = pd.date_range(start='2023-01-01', periods=252, freq='D')
        returns = np.random.normal(0.10/252, 0.15/np.sqrt(252), 252)
        equity = 100000 * (1 + returns).cumprod()
        sample_equity_curve = pd.Series(equity, index=dates)
        
        sample_trades = [
            {"entry_date": "2023-01-05", "exit_date": "2023-01-10", "pnl": 1000, "pnl_pct": 0.02},
            {"entry_date": "2023-01-15", "exit_date": "2023-01-20", "pnl": -500, "pnl_pct": -0.01},
        ]
        
        # Run full calculation
        metrics = calculator.calculate_all_metrics(sample_equity_curve, sample_trades)
        
        # Check that debug cycles are logged
        log_messages = [record.message for record in caplog.records]
        
        # Should have logs from multiple cycles
        assert any("Cycle 1" in msg for msg in log_messages)
        assert any("Cycle 2" in msg for msg in log_messages)
        assert any("Cycle 10" in msg for msg in log_messages)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
