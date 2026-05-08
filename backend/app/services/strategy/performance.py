import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class PerformanceMetrics:
    total_return: float
    annual_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    calmar_ratio: float
    win_rate: float
    profit_loss_ratio: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win: float
    avg_loss: float
    avg_holding_period: float
    equity_curve: pd.Series
    drawdown_curve: pd.Series


class PerformanceAnalyzer:
    def __init__(self, returns: pd.Series, positions: Optional[pd.DataFrame] = None):
        self.returns = returns.dropna()
        self.positions = positions

    def calculate_metrics(self) -> PerformanceMetrics:
        total_return = self._total_return()
        annual_return = self._annual_return()
        sharpe = self._sharpe_ratio()
        sortino = self._sortino_ratio()
        max_dd = self._max_drawdown()
        calmar = self._calmar_ratio()
        win_rate, pl_ratio, avg_win, avg_loss = self._trade_stats()
        holding_period = self._avg_holding_period()
        equity = self._equity_curve()
        drawdown = self._drawdown_curve()

        return PerformanceMetrics(
            total_return=total_return,
            annual_return=annual_return,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_dd,
            calmar_ratio=calmar,
            win_rate=win_rate,
            profit_loss_ratio=pl_ratio,
            total_trades=len([r for r in self.returns if r != 0]),
            winning_trades=int(win_rate * len(self.returns)),
            losing_trades=int((1 - win_rate) * len(self.returns)),
            avg_win=avg_win,
            avg_loss=avg_loss,
            avg_holding_period=holding_period,
            equity_curve=equity,
            drawdown_curve=drawdown,
        )

    def _total_return(self) -> float:
        if len(self.returns) == 0:
            return 0.0
        return float((1 + self.returns).prod() - 1)

    def _annual_return(self, periods_per_year: int = 252) -> float:
        if len(self.returns) == 0:
            return 0.0
        total = (1 + self.returns).prod() - 1
        years = len(self.returns) / periods_per_year
        if years <= 0:
            return 0.0
        return float((1 + total) ** (1 / years) - 1)

    def _sharpe_ratio(self, risk_free_rate: float = 0.0, periods_per_year: int = 252) -> float:
        if len(self.returns) == 0 or self.returns.std() == 0:
            return 0.0
        excess_returns = self.returns - risk_free_rate / periods_per_year
        return float(np.sqrt(periods_per_year) * excess_returns.mean() / excess_returns.std())

    def _sortino_ratio(self, risk_free_rate: float = 0.0, periods_per_year: int = 252) -> float:
        if len(self.returns) == 0:
            return 0.0
        excess_returns = self.returns - risk_free_rate / periods_per_year
        downside_returns = excess_returns[excess_returns < 0]
        if len(downside_returns) == 0 or downside_returns.std() == 0:
            return 0.0
        return float(np.sqrt(periods_per_year) * excess_returns.mean() / downside_returns.std())

    def _max_drawdown(self) -> float:
        if len(self.returns) == 0:
            return 0.0
        equity = (1 + self.returns).cumprod()
        running_max = equity.expanding().max()
        drawdown = (equity - running_max) / running_max
        return float(drawdown.min())

    def _calmar_ratio(self) -> float:
        max_dd = abs(self._max_drawdown())
        if max_dd == 0:
            return 0.0
        return self._annual_return() / max_dd

    def _trade_stats(self) -> Tuple[float, float, float, float]:
        if len(self.returns) == 0:
            return 0.0, 0.0, 0.0, 0.0
        wins = self.returns[self.returns > 0]
        losses = self.returns[self.returns < 0]
        win_rate = len(wins) / len(self.returns) if len(self.returns) > 0 else 0.0
        avg_win = float(wins.mean()) if len(wins) > 0 else 0.0
        avg_loss = float(losses.mean()) if len(losses) > 0 else 0.0
        pl_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0.0
        return win_rate, pl_ratio, avg_win, avg_loss

    def _avg_holding_period(self) -> float:
        if self.positions is None or len(self.positions) == 0:
            return 0.0
        if 'holding_period' not in self.positions.columns:
            return 0.0
        return float(self.positions['holding_period'].mean())

    def _equity_curve(self) -> pd.Series:
        if len(self.returns) == 0:
            return pd.Series([1.0])
        return (1 + self.returns).cumprod()

    def _drawdown_curve(self) -> pd.Series:
        if len(self.returns) == 0:
            return pd.Series([0.0])
        equity = self._equity_curve()
        running_max = equity.expanding().max()
        return (equity - running_max) / running_max

    def to_dict(self) -> Dict:
        m = self.calculate_metrics()
        return {
            "total_return": f"{m.total_return*100:.2f}%",
            "annual_return": f"{m.annual_return*100:.2f}%",
            "sharpe_ratio": f"{m.sharpe_ratio:.2f}",
            "sortino_ratio": f"{m.sortino_ratio:.2f}",
            "max_drawdown": f"{m.max_drawdown*100:.2f}%",
            "calmar_ratio": f"{m.calmar_ratio:.2f}",
            "win_rate": f"{m.win_rate*100:.2f}%",
            "profit_loss_ratio": f"{m.profit_loss_ratio:.2f}",
            "total_trades": m.total_trades,
            "winning_trades": m.winning_trades,
            "losing_trades": m.losing_trades,
            "avg_win": f"{m.avg_win:.4f}",
            "avg_loss": f"{m.avg_loss:.4f}",
            "avg_holding_period": f"{m.avg_holding_period:.1f}",
        }


def analyze_backtest_result(equity_curve: pd.Series, trades: List[Dict]) -> Dict:
    if len(equity_curve) < 2:
        return {"error": "Insufficient data"}

    returns = equity_curve.pct_change().dropna()
    analyzer = PerformanceAnalyzer(returns)
    metrics = analyzer.calculate_metrics()

    return {
        "final_equity": float(equity_curve.iloc[-1]),
        "initial_equity": float(equity_curve.iloc[0]),
        "total_return": f"{metrics.total_return*100:.2f}%",
        "annual_return": f"{metrics.annual_return*100:.2f}%",
        "sharpe_ratio": round(metrics.sharpe_ratio, 2),
        "sortino_ratio": round(metrics.sortino_ratio, 2),
        "max_drawdown": f"{metrics.max_drawdown*100:.2f}%",
        "calmar_ratio": round(metrics.calmar_ratio, 2),
        "win_rate": f"{metrics.win_rate*100:.1f}%",
        "total_trades": metrics.total_trades,
        "winning_trades": metrics.winning_trades,
        "losing_trades": metrics.losing_trades,
        "equity_curve": equity_curve.tolist(),
        "drawdown_curve": metrics.drawdown_curve.tolist(),
    }
