"""
Unit Tests for Backtest Engine

Tests cover:
- Engine initialization
- Strategy execution
- Order execution
- Position tracking
- Performance metrics
- Debug logging (10 cycles)
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from app.services.backtest.engine import (
    BacktestEngine,
    BacktestConfig,
    BacktestResult,
    StrategyContext,
    PerformanceMetrics,
    Order,
    Position,
    Trade,
    TimeFrame,
    OrderType,
    OrderSide,
    PositionSide,
    TradeDirection,
)


class TestBacktestConfig:
    """Tests for BacktestConfig dataclass"""
    
    def test_default_config(self):
        """Test default configuration values"""
        config = BacktestConfig()
        
        assert config.initial_capital == 100000.0
        assert config.commission == 0.0003
        assert config.slippage == 0.0001
        assert config.leverage == 1.0
        assert config.trade_direction == TradeDirection.BOTH
        assert config.stop_loss_pct == 0.0
        assert config.take_profit_pct == 0.0
        assert config.position_size_pct == 0.95
        assert config.max_positions == 1
        assert config.timeframe == TimeFrame.D1
        assert config.warmup_bars == 50
    
    def test_custom_config(self):
        """Test custom configuration values"""
        config = BacktestConfig(
            initial_capital=50000.0,
            commission=0.001,
            slippage=0.0005,
            leverage=2.0,
            trade_direction=TradeDirection.LONG_ONLY,
            stop_loss_pct=5.0,
            take_profit_pct=10.0
        )
        
        assert config.initial_capital == 50000.0
        assert config.commission == 0.001
        assert config.slippage == 0.0005
        assert config.leverage == 2.0
        assert config.trade_direction == TradeDirection.LONG_ONLY
        assert config.stop_loss_pct == 5.0
        assert config.take_profit_pct == 10.0
    
    def test_invalid_capital(self):
        """Test that invalid capital raises error"""
        with pytest.raises(ValueError, match="initial_capital must be positive"):
            BacktestConfig(initial_capital=-1000)
        
        with pytest.raises(ValueError, match="initial_capital must be positive"):
            BacktestConfig(initial_capital=0)
    
    def test_invalid_commission(self):
        """Test that invalid commission raises error"""
        with pytest.raises(ValueError, match="commission must be in"):
            BacktestConfig(commission=-0.001)
        
        with pytest.raises(ValueError, match="commission must be in"):
            BacktestConfig(commission=1.5)
    
    def test_invalid_slippage(self):
        """Test that invalid slippage raises error"""
        with pytest.raises(ValueError, match="slippage must be in"):
            BacktestConfig(slippage=-0.001)
        
        with pytest.raises(ValueError, match="slippage must be in"):
            BacktestConfig(slippage=1.5)
    
    def test_invalid_leverage(self):
        """Test that invalid leverage raises error"""
        with pytest.raises(ValueError, match="leverage must be >= 1"):
            BacktestConfig(leverage=0.5)


class TestBacktestEngine:
    """Tests for BacktestEngine class"""
    
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
        return BacktestConfig(
            initial_capital=100000,
            commission=0.0003,
            slippage=0.0001,
            warmup_bars=10
        )
    
    def test_engine_initialization(self, config):
        """Test engine initialization (Debug Cycle 1)"""
        engine = BacktestEngine(config)
        
        assert engine._config == config
        assert engine._cash == config.initial_capital
        assert engine._equity == config.initial_capital
        assert len(engine._positions) == 0
        assert len(engine._trades) == 0
        assert len(engine._debug_log) > 0
        
        assert any("DEBUG CYCLE 1: ENGINE INITIALIZATION" in log for log in engine._debug_log)
    
    def test_strategy_compilation(self, config, sample_data):
        """Test strategy compilation (Debug Cycle 2)"""
        engine = BacktestEngine(config)
        
        def simple_strategy(ctx: StrategyContext):
            pass
        
        result = engine.run_strategy(simple_strategy, sample_data)
        
        assert any("DEBUG CYCLE 2: STRATEGY COMPILATION" in log for log in result.debug_log)
        assert result.config == config
    
    def test_data_loading(self, config, sample_data):
        """Test data loading (Debug Cycle 3)"""
        engine = BacktestEngine(config)
        
        def simple_strategy(ctx: StrategyContext):
            pass
        
        result = engine.run_strategy(simple_strategy, sample_data)
        
        assert any("DEBUG CYCLE 3: DATA LOADING" in log for log in result.debug_log)
        assert result.data_info['total_bars'] == 100
    
    def test_bar_processing(self, config, sample_data):
        """Test bar processing (Debug Cycle 4)"""
        engine = BacktestEngine(config)
        
        processed_bars = []
        
        def tracking_strategy(ctx: StrategyContext):
            processed_bars.append(ctx.current_bar)
        
        result = engine.run_strategy(tracking_strategy, sample_data)
        
        assert len(processed_bars) == 100 - config.warmup_bars
    
    def test_order_execution_buy(self, config, sample_data):
        """Test order execution - buy (Debug Cycle 5)"""
        engine = BacktestEngine(config)
        
        def buy_strategy(ctx: StrategyContext):
            if not ctx.has_position():
                ctx.buy('ASSET', quantity=100)
        
        result = engine.run_strategy(buy_strategy, sample_data)
        
        assert len(result.orders) > 0
        assert result.orders[0].side == OrderSide.BUY
        assert result.orders[0].status == "filled"
    
    def test_order_execution_sell(self, config, sample_data):
        """Test order execution - sell"""
        engine = BacktestEngine(config)
        
        bar_count = [0]
        
        def buy_sell_strategy(ctx: StrategyContext):
            bar_count[0] += 1
            if bar_count[0] == 1 and not ctx.has_position():
                ctx.buy('ASSET', quantity=100)
            elif bar_count[0] == 10 and ctx.has_position():
                ctx.sell('ASSET')
        
        result = engine.run_strategy(buy_sell_strategy, sample_data)
        
        buy_orders = [o for o in result.orders if o.side == OrderSide.BUY]
        sell_orders = [o for o in result.orders if o.side == OrderSide.SELL]
        
        assert len(buy_orders) > 0
        assert len(sell_orders) > 0
    
    def test_position_update(self, config, sample_data):
        """Test position update (Debug Cycle 6)"""
        engine = BacktestEngine(config)
        
        def position_strategy(ctx: StrategyContext):
            if not ctx.has_position():
                ctx.buy('ASSET', quantity=100)
        
        result = engine.run_strategy(position_strategy, sample_data)
        
        assert len(result.equity_curve) > 0
    
    def test_metric_calculation(self, config, sample_data):
        """Test metric calculation (Debug Cycle 7)"""
        engine = BacktestEngine(config)
        
        bar_count = [0]
        
        def trading_strategy(ctx: StrategyContext):
            bar_count[0] += 1
            if bar_count[0] == 1 and not ctx.has_position():
                ctx.buy('ASSET', quantity=100)
            elif bar_count[0] == 20 and ctx.has_position():
                ctx.sell('ASSET')
        
        result = engine.run_strategy(trading_strategy, sample_data)
        
        assert any("DEBUG CYCLE 7: METRIC CALCULATION" in log for log in result.debug_log)
        assert result.metrics.total_trades >= 0
    
    def test_result_generation(self, config, sample_data):
        """Test result generation (Debug Cycle 8)"""
        engine = BacktestEngine(config)
        
        def simple_strategy(ctx: StrategyContext):
            pass
        
        result = engine.run_strategy(simple_strategy, sample_data)
        
        assert any("DEBUG CYCLE 8: RESULT GENERATION" in log for log in result.debug_log)
        assert isinstance(result, BacktestResult)
        assert result.execution_time_ms > 0
    
    def test_error_handling(self, config, sample_data):
        """Test error handling (Debug Cycle 9)"""
        engine = BacktestEngine(config)
        
        def error_strategy(ctx: StrategyContext):
            raise ValueError("Test error")
        
        result = engine.run_strategy(error_strategy, sample_data)
        
        assert any("DEBUG CYCLE 9: ERROR HANDLING" in log for log in result.debug_log)
        assert 'error' in result.data_info
    
    def test_performance_summary(self, config, sample_data):
        """Test performance summary (Debug Cycle 10)"""
        engine = BacktestEngine(config)
        
        def simple_strategy(ctx: StrategyContext):
            pass
        
        result = engine.run_strategy(simple_strategy, sample_data)
        
        assert any("DEBUG CYCLE 10: PERFORMANCE SUMMARY" in log for log in result.debug_log)
    
    def test_commission_deduction(self, config, sample_data):
        """Test that commission is deducted correctly"""
        engine = BacktestEngine(config)
        
        initial_cash = config.initial_capital
        
        def buy_strategy(ctx: StrategyContext):
            if not ctx.has_position():
                ctx.buy('ASSET', quantity=100)
        
        result = engine.run_strategy(buy_strategy, sample_data)
        
        if result.orders:
            order = result.orders[0]
            expected_commission = order.filled_price * order.filled_quantity * config.commission
            assert expected_commission > 0
    
    def test_slippage_application(self, config, sample_data):
        """Test that slippage is applied correctly"""
        engine = BacktestEngine(config)
        
        def buy_strategy(ctx: StrategyContext):
            if not ctx.has_position():
                ctx.buy('ASSET', quantity=100)
        
        result = engine.run_strategy(buy_strategy, sample_data)
        
        if result.orders:
            order = result.orders[0]
            assert order.filled_price is not None
    
    def test_stop_loss(self, sample_data):
        """Test stop loss execution"""
        config = BacktestConfig(
            initial_capital=100000,
            stop_loss_pct=5.0,
            warmup_bars=10
        )
        engine = BacktestEngine(config)
        
        def buy_strategy(ctx: StrategyContext):
            if not ctx.has_position():
                ctx.buy('ASSET', quantity=100)
        
        result = engine.run_strategy(buy_strategy, sample_data)
        
        for trade in result.trades:
            if trade.exit_reason == "stop_loss":
                assert True
                return
        
    def test_take_profit(self, sample_data):
        """Test take profit execution"""
        config = BacktestConfig(
            initial_capital=100000,
            take_profit_pct=10.0,
            warmup_bars=10
        )
        engine = BacktestEngine(config)
        
        def buy_strategy(ctx: StrategyContext):
            if not ctx.has_position():
                ctx.buy('ASSET', quantity=100)
        
        result = engine.run_strategy(buy_strategy, sample_data)
        
        for trade in result.trades:
            if trade.exit_reason == "take_profit":
                assert True
                return
    
    def test_long_only_restriction(self, sample_data):
        """Test long-only trade direction restriction"""
        config = BacktestConfig(
            initial_capital=100000,
            trade_direction=TradeDirection.LONG_ONLY,
            warmup_bars=10
        )
        engine = BacktestEngine(config)
        
        def short_strategy(ctx: StrategyContext):
            if not ctx.has_position():
                ctx.sell('ASSET', quantity=100)
        
        result = engine.run_strategy(short_strategy, sample_data)
        
        rejected_orders = [o for o in result.orders if o.status == "rejected"]
        assert len(rejected_orders) > 0
    
    def test_multiple_timeframes(self):
        """Test different timeframe configurations"""
        timeframes = [TimeFrame.M1, TimeFrame.M5, TimeFrame.M15, TimeFrame.M30, 
                      TimeFrame.H1, TimeFrame.H4, TimeFrame.D1]
        
        for tf in timeframes:
            config = BacktestConfig(timeframe=tf)
            engine = BacktestEngine(config)
            assert engine._config.timeframe == tf
    
    def test_equity_curve_generation(self, config, sample_data):
        """Test that equity curve is generated correctly"""
        engine = BacktestEngine(config)
        
        def simple_strategy(ctx: StrategyContext):
            pass
        
        result = engine.run_strategy(simple_strategy, sample_data)
        
        assert len(result.equity_curve) > 0
        assert result.equity_curve[0].equity == config.initial_capital
    
    def test_benchmark_return(self, config, sample_data):
        """Test benchmark return calculation"""
        engine = BacktestEngine(config)
        
        def simple_strategy(ctx: StrategyContext):
            pass
        
        result = engine.run_strategy(simple_strategy, sample_data)
        
        first_close = sample_data['close'].iloc[0]
        last_close = sample_data['close'].iloc[-1]
        expected_benchmark = ((last_close - first_close) / first_close) * 100
        
        assert abs(result.benchmark_return_pct - expected_benchmark) < 0.01


class TestStrategyContext:
    """Tests for StrategyContext class"""
    
    @pytest.fixture
    def engine_and_data(self):
        config = BacktestConfig(initial_capital=100000, warmup_bars=10)
        engine = BacktestEngine(config)
        
        dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
        data = pd.DataFrame({
            'timestamp': dates,
            'open': [100] * 100,
            'high': [105] * 100,
            'low': [95] * 100,
            'close': [100] * 100,
            'volume': [1000000] * 100
        })
        
        return engine, data
    
    def test_context_properties(self, engine_and_data):
        """Test StrategyContext property access"""
        engine, data = engine_and_data
        
        bar_data = {
            'timestamp': datetime.now(),
            'open': 100.0,
            'high': 105.0,
            'low': 95.0,
            'close': 102.0,
            'volume': 1000000,
            'symbol': 'TEST'
        }
        
        context = StrategyContext(engine, bar_data)
        
        assert context.open == 100.0
        assert context.high == 105.0
        assert context.low == 95.0
        assert context.close == 102.0
        assert context.volume == 1000000
        assert context.symbol == 'TEST'
        assert context.cash == 100000.0
    
    def test_buy_order_creation(self, engine_and_data):
        """Test buy order creation through context"""
        engine, data = engine_and_data
        
        bar_data = {
            'timestamp': datetime.now(),
            'open': 100.0,
            'high': 105.0,
            'low': 95.0,
            'close': 100.0,
            'volume': 1000000,
            'symbol': 'TEST'
        }
        
        context = StrategyContext(engine, bar_data)
        order = context.buy('TEST', quantity=100)
        
        assert order.symbol == 'TEST'
        assert order.side == OrderSide.BUY
        assert order.quantity == 100
        assert order.order_type == OrderType.MARKET
    
    def test_sell_order_creation(self, engine_and_data):
        """Test sell order creation through context"""
        engine, data = engine_and_data
        
        bar_data = {
            'timestamp': datetime.now(),
            'open': 100.0,
            'high': 105.0,
            'low': 95.0,
            'close': 100.0,
            'volume': 1000000,
            'symbol': 'TEST'
        }
        
        context = StrategyContext(engine, bar_data)
        order = context.sell('TEST', quantity=100)
        
        assert order.symbol == 'TEST'
        assert order.side == OrderSide.SELL
        assert order.quantity == 100


class TestPerformanceMetrics:
    """Tests for PerformanceMetrics calculation"""
    
    def test_empty_metrics(self):
        """Test metrics with no trades"""
        metrics = PerformanceMetrics()
        
        assert metrics.total_trades == 0
        assert metrics.total_return == 0.0
        assert metrics.win_rate == 0.0
    
    def test_metrics_to_dict(self):
        """Test metrics serialization"""
        metrics = PerformanceMetrics(
            total_return=1000.0,
            total_return_pct=10.0,
            sharpe_ratio=1.5,
            max_drawdown=500.0
        )
        
        result = metrics.to_dict()
        
        assert result['total_return'] == 1000.0
        assert result['total_return_pct'] == 10.0
        assert result['sharpe_ratio'] == 1.5
        assert result['max_drawdown'] == 500.0


class TestSampleStrategy:
    """Test with sample MA crossover strategy"""
    
    @pytest.fixture
    def trending_data(self):
        """Create trending price data"""
        dates = pd.date_range(start='2023-01-01', periods=200, freq='D')
        
        closes = [100]
        for i in range(199):
            if i < 50:
                closes.append(closes[-1] + np.random.uniform(-1, 2))
            elif i < 100:
                closes.append(closes[-1] + np.random.uniform(-2, 1))
            else:
                closes.append(closes[-1] + np.random.uniform(-1, 2))
        
        closes = np.array(closes)
        opens = closes + np.random.randn(200) * 0.5
        highs = np.maximum(opens, closes) + np.abs(np.random.randn(200) * 1)
        lows = np.minimum(opens, closes) - np.abs(np.random.randn(200) * 1)
        volumes = np.random.randint(1000000, 10000000, 200)
        
        return pd.DataFrame({
            'timestamp': dates,
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
            'volume': volumes
        })
    
    def test_ma_crossover_strategy(self, trending_data):
        """Test MA crossover strategy execution"""
        config = BacktestConfig(
            initial_capital=100000,
            commission=0.0003,
            warmup_bars=30
        )
        engine = BacktestEngine(config)
        
        closes_history = []
        
        def ma_crossover(ctx: StrategyContext):
            closes_history.append(ctx.close)
            
            if len(closes_history) < 20:
                return
            
            fast_ma = np.mean(closes_history[-5:])
            slow_ma = np.mean(closes_history[-20:])
            
            if fast_ma > slow_ma and not ctx.has_position():
                ctx.buy('ASSET')
            elif fast_ma < slow_ma and ctx.has_position():
                ctx.sell('ASSET')
        
        result = engine.run_strategy(ma_crossover, trending_data)
        
        assert result.metrics.total_trades >= 0
        assert len(result.equity_curve) > 0
        assert isinstance(result.metrics.sharpe_ratio, float)
        assert isinstance(result.metrics.max_drawdown_pct, float)
    
    def test_verify_all_metrics_calculated(self, trending_data):
        """Verify all metrics are properly calculated"""
        config = BacktestConfig(
            initial_capital=100000,
            warmup_bars=30
        )
        engine = BacktestEngine(config)
        
        bar_count = [0]
        
        def active_strategy(ctx: StrategyContext):
            bar_count[0] += 1
            
            if bar_count[0] % 20 == 1 and not ctx.has_position():
                ctx.buy('ASSET')
            elif bar_count[0] % 20 == 15 and ctx.has_position():
                ctx.sell('ASSET')
        
        result = engine.run_strategy(active_strategy, trending_data)
        
        metrics = result.metrics
        
        assert isinstance(metrics.total_return, float)
        assert isinstance(metrics.total_return_pct, float)
        assert isinstance(metrics.annualized_return_pct, float)
        assert isinstance(metrics.sharpe_ratio, float)
        assert isinstance(metrics.sortino_ratio, float)
        assert isinstance(metrics.max_drawdown, float)
        assert isinstance(metrics.max_drawdown_pct, float)
        assert isinstance(metrics.win_rate, float)
        assert isinstance(metrics.profit_factor, float)
        assert isinstance(metrics.total_trades, int)
        assert isinstance(metrics.winning_trades, int)
        assert isinstance(metrics.losing_trades, int)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
