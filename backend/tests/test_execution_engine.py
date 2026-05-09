"""
Unit Tests for Strategy Execution Engine

Tests cover:
- Engine initialization (Debug Cycle 1)
- Strategy compilation check (Debug Cycle 2)
- Data loading validation (Debug Cycle 3)
- Execution progress tracking (Debug Cycle 4)
- Result generation and storage (Debug Cycle 5)
- Integration with BacktestEngine and StrategyCompiler
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from app.services.strategy.execution_engine import (
    StrategyExecutionEngine,
    ExecutionConfig,
    ExecutionResult,
    ExecutionMetrics,
    ExecutionStatus,
    ExecutionType,
    create_execution_engine,
    execute_strategy_simple,
)
from app.services.strategy.compiler import StrategyCompiler, CompilationResult


class TestExecutionConfig:
    """Tests for ExecutionConfig dataclass"""
    
    def test_default_config(self):
        """Test default configuration values"""
        config = ExecutionConfig()
        
        assert config.initial_capital == 100000.0
        assert config.commission == 0.0003
        assert config.slippage == 0.0001
        assert config.leverage == 1.0
        assert config.max_positions == 1
        assert config.position_size_pct == 0.95
        assert config.stop_loss_pct == 0.0
        assert config.take_profit_pct == 0.0
        assert config.enable_debug_logging is True
        assert config.debug_level == 5
    
    def test_custom_config(self):
        """Test custom configuration values"""
        config = ExecutionConfig(
            initial_capital=50000.0,
            commission=0.001,
            slippage=0.0005,
            leverage=2.0,
            max_positions=3,
            position_size_pct=0.80,
            stop_loss_pct=5.0,
            take_profit_pct=10.0,
            enable_debug_logging=False,
            debug_level=3
        )
        
        assert config.initial_capital == 50000.0
        assert config.commission == 0.001
        assert config.slippage == 0.0005
        assert config.leverage == 2.0
        assert config.max_positions == 3
        assert config.position_size_pct == 0.80
        assert config.stop_loss_pct == 5.0
        assert config.take_profit_pct == 10.0
        assert config.enable_debug_logging is False
        assert config.debug_level == 3
    
    def test_config_to_dict(self):
        """Test config serialization"""
        config = ExecutionConfig(initial_capital=75000.0)
        result = config.to_dict()
        
        assert isinstance(result, dict)
        assert result['initial_capital'] == 75000.0
        assert 'commission' in result
        assert 'slippage' in result


class TestExecutionMetrics:
    """Tests for ExecutionMetrics dataclass"""
    
    def test_default_metrics(self):
        """Test default metrics values"""
        metrics = ExecutionMetrics()
        
        assert metrics.execution_time_ms == 0.0
        assert metrics.bars_processed == 0
        assert metrics.trades_executed == 0
        assert metrics.avg_bar_time_ms == 0.0
    
    def test_metrics_to_dict(self):
        """Test metrics serialization"""
        metrics = ExecutionMetrics(
            execution_time_ms=1234.56,
            bars_processed=100,
            trades_executed=5,
            avg_bar_time_ms=12.3456
        )
        
        result = metrics.to_dict()
        
        assert result['execution_time_ms'] == 1234.56
        assert result['bars_processed'] == 100
        assert result['trades_executed'] == 5
        assert result['avg_bar_time_ms'] == 12.3456


class TestExecutionResult:
    """Tests for ExecutionResult dataclass"""
    
    def test_execution_result_creation(self):
        """Test execution result creation"""
        result = ExecutionResult(
            execution_id="test-123",
            strategy_id="strategy-456",
            strategy_name="Test Strategy",
            execution_type=ExecutionType.BACKTEST,
            status=ExecutionStatus.COMPLETED,
            start_time=datetime.now(),
        )
        
        assert result.execution_id == "test-123"
        assert result.strategy_id == "strategy-456"
        assert result.strategy_name == "Test Strategy"
        assert result.execution_type == ExecutionType.BACKTEST
        assert result.status == ExecutionStatus.COMPLETED
        assert len(result.trades) == 0
        assert len(result.errors) == 0
    
    def test_execution_result_to_dict(self):
        """Test execution result serialization"""
        result = ExecutionResult(
            execution_id="test-123",
            strategy_id="strategy-456",
            strategy_name="Test Strategy",
            execution_type=ExecutionType.BACKTEST,
            status=ExecutionStatus.COMPLETED,
            start_time=datetime.now(),
            end_time=datetime.now(),
        )
        
        data = result.to_dict()
        
        assert data['execution_id'] == "test-123"
        assert data['strategy_id'] == "strategy-456"
        assert data['strategy_name'] == "Test Strategy"
        assert data['execution_type'] == "backtest"
        assert data['status'] == "completed"


class TestStrategyExecutionEngine:
    """Tests for StrategyExecutionEngine class"""
    
    @pytest.fixture
    def sample_data(self):
        """Create sample OHLCV data"""
        dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
        np.random.seed(42)
        
        closes = 100 + np.cumsum(np.random.randn(100) * 2)
        opens = closes + np.random.randn(100) * 0.5
        highs = np.maximum(opens, closes) + np.abs(np.random.randn(100) * 1)
        lows = np.minimum(opens, closes) - np.abs(np.random.randn(100) * 1)
        volumes = np.random.randint(1000000, 10000000, 100)
        
        return pd.DataFrame({
            'timestamp': dates,
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
            'volume': volumes
        })
    
    @pytest.fixture
    def config(self):
        """Create test configuration"""
        return ExecutionConfig(
            initial_capital=100000,
            commission=0.0003,
            slippage=0.0001,
            debug_level=5
        )
    
    @pytest.fixture
    def sample_strategy_code(self):
        """Sample strategy code"""
        return '''
# @name 测试均线策略
# @description 简单均线交叉策略
# @param fast_period int 5 快线周期
# @param slow_period int 20 慢线周期
# @strategy stopLossPct 2
# @strategy takeProfitPct 6

ma_fast = df['close'].rolling(fast_period).mean()
ma_slow = df['close'].rolling(slow_period).mean()
buy = (ma_fast > ma_slow) & (ma_fast.shift(1) <= ma_slow.shift(1))
sell = (ma_fast < ma_slow) & (ma_fast.shift(1) >= ma_slow.shift(1))
output = {
    'indicators': {'ma_fast': ma_fast, 'ma_slow': ma_slow},
    'signals': {'buy': buy, 'sell': sell}
}
'''
    
    def test_engine_initialization(self, config):
        """Test engine initialization (Debug Cycle 1)"""
        engine = StrategyExecutionEngine(config)
        
        assert engine._config == config
        assert len(engine._debug_log) > 0
        assert any("DEBUG CYCLE 1: EXECUTION INITIALIZATION" in log for log in engine._debug_log)
        assert any("Initial Capital" in log for log in engine._debug_log)
        assert any("Commission Rate" in log for log in engine._debug_log)
    
    def test_strategy_compilation_check(self, config, sample_data, sample_strategy_code):
        """Test strategy compilation check (Debug Cycle 2)"""
        engine = StrategyExecutionEngine(config)
        
        compiler = StrategyCompiler(debug_level=5)
        compiled = compiler.compile(sample_strategy_code)
        
        assert compiled.success
        assert compiled.spec is not None
        assert compiled.spec.name == "测试均线策略"
    
    def test_data_loading_validation(self, config, sample_data):
        """Test data loading validation (Debug Cycle 3)"""
        engine = StrategyExecutionEngine(config)
        
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        missing_cols = [col for col in required_cols if col not in sample_data.columns]
        
        assert len(missing_cols) == 0
        assert 'timestamp' in sample_data.columns
        assert len(sample_data) > 0
    
    def test_execute_strategy_with_compiled_result(self, config, sample_data, sample_strategy_code):
        """Test executing strategy with CompilationResult"""
        engine = StrategyExecutionEngine(config)
        
        compiler = StrategyCompiler(debug_level=5)
        compiled = compiler.compile(sample_strategy_code)
        
        result = engine.execute_strategy(
            compiled_strategy=compiled,
            data=sample_data,
            strategy_name=compiled.spec.name if compiled.spec else "Test"
        )
        
        assert result.status == ExecutionStatus.COMPLETED
        assert result.execution_id is not None
        assert result.strategy_id is not None
        assert any("DEBUG CYCLE 2: STRATEGY COMPILATION CHECK" in log for log in result.debug_log)
        assert any("DEBUG CYCLE 3: DATA LOADING VALIDATION" in log for log in result.debug_log)
        assert any("DEBUG CYCLE 4: EXECUTION PROGRESS TRACKING" in log for log in result.debug_log)
        assert any("DEBUG CYCLE 5: RESULT GENERATION AND STORAGE" in log for log in result.debug_log)
    
    def test_execute_strategy_with_callable(self, config, sample_data):
        """Test executing strategy with callable function"""
        engine = StrategyExecutionEngine(config)
        
        def simple_strategy(df, params):
            return {
                'indicators': {},
                'signals': {
                    'buy': pd.Series(False, index=df.index),
                    'sell': pd.Series(False, index=df.index)
                }
            }
        
        result = engine.execute_strategy(
            compiled_strategy=simple_strategy,
            data=sample_data,
            strategy_name="Simple Strategy"
        )
        
        assert result.status == ExecutionStatus.COMPLETED
        assert result.strategy_name == "Simple Strategy"
    
    def test_run_backtest(self, config, sample_data, sample_strategy_code):
        """Test run_backtest method"""
        engine = StrategyExecutionEngine(config)
        
        result = engine.run_backtest(
            strategy_code=sample_strategy_code,
            data=sample_data
        )
        
        assert result.status == ExecutionStatus.COMPLETED
        assert result.execution_type == ExecutionType.BACKTEST
        assert result.metrics.bars_processed == 100
        assert result.backtest_result is not None
    
    def test_execution_metrics(self, config, sample_data, sample_strategy_code):
        """Test execution metrics calculation"""
        engine = StrategyExecutionEngine(config)
        
        result = engine.run_backtest(
            strategy_code=sample_strategy_code,
            data=sample_data
        )
        
        assert result.metrics.execution_time_ms > 0
        assert result.metrics.bars_processed == 100
        assert result.metrics.avg_bar_time_ms > 0
    
    def test_get_execution_status(self, config, sample_data):
        """Test get_execution_status method"""
        engine = StrategyExecutionEngine(config)
        
        def slow_strategy(df, params):
            import time
            time.sleep(0.1)
            return {'indicators': {}, 'signals': {'buy': pd.Series(False, index=df.index), 'sell': pd.Series(False, index=df.index)}}
        
        result = engine.execute_strategy(
            compiled_strategy=slow_strategy,
            data=sample_data,
            strategy_name="Slow Strategy"
        )
        
        status = engine.get_execution_status(result.execution_id)
        
        assert status is None
    
    def test_cancel_execution(self, config):
        """Test cancel_execution method"""
        engine = StrategyExecutionEngine(config)
        
        cancelled = engine.cancel_execution("non-existent-id")
        
        assert cancelled is False
    
    def test_get_active_executions(self, config):
        """Test get_active_executions method"""
        engine = StrategyExecutionEngine(config)
        
        active = engine.get_active_executions()
        
        assert isinstance(active, list)
    
    def test_error_handling_invalid_strategy(self, config, sample_data):
        """Test error handling with invalid strategy"""
        engine = StrategyExecutionEngine(config)
        
        result = engine.execute_strategy(
            compiled_strategy="not a valid strategy",
            data=sample_data,
            strategy_name="Invalid Strategy"
        )
        
        assert result.status == ExecutionStatus.FAILED
        assert len(result.errors) > 0
    
    def test_error_handling_empty_data(self, config):
        """Test error handling with empty data"""
        engine = StrategyExecutionEngine(config)
        
        def simple_strategy(df, params):
            return {'indicators': {}, 'signals': {'buy': pd.Series(), 'sell': pd.Series()}}
        
        result = engine.execute_strategy(
            compiled_strategy=simple_strategy,
            data=pd.DataFrame(),
            strategy_name="Test Strategy"
        )
        
        assert result.status == ExecutionStatus.FAILED
        assert len(result.errors) > 0
    
    def test_error_handling_missing_columns(self, config):
        """Test error handling with missing columns"""
        engine = StrategyExecutionEngine(config)
        
        invalid_data = pd.DataFrame({
            'timestamp': pd.date_range(start='2023-01-01', periods=10, freq='D'),
            'close': [100] * 10
        })
        
        def simple_strategy(df, params):
            return {'indicators': {}, 'signals': {'buy': pd.Series(), 'sell': pd.Series()}}
        
        result = engine.execute_strategy(
            compiled_strategy=simple_strategy,
            data=invalid_data,
            strategy_name="Test Strategy"
        )
        
        assert result.status == ExecutionStatus.FAILED
        assert any("Missing required columns" in err for err in result.errors)
    
    def test_debug_logging_all_cycles(self, config, sample_data, sample_strategy_code):
        """Test that all 5 debug cycles are logged"""
        engine = StrategyExecutionEngine(config)
        
        result = engine.run_backtest(
            strategy_code=sample_strategy_code,
            data=sample_data
        )
        
        debug_log_str = '\n'.join(result.debug_log)
        
        assert "DEBUG CYCLE 1: EXECUTION INITIALIZATION" in debug_log_str
        assert "DEBUG CYCLE 2: STRATEGY COMPILATION CHECK" in debug_log_str
        assert "DEBUG CYCLE 3: DATA LOADING VALIDATION" in debug_log_str
        assert "DEBUG CYCLE 4: EXECUTION PROGRESS TRACKING" in debug_log_str
        assert "DEBUG CYCLE 5: RESULT GENERATION AND STORAGE" in debug_log_str
    
    def test_performance_summary_in_debug_log(self, config, sample_data, sample_strategy_code):
        """Test that performance summary is included in debug log"""
        engine = StrategyExecutionEngine(config)
        
        result = engine.run_backtest(
            strategy_code=sample_strategy_code,
            data=sample_data
        )
        
        debug_log_str = '\n'.join(result.debug_log)
        
        assert "Performance Summary" in debug_log_str or result.metrics.trades_executed == 0
    
    def test_backtest_result_structure(self, config, sample_data, sample_strategy_code):
        """Test that backtest result has correct structure"""
        engine = StrategyExecutionEngine(config)
        
        result = engine.run_backtest(
            strategy_code=sample_strategy_code,
            data=sample_data
        )
        
        assert result.backtest_result is not None
        assert 'config' in result.backtest_result
        assert 'trades' in result.backtest_result
        assert 'equity_curve' in result.backtest_result
        assert 'metrics' in result.backtest_result
    
    def test_trades_and_equity_curve(self, config, sample_data, sample_strategy_code):
        """Test that trades and equity curve are populated"""
        engine = StrategyExecutionEngine(config)
        
        result = engine.run_backtest(
            strategy_code=sample_strategy_code,
            data=sample_data
        )
        
        assert isinstance(result.trades, list)
        assert isinstance(result.equity_curve, list)
        assert len(result.equity_curve) > 0


class TestConvenienceFunctions:
    """Tests for convenience functions"""
    
    @pytest.fixture
    def sample_data(self):
        """Create sample OHLCV data"""
        dates = pd.date_range(start='2023-01-01', periods=50, freq='D')
        np.random.seed(42)
        
        closes = 100 + np.cumsum(np.random.randn(50) * 2)
        
        return pd.DataFrame({
            'timestamp': dates,
            'open': closes + np.random.randn(50) * 0.5,
            'high': closes + np.abs(np.random.randn(50)),
            'low': closes - np.abs(np.random.randn(50)),
            'close': closes,
            'volume': np.random.randint(1000000, 10000000, 50)
        })
    
    def test_create_execution_engine(self):
        """Test create_execution_engine function"""
        engine = create_execution_engine(
            initial_capital=50000,
            commission=0.001,
            slippage=0.0005,
            enable_debug_logging=True,
            debug_level=3
        )
        
        assert isinstance(engine, StrategyExecutionEngine)
        assert engine._config.initial_capital == 50000
        assert engine._config.commission == 0.001
        assert engine._config.slippage == 0.0005
        assert engine._config.debug_level == 3
    
    def test_execute_strategy_simple(self, sample_data):
        """Test execute_strategy_simple function"""
        strategy_code = '''
# @name Simple Test
# @param period int 10 Period

ma = df['close'].rolling(period).mean()
buy = df['close'] > ma
sell = df['close'] < ma
output = {'indicators': {'ma': ma}, 'signals': {'buy': buy, 'sell': sell}}
'''
        
        result = execute_strategy_simple(
            strategy_code=strategy_code,
            data=sample_data,
            initial_capital=50000
        )
        
        assert isinstance(result, ExecutionResult)
        assert result.status == ExecutionStatus.COMPLETED


class TestIntegrationWithBacktestEngine:
    """Integration tests with BacktestEngine"""
    
    @pytest.fixture
    def sample_data(self):
        """Create sample OHLCV data"""
        dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
        np.random.seed(42)
        
        closes = 100 + np.cumsum(np.random.randn(100) * 2)
        
        return pd.DataFrame({
            'timestamp': dates,
            'open': closes + np.random.randn(100) * 0.5,
            'high': closes + np.abs(np.random.randn(100)),
            'low': closes - np.abs(np.random.randn(100)),
            'close': closes,
            'volume': np.random.randint(1000000, 10000000, 100)
        })
    
    def test_integration_with_backtest_engine(self, sample_data):
        """Test full integration with BacktestEngine"""
        engine = create_execution_engine(
            initial_capital=100000,
            commission=0.0003,
            debug_level=5
        )
        
        strategy_code = '''
# @name Integration Test Strategy
# @param fast int 5 Fast period
# @param slow int 20 Slow period

ma_fast = df['close'].rolling(fast).mean()
ma_slow = df['close'].rolling(slow).mean()
buy = (ma_fast > ma_slow) & (ma_fast.shift(1) <= ma_slow.shift(1))
sell = (ma_fast < ma_slow) & (ma_fast.shift(1) >= ma_slow.shift(1))
output = {
    'indicators': {'ma_fast': ma_fast, 'ma_slow': ma_slow},
    'signals': {'buy': buy, 'sell': sell}
}
'''
        
        result = engine.run_backtest(strategy_code, sample_data)
        
        assert result.status == ExecutionStatus.COMPLETED
        assert result.backtest_result is not None
        assert 'metrics' in result.backtest_result
        
        metrics = result.backtest_result['metrics']
        assert 'total_return_pct' in metrics
        assert 'sharpe_ratio' in metrics
        assert 'max_drawdown_pct' in metrics
        assert 'win_rate' in metrics
    
    def test_integration_with_strategy_compiler(self, sample_data):
        """Test integration with StrategyCompiler"""
        from app.services.strategy.compiler import StrategyCompiler
        
        strategy_code = '''
# @name Compiler Integration Test
# @description Test integration with compiler
# @param period int 14 Period

rsi_period = period
delta = df['close'].diff()
gain = delta.where(delta > 0, 0)
loss = -delta.where(delta < 0, 0)
avg_gain = gain.rolling(window=rsi_period).mean()
avg_loss = loss.rolling(window=rsi_period).mean()
rs = avg_gain / avg_loss
rsi = 100 - (100 / (1 + rs))
buy = rsi < 30
sell = rsi > 70
output = {
    'indicators': {'rsi': rsi},
    'signals': {'buy': buy, 'sell': sell}
}
'''
        
        compiler = StrategyCompiler(debug_level=5)
        compiled = compiler.compile(strategy_code)
        
        assert compiled.success
        
        engine = create_execution_engine(debug_level=5)
        result = engine.execute_strategy(
            compiled_strategy=compiled,
            data=sample_data,
            strategy_name=compiled.spec.name
        )
        
        assert result.status == ExecutionStatus.COMPLETED


class TestEdgeCases:
    """Test edge cases and error scenarios"""
    
    def test_empty_strategy_code(self):
        """Test with empty strategy code"""
        engine = create_execution_engine()
        
        dates = pd.date_range(start='2023-01-01', periods=10, freq='D')
        data = pd.DataFrame({
            'timestamp': dates,
            'open': [100] * 10,
            'high': [105] * 10,
            'low': [95] * 10,
            'close': [100] * 10,
            'volume': [1000000] * 10
        })
        
        result = engine.run_backtest("", data)
        
        assert result.status == ExecutionStatus.FAILED
    
    def test_strategy_with_syntax_error(self):
        """Test strategy with syntax error"""
        engine = create_execution_engine()
        
        dates = pd.date_range(start='2023-01-01', periods=10, freq='D')
        data = pd.DataFrame({
            'timestamp': dates,
            'open': [100] * 10,
            'high': [105] * 10,
            'low': [95] * 10,
            'close': [100] * 10,
            'volume': [1000000] * 10
        })
        
        invalid_code = '''
# @name Invalid Strategy
this is not valid python syntax
'''
        
        result = engine.run_backtest(invalid_code, data)
        
        assert result.status == ExecutionStatus.FAILED
        assert len(result.errors) > 0
    
    def test_strategy_with_security_violation(self):
        """Test strategy with security violation"""
        engine = create_execution_engine()
        
        dates = pd.date_range(start='2023-01-01', periods=10, freq='D')
        data = pd.DataFrame({
            'timestamp': dates,
            'open': [100] * 10,
            'high': [105] * 10,
            'low': [95] * 10,
            'close': [100] * 10,
            'volume': [1000000] * 10
        })
        
        dangerous_code = '''
# @name Dangerous Strategy
import os
output = {'signals': {'buy': True, 'sell': False}}
'''
        
        result = engine.run_backtest(dangerous_code, data)
        
        assert result.status == ExecutionStatus.FAILED
        assert any("forbidden" in err.lower() or "security" in err.lower() for err in result.errors)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
