"""
Walk-Forward Analysis for Out-of-Sample Validation

Implements walk-forward optimization to detect overfitting and validate
strategy performance on out-of-sample data.
"""
import logging
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field
import statistics

logger = logging.getLogger(__name__)


@dataclass
class WindowResult:
    """Result for a single walk-forward window"""
    window_index: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    
    # Train metrics (in-sample)
    train_return_pct: float = 0.0
    train_sharpe: float = 0.0
    train_max_dd_pct: float = 0.0
    train_win_rate: float = 0.0
    train_trades: int = 0
    
    # Test metrics (out-of-sample)
    test_return_pct: float = 0.0
    test_sharpe: float = 0.0
    test_max_dd_pct: float = 0.0
    test_win_rate: float = 0.0
    test_trades: int = 0
    
    # Overfitting indicators
    return_gap: float = 0.0  # train_return - test_return
    sharpe_gap: float = 0.0  # train_sharpe - test_sharpe
    is_overfitted: bool = False
    
    # Optimized params for this window
    best_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WalkForwardResult:
    """Aggregated walk-forward analysis result"""
    symbol: str
    strategy_type: str
    window_mode: str  # 'rolling' or 'anchored'
    total_windows: int
    
    # Aggregated out-of-sample metrics
    avg_test_return_pct: float = 0.0
    avg_test_sharpe: float = 0.0
    avg_test_max_dd_pct: float = 0.0
    avg_test_win_rate: float = 0.0
    total_test_trades: int = 0
    
    # Aggregated in-sample metrics
    avg_train_return_pct: float = 0.0
    avg_train_sharpe: float = 0.0
    
    # Overfitting analysis
    avg_return_gap: float = 0.0
    avg_sharpe_gap: float = 0.0
    overfitting_windows: int = 0
    overfitting_ratio: float = 0.0  # overfitted windows / total windows
    overfitting_severity: str = "none"  # 'none', 'mild', 'moderate', 'severe'
    
    # Consistency metrics
    return_std: float = 0.0
    sharpe_std: float = 0.0
    consistency_score: float = 0.0  # 0-100, higher is better
    
    # All window results
    windows: List[WindowResult] = field(default_factory=list)
    
    # Final verdict
    recommendation: str = ""
    confidence: str = "low"  # 'low', 'medium', 'high'


class WalkForwardAnalyzer:
    """
    Walk-Forward Analysis Engine
    
    Splits data into train/test windows, optimizes on train, tests on out-of-sample,
    and aggregates results to detect overfitting.
    """
    
    def __init__(
        self,
        train_window_days: int = 252,  # 1 year
        test_window_days: int = 63,    # 3 months
        step_days: int = 63,           # Roll forward by 3 months
        min_data_days: int = 126,      # Minimum 6 months of data
        mode: str = "rolling"          # 'rolling' or 'anchored'
    ):
        """
        Initialize analyzer
        
        Args:
            train_window_days: Training window size in days
            test_window_days: Test window size in days
            step_days: Step size for rolling forward
            min_data_days: Minimum data required
            mode: 'rolling' (train window moves) or 'anchored' (train window expands)
        """
        self.train_window_days = train_window_days
        self.test_window_days = test_window_days
        self.step_days = step_days
        self.min_data_days = min_data_days
        self.mode = mode
        
        # Overfitting thresholds
        self.RETURN_GAP_WARNING = 10.0    # 10% gap = warning
        self.RETURN_GAP_SEVERE = 20.0     # 20% gap = severe
        self.SHARPE_GAP_WARNING = 0.5
        self.SHARPE_GAP_SEVERE = 1.0
        
    def analyze(
        self,
        data: List[Dict[str, Any]],
        strategy_type: str,
        param_grid: Dict[str, List[Any]],
        initial_capital: float = 100000.0,
        symbol: str = ""
    ) -> WalkForwardResult:
        """
        Run walk-forward analysis
        
        Args:
            data: Historical data list with 'date', 'close' fields
            strategy_type: Strategy type (ma_crossover, rsi_oversold, bollinger_bands)
            param_grid: Dict of param_name -> list of values to test
            initial_capital: Starting capital
            symbol: Symbol being analyzed
            
        Returns:
            WalkForwardResult with all metrics and window results
        """
        logger.info(f"[WalkForward] Starting analysis for {symbol}, strategy={strategy_type}, mode={self.mode}")
        
        # Validate data
        if len(data) < self.min_data_days:
            logger.warning(f"[WalkForward] Insufficient data: {len(data)} < {self.min_data_days}")
            return self._create_empty_result(symbol, strategy_type, "Insufficient data")
        
        # Generate windows
        windows = self._generate_windows(data)
        if not windows:
            logger.warning(f"[WalkForward] No valid windows generated")
            return self._create_empty_result(symbol, strategy_type, "No valid windows")
        
        logger.info(f"[WalkForward] Generated {len(windows)} windows")
        
        # Run analysis for each window
        window_results = []
        for i, (train_data, test_data, train_dates, test_dates) in enumerate(windows):
            logger.info(f"[WalkForward] Processing window {i+1}/{len(windows)}")
            
            result = self._analyze_window(
                window_index=i,
                train_data=train_data,
                test_data=test_data,
                train_dates=train_dates,
                test_dates=test_dates,
                strategy_type=strategy_type,
                param_grid=param_grid,
                initial_capital=initial_capital
            )
            window_results.append(result)
        
        # Aggregate results
        final_result = self._aggregate_results(
            symbol=symbol,
            strategy_type=strategy_type,
            window_results=window_results
        )
        
        logger.info(f"[WalkForward] Analysis complete: {final_result.overfitting_severity} overfitting, "
                   f"avg test return={final_result.avg_test_return_pct:.2f}%")
        
        return final_result
    
    def _generate_windows(
        self,
        data: List[Dict[str, Any]]
    ) -> List[Tuple[List, List, Tuple[str, str], Tuple[str, str]]]:
        """
        Generate train/test windows
        
        Returns:
            List of (train_data, test_data, (train_start, train_end), (test_start, test_end))
        """
        windows = []
        total_days = len(data)
        
        if self.mode == "rolling":
            # Rolling window: train window moves forward
            start_idx = 0
            while start_idx + self.train_window_days + self.test_window_days <= total_days:
                train_end_idx = start_idx + self.train_window_days
                test_end_idx = train_end_idx + self.test_window_days
                
                train_data = data[start_idx:train_end_idx]
                test_data = data[train_end_idx:test_end_idx]
                
                train_dates = (train_data[0]['date'], train_data[-1]['date'])
                test_dates = (test_data[0]['date'], test_data[-1]['date'])
                
                windows.append((train_data, test_data, train_dates, test_dates))
                
                # Move forward
                start_idx += self.step_days
                
        elif self.mode == "anchored":
            # Anchored window: train window expands from start
            train_start_idx = 0
            test_start_idx = self.train_window_days
            
            while test_start_idx + self.test_window_days <= total_days:
                # Train window is always from beginning
                train_data = data[train_start_idx:test_start_idx]
                test_data = data[test_start_idx:test_start_idx + self.test_window_days]
                
                train_dates = (train_data[0]['date'], train_data[-1]['date'])
                test_dates = (test_data[0]['date'], test_data[-1]['date'])
                
                windows.append((train_data, test_data, train_dates, test_dates))
                
                # Expand train window
                test_start_idx += self.step_days
        
        return windows
    
    def _analyze_window(
        self,
        window_index: int,
        train_data: List[Dict],
        test_data: List[Dict],
        train_dates: Tuple[str, str],
        test_dates: Tuple[str, str],
        strategy_type: str,
        param_grid: Dict[str, List[Any]],
        initial_capital: float
    ) -> WindowResult:
        """Analyze a single window: optimize on train, test on out-of-sample"""
        
        result = WindowResult(
            window_index=window_index,
            train_start=train_dates[0],
            train_end=train_dates[1],
            test_start=test_dates[0],
            test_end=test_dates[1]
        )
        
        # Step 1: Optimize parameters on training data
        best_params, best_train_return = self._optimize_params(
            data=train_data,
            strategy_type=strategy_type,
            param_grid=param_grid,
            initial_capital=initial_capital
        )
        result.best_params = best_params
        
        # Step 2: Calculate train metrics with best params
        train_metrics = self._run_strategy(
            data=train_data,
            strategy_type=strategy_type,
            params=best_params,
            initial_capital=initial_capital
        )
        result.train_return_pct = train_metrics['return_pct']
        result.train_sharpe = train_metrics['sharpe']
        result.train_max_dd_pct = train_metrics['max_dd_pct']
        result.train_win_rate = train_metrics['win_rate']
        result.train_trades = train_metrics['trades']
        
        # Step 3: Test on out-of-sample data
        test_metrics = self._run_strategy(
            data=test_data,
            strategy_type=strategy_type,
            params=best_params,
            initial_capital=initial_capital
        )
        result.test_return_pct = test_metrics['return_pct']
        result.test_sharpe = test_metrics['sharpe']
        result.test_max_dd_pct = test_metrics['max_dd_pct']
        result.test_win_rate = test_metrics['win_rate']
        result.test_trades = test_metrics['trades']
        
        # Step 4: Calculate overfitting indicators
        result.return_gap = result.train_return_pct - result.test_return_pct
        result.sharpe_gap = result.train_sharpe - result.test_sharpe
        
        # Detect overfitting
        if result.return_gap > self.RETURN_GAP_SEVERE or result.sharpe_gap > self.SHARPE_GAP_SEVERE:
            result.is_overfitted = True
        elif result.return_gap > self.RETURN_GAP_WARNING or result.sharpe_gap > self.SHARPE_GAP_WARNING:
            result.is_overfitted = True
        
        logger.info(f"[WalkForward] Window {window_index}: train={result.train_return_pct:.2f}%, "
                   f"test={result.test_return_pct:.2f}%, gap={result.return_gap:.2f}%")
        
        return result
    
    def _optimize_params(
        self,
        data: List[Dict],
        strategy_type: str,
        param_grid: Dict[str, List[Any]],
        initial_capital: float
    ) -> Tuple[Dict[str, Any], float]:
        """
        Grid search to find best parameters on training data
        
        Returns:
            (best_params, best_return)
        """
        best_params = {}
        best_return = -999999.0
        
        # Generate all parameter combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        
        def generate_combinations(idx, current):
            if idx == len(param_names):
                yield current.copy()
                return
            for val in param_values[idx]:
                current[param_names[idx]] = val
                yield from generate_combinations(idx + 1, current)
        
        # Test each combination
        for params in generate_combinations(0, {}):
            metrics = self._run_strategy(
                data=data,
                strategy_type=strategy_type,
                params=params,
                initial_capital=initial_capital
            )
            
            if metrics['return_pct'] > best_return:
                best_return = metrics['return_pct']
                best_params = params.copy()
        
        return best_params, best_return
    
    def _run_strategy(
        self,
        data: List[Dict],
        strategy_type: str,
        params: Dict[str, Any],
        initial_capital: float
    ) -> Dict[str, Any]:
        """
        Run strategy and return metrics
        
        Returns:
            Dict with return_pct, sharpe, max_dd_pct, win_rate, trades
        """
        closes = [d['close'] for d in data]
        
        # Generate signals
        signals = self._generate_signals(strategy_type, closes, params)
        
        # Simulate trades
        trades, wins, losses, final_capital = self._simulate_trades(
            signals, closes, data, initial_capital
        )
        
        # Calculate metrics
        total_return = final_capital - initial_capital
        return_pct = (total_return / initial_capital) * 100 if initial_capital > 0 else 0
        
        # Calculate max drawdown
        equity = initial_capital
        peak = equity
        max_dd = 0.0
        
        for t in trades:
            equity += t.get('pnl', 0)
            if equity > peak:
                peak = equity
            dd = peak - equity
            if dd > max_dd:
                max_dd = dd
        
        max_dd_pct = (max_dd / initial_capital) * 100 if initial_capital > 0 else 0
        
        # Calculate win rate
        total_trades = wins + losses
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        # Calculate Sharpe ratio
        sharpe = self._calculate_sharpe(trades, len(data))
        
        return {
            'return_pct': round(return_pct, 2),
            'sharpe': round(sharpe, 2),
            'max_dd_pct': round(max_dd_pct, 2),
            'win_rate': round(win_rate, 2),
            'trades': total_trades
        }
    
    def _generate_signals(
        self,
        strategy_type: str,
        closes: List[float],
        params: Dict[str, Any]
    ) -> List[int]:
        """Generate trading signals based on strategy type"""
        signals = [0] * len(closes)
        
        if strategy_type == "ma_crossover":
            fast_ma = params.get('fast_ma', 5)
            slow_ma = params.get('slow_ma', 20)
            
            fast_vals = self._calc_ma(closes, fast_ma)
            slow_vals = self._calc_ma(closes, slow_ma)
            
            for i in range(slow_ma, len(closes)):
                if fast_vals[i] is None or slow_vals[i] is None:
                    continue
                if fast_vals[i] > slow_vals[i] and fast_vals[i-1] <= slow_vals[i-1]:
                    signals[i] = 1
                elif fast_vals[i] < slow_vals[i] and fast_vals[i-1] >= slow_vals[i-1]:
                    signals[i] = -1
                    
        elif strategy_type == "rsi_oversold":
            rsi_period = params.get('rsi_period', 14)
            rsi_buy = params.get('rsi_buy', 30)
            rsi_sell = params.get('rsi_sell', 70)
            
            rsi_vals = self._calc_rsi(closes, rsi_period)
            in_position = False
            
            for i in range(1, len(closes)):
                if rsi_vals[i] is None:
                    continue
                if not in_position and rsi_vals[i] < rsi_buy:
                    signals[i] = 1
                    in_position = True
                elif in_position and rsi_vals[i] > rsi_sell:
                    signals[i] = -1
                    in_position = False
                    
        elif strategy_type == "bollinger_bands":
            bb_period = params.get('bb_period', 20)
            bb_std = params.get('bb_std', 2)
            
            mid, upper, lower = self._calc_bollinger(closes, bb_period, bb_std)
            
            for i in range(1, len(closes)):
                if lower[i] is None:
                    continue
                if closes[i-1] <= lower[i-1] and closes[i] > lower[i]:
                    signals[i] = 1
                elif closes[i-1] >= upper[i-1] and closes[i] < upper[i]:
                    signals[i] = -1
        
        return signals
    
    def _simulate_trades(
        self,
        signals: List[int],
        closes: List[float],
        data: List[Dict],
        initial_capital: float
    ) -> Tuple[List[Dict], int, int, float]:
        """Simulate trades based on signals"""
        capital = float(initial_capital)
        position = 0
        entry_price = 0.0
        trades = []
        wins = 0
        losses = 0
        
        for i in range(1, len(closes)):
            if signals[i] == 1 and position == 0 and capital > 0:
                shares = int(capital * 0.9 / closes[i])
                if shares > 0:
                    position = shares
                    entry_price = closes[i]
                    capital -= shares * entry_price
                    trades.append({
                        "entry_date": data[i]['date'],
                        "entry_price": round(entry_price, 2),
                        "shares": shares,
                        "type": "long"
                    })
            elif signals[i] == -1 and position > 0:
                exit_price = closes[i]
                pnl = (exit_price - entry_price) * position
                if pnl > 0:
                    wins += 1
                else:
                    losses += 1
                capital += position * exit_price
                trades[-1].update({
                    "exit_date": data[i]['date'],
                    "exit_price": round(exit_price, 2),
                    "pnl": round(pnl, 2),
                    "pnl_pct": round((exit_price - entry_price) / entry_price * 100, 2)
                })
                position = 0
        
        # Close remaining position
        if position > 0:
            exit_price = closes[-1]
            pnl = (exit_price - entry_price) * position
            if pnl > 0:
                wins += 1
            else:
                losses += 1
            capital += position * exit_price
            trades[-1].update({
                "exit_date": data[-1]['date'],
                "exit_price": round(exit_price, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round((exit_price - entry_price) / entry_price * 100, 2)
            })
        
        return trades, wins, losses, capital
    
    def _calc_ma(self, data: List[float], period: int) -> List[Optional[float]]:
        """Calculate moving average"""
        return [None] * (period - 1) + [
            round(sum(data[i-period+1:i+1]) / period, 2) 
            for i in range(period - 1, len(data))
        ]
    
    def _calc_rsi(self, closes: List[float], period: int = 14) -> List[Optional[float]]:
        """Calculate RSI"""
        gains, losses = [], []
        for i in range(1, len(closes)):
            d = closes[i] - closes[i-1]
            gains.append(max(d, 0))
            losses.append(max(-d, 0))
        
        if not gains or sum(losses[:period]) == 0:
            return [50.0] * len(closes)
        
        ag = sum(gains[:period]) / period
        al = sum(losses[:period]) / period
        rs = ag / al if al != 0 else 0
        
        rsi_vals = [None] * period + [100 - 100/(1+rs)]
        
        for i in range(period, len(gains)):
            ag = (ag*(period-1) + gains[i]) / period
            al = (al*(period-1) + losses[i]) / period
            rs = ag / al if al != 0 else 0
            rsi_vals.append(100 - 100/(1+rs) if al != 0 else 50.0)
        
        return rsi_vals + [None] * (len(closes) - len(rsi_vals))
    
    def _calc_bollinger(
        self, 
        closes: List[float], 
        period: int = 20, 
        multiplier: float = 2
    ) -> Tuple[List, List, List]:
        """Calculate Bollinger Bands"""
        mid = self._calc_ma(closes, period)
        upper, lower = [None] * len(closes), [None] * len(closes)
        
        for i in range(period - 1, len(closes)):
            if mid[i] is not None:
                std = (sum((closes[j] - mid[i])**2 for j in range(i-period+1, i+1)) / period) ** 0.5
                upper[i] = round(mid[i] + multiplier * std, 2)
                lower[i] = round(mid[i] - multiplier * std, 2)
        
        return mid, upper, lower
    
    def _calculate_sharpe(self, trades: List[Dict], days: int) -> float:
        """Calculate Sharpe ratio from trades"""
        if len(trades) < 2:
            return 0.0
        
        returns = []
        for t in trades:
            if 'pnl_pct' in t:
                returns.append(t['pnl_pct'] / 100)
        
        if len(returns) < 2:
            return 0.0
        
        avg_return = statistics.mean(returns)
        std_return = statistics.stdev(returns)
        
        if std_return == 0:
            return 0.0
        
        # Annualize
        years = days / 252
        annualized_return = avg_return * 252 / max(len(trades), 1)
        annualized_vol = std_return * (252 ** 0.5)
        
        sharpe = annualized_return / annualized_vol if annualized_vol > 0 else 0
        return sharpe
    
    def _aggregate_results(
        self,
        symbol: str,
        strategy_type: str,
        window_results: List[WindowResult]
    ) -> WalkForwardResult:
        """Aggregate all window results into final metrics"""
        if not window_results:
            return self._create_empty_result(symbol, strategy_type, "No results")
        
        result = WalkForwardResult(
            symbol=symbol,
            strategy_type=strategy_type,
            window_mode=self.mode,
            total_windows=len(window_results),
            windows=window_results
        )
        
        # Calculate averages
        test_returns = [w.test_return_pct for w in window_results]
        test_sharpes = [w.test_sharpe for w in window_results]
        test_dds = [w.test_max_dd_pct for w in window_results]
        test_wins = [w.test_win_rate for w in window_results]
        
        train_returns = [w.train_return_pct for w in window_results]
        train_sharpes = [w.train_sharpe for w in window_results]
        
        result.avg_test_return_pct = round(statistics.mean(test_returns), 2)
        result.avg_test_sharpe = round(statistics.mean(test_sharpes), 2)
        result.avg_test_max_dd_pct = round(statistics.mean(test_dds), 2)
        result.avg_test_win_rate = round(statistics.mean(test_wins), 2)
        result.total_test_trades = sum(w.test_trades for w in window_results)
        
        result.avg_train_return_pct = round(statistics.mean(train_returns), 2)
        result.avg_train_sharpe = round(statistics.mean(train_sharpes), 2)
        
        # Calculate gaps
        result.avg_return_gap = round(result.avg_train_return_pct - result.avg_test_return_pct, 2)
        result.avg_sharpe_gap = round(result.avg_train_sharpe - result.avg_test_sharpe, 2)
        
        # Count overfitted windows
        result.overfitting_windows = sum(1 for w in window_results if w.is_overfitted)
        result.overfitting_ratio = round(result.overfitting_windows / len(window_results), 2)
        
        # Calculate consistency
        result.return_std = round(statistics.stdev(test_returns), 2) if len(test_returns) > 1 else 0
        result.sharpe_std = round(statistics.stdev(test_sharpes), 2) if len(test_sharpes) > 1 else 0
        
        # Consistency score: lower std = higher consistency
        if result.return_std > 0:
            result.consistency_score = round(max(0, 100 - result.return_std * 2), 1)
        else:
            result.consistency_score = 100.0
        
        # Determine overfitting severity
        if result.overfitting_ratio >= 0.7 or result.avg_return_gap > self.RETURN_GAP_SEVERE:
            result.overfitting_severity = "severe"
        elif result.overfitting_ratio >= 0.4 or result.avg_return_gap > self.RETURN_GAP_WARNING:
            result.overfitting_severity = "moderate"
        elif result.overfitting_ratio >= 0.2 or result.avg_return_gap > 5:
            result.overfitting_severity = "mild"
        else:
            result.overfitting_severity = "none"
        
        # Generate recommendation
        result.recommendation = self._generate_recommendation(result)
        result.confidence = self._assess_confidence(result)
        
        return result
    
    def _generate_recommendation(self, result: WalkForwardResult) -> str:
        """Generate actionable recommendation"""
        if result.overfitting_severity == "severe":
            return f"⚠️ 严重过拟合：训练收益({result.avg_train_return_pct:.1f}%)远高于测试收益({result.avg_test_return_pct:.1f}%)。建议：重新设计策略或增加数据量。"
        elif result.overfitting_severity == "moderate":
            return f"⚡ 中度过拟合：训练-测试差距{result.avg_return_gap:.1f}%。建议：简化参数或扩大训练窗口。"
        elif result.overfitting_severity == "mild":
            return f"📊 轻度过拟合：差距{result.avg_return_gap:.1f}%可接受。建议：监控实盘表现。"
        else:
            if result.avg_test_return_pct > 0:
                return f"✅ 策略稳健：样本外平均收益{result.avg_test_return_pct:.1f}%，一致性得分{result.consistency_score:.1f}。可以实盘测试。"
            else:
                return f"📉 策略亏损：样本外平均收益{result.avg_test_return_pct:.1f}%。建议：优化策略逻辑。"
    
    def _assess_confidence(self, result: WalkForwardResult) -> str:
        """Assess confidence level based on data quality"""
        if result.total_windows >= 5 and result.total_test_trades >= 30:
            return "high"
        elif result.total_windows >= 3 and result.total_test_trades >= 15:
            return "medium"
        else:
            return "low"
    
    def _create_empty_result(
        self, 
        symbol: str, 
        strategy_type: str, 
        reason: str
    ) -> WalkForwardResult:
        """Create empty result for error cases"""
        result = WalkForwardResult(
            symbol=symbol,
            strategy_type=strategy_type,
            window_mode=self.mode,
            total_windows=0
        )
        result.recommendation = f"❌ 无法分析：{reason}"
        return result
