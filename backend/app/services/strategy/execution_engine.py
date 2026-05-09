"""
Strategy Execution Engine with Comprehensive Debug Logging

This module provides a unified execution engine that:
- Executes compiled strategies with real-time tracking
- Integrates with BacktestEngine and StrategyCompiler
- Manages execution lifecycle (start, monitor, cancel)
- Provides performance tracking and metrics
- Implements 5 comprehensive debug cycles

Debug Cycles:
  1. Execution initialization
  2. Strategy compilation check
  3. Data loading validation
  4. Execution progress tracking
  5. Result generation and storage

Author: AlphaTerminal Team
Version: 0.6.12
"""

from __future__ import annotations

import logging
import time
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
import pandas as pd

# Configure logger with DEBUG level
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create console handler if not exists
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [ExecutionEngine] %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


# ============================================================================
# Enums
# ============================================================================

class ExecutionStatus(Enum):
    """Execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionType(Enum):
    """Execution type"""
    BACKTEST = "backtest"
    PAPER_TRADING = "paper_trading"
    LIVE_TRADING = "live_trading"


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ExecutionMetrics:
    """
    Execution performance metrics
    
    Attributes:
        execution_time_ms: Total execution time in milliseconds
        bars_processed: Number of bars processed
        trades_executed: Number of trades executed
        avg_bar_time_ms: Average time per bar in milliseconds
        peak_memory_mb: Peak memory usage in MB
        cpu_usage_pct: CPU usage percentage
    """
    execution_time_ms: float = 0.0
    bars_processed: int = 0
    trades_executed: int = 0
    avg_bar_time_ms: float = 0.0
    peak_memory_mb: float = 0.0
    cpu_usage_pct: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'execution_time_ms': round(self.execution_time_ms, 2),
            'bars_processed': self.bars_processed,
            'trades_executed': self.trades_executed,
            'avg_bar_time_ms': round(self.avg_bar_time_ms, 4),
            'peak_memory_mb': round(self.peak_memory_mb, 2),
            'cpu_usage_pct': round(self.cpu_usage_pct, 2),
        }


@dataclass
class ExecutionResult:
    """
    Complete execution result
    
    Attributes:
        execution_id: Unique execution identifier
        strategy_id: Strategy identifier
        strategy_name: Strategy name
        execution_type: Type of execution (backtest/paper/live)
        status: Execution status
        start_time: Execution start timestamp
        end_time: Execution end timestamp
        metrics: Execution performance metrics
        trades: List of executed trades
        equity_curve: Equity curve over time
        backtest_result: Full backtest result (if backtest)
        errors: List of errors encountered
        warnings: List of warnings
        debug_log: Debug messages from all cycles
    """
    execution_id: str
    strategy_id: str
    strategy_name: str
    execution_type: ExecutionType
    status: ExecutionStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    metrics: ExecutionMetrics = field(default_factory=ExecutionMetrics)
    trades: List[Dict[str, Any]] = field(default_factory=list)
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)
    backtest_result: Optional[Dict[str, Any]] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    debug_log: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'execution_id': self.execution_id,
            'strategy_id': self.strategy_id,
            'strategy_name': self.strategy_name,
            'execution_type': self.execution_type.value,
            'status': self.status.value,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'metrics': self.metrics.to_dict(),
            'trades': self.trades,
            'equity_curve': self.equity_curve,
            'backtest_result': self.backtest_result,
            'errors': self.errors,
            'warnings': self.warnings,
            'debug_log': self.debug_log,
        }


@dataclass
class ExecutionConfig:
    """
    Execution configuration
    
    Attributes:
        initial_capital: Starting capital
        commission: Commission rate
        slippage: Slippage rate
        leverage: Leverage multiplier
        max_positions: Maximum concurrent positions
        position_size_pct: Position size as % of capital
        stop_loss_pct: Stop loss percentage
        take_profit_pct: Take profit percentage
        enable_debug_logging: Enable comprehensive debug logging
        debug_level: Debug level (1-5)
    """
    initial_capital: float = 100000.0
    commission: float = 0.0003
    slippage: float = 0.0001
    leverage: float = 1.0
    max_positions: int = 1
    position_size_pct: float = 0.95
    stop_loss_pct: float = 0.0
    take_profit_pct: float = 0.0
    enable_debug_logging: bool = True
    debug_level: int = 5
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'initial_capital': self.initial_capital,
            'commission': self.commission,
            'slippage': self.slippage,
            'leverage': self.leverage,
            'max_positions': self.max_positions,
            'position_size_pct': self.position_size_pct,
            'stop_loss_pct': self.stop_loss_pct,
            'take_profit_pct': self.take_profit_pct,
            'enable_debug_logging': self.enable_debug_logging,
            'debug_level': self.debug_level,
        }


# ============================================================================
# Strategy Execution Engine
# ============================================================================

class StrategyExecutionEngine:
    """
    Unified Strategy Execution Engine with Comprehensive Debug Logging
    
    Features:
    - Execute compiled strategies with real-time tracking
    - Integrate with BacktestEngine and StrategyCompiler
    - Manage execution lifecycle (start, monitor, cancel)
    - Performance tracking and metrics
    - 5 comprehensive debug cycles
    
    Usage:
        engine = StrategyExecutionEngine()
        result = engine.execute_strategy(compiled_strategy, data)
    """
    
    def __init__(self, config: Optional[ExecutionConfig] = None):
        """
        Initialize execution engine.
        
        Args:
            config: Execution configuration
        """
        self._config = config or ExecutionConfig()
        self._debug_log: List[str] = []
        self._active_executions: Dict[str, ExecutionResult] = {}
        
        # Import dependencies
        self._backtest_engine = None
        self._strategy_compiler = None
        
        # ══════════════════════════════════════════════════════════════
        # DEBUG CYCLE 1: Execution Initialization
        # ══════════════════════════════════════════════════════════════
        self._log_debug("=" * 80)
        self._log_debug("DEBUG CYCLE 1: EXECUTION INITIALIZATION")
        self._log_debug("=" * 80)
        self._log_debug(f"Initial Capital: ${self._config.initial_capital:,.2f}")
        self._log_debug(f"Commission Rate: {self._config.commission * 100:.4f}%")
        self._log_debug(f"Slippage Rate: {self._config.slippage * 100:.4f}%")
        self._log_debug(f"Leverage: {self._config.leverage}x")
        self._log_debug(f"Max Positions: {self._config.max_positions}")
        self._log_debug(f"Position Size: {self._config.position_size_pct * 100}% of capital")
        self._log_debug(f"Stop Loss: {self._config.stop_loss_pct}% (0 = disabled)")
        self._log_debug(f"Take Profit: {self._config.take_profit_pct}% (0 = disabled)")
        self._log_debug(f"Debug Logging: {'Enabled' if self._config.enable_debug_logging else 'Disabled'}")
        self._log_debug(f"Debug Level: {self._config.debug_level}/5")
        self._log_debug("-" * 80)
        self._log_debug("✓ Execution engine initialized successfully")
        self._log_debug("")
    
    def _log_debug(self, message: str):
        """Add message to debug log"""
        self._debug_log.append(message)
        logger.debug(message)
    
    def _get_backtest_engine(self):
        """Lazy load BacktestEngine"""
        if self._backtest_engine is None:
            from ..backtest.engine import BacktestEngine, BacktestConfig, TimeFrame, TradeDirection
            self._BacktestEngine = BacktestEngine
            self._BacktestConfig = BacktestConfig
            self._TimeFrame = TimeFrame
            self._TradeDirection = TradeDirection
            self._backtest_engine = True
        return self._BacktestEngine, self._BacktestConfig
    
    def _get_strategy_compiler(self):
        """Lazy load StrategyCompiler"""
        if self._strategy_compiler is None:
            from .compiler import StrategyCompiler, CompilationResult
            self._StrategyCompiler = StrategyCompiler
            self._CompilationResult = CompilationResult
            self._strategy_compiler = True
        return self._StrategyCompiler
    
    def execute_strategy(
        self,
        compiled_strategy: Any,
        data: pd.DataFrame,
        strategy_id: Optional[str] = None,
        strategy_name: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        symbol: str = "ASSET"
    ) -> ExecutionResult:
        """
        Execute a compiled strategy.
        
        Args:
            compiled_strategy: Compiled strategy (CompilationResult or execute function)
            data: DataFrame with OHLCV data
            strategy_id: Strategy identifier (auto-generated if None)
            strategy_name: Strategy name
            params: Strategy parameters
            symbol: Symbol name
            
        Returns:
            ExecutionResult with execution details
        """
        execution_id = str(uuid.uuid4())
        strategy_id = strategy_id or f"strategy_{int(time.time())}"
        strategy_name = strategy_name or "Unnamed Strategy"
        
        start_time = datetime.now()
        
        result = ExecutionResult(
            execution_id=execution_id,
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            execution_type=ExecutionType.BACKTEST,
            status=ExecutionStatus.PENDING,
            start_time=start_time,
        )
        
        self._active_executions[execution_id] = result
        
        try:
            # ══════════════════════════════════════════════════════════════
            # DEBUG CYCLE 2: Strategy Compilation Check
            # ══════════════════════════════════════════════════════════════
            self._log_debug("=" * 80)
            self._log_debug("DEBUG CYCLE 2: STRATEGY COMPILATION CHECK")
            self._log_debug("=" * 80)
            
            execute_func = None
            spec = None
            
            # Check if compiled_strategy is a CompilationResult
            if hasattr(compiled_strategy, 'execute_func'):
                # It's a CompilationResult
                if not compiled_strategy.success:
                    raise ValueError(f"Strategy compilation failed: {compiled_strategy.errors}")
                
                execute_func = compiled_strategy.execute_func
                spec = compiled_strategy.spec
                
                self._log_debug(f"Strategy Type: CompilationResult")
                self._log_debug(f"Strategy Name: {spec.name if spec else 'Unknown'}")
                self._log_debug(f"Strategy Type: {spec.strategy_type if spec else 'Unknown'}")
                self._log_debug(f"Compilation Success: True")
                self._log_debug(f"Parameters: {list(spec.parameters.keys()) if spec else []}")
                
            elif callable(compiled_strategy):
                # It's already an execute function
                execute_func = compiled_strategy
                
                self._log_debug(f"Strategy Type: Callable Function")
                self._log_debug(f"Strategy Name: {strategy_name}")
                self._log_debug(f"Function: {execute_func.__name__ if hasattr(execute_func, '__name__') else 'lambda'}")
                
            else:
                raise ValueError(f"Invalid strategy type: {type(compiled_strategy)}")
            
            self._log_debug("✓ Strategy compilation validated")
            self._log_debug("")
            
            # Update status
            result.status = ExecutionStatus.RUNNING
            
            # ══════════════════════════════════════════════════════════════
            # DEBUG CYCLE 3: Data Loading Validation
            # ══════════════════════════════════════════════════════════════
            self._log_debug("=" * 80)
            self._log_debug("DEBUG CYCLE 3: DATA LOADING VALIDATION")
            self._log_debug("=" * 80)
            
            # Validate data
            if data is None or len(data) == 0:
                raise ValueError("Data cannot be empty")
            
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            missing_cols = [col for col in required_cols if col not in data.columns]
            if missing_cols:
                raise ValueError(f"Missing required columns: {missing_cols}")
            
            # Ensure timestamp column
            if 'timestamp' not in data.columns:
                if isinstance(data.index, pd.DatetimeIndex):
                    data = data.reset_index()
                    data.rename(columns={'index': 'timestamp'}, inplace=True)
                else:
                    data['timestamp'] = pd.date_range(start='2020-01-01', periods=len(data), freq='D')
            
            self._log_debug(f"Data Shape: {data.shape[0]} rows × {data.shape[1]} columns")
            self._log_debug(f"Date Range: {data['timestamp'].min()} to {data['timestamp'].max()}")
            self._log_debug(f"Price Range: ${data['close'].min():.2f} to ${data['close'].max():.2f}")
            self._log_debug(f"Volume Range: {data['volume'].min():,.0f} to {data['volume'].max():,.0f}")
            self._log_debug(f"Symbol: {symbol}")
            self._log_debug("✓ Data validated successfully")
            self._log_debug("")
            
            # ══════════════════════════════════════════════════════════════
            # DEBUG CYCLE 4: Execution Progress Tracking
            # ══════════════════════════════════════════════════════════════
            self._log_debug("=" * 80)
            self._log_debug("DEBUG CYCLE 4: EXECUTION PROGRESS TRACKING")
            self._log_debug("=" * 80)
            
            execution_start = time.time()
            
            # Create backtest configuration
            BacktestEngine, BacktestConfig = self._get_backtest_engine()
            
            backtest_config = BacktestConfig(
                initial_capital=self._config.initial_capital,
                commission=self._config.commission,
                slippage=self._config.slippage,
                leverage=self._config.leverage,
                max_positions=self._config.max_positions,
                position_size_pct=self._config.position_size_pct,
                stop_loss_pct=self._config.stop_loss_pct,
                take_profit_pct=self._config.take_profit_pct,
            )
            
            self._log_debug(f"Backtest Config Created:")
            self._log_debug(f"  Initial Capital: ${backtest_config.initial_capital:,.2f}")
            self._log_debug(f"  Commission: {backtest_config.commission * 100:.4f}%")
            self._log_debug(f"  Slippage: {backtest_config.slippage * 100:.4f}%")
            
            # Create backtest engine
            bt_engine = BacktestEngine(backtest_config)
            
            self._log_debug("Backtest Engine Created")
            self._log_debug("Starting Strategy Execution...")
            self._log_debug("")
            
            # Wrap execute function for backtest
            def strategy_wrapper(ctx):
                """Wrapper to execute strategy with context"""
                try:
                    # Create bar data dict
                    bar_data = {
                        'open': ctx.open,
                        'high': ctx.high,
                        'low': ctx.low,
                        'close': ctx.close,
                        'volume': ctx.volume,
                        'timestamp': ctx.timestamp,
                    }
                    
                    # Create single-row DataFrame
                    bar_df = pd.DataFrame([bar_data])
                    
                    # Execute strategy
                    if spec and spec.strategy_type == "indicator":
                        # Indicator strategy
                        params_dict = params or {}
                        output = execute_func(bar_df, params_dict)
                        
                        # Process signals
                        if output and 'signals' in output:
                            signals = output['signals']
                            if signals.get('buy', False):
                                if not ctx.has_position():
                                    ctx.buy(symbol)
                            elif signals.get('sell', False):
                                if ctx.has_position(symbol):
                                    ctx.close_position(symbol)
                    else:
                        # Script strategy or callable
                        output = execute_func(bar_df)
                        
                        # Process output
                        if output and 'signals' in output:
                            signals = output['signals']
                            if signals.get('buy', False):
                                if not ctx.has_position():
                                    ctx.buy(symbol)
                            elif signals.get('sell', False):
                                if ctx.has_position(symbol):
                                    ctx.close_position(symbol)
                                
                except Exception as e:
                    self._log_debug(f"ERROR in strategy execution at bar: {e}")
                    logger.warning(f"Strategy execution error: {e}")
            
            # Run backtest
            self._log_debug("Running Backtest...")
            backtest_result = bt_engine.run_strategy(strategy_wrapper, data, symbol)
            
            execution_time_ms = (time.time() - execution_start) * 1000
            
            self._log_debug(f"Execution Time: {execution_time_ms:.2f}ms")
            self._log_debug(f"Bars Processed: {len(data)}")
            self._log_debug(f"Trades Executed: {len(backtest_result.trades)}")
            self._log_debug("✓ Execution completed")
            self._log_debug("")
            
            # ══════════════════════════════════════════════════════════════
            # DEBUG CYCLE 5: Result Generation and Storage
            # ══════════════════════════════════════════════════════════════
            self._log_debug("=" * 80)
            self._log_debug("DEBUG CYCLE 5: RESULT GENERATION AND STORAGE")
            self._log_debug("=" * 80)
            
            # Create execution metrics
            metrics = ExecutionMetrics(
                execution_time_ms=execution_time_ms,
                bars_processed=len(data),
                trades_executed=len(backtest_result.trades),
                avg_bar_time_ms=execution_time_ms / len(data) if len(data) > 0 else 0.0,
            )
            
            self._log_debug(f"Metrics Generated:")
            self._log_debug(f"  Execution Time: {metrics.execution_time_ms:.2f}ms")
            self._log_debug(f"  Bars Processed: {metrics.bars_processed}")
            self._log_debug(f"  Trades Executed: {metrics.trades_executed}")
            self._log_debug(f"  Avg Bar Time: {metrics.avg_bar_time_ms:.4f}ms")
            
            # Update result
            result.status = ExecutionStatus.COMPLETED
            result.end_time = datetime.now()
            result.metrics = metrics
            result.trades = [t.to_dict() for t in backtest_result.trades]
            result.equity_curve = [e.to_dict() for e in backtest_result.equity_curve]
            result.backtest_result = backtest_result.to_dict()
            result.debug_log = self._debug_log.copy()
            
            self._log_debug(f"Result Generated:")
            self._log_debug(f"  Execution ID: {result.execution_id}")
            self._log_debug(f"  Strategy ID: {result.strategy_id}")
            self._log_debug(f"  Status: {result.status.value}")
            self._log_debug(f"  Trades: {len(result.trades)}")
            self._log_debug(f"  Equity Points: {len(result.equity_curve)}")
            
            # Log performance summary
            if backtest_result.trades:
                total_return = backtest_result.metrics.total_return
                total_return_pct = backtest_result.metrics.total_return_pct
                sharpe = backtest_result.metrics.sharpe_ratio
                max_dd = backtest_result.metrics.max_drawdown_pct
                win_rate = backtest_result.metrics.win_rate
                
                self._log_debug("")
                self._log_debug("Performance Summary:")
                self._log_debug(f"  Total Return: ${total_return:,.2f} ({total_return_pct:.2f}%)")
                self._log_debug(f"  Sharpe Ratio: {sharpe:.3f}")
                self._log_debug(f"  Max Drawdown: {max_dd:.2f}%")
                self._log_debug(f"  Win Rate: {win_rate:.2f}%")
            
            self._log_debug("✓ Result stored successfully")
            self._log_debug("=" * 80)
            self._log_debug("✓ EXECUTION COMPLETED SUCCESSFULLY")
            self._log_debug("=" * 80)
            
            return result
            
        except Exception as e:
            # Error handling
            self._log_debug("=" * 80)
            self._log_debug("ERROR IN EXECUTION")
            self._log_debug("=" * 80)
            self._log_debug(f"ERROR: {type(e).__name__}: {e}")
            self._log_debug(f"Traceback:\n{traceback.format_exc()}")
            
            result.status = ExecutionStatus.FAILED
            result.end_time = datetime.now()
            result.errors.append(str(e))
            result.errors.append(traceback.format_exc())
            result.debug_log = self._debug_log.copy()
            
            return result
        
        finally:
            # Clean up
            if execution_id in self._active_executions:
                del self._active_executions[execution_id]
    
    def run_backtest(
        self,
        strategy_code: str,
        data: pd.DataFrame,
        config: Optional[Dict[str, Any]] = None,
        symbol: str = "ASSET"
    ) -> ExecutionResult:
        """
        Run backtest with strategy code.
        
        Args:
            strategy_code: Strategy DSL code
            data: DataFrame with OHLCV data
            config: Backtest configuration
            symbol: Symbol name
            
        Returns:
            ExecutionResult with backtest results
        """
        # Compile strategy
        StrategyCompiler = self._get_strategy_compiler()
        compiler = StrategyCompiler(debug_level=self._config.debug_level)
        
        compilation_result = compiler.compile(strategy_code, strategy_type="auto")
        
        if not compilation_result.success:
            execution_id = str(uuid.uuid4())
            return ExecutionResult(
                execution_id=execution_id,
                strategy_id=f"strategy_{int(time.time())}",
                strategy_name=compilation_result.spec.name if compilation_result.spec else "Unknown",
                execution_type=ExecutionType.BACKTEST,
                status=ExecutionStatus.FAILED,
                start_time=datetime.now(),
                end_time=datetime.now(),
                errors=compilation_result.errors,
                debug_log=self._debug_log,
            )
        
        # Execute strategy
        strategy_name = compilation_result.spec.name if compilation_result.spec else "Unnamed"
        
        return self.execute_strategy(
            compiled_strategy=compilation_result,
            data=data,
            strategy_name=strategy_name,
            params=config,
            symbol=symbol,
        )
    
    def get_execution_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        Get execution status by ID.
        
        Args:
            execution_id: Execution identifier
            
        Returns:
            Execution status dict or None if not found
        """
        if execution_id in self._active_executions:
            result = self._active_executions[execution_id]
            return {
                'execution_id': result.execution_id,
                'strategy_id': result.strategy_id,
                'strategy_name': result.strategy_name,
                'status': result.status.value,
                'start_time': result.start_time.isoformat() if result.start_time else None,
            }
        return None
    
    def cancel_execution(self, execution_id: str) -> bool:
        """
        Cancel active execution.
        
        Args:
            execution_id: Execution identifier
            
        Returns:
            True if cancelled, False if not found
        """
        if execution_id in self._active_executions:
            result = self._active_executions[execution_id]
            result.status = ExecutionStatus.CANCELLED
            result.end_time = datetime.now()
            self._log_debug(f"Execution {execution_id} cancelled")
            return True
        return False
    
    def get_active_executions(self) -> List[Dict[str, Any]]:
        """
        Get all active executions.
        
        Returns:
            List of active execution status dicts
        """
        return [
            {
                'execution_id': result.execution_id,
                'strategy_id': result.strategy_id,
                'strategy_name': result.strategy_name,
                'status': result.status.value,
                'start_time': result.start_time.isoformat() if result.start_time else None,
            }
            for result in self._active_executions.values()
        ]


# ============================================================================
# Convenience Functions
# ============================================================================

def create_execution_engine(
    initial_capital: float = 100000.0,
    commission: float = 0.0003,
    slippage: float = 0.0001,
    enable_debug_logging: bool = True,
    debug_level: int = 5,
) -> StrategyExecutionEngine:
    """
    Create execution engine with configuration.
    
    Args:
        initial_capital: Starting capital
        commission: Commission rate
        slippage: Slippage rate
        enable_debug_logging: Enable debug logging
        debug_level: Debug level (1-5)
    
    Returns:
        Configured StrategyExecutionEngine
    """
    config = ExecutionConfig(
        initial_capital=initial_capital,
        commission=commission,
        slippage=slippage,
        enable_debug_logging=enable_debug_logging,
        debug_level=debug_level,
    )
    
    return StrategyExecutionEngine(config)


def execute_strategy_simple(
    strategy_code: str,
    data: pd.DataFrame,
    initial_capital: float = 100000.0,
) -> ExecutionResult:
    """
    Execute strategy with simple configuration.
    
    Args:
        strategy_code: Strategy DSL code
        data: DataFrame with OHLCV data
        initial_capital: Starting capital
    
    Returns:
        ExecutionResult
    """
    engine = create_execution_engine(initial_capital=initial_capital)
    return engine.run_backtest(strategy_code, data)


# ============================================================================
# Example Usage
# ============================================================================

EXAMPLE_STRATEGY_CODE = '''
# @name 简单均线策略
# @description 短期均线上穿长期均线时买入
# @param fast_period int 5 短期均线周期
# @param slow_period int 20 长期均线周期
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


# ============================================================================
# Main Entry Point (for testing)
# ============================================================================

if __name__ == "__main__":
    print("Testing Strategy Execution Engine...")
    print("=" * 80)
    
    # Create sample data
    import numpy as np
    
    np.random.seed(42)
    dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
    
    # Generate random price data with trend
    returns = np.random.randn(100) * 0.02
    price_data = 100 * (1 + returns).cumprod()
    
    data = pd.DataFrame({
        'timestamp': dates,
        'open': price_data * (1 + np.random.randn(100) * 0.005),
        'high': price_data * (1 + np.abs(np.random.randn(100) * 0.01)),
        'low': price_data * (1 - np.abs(np.random.randn(100) * 0.01)),
        'close': price_data,
        'volume': np.random.randint(1000000, 5000000, 100),
    })
    
    # Create execution engine
    engine = create_execution_engine(
        initial_capital=100000,
        enable_debug_logging=True,
        debug_level=5,
    )
    
    # Run backtest
    print("\n[Test 1] Running Backtest with Strategy Code")
    result = engine.run_backtest(EXAMPLE_STRATEGY_CODE, data)
    
    print(f"\nResult: {result.status.value}")
    print(f"Execution ID: {result.execution_id}")
    print(f"Strategy: {result.strategy_name}")
    print(f"Execution Time: {result.metrics.execution_time_ms:.2f}ms")
    print(f"Trades: {result.metrics.trades_executed}")
    
    if result.backtest_result:
        metrics = result.backtest_result.get('metrics', {})
        print(f"\nPerformance:")
        print(f"  Total Return: {metrics.get('total_return_pct', 0):.2f}%")
        print(f"  Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.3f}")
        print(f"  Max Drawdown: {metrics.get('max_drawdown_pct', 0):.2f}%")
        print(f"  Win Rate: {metrics.get('win_rate', 0):.2f}%")
    
    print("\n" + "=" * 80)
    print("Test completed!")
