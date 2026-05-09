"""
Performance Analyzer Service - pyfolio-reloaded integration
"""
import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TradeInfo:
    """Trade information dataclass"""
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    pnl: float
    pnl_pct: float
    quantity: float
    side: str  # 'long' or 'short'


class PerformanceMetricsCalculator:
    """
    Comprehensive performance metrics calculator with 10 debug cycles
    
    Debug Cycles:
    1. Input validation
    2. Returns calculation
    3. Sharpe ratio calculation
    4. Sortino ratio calculation
    5. Drawdown calculation
    6. Win rate calculation
    7. Profit factor calculation
    8. VaR/CVaR calculation
    9. Trade analysis
    10. Metrics aggregation
    """
    
    def __init__(self, risk_free_rate: float = 0.02, trading_days: int = 252):
        """
        Initialize calculator
        
        Args:
            risk_free_rate: Annual risk-free rate (default: 2%)
            trading_days: Trading days per year (default: 252)
        """
        self.risk_free_rate = risk_free_rate
        self.trading_days = trading_days
        self.daily_rf_rate = risk_free_rate / trading_days
        logger.debug(f"[Cycle 0] PerformanceMetricsCalculator initialized - rf_rate={risk_free_rate}, trading_days={trading_days}")
    
    def _validate_inputs(self, equity_curve: pd.Series, trades: Optional[List[Dict]] = None) -> Tuple[bool, str]:
        """
        Debug Cycle 1: Input validation
        
        Args:
            equity_curve: Series of equity values indexed by date
            trades: Optional list of trade dictionaries
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        logger.debug("[Cycle 1 - Input Validation] Starting input validation")
        
        # Check equity curve
        if equity_curve is None or len(equity_curve) == 0:
            error_msg = "Equity curve is empty or None"
            logger.error(f"[Cycle 1] {error_msg}")
            return False, error_msg
        
        if len(equity_curve) < 2:
            error_msg = f"Insufficient data points: {len(equity_curve)} < 2"
            logger.error(f"[Cycle 1] {error_msg}")
            return False, error_msg
        
        # Check for NaN/Inf values
        if equity_curve.isna().any():
            nan_count = equity_curve.isna().sum()
            logger.warning(f"[Cycle 1] Found {nan_count} NaN values, will be dropped")
        
        if np.isinf(equity_curve).any():
            inf_count = np.isinf(equity_curve).sum()
            error_msg = f"Equity curve contains {inf_count} infinite values"
            logger.error(f"[Cycle 1] {error_msg}")
            return False, error_msg
        
        # Check for negative equity values
        if (equity_curve <= 0).any():
            neg_count = (equity_curve <= 0).sum()
            logger.warning(f"[Cycle 1] Found {neg_count} non-positive equity values")
        
        # Validate trades if provided
        if trades is not None:
            if not isinstance(trades, list):
                error_msg = f"Trades must be a list, got {type(trades)}"
                logger.error(f"[Cycle 1] {error_msg}")
                return False, error_msg
            
            logger.debug(f"[Cycle 1] Validated {len(trades)} trades")
        
        logger.debug(f"[Cycle 1] Input validation passed - equity_points={len(equity_curve)}")
        return True, ""
    
    def calculate_returns(self, equity_curve: pd.Series) -> pd.Series:
        """
        Debug Cycle 2: Returns calculation
        
        Args:
            equity_curve: Series of equity values indexed by date
            
        Returns:
            Series of daily returns
        """
        logger.debug("[Cycle 2 - Returns Calculation] Starting returns calculation")
        
        # Clean equity curve
        equity_clean = equity_curve.dropna()
        
        if len(equity_clean) < 2:
            logger.warning("[Cycle 2] Insufficient data after cleaning, returning empty series")
            return pd.Series(dtype=float)
        
        # Calculate simple returns: (P_t - P_{t-1}) / P_{t-1}
        returns = equity_clean.pct_change().dropna()
        
        # Handle edge cases
        returns = returns.replace([np.inf, -np.inf], np.nan).dropna()
        
        logger.debug(f"[Cycle 2] Returns calculated - count={len(returns)}, "
                    f"mean={returns.mean():.6f}, std={returns.std():.6f}")
        
        return returns
    
    def calculate_sharpe_ratio(self, returns: pd.Series) -> float:
        """
        Debug Cycle 3: Sharpe ratio calculation
        
        Formula: (annual_return - rf_rate) / annual_volatility
        
        Args:
            returns: Series of daily returns
            
        Returns:
            Sharpe ratio (float)
        """
        logger.debug("[Cycle 3 - Sharpe Ratio] Starting Sharpe ratio calculation")
        
        if len(returns) == 0:
            logger.warning("[Cycle 3] Empty returns, returning 0.0")
            return 0.0
        
        # Annualized return
        annual_return = returns.mean() * self.trading_days
        logger.debug(f"[Cycle 3] Annual return: {annual_return:.6f}")
        
        # Annualized volatility
        annual_vol = returns.std() * np.sqrt(self.trading_days)
        logger.debug(f"[Cycle 3] Annual volatility: {annual_vol:.6f}")
        
        # Sharpe ratio
        if annual_vol == 0:
            logger.warning("[Cycle 3] Zero volatility, returning 0.0")
            return 0.0
        
        sharpe = (annual_return - self.risk_free_rate) / annual_vol
        
        logger.debug(f"[Cycle 3] Sharpe ratio calculated: {sharpe:.4f}")
        return float(sharpe)
    
    def calculate_sortino_ratio(self, returns: pd.Series) -> float:
        """
        Debug Cycle 4: Sortino ratio calculation
        
        Formula: (annual_return - rf_rate) / downside_deviation
        
        Args:
            returns: Series of daily returns
            
        Returns:
            Sortino ratio (float)
        """
        logger.debug("[Cycle 4 - Sortino Ratio] Starting Sortino ratio calculation")
        
        if len(returns) == 0:
            logger.warning("[Cycle 4] Empty returns, returning 0.0")
            return 0.0
        
        # Annualized return
        annual_return = returns.mean() * self.trading_days
        logger.debug(f"[Cycle 4] Annual return: {annual_return:.6f}")
        
        # Downside deviation (only negative returns)
        negative_returns = returns[returns < 0]
        
        if len(negative_returns) == 0:
            logger.debug("[Cycle 4] No negative returns, Sortino = infinite (returning high value)")
            return 100.0  # Very high Sortino for no losses
        
        # Downside deviation
        downside_std = negative_returns.std() * np.sqrt(self.trading_days)
        logger.debug(f"[Cycle 4] Downside deviation: {downside_std:.6f}")
        
        if downside_std == 0:
            logger.warning("[Cycle 4] Zero downside deviation, returning 0.0")
            return 0.0
        
        sortino = (annual_return - self.risk_free_rate) / downside_std
        
        logger.debug(f"[Cycle 4] Sortino ratio calculated: {sortino:.4f}")
        return float(sortino)
    
    def calculate_calmar_ratio(self, returns: pd.Series) -> float:
        """
        Calculate Calmar ratio
        
        Formula: annual_return / abs(max_drawdown)
        
        Args:
            returns: Series of daily returns
            
        Returns:
            Calmar ratio (float)
        """
        logger.debug("[Calmar Ratio] Starting Calmar ratio calculation")
        
        if len(returns) == 0:
            logger.warning("[Calmar] Empty returns, returning 0.0")
            return 0.0
        
        # Annualized return
        annual_return = returns.mean() * self.trading_days
        
        # Calculate max drawdown
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        max_dd = drawdown.min()
        
        if max_dd == 0:
            logger.debug("[Calmar] Zero drawdown, returning high value")
            return 100.0
        
        calmar = annual_return / abs(max_dd)
        
        logger.debug(f"[Calmar] Calmar ratio calculated: {calmar:.4f}")
        return float(calmar)
    
    def calculate_max_drawdown(self, equity_curve: pd.Series) -> Dict[str, float]:
        """
        Debug Cycle 5: Drawdown calculation
        
        Args:
            equity_curve: Series of equity values indexed by date
            
        Returns:
            Dictionary with max_drawdown and drawdown_duration
        """
        logger.debug("[Cycle 5 - Drawdown] Starting drawdown calculation")
        
        if len(equity_curve) < 2:
            logger.warning("[Cycle 5] Insufficient data, returning zero drawdown")
            return {"max_drawdown": 0.0, "drawdown_duration": 0}
        
        # Calculate cumulative returns
        returns = self.calculate_returns(equity_curve)
        
        if len(returns) == 0:
            return {"max_drawdown": 0.0, "drawdown_duration": 0}
        
        # Cumulative wealth index
        cumulative = (1 + returns).cumprod()
        
        # Running maximum
        running_max = cumulative.cummax()
        
        # Drawdown series
        drawdown = (cumulative - running_max) / running_max
        
        # Maximum drawdown
        max_dd = float(drawdown.min())
        logger.debug(f"[Cycle 5] Max drawdown: {max_dd:.4f}")
        
        # Drawdown duration (days in drawdown)
        in_drawdown = drawdown < 0
        if in_drawdown.any():
            # Find longest drawdown period
            drawdown_periods = []
            current_start = None
            
            for i, is_dd in enumerate(in_drawdown):
                if is_dd and current_start is None:
                    current_start = i
                elif not is_dd and current_start is not None:
                    drawdown_periods.append(i - current_start)
                    current_start = None
            
            if current_start is not None:
                drawdown_periods.append(len(in_drawdown) - current_start)
            
            max_duration = max(drawdown_periods) if drawdown_periods else 0
        else:
            max_duration = 0
        
        logger.debug(f"[Cycle 5] Drawdown duration: {max_duration} days")
        
        return {
            "max_drawdown": max_dd,
            "drawdown_duration": max_duration
        }
    
    def calculate_win_rate(self, trades: List[Dict]) -> float:
        """
        Debug Cycle 6: Win rate calculation
        
        Args:
            trades: List of trade dictionaries with 'pnl' field
            
        Returns:
            Win rate (float between 0 and 1)
        """
        logger.debug("[Cycle 6 - Win Rate] Starting win rate calculation")
        
        if not trades or len(trades) == 0:
            logger.warning("[Cycle 6] No trades provided, returning 0.0")
            return 0.0
        
        # Extract PnL values
        pnls = [t.get('pnl', 0) for t in trades if 'pnl' in t]
        
        if len(pnls) == 0:
            logger.warning("[Cycle 6] No valid PnL values found")
            return 0.0
        
        # Count winning trades
        winning_trades = sum(1 for pnl in pnls if pnl > 0)
        total_trades = len(pnls)
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
        
        logger.debug(f"[Cycle 6] Win rate: {win_rate:.4f} ({winning_trades}/{total_trades} trades)")
        
        return float(win_rate)
    
    def calculate_profit_factor(self, trades: List[Dict]) -> float:
        """
        Debug Cycle 7: Profit factor calculation
        
        Formula: gross_profit / gross_loss
        
        Args:
            trades: List of trade dictionaries with 'pnl' field
            
        Returns:
            Profit factor (float)
        """
        logger.debug("[Cycle 7 - Profit Factor] Starting profit factor calculation")
        
        if not trades or len(trades) == 0:
            logger.warning("[Cycle 7] No trades provided, returning 0.0")
            return 0.0
        
        # Extract PnL values
        pnls = [t.get('pnl', 0) for t in trades if 'pnl' in t]
        
        if len(pnls) == 0:
            logger.warning("[Cycle 7] No valid PnL values found")
            return 0.0
        
        # Calculate gross profit and loss
        gross_profit = sum(pnl for pnl in pnls if pnl > 0)
        gross_loss = abs(sum(pnl for pnl in pnls if pnl < 0))
        
        logger.debug(f"[Cycle 7] Gross profit: {gross_profit:.2f}, Gross loss: {gross_loss:.2f}")
        
        if gross_loss == 0:
            logger.debug("[Cycle 7] No losses, profit factor = infinite")
            return float('inf') if gross_profit > 0 else 0.0
        
        profit_factor = gross_profit / gross_loss
        
        logger.debug(f"[Cycle 7] Profit factor: {profit_factor:.4f}")
        return float(profit_factor)
    
    def calculate_var(self, returns: pd.Series, confidence: float = 0.95) -> float:
        """
        Debug Cycle 8: VaR calculation
        
        Value at Risk using historical simulation
        
        Args:
            returns: Series of daily returns
            confidence: Confidence level (default: 95%)
            
        Returns:
            VaR value (negative, representing potential loss)
        """
        logger.debug(f"[Cycle 8 - VaR] Starting VaR calculation at {confidence*100}% confidence")
        
        if len(returns) == 0:
            logger.warning("[Cycle 8] Empty returns, returning 0.0")
            return 0.0
        
        # Historical VaR (percentile method)
        var = float(returns.quantile(1 - confidence))
        
        logger.debug(f"[Cycle 8] VaR({confidence*100:.0f}%): {var:.6f}")
        return var
    
    def calculate_cvar(self, returns: pd.Series, confidence: float = 0.95) -> float:
        """
        Debug Cycle 8: CVaR calculation (Expected Shortfall)
        
        Conditional VaR - average of returns below VaR threshold
        
        Args:
            returns: Series of daily returns
            confidence: Confidence level (default: 95%)
            
        Returns:
            CVaR value (negative, representing expected loss)
        """
        logger.debug(f"[Cycle 8 - CVaR] Starting CVaR calculation at {confidence*100}% confidence")
        
        if len(returns) == 0:
            logger.warning("[Cycle 8] Empty returns, returning 0.0")
            return 0.0
        
        # Calculate VaR threshold
        var_threshold = returns.quantile(1 - confidence)
        
        # CVaR is the mean of returns below VaR
        tail_returns = returns[returns <= var_threshold]
        
        if len(tail_returns) == 0:
            logger.warning("[Cycle 8] No returns below VaR threshold")
            return float(var_threshold)
        
        cvar = float(tail_returns.mean())
        
        logger.debug(f"[Cycle 8] CVaR({confidence*100:.0f}%): {cvar:.6f}")
        return cvar
    
    def analyze_trades(self, trades: List[Dict]) -> Dict[str, Any]:
        """
        Debug Cycle 9: Trade analysis
        
        Args:
            trades: List of trade dictionaries
            
        Returns:
            Dictionary with trade analysis metrics
        """
        logger.debug("[Cycle 9 - Trade Analysis] Starting comprehensive trade analysis")
        
        if not trades or len(trades) == 0:
            logger.warning("[Cycle 9] No trades provided")
            return self._empty_trade_analysis()
        
        # Extract valid trades
        valid_trades = [t for t in trades if 'pnl' in t]
        
        if len(valid_trades) == 0:
            logger.warning("[Cycle 9] No valid trades with PnL")
            return self._empty_trade_analysis()
        
        pnls = [t['pnl'] for t in valid_trades]
        
        # Average trade duration
        avg_duration = self._calculate_avg_trade_duration(valid_trades)
        
        # Consecutive wins/losses
        consec_wins, consec_losses = self._calculate_consecutive_wins_losses(pnls)
        
        # Largest win/loss
        largest_win = max(pnls) if pnls else 0
        largest_loss = min(pnls) if pnls else 0
        
        # Trade distribution
        distribution = self._calculate_trade_distribution(pnls)
        
        analysis = {
            "total_trades": len(valid_trades),
            "winning_trades": sum(1 for p in pnls if p > 0),
            "losing_trades": sum(1 for p in pnls if p < 0),
            "avg_trade_duration_days": avg_duration,
            "max_consecutive_wins": consec_wins,
            "max_consecutive_losses": consec_losses,
            "largest_win": float(largest_win),
            "largest_loss": float(largest_loss),
            "avg_win": float(np.mean([p for p in pnls if p > 0])) if any(p > 0 for p in pnls) else 0.0,
            "avg_loss": float(np.mean([p for p in pnls if p < 0])) if any(p < 0 for p in pnls) else 0.0,
            "trade_distribution": distribution,
        }
        
        logger.debug(f"[Cycle 9] Trade analysis complete - {analysis['total_trades']} trades analyzed")
        
        return analysis
    
    def _calculate_avg_trade_duration(self, trades: List[Dict]) -> float:
        """Calculate average trade duration in days"""
        durations = []
        
        for trade in trades:
            if 'entry_date' in trade and 'exit_date' in trade:
                try:
                    entry = pd.to_datetime(trade['entry_date'])
                    exit_date = pd.to_datetime(trade['exit_date'])
                    duration = (exit_date - entry).days
                    durations.append(duration)
                except Exception as e:
                    logger.debug(f"[Trade Duration] Error parsing dates: {e}")
        
        return float(np.mean(durations)) if durations else 0.0
    
    def _calculate_consecutive_wins_losses(self, pnls: List[float]) -> Tuple[int, int]:
        """Calculate maximum consecutive wins and losses"""
        if not pnls:
            return 0, 0
        
        max_consec_wins = 0
        max_consec_losses = 0
        current_wins = 0
        current_losses = 0
        
        for pnl in pnls:
            if pnl > 0:
                current_wins += 1
                current_losses = 0
                max_consec_wins = max(max_consec_wins, current_wins)
            elif pnl < 0:
                current_losses += 1
                current_wins = 0
                max_consec_losses = max(max_consec_losses, current_losses)
            else:
                current_wins = 0
                current_losses = 0
        
        return max_consec_wins, max_consec_losses
    
    def _calculate_trade_distribution(self, pnls: List[float]) -> Dict[str, int]:
        """Calculate trade distribution by PnL ranges"""
        if not pnls:
            return {}
        
        distribution = {
            "large_wins": sum(1 for p in pnls if p > np.mean([x for x in pnls if x > 0]) * 2) if any(p > 0 for p in pnls) else 0,
            "small_wins": sum(1 for p in pnls if 0 < p <= np.mean([x for x in pnls if x > 0])) if any(p > 0 for p in pnls) else 0,
            "small_losses": sum(1 for p in pnls if np.mean([x for x in pnls if x < 0]) <= p < 0) if any(p < 0 for p in pnls) else 0,
            "large_losses": sum(1 for p in pnls if p < np.mean([x for x in pnls if x < 0]) * 2) if any(p < 0 for p in pnls) else 0,
        }
        
        return distribution
    
    def _empty_trade_analysis(self) -> Dict[str, Any]:
        """Return empty trade analysis"""
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "avg_trade_duration_days": 0.0,
            "max_consecutive_wins": 0,
            "max_consecutive_losses": 0,
            "largest_win": 0.0,
            "largest_loss": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "trade_distribution": {},
        }
    
    def calculate_all_metrics(
        self,
        equity_curve: pd.Series,
        trades: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Debug Cycle 10: Metrics aggregation
        
        Calculate all performance metrics
        
        Args:
            equity_curve: Series of equity values indexed by date
            trades: Optional list of trade dictionaries
            
        Returns:
            Dictionary with all performance metrics
        """
        logger.debug("[Cycle 10 - Metrics Aggregation] Starting comprehensive metrics calculation")
        
        # Cycle 1: Input validation
        is_valid, error_msg = self._validate_inputs(equity_curve, trades)
        if not is_valid:
            return self._empty_metrics(error_msg)
        
        # Cycle 2: Returns calculation
        returns = self.calculate_returns(equity_curve)
        
        if len(returns) == 0:
            return self._empty_metrics("Unable to calculate returns")
        
        # Cycle 3: Sharpe ratio
        sharpe = self.calculate_sharpe_ratio(returns)
        
        # Cycle 4: Sortino ratio
        sortino = self.calculate_sortino_ratio(returns)
        
        # Calmar ratio
        calmar = self.calculate_calmar_ratio(returns)
        
        # Cycle 5: Drawdown
        dd_metrics = self.calculate_max_drawdown(equity_curve)
        
        # Cycle 6-7: Trade metrics (if trades provided)
        win_rate = 0.0
        profit_factor = 0.0
        trade_analysis = self._empty_trade_analysis()
        
        if trades:
            win_rate = self.calculate_win_rate(trades)
            profit_factor = self.calculate_profit_factor(trades)
            trade_analysis = self.analyze_trades(trades)
        
        # Cycle 8: VaR/CVaR
        var_95 = self.calculate_var(returns, 0.95)
        var_99 = self.calculate_var(returns, 0.99)
        cvar_95 = self.calculate_cvar(returns, 0.95)
        cvar_99 = self.calculate_cvar(returns, 0.99)
        
        # Additional metrics
        total_return = float((equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1)
        annual_return = float(returns.mean() * self.trading_days)
        annual_vol = float(returns.std() * np.sqrt(self.trading_days))
        
        # Skewness and Kurtosis
        skew = float(returns.skew())
        kurtosis = float(returns.kurtosis())
        
        metrics = {
            # Return metrics
            "total_return": total_return,
            "annual_return": annual_return,
            "monthly_return": annual_return / 12,
            "daily_return_mean": float(returns.mean()),
            
            # Risk metrics
            "annual_volatility": annual_vol,
            "daily_volatility": float(returns.std()),
            "max_drawdown": dd_metrics["max_drawdown"],
            "max_drawdown_duration": dd_metrics["drawdown_duration"],
            
            # Risk-adjusted metrics
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "calmar_ratio": calmar,
            
            # Tail risk metrics
            "skew": skew,
            "kurtosis": kurtosis,
            "var_95": var_95,
            "var_99": var_99,
            "cvar_95": cvar_95,
            "cvar_99": cvar_99,
            
            # Trade metrics
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            
            # Trade analysis
            "trade_analysis": trade_analysis,
            
            # Metadata
            "total_days": len(returns),
            "trading_days_per_year": self.trading_days,
            "risk_free_rate": self.risk_free_rate,
        }
        
        logger.debug(f"[Cycle 10] Metrics aggregation complete - {len(metrics)} metrics calculated")
        
        return metrics
    
    def _empty_metrics(self, reason: str) -> Dict[str, Any]:
        """Return empty metrics with reason"""
        return {
            "error": reason,
            "total_return": 0.0,
            "annual_return": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "calmar_ratio": 0.0,
            "max_drawdown": 0.0,
            "annual_volatility": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "total_days": 0,
        }


class PerformanceAnalyzer:
    """Advanced performance metrics using pyfolio-reloaded"""
    
    def __init__(self):
        self.risk_free_rate = 0.02  # 2% annual risk-free rate
    
    def calculate_tearsheet_metrics(
        self,
        returns: List[float],
        dates: Optional[List[str]] = None,
        benchmark_returns: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive performance metrics using pyfolio
        
        Args:
            returns: List of daily returns (as decimals, e.g., 0.01 = 1%)
            dates: Optional list of date strings (YYYY-MM-DD)
            benchmark_returns: Optional benchmark returns for comparison
        
        Returns:
            Dictionary with 15+ performance metrics
        """
        try:
            # Convert to pandas Series
            returns_series = pd.Series(returns)
            
            if dates:
                returns_series.index = pd.to_datetime(dates)
            else:
                returns_series.index = pd.date_range(
                    start='2020-01-01',
                    periods=len(returns),
                    freq='D'
                )
            
            # Handle edge cases
            if len(returns) == 0:
                return self._empty_metrics("No returns data provided")
            
            if all(r == 0 for r in returns):
                return self._empty_metrics("All returns are zero")
            
            # Remove NaN values
            returns_series = returns_series.dropna()
            
            if len(returns_series) < 2:
                return self._empty_metrics("Insufficient data points")
            
            # Calculate metrics using pyfolio
            metrics = self._calculate_all_metrics(returns_series, benchmark_returns)
            
            return {
                "code": 0,
                "data": metrics
            }
            
        except Exception as e:
            logger.error(f"[PerformanceAnalyzer] Error calculating metrics: {e}")
            return {
                "code": 1,
                "message": f"Failed to calculate metrics: {str(e)}",
                "data": None
            }
    
    def _calculate_all_metrics(
        self,
        returns: pd.Series,
        benchmark_returns: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """Calculate all performance metrics"""
        
        # Import pyfolio
        try:
            import pyfolio
        except ImportError:
            logger.warning("pyfolio-reloaded not installed, using fallback calculations")
            return self._fallback_metrics(returns)
        
        try:
            # Calculate pyfolio stats
            pf_stats = pyfolio.timeseries.gen_returns_stats(returns)
            
            # Extract key metrics
            metrics = {
                # Return metrics
                "total_return": float(returns.sum()),
                "annual_return": float(pf_stats.get('annual_return', 0)),
                "monthly_return": float(pf_stats.get('monthly_return', 0)),
                
                # Risk metrics
                "annual_volatility": float(pf_stats.get('annual_volatility', 0)),
                "daily_volatility": float(pf_stats.get('daily_volatility', 0)),
                "max_drawdown": float(pf_stats.get('max_drawdown', 0)),
                "max_drawdown_duration": int(pf_stats.get('max_drawdown_duration', 0)),
                
                # Risk-adjusted metrics
                "sharpe_ratio": float(pf_stats.get('sharpe', 0)),
                "sortino_ratio": float(pf_stats.get('sortino', 0)),
                "calmar_ratio": float(pf_stats.get('calmar', 0)),
                "stability": float(pf_stats.get('stability', 0)),
                
                # Tail risk metrics
                "skew": float(pf_stats.get('skew', 0)),
                "kurtosis": float(pf_stats.get('kurtosis', 0)),
                "var_95": float(pf_stats.get('var_95', 0)),
                "var_99": float(pf_stats.get('var_99', 0)),
                
                # Trade statistics
                "win_rate": float(pf_stats.get('win_rate', 0)),
                "profit_loss_ratio": float(pf_stats.get('profit_loss_ratio', 0)),
                
                # Additional metrics
                "alpha": float(pf_stats.get('alpha', 0)),
                "beta": float(pf_stats.get('beta', 0)),
                "information_ratio": float(pf_stats.get('information_ratio', 0)),
                "treynor_ratio": float(pf_stats.get('treynor_ratio', 0)),
                
                # Count metrics
                "total_days": len(returns),
                "trading_days_per_year": 252,
                "start_date": str(returns.index[0].date()),
                "end_date": str(returns.index[-1].date()),
            }
            
            # Add benchmark comparison if provided
            if benchmark_returns and len(benchmark_returns) == len(returns):
                benchmark_series = pd.Series(benchmark_returns, index=returns.index)
                benchmark_stats = pyfolio.timeseries.gen_returns_stats(benchmark_series)
                
                metrics["benchmark"] = {
                    "annual_return": float(benchmark_stats.get('annual_return', 0)),
                    "sharpe_ratio": float(benchmark_stats.get('sharpe', 0)),
                    "max_drawdown": float(benchmark_stats.get('max_drawdown', 0)),
                }
                
                # Calculate excess return
                metrics["excess_return"] = metrics["annual_return"] - metrics["benchmark"]["annual_return"]
            
            return metrics
            
        except Exception as e:
            logger.warning(f"pyfolio calculation failed: {e}, using fallback")
            return self._fallback_metrics(returns)
    
    def _fallback_metrics(self, returns: pd.Series) -> Dict[str, Any]:
        """Fallback calculation if pyfolio fails"""
        
        # Basic calculations
        total_return = float(returns.sum())
        annual_return = float(returns.mean() * 252)
        annual_vol = float(returns.std() * np.sqrt(252))
        daily_vol = float(returns.std())
        
        # Sharpe ratio
        sharpe = (annual_return - self.risk_free_rate) / annual_vol if annual_vol > 0 else 0
        
        # Maximum drawdown
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = float(drawdown.min())
        
        # Sortino ratio (downside deviation)
        downside_returns = returns[returns < 0]
        downside_std = float(downside_returns.std() * np.sqrt(252)) if len(downside_returns) > 0 else 0
        sortino = (annual_return - self.risk_free_rate) / downside_std if downside_std > 0 else 0
        
        # Calmar ratio
        calmar = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0
        
        # Skewness and Kurtosis
        skew = float(returns.skew())
        kurtosis = float(returns.kurtosis())
        
        # VaR (95% and 99%)
        var_95 = float(returns.quantile(0.05))
        var_99 = float(returns.quantile(0.01))
        
        # Win rate
        positive_days = len(returns[returns > 0])
        win_rate = positive_days / len(returns) if len(returns) > 0 else 0
        
        return {
            "total_return": total_return,
            "annual_return": annual_return,
            "monthly_return": annual_return / 12,
            "annual_volatility": annual_vol,
            "daily_volatility": daily_vol,
            "max_drawdown": max_drawdown,
            "max_drawdown_duration": 0,
            "sharpe_ratio": float(sharpe),
            "sortino_ratio": float(sortino),
            "calmar_ratio": float(calmar),
            "stability": 0.0,
            "skew": skew,
            "kurtosis": kurtosis,
            "var_95": var_95,
            "var_99": var_99,
            "win_rate": float(win_rate),
            "profit_loss_ratio": 0.0,
            "alpha": 0.0,
            "beta": 1.0,
            "information_ratio": 0.0,
            "treynor_ratio": 0.0,
            "total_days": len(returns),
            "trading_days_per_year": 252,
            "start_date": str(returns.index[0].date()),
            "end_date": str(returns.index[-1].date()),
        }
    
    def _empty_metrics(self, reason: str) -> Dict[str, Any]:
        """Return empty metrics with reason"""
        return {
            "code": 1,
            "message": reason,
            "data": {
                "total_return": 0.0,
                "annual_return": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "calmar_ratio": 0.0,
                "max_drawdown": 0.0,
                "annual_volatility": 0.0,
                "total_days": 0,
            }
        }
    
    def calculate_from_equity_curve(
        self,
        equity_curve: List[Dict[str, Any]],
        initial_capital: float
    ) -> Dict[str, Any]:
        """
        Calculate metrics from equity curve
        
        Args:
            equity_curve: List of {"date": str, "value": float}
            initial_capital: Starting capital
        
        Returns:
            Performance metrics dictionary
        """
        if not equity_curve or len(equity_curve) < 2:
            return self._empty_metrics("Insufficient equity curve data")
        
        try:
            # Convert equity curve to returns
            values = [e["value"] for e in equity_curve]
            dates = [e["date"] for e in equity_curve]
            
            # Calculate daily returns
            returns = []
            for i in range(1, len(values)):
                if values[i-1] > 0:
                    ret = (values[i] - values[i-1]) / values[i-1]
                    returns.append(ret)
                else:
                    returns.append(0)
            
            # Calculate metrics
            return self.calculate_tearsheet_metrics(
                returns=returns,
                dates=dates[1:]  # Returns start from second day
            )
            
        except Exception as e:
            logger.error(f"[PerformanceAnalyzer] Error processing equity curve: {e}")
            return {
                "code": 1,
                "message": f"Failed to process equity curve: {str(e)}",
                "data": None
            }
    
    def calculate_from_trades(
        self,
        trades: List[Dict[str, Any]],
        initial_capital: float,
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """
        Calculate metrics from trade list
        
        Args:
            trades: List of trade dictionaries with pnl
            initial_capital: Starting capital
            start_date: Backtest start date
            end_date: Backtest end date
        
        Returns:
            Performance metrics dictionary
        """
        if not trades:
            return self._empty_metrics("No trades provided")
        
        try:
            # Build equity curve from trades
            equity = initial_capital
            equity_curve = []
            
            for trade in trades:
                if "pnl" in trade:
                    equity += trade["pnl"]
                    date = trade.get("exit_date", trade.get("entry_date", ""))
                    equity_curve.append({
                        "date": date,
                        "value": equity
                    })
            
            if not equity_curve:
                return self._empty_metrics("No valid trades with PnL")
            
            return self.calculate_from_equity_curve(equity_curve, initial_capital)
            
        except Exception as e:
            logger.error(f"[PerformanceAnalyzer] Error processing trades: {e}")
            return {
                "code": 1,
                "message": f"Failed to process trades: {str(e)}",
                "data": None
            }
