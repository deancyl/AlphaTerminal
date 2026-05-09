#!/usr/bin/env python3
"""
Sample Strategy Test for Backtest Engine

Demonstrates the backtest engine with a simple MA crossover strategy.
"""
import sys
sys.path.insert(0, '/vol3/1000/docker/opencode/workspace/AlphaTerminal/backend')

import pandas as pd
import numpy as np
from datetime import datetime
from app.services.backtest.engine import (
    BacktestEngine,
    BacktestConfig,
    StrategyContext,
    TimeFrame,
    TradeDirection,
)


def generate_sample_data(days: int = 252) -> pd.DataFrame:
    """Generate sample OHLCV data with trend"""
    np.random.seed(42)
    dates = pd.date_range(start='2023-01-01', periods=days, freq='D')
    
    # Generate trending price data
    closes = [100]
    for i in range(days - 1):
        if i < 60:
            closes.append(closes[-1] + np.random.uniform(-0.5, 1.5))
        elif i < 120:
            closes.append(closes[-1] + np.random.uniform(-1.5, 0.5))
        else:
            closes.append(closes[-1] + np.random.uniform(-0.5, 1.5))
    
    closes = np.array(closes)
    opens = closes + np.random.randn(days) * 0.5
    highs = np.maximum(opens, closes) + np.abs(np.random.randn(days) * 1)
    lows = np.minimum(opens, closes) - np.abs(np.random.randn(days) * 1)
    volumes = np.random.randint(1000000, 10000000, days)
    
    return pd.DataFrame({
        'timestamp': dates,
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': volumes
    })


def ma_crossover_strategy(ctx: StrategyContext):
    """Simple MA crossover strategy"""
    global price_history
    price_history.append(ctx.close)
    
    if len(price_history) < 30:
        return
    
    fast_ma = np.mean(price_history[-10:])
    slow_ma = np.mean(price_history[-30:])
    
    if fast_ma > slow_ma and not ctx.has_position():
        ctx.buy('AAPL')
    elif fast_ma < slow_ma and ctx.has_position():
        ctx.sell('AAPL')


def rsi_strategy(ctx: StrategyContext):
    """RSI mean reversion strategy"""
    global price_history
    price_history.append(ctx.close)
    
    if len(price_history) < 20:
        return
    
    # Calculate RSI
    changes = [price_history[i] - price_history[i-1] for i in range(1, len(price_history))]
    gains = [max(0, c) for c in changes[-14:]]
    losses = [abs(min(0, c)) for c in changes[-14:]]
    
    avg_gain = sum(gains) / 14
    avg_loss = sum(losses) / 14
    
    if avg_loss == 0:
        rsi = 100
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
    
    if rsi < 30 and not ctx.has_position():
        ctx.buy('AAPL')
    elif rsi > 70 and ctx.has_position():
        ctx.sell('AAPL')


def run_backtest():
    """Run backtest with sample strategy"""
    global price_history
    
    print("=" * 70)
    print("BACKTEST ENGINE DEMO")
    print("=" * 70)
    
    # Generate data
    print("\n[1] Generating sample data...")
    data = generate_sample_data(252)
    print(f"    Generated {len(data)} bars")
    print(f"    Date range: {data['timestamp'].min()} to {data['timestamp'].max()}")
    print(f"    Price range: ${data['close'].min():.2f} to ${data['close'].max():.2f}")
    
    # Configure backtest
    print("\n[2] Configuring backtest...")
    config = BacktestConfig(
        initial_capital=100000,
        commission=0.0003,
        slippage=0.0001,
        leverage=1.0,
        trade_direction=TradeDirection.BOTH,
        stop_loss_pct=5.0,
        take_profit_pct=10.0,
        position_size_pct=0.95,
        max_positions=1,
        timeframe=TimeFrame.D1,
        warmup_bars=30
    )
    print(f"    Initial capital: ${config.initial_capital:,.2f}")
    print(f"    Commission: {config.commission * 100:.4f}%")
    print(f"    Slippage: {config.slippage * 100:.4f}%")
    print(f"    Stop loss: {config.stop_loss_pct}%")
    print(f"    Take profit: {config.take_profit_pct}%")
    
    # Run MA crossover strategy
    print("\n[3] Running MA Crossover Strategy...")
    price_history = []
    engine = BacktestEngine(config)
    result = engine.run_strategy(ma_crossover_strategy, data, symbol='AAPL')
    
    # Print results
    print("\n" + "=" * 70)
    print("RESULTS - MA CROSSOVER STRATEGY")
    print("=" * 70)
    print(f"Total Return: ${result.metrics.total_return:,.2f} ({result.metrics.total_return_pct:.2f}%)")
    print(f"Annualized Return: {result.metrics.annualized_return_pct:.2f}%")
    print(f"Sharpe Ratio: {result.metrics.sharpe_ratio:.3f}")
    print(f"Sortino Ratio: {result.metrics.sortino_ratio:.3f}")
    print(f"Max Drawdown: ${result.metrics.max_drawdown:,.2f} ({result.metrics.max_drawdown_pct:.2f}%)")
    print(f"Win Rate: {result.metrics.win_rate:.2f}%")
    print(f"Profit Factor: {result.metrics.profit_factor:.2f}")
    print(f"Total Trades: {result.metrics.total_trades}")
    print(f"Winning/Losing: {result.metrics.winning_trades}/{result.metrics.losing_trades}")
    print(f"Benchmark Return: {result.benchmark_return_pct:.2f}%")
    print(f"Execution Time: {result.execution_time_ms:.2f}ms")
    
    # Show sample trades
    print("\n[4] Sample Trades (first 5):")
    for i, trade in enumerate(result.trades[:5]):
        print(f"    Trade {i+1}: {trade.side.value} {trade.quantity} @ ${trade.entry_price:.2f} -> ${trade.exit_price:.2f}")
        print(f"             PnL: ${trade.pnl:.2f} ({trade.pnl_pct:.2f}%) - {trade.exit_reason}")
    
    # Run RSI strategy
    print("\n" + "=" * 70)
    print("RESULTS - RSI MEAN REVERSION STRATEGY")
    print("=" * 70)
    
    price_history = []
    engine2 = BacktestEngine(config)
    result2 = engine2.run_strategy(rsi_strategy, data, symbol='AAPL')
    
    print(f"Total Return: ${result2.metrics.total_return:,.2f} ({result2.metrics.total_return_pct:.2f}%)")
    print(f"Annualized Return: {result2.metrics.annualized_return_pct:.2f}%")
    print(f"Sharpe Ratio: {result2.metrics.sharpe_ratio:.3f}")
    print(f"Max Drawdown: {result2.metrics.max_drawdown_pct:.2f}%")
    print(f"Win Rate: {result2.metrics.win_rate:.2f}%")
    print(f"Total Trades: {result2.metrics.total_trades}")
    
    # Show debug log summary
    print("\n[5] Debug Log Summary:")
    debug_cycles = [
        "DEBUG CYCLE 1: ENGINE INITIALIZATION",
        "DEBUG CYCLE 2: STRATEGY COMPILATION",
        "DEBUG CYCLE 3: DATA LOADING",
        "DEBUG CYCLE 7: METRIC CALCULATION",
        "DEBUG CYCLE 8: RESULT GENERATION",
        "DEBUG CYCLE 10: PERFORMANCE SUMMARY"
    ]
    
    for cycle in debug_cycles:
        found = any(cycle in log for log in result.debug_log)
        status = "✓" if found else "✗"
        print(f"    {status} {cycle}")
    
    print("\n" + "=" * 70)
    print("BACKTEST COMPLETED SUCCESSFULLY")
    print("=" * 70)
    
    return result


if __name__ == "__main__":
    price_history = []
    result = run_backtest()
