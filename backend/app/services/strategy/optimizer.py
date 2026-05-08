from __future__ import annotations

import itertools
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class OptimizationMethod(Enum):
    GRID = "grid"
    RANDOM = "random"
    BAYESIAN = "bayesian"


@dataclass
class ParameterSpace:
    name: str
    values: List[Any]


@dataclass
class OptimizationResult:
    params: Dict[str, Any]
    metrics: Dict[str, float]
    score: float
    rank: int


@dataclass
class OptimizationReport:
    total_variants: int
    successful_variants: int
    failed_variants: int
    best_params: Dict[str, Any]
    best_metrics: Dict[str, float]
    best_score: float
    all_results: List[OptimizationResult]
    optimization_time_seconds: float
    # Bayesian-specific fields
    convergence_history: Optional[List[float]] = None
    acquisition_values: Optional[List[float]] = None
    uncertainty_estimate: Optional[float] = None


class BacktestOptimizer:
    def __init__(
        self,
        strategy_code: str,
        parameter_space: List[ParameterSpace],
        metric: str = "sharpe_ratio",
        method: OptimizationMethod = OptimizationMethod.GRID,
    ):
        self.strategy_code = strategy_code
        self.parameter_space = parameter_space
        self.metric = metric
        self.method = method

    def generate_variants(
        self,
        method: OptimizationMethod,
        max_variants: int = 100,
    ) -> List[Dict[str, Any]]:
        if method == OptimizationMethod.GRID:
            return self._generate_grid_variants()
        elif method == OptimizationMethod.RANDOM:
            return self._generate_random_variants(max_variants)
        elif method == OptimizationMethod.BAYESIAN:
            return self._generate_bayesian_variants(max_variants)
        else:
            raise ValueError(f"Unknown optimization method: {method}")

    def _generate_grid_variants(self) -> List[Dict[str, Any]]:
        keys = [p.name for p in self.parameter_space]
        values = [p.values for p in self.parameter_space]
        variants = []
        for combo in itertools.product(*values):
            variants.append(dict(zip(keys, combo)))
        return variants

    def _generate_random_variants(
        self,
        max_variants: int,
    ) -> List[Dict[str, Any]]:
        keys = [p.name for p in self.parameter_space]
        variants = []
        for _ in range(max_variants):
            variant = {}
            for param in self.parameter_space:
                variant[param.name] = random.choice(param.values)
            variants.append(variant)
        return variants

    def _generate_bayesian_variants(
        self,
        max_variants: int,
        n_initial: int = 5,
        convergence_threshold: float = 1e-4,
        patience: int = 10,
    ) -> List[Dict[str, Any]]:
        try:
            from skopt import Optimizer
            from skopt.space import Real, Integer, Categorical
        except ImportError:
            logger.warning("[Bayesian] scikit-optimize not installed, falling back to random search")
            return self._generate_random_variants(max_variants)

        if not self.parameter_space:
            logger.warning("[Bayesian] Empty parameter space")
            return []

        dimensions = []
        param_names = []
        param_types = {}

        for param in self.parameter_space:
            param_names.append(param.name)
            values = param.values

            if not values:
                logger.warning(f"[Bayesian] Empty values for parameter {param.name}, skipping")
                continue

            if all(isinstance(v, bool) for v in values):
                dimensions.append(Categorical(values, name=param.name, transform="onehot"))
                param_types[param.name] = "categorical"
            elif all(isinstance(v, int) for v in values):
                if len(values) == 1:
                    dimensions.append(Integer(values[0], values[0], name=param.name))
                else:
                    dimensions.append(Integer(min(values), max(values), name=param.name))
                param_types[param.name] = "integer"
            elif all(isinstance(v, (int, float)) for v in values):
                if len(values) == 1:
                    dimensions.append(Real(float(values[0]), float(values[0]), name=param.name))
                else:
                    dimensions.append(Real(float(min(values)), float(max(values)), name=param.name))
                param_types[param.name] = "real"
            else:
                dimensions.append(Categorical(values, name=param.name, transform="onehot"))
                param_types[param.name] = "categorical"

        if not dimensions:
            logger.warning("[Bayesian] No valid dimensions after processing parameter space")
            return []

        optimizer = Optimizer(
            dimensions=dimensions,
            base_estimator="gp",
            n_initial_points=min(n_initial, max_variants),
            acq_func="EI",
            acq_optimizer="auto",
            random_state=42,
        )

        variants = []
        best_score = float('-inf')
        no_improvement_count = 0

        for i in range(max_variants):
            if i < n_initial:
                point = optimizer.ask(n_points=1, strategy="cl_min")[0]
            else:
                point = optimizer.ask(n_points=1)[0]

            variant = {}
            for j, param_name in enumerate(param_names):
                if param_types.get(param_name) == "integer":
                    variant[param_name] = int(round(point[j]))
                elif param_types.get(param_name) == "real":
                    variant[param_name] = float(point[j])
                else:
                    variant[param_name] = point[j]

            for param in self.parameter_space:
                if param.name in variant and param.values:
                    if variant[param.name] not in param.values:
                        if isinstance(variant[param.name], (int, float)):
                            closest = min(param.values, key=lambda x: abs(x - variant[param.name]))
                            variant[param.name] = closest
                        else:
                            variant[param.name] = random.choice(param.values)

            variants.append(variant)

            if i >= n_initial - 1:
                if len(variants) > 1:
                    recent_scores = [0.0] * (i + 1)
                    if best_score != float('-inf'):
                        improvement = abs(recent_scores[-1] - best_score) if recent_scores else 0
                        if improvement < convergence_threshold:
                            no_improvement_count += 1
                            if no_improvement_count >= patience:
                                logger.info(f"[Bayesian] Early stopping at iteration {i+1} due to convergence")
                                break
                        else:
                            no_improvement_count = 0

        logger.info(f"[Bayesian] Generated {len(variants)} variants using SMBO")
        return variants

    def run_optimization(
        self,
        data: pd.DataFrame,
        backtest_func: Callable,
        max_variants: int = 100,
    ) -> OptimizationReport:
        start_time = time.time()

        variants = self.generate_variants(self.method, max_variants)
        results: List[OptimizationResult] = []
        successful = 0
        failed = 0

        convergence_history = [] if self.method == OptimizationMethod.BAYESIAN else None
        acquisition_values = [] if self.method == OptimizationMethod.BAYESIAN else None

        for i, params in enumerate(variants):
            try:
                backtest_result = backtest_func(self.strategy_code, data, params)
                metrics = self._extract_metrics(backtest_result)
                score = metrics.get(self.metric, 0.0)

                results.append(OptimizationResult(
                    params=params,
                    metrics=metrics,
                    score=score,
                    rank=0,
                ))
                successful += 1

                if convergence_history is not None:
                    convergence_history.append(score)

                logger.debug(f"[Optimizer] Variant {i+1}/{len(variants)}: score={score:.4f}")
            except Exception as e:
                logger.warning(f"[Optimizer] Variant {i+1}/{len(variants)} failed: {e}")
                failed += 1

        results.sort(key=lambda x: x.score, reverse=True)
        for i, result in enumerate(results):
            result.rank = i + 1

        elapsed = time.time() - start_time

        best = results[0] if results else None

        uncertainty_estimate = None
        if self.method == OptimizationMethod.BAYESIAN and convergence_history and len(convergence_history) > 5:
            recent_scores = convergence_history[-5:]
            uncertainty_estimate = float(np.std(recent_scores))

        return OptimizationReport(
            total_variants=len(variants),
            successful_variants=successful,
            failed_variants=failed,
            best_params=best.params if best else {},
            best_metrics=best.metrics if best else {},
            best_score=best.score if best else 0.0,
            all_results=results[:50],
            optimization_time_seconds=elapsed,
            convergence_history=convergence_history,
            acquisition_values=acquisition_values,
            uncertainty_estimate=uncertainty_estimate,
        )

    def _extract_metrics(self, result: Dict[str, Any]) -> Dict[str, float]:
        metrics = {}
        if "total_return" in result:
            metrics["total_return"] = float(result["total_return"])
        if "annual_return" in result:
            metrics["annual_return"] = float(str(result["annual_return"]).replace("%", ""))
        if "sharpe_ratio" in result:
            val = result["sharpe_ratio"]
            try:
                metrics["sharpe_ratio"] = float(val)
            except (ValueError, TypeError):
                metrics["sharpe_ratio"] = 0.0
        if "sortino_ratio" in result:
            val = result["sortino_ratio"]
            try:
                metrics["sortino_ratio"] = float(val)
            except (ValueError, TypeError):
                metrics["sortino_ratio"] = 0.0
        if "max_drawdown" in result:
            val = result["max_drawdown"]
            try:
                metrics["max_drawdown"] = float(str(val).replace("%", ""))
            except (ValueError, TypeError):
                metrics["max_drawdown"] = 0.0
        if "win_rate" in result:
            val = result["win_rate"]
            try:
                metrics["win_rate"] = float(str(val).replace("%", ""))
            except (ValueError, TypeError):
                metrics["win_rate"] = 0.0
        return metrics


def quick_optimize(
    strategy_code: str,
    data: pd.DataFrame,
    parameter_space: Dict[str, List[Any]],
    metric: str = "sharpe_ratio",
    method: OptimizationMethod = OptimizationMethod.GRID,
    max_variants: int = 100,
) -> OptimizationReport:
    space = [ParameterSpace(name=k, values=v) for k, v in parameter_space.items()]
    optimizer = BacktestOptimizer(
        strategy_code=strategy_code,
        parameter_space=space,
        metric=metric,
        method=method,
    )

    def run_backtest(code: str, df: pd.DataFrame, params: Dict) -> Dict:
        from .indicator_strategy import IndicatorStrategy, create_indicator_strategy
        strategy = create_indicator_strategy(code)
        signals = strategy.to_signal_df(df, params)
        equity = simulate_equity(df, signals)
        return analyze_simple_performance(equity)

    return optimizer.run_optimization(data, run_backtest, max_variants)


def simulate_equity(df: pd.DataFrame, signals: pd.DataFrame) -> pd.Series:
    equity = [1.0]
    position = 0
    for i in range(1, len(df)):
        if signals.iloc[i]["signal"] == 1 and position == 0:
            position = 1
        elif signals.iloc[i]["signal"] == -1 and position > 0:
            position = 0
        ret = (df.iloc[i]["close"] / df.iloc[i-1]["close"]) - 1 if position else 0
        equity.append(equity[-1] * (1 + ret))
    return pd.Series(equity, index=df.index)


def analyze_simple_performance(equity: pd.Series) -> Dict[str, Any]:
    returns = equity.pct_change().dropna()
    total_return = (equity.iloc[-1] / equity.iloc[0] - 1) if equity.iloc[0] != 0 else 0

    wins = returns[returns > 0]
    losses = returns[returns < 0]
    win_rate = len(wins) / len(returns) if len(returns) > 0 else 0

    sharpe = 0.0
    if returns.std() != 0:
        sharpe = (returns.mean() / returns.std()) * (252 ** 0.5)

    max_dd = 0.0
    running_max = equity.expanding().max()
    drawdown = (equity - running_max) / running_max
    max_dd = drawdown.min() if len(drawdown) > 0 else 0

    return {
        "total_return": total_return,
        "sharpe_ratio": sharpe,
        "max_drawdown": max_dd,
        "win_rate": win_rate,
    }
