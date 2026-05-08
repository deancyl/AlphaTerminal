"""
Performance Analyzer Service - pyfolio-reloaded integration
"""
import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


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
