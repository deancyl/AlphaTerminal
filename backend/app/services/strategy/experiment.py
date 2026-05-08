from __future__ import annotations

import logging
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    BULL = "bull"
    BEAR = "bear"
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"


@dataclass
class RegimeAnalysis:
    regime: MarketRegime
    confidence: float
    indicators: Dict[str, float]
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


@dataclass
class BacktestJob:
    job_id: str
    strategy_code: str
    params: Dict[str, Any]
    status: str = "pending"
    result: Optional[Dict] = None
    error: Optional[str] = None


@dataclass
class ExperimentResult:
    experiment_id: str
    regime: MarketRegime
    strategy_results: List[Dict]
    best_strategy: Optional[Dict]
    ranking: List[Dict]
    created_at: datetime = field(default_factory=datetime.now)


class RegimeDetector:
    def detect(self, data: pd.DataFrame) -> RegimeAnalysis:
        close = data["close"]
        returns = close.pct_change().dropna()

        ma_short = close.rolling(20).mean()
        ma_long = close.rolling(50).mean()
        volatility = returns.rolling(20).std()

        trend_strength = (ma_short.iloc[-1] - ma_long.iloc[-1]) / ma_long.iloc[-1] if not pd.isna(ma_long.iloc[-1]) else 0
        vol_level = volatility.iloc[-1] / volatility.rolling(60).mean().iloc[-1] if not pd.isna(volatility.iloc[-1]) and volatility.iloc[-1] != 0 else 1

        recent_returns = returns.tail(20)
        positive_ratio = (recent_returns > 0).sum() / len(recent_returns) if len(recent_returns) > 0 else 0.5

        if ma_short.iloc[-1] > ma_long.iloc[-1] and trend_strength > 0.02:
            if vol_level > 1.5:
                regime = MarketRegime.VOLATILE
            else:
                regime = MarketRegime.TRENDING_UP
        elif ma_short.iloc[-1] < ma_long.iloc[-1] and trend_strength < -0.02:
            if vol_level > 1.5:
                regime = MarketRegime.VOLATILE
            else:
                regime = MarketRegime.TRENDING_DOWN
        elif abs(trend_strength) < 0.01:
            regime = MarketRegime.RANGING
        elif positive_ratio > 0.6:
            regime = MarketRegime.BULL
        elif positive_ratio < 0.4:
            regime = MarketRegime.BEAR
        else:
            regime = MarketRegime.UNKNOWN

        confidence = min(abs(trend_strength) * 10 + (vol_level - 1) * 0.3 + abs(positive_ratio - 0.5) * 2, 1.0)

        return RegimeAnalysis(
            regime=regime,
            confidence=float(confidence),
            indicators={
                "trend_strength": float(trend_strength),
                "volatility_ratio": float(vol_level),
                "positive_ratio": float(positive_ratio),
            },
        )


class BatchBacktester:
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers

    def _generate_param_combinations(self, param_grid: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
        import itertools
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        combinations = []
        for combo in itertools.product(*values):
            combinations.append(dict(zip(keys, combo)))
        return combinations

    def run_batch(
        self,
        strategy_codes: List[str],
        data: pd.DataFrame,
        param_grid: Dict[str, List[Any]],
    ) -> List[BacktestJob]:
        jobs: List[BacktestJob] = []
        job_id = 0

        for code in strategy_codes:
            for params in self._generate_param_combinations(param_grid):
                job = BacktestJob(
                    job_id=f"job_{job_id}",
                    strategy_code=code,
                    params=params,
                )
                jobs.append(job)
                job_id += 1

        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self._run_single_backtest, job, data): job for job in jobs}
            for future in as_completed(futures):
                job = futures[future]
                try:
                    result = future.result()
                    job.status = "completed"
                    job.result = result
                except Exception as e:
                    job.status = "failed"
                    job.error = str(e)
                results.append(job)

        return results

    def _run_single_backtest(self, job: BacktestJob, data: pd.DataFrame) -> Dict:
        from .indicator_strategy import create_indicator_strategy
        from .performance import analyze_backtest_result

        strategy = create_indicator_strategy(job.strategy_code)
        signals = strategy.to_signal_df(data, job.params)
        equity = self._simulate_equity(data, signals)
        metrics = analyze_backtest_result(equity, [])

        return {
            "job_id": job.job_id,
            "params": job.params,
            "metrics": metrics,
        }

    def _simulate_equity(self, data: pd.DataFrame, signals: pd.DataFrame) -> pd.Series:
        equity = [1.0]
        position = 0
        for i in range(1, len(data)):
            if position == 0 and signals.iloc[i]["signal"] == 1:
                position = 1
            elif position > 0 and signals.iloc[i]["signal"] == -1:
                position = 0
            ret = (data.iloc[i]["close"] / data.iloc[i-1]["close"]) - 1 if position else 0
            equity.append(equity[-1] * (1 + ret))
        return pd.Series(equity, index=data.index)


class StrategyScorer:
    WEIGHTS = {
        "sharpe_ratio": 0.30,
        "total_return": 0.25,
        "max_drawdown": 0.20,
        "win_rate": 0.15,
        "sortino_ratio": 0.10,
    }

    def score(self, metrics: Dict[str, Any]) -> float:
        score = 0.0
        for metric, weight in self.WEIGHTS.items():
            value = self._normalize_metric(metric, metrics.get(metric, 0))
            score += weight * value
        return score

    def _normalize_metric(self, metric: str, value: Any) -> float:
        if isinstance(value, str):
            try:
                value = float(value.replace("%", ""))
            except (ValueError, AttributeError):
                return 0.0

        if metric == "sharpe_ratio":
            return max(0, min(value / 3.0, 1.0))
        elif metric == "total_return":
            return max(0, min(value / 0.5, 1.0))
        elif metric == "max_drawdown":
            return max(0, min(-value / 0.3, 1.0))
        elif metric == "win_rate":
            return max(0, min(value / 80.0, 1.0))
        elif metric == "sortino_ratio":
            return max(0, min(value / 3.0, 1.0))
        return 0.0


class ExperimentPipeline:
    def __init__(self):
        self.regime_detector = RegimeDetector()
        self.batch_backtester = BatchBacktester()
        self.scorer = StrategyScorer()

    def run(
        self,
        experiment_id: str,
        strategy_codes: List[str],
        data: pd.DataFrame,
        param_grid: Dict[str, List[Any]],
    ) -> ExperimentResult:
        logger.info(f"[Experiment] Starting experiment {experiment_id}")

        regime_analysis = self.regime_detector.detect(data)
        logger.info(f"[Experiment] Detected regime: {regime_analysis.regime.value} (confidence: {regime_analysis.confidence:.2f})")

        jobs = self.batch_backtester.run_batch(strategy_codes, data, param_grid)

        strategy_results = []
        for job in jobs:
            if job.status == "completed" and job.result:
                score = self.scorer.score(job.result["metrics"])
                strategy_results.append({
                    "job_id": job.job_id,
                    "params": job.params,
                    "metrics": job.result["metrics"],
                    "score": score,
                })

        strategy_results.sort(key=lambda x: x["score"], reverse=True)

        best = strategy_results[0] if strategy_results else None

        ranking = [
            {
                "rank": i + 1,
                "job_id": r["job_id"],
                "params": r["params"],
                "score": r["score"],
                "metrics": r["metrics"],
            }
            for i, r in enumerate(strategy_results[:10])
        ]

        return ExperimentResult(
            experiment_id=experiment_id,
            regime=regime_analysis.regime,
            strategy_results=strategy_results,
            best_strategy=best,
            ranking=ranking,
        )


def detect_regime(data: pd.DataFrame) -> RegimeAnalysis:
    detector = RegimeDetector()
    return detector.detect(data)


def run_experiment(
    experiment_id: str,
    strategy_codes: List[str],
    data: pd.DataFrame,
    param_grid: Dict[str, List[Any]],
) -> ExperimentResult:
    pipeline = ExperimentPipeline()
    return pipeline.run(experiment_id, strategy_codes, data, param_grid)
