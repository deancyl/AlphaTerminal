"""
Attribution Engine for Multi-Factor Analysis

Calculates factor contributions to portfolio returns using regression-based attribution.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd

try:
    from scipy import stats
    _scipy_available = True
except ImportError:
    _scipy_available = False
    stats = None  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class FactorContribution:
    """Single factor contribution to returns"""
    factor_id: str
    factor_name: str
    category: str
    contribution: Any
    exposure: Any
    return_attribution: Any
    t_statistic: Any
    p_value: Any


@dataclass
class AttributionResult:
    """Complete attribution analysis result"""
    total_return: Any
    factor_contributions: List[FactorContribution]
    residual: Any
    r_squared: Any
    adjusted_r_squared: Any
    f_statistic: Any
    f_p_value: Any
    num_observations: int
    period_start: str
    period_end: str
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API response"""
        return {
            "total_return": self.total_return,
            "factor_contributions": [
                {
                    "factor_id": fc.factor_id,
                    "factor_name": fc.factor_name,
                    "category": fc.category,
                    "contribution": round(fc.contribution, 4),
                    "exposure": round(fc.exposure, 4),
                    "return_attribution": round(fc.return_attribution, 4),
                    "t_statistic": round(fc.t_statistic, 4),
                    "p_value": round(fc.p_value, 4),
                }
                for fc in self.factor_contributions
            ],
            "residual": round(self.residual, 4),
            "r_squared": round(self.r_squared, 4),
            "adjusted_r_squared": round(self.adjusted_r_squared, 4),
            "f_statistic": round(self.f_statistic, 4),
            "f_p_value": round(self.f_p_value, 4),
            "num_observations": self.num_observations,
            "period_start": self.period_start,
            "period_end": self.period_end,
        }


class AttributionEngine:
    """
    Multi-factor attribution engine.
    
    Uses regression-based factor model to decompose returns into factor contributions.
    """
    
    def __init__(self):
        self.min_observations = 20
    
    def calculate_attribution(
        self,
        returns: np.ndarray,
        factor_data: pd.DataFrame,
        factor_ids: List[str],
        period_start: str,
        period_end: str,
    ) -> AttributionResult:
        """
        Calculate factor attribution for given returns.
        
        Args:
            returns: Array of portfolio returns
            factor_data: DataFrame with factor values (columns = factor_ids)
            factor_ids: List of factor IDs to include
            period_start: Start date string
            period_end: End date string
            
        Returns:
            AttributionResult with factor contributions
        """
        # Validate inputs
        if len(returns) < self.min_observations:
            logger.warning(f"[Attribution] Insufficient observations: {len(returns)} < {self.min_observations}")
            return self._empty_result(returns, period_start, period_end)
        
        # Prepare factor matrix
        factor_matrix, valid_factor_ids = self._prepare_factor_matrix(factor_data, factor_ids)
        
        if factor_matrix.shape[1] == 0:
            logger.warning("[Attribution] No valid factors for regression")
            return self._empty_result(returns, period_start, period_end)
        
        # Align returns with factor data
        min_len = min(len(returns), len(factor_matrix))
        returns = returns[-min_len:]
        factor_matrix = factor_matrix[-min_len:]
        
        # Run regression
        try:
            result = self._run_regression(returns, factor_matrix, valid_factor_ids, factor_data)
            result.period_start = period_start
            result.period_end = period_end
            return result
        except Exception as e:
            logger.error(f"[Attribution] Regression failed: {e}")
            return self._empty_result(returns, period_start, period_end)
    
    def calculate_rolling_attribution(
        self,
        returns: np.ndarray,
        factor_data: pd.DataFrame,
        factor_ids: List[str],
        window: int = 60,
        step: int = 20,
    ) -> List[AttributionResult]:
        """
        Calculate rolling window attribution.
        
        Args:
            returns: Array of portfolio returns
            factor_data: DataFrame with factor values
            factor_ids: List of factor IDs
            window: Rolling window size
            step: Step size between windows
            
        Returns:
            List of AttributionResult for each window
        """
        results = []
        
        for i in range(window, len(returns), step):
            window_returns = returns[i - window:i]
            window_factor_data = factor_data.iloc[i - window:i]
            
            result = self.calculate_attribution(
                window_returns,
                window_factor_data,
                factor_ids,
                period_start=str(i - window),
                period_end=str(i),
            )
            results.append(result)
        
        return results
    
    def _prepare_factor_matrix(
        self,
        factor_data: pd.DataFrame,
        factor_ids: List[str],
    ) -> Tuple[np.ndarray, List[str]]:
        """Prepare factor matrix for regression"""
        valid_factors = []
        factor_columns = []
        
        for fid in factor_ids:
            if fid in factor_data.columns:
                col_data = factor_data[fid].values
                # Check for valid data
                if not np.all(np.isnan(col_data)):
                    valid_factors.append(fid)
                    factor_columns.append(col_data)
        
        if not valid_factors:
            return np.array([]).reshape(len(factor_data), 0), []
        
        factor_matrix = np.column_stack(factor_columns)
        
        # Standardize factors (z-score)
        factor_matrix = self._standardize(factor_matrix)
        
        return factor_matrix, valid_factors
    
    def _standardize(self, matrix: np.ndarray) -> np.ndarray:
        """Standardize factor values (z-score normalization)"""
        mean = np.nanmean(matrix, axis=0)
        std = np.nanstd(matrix, axis=0)
        std[std == 0] = 1  # Avoid division by zero
        return (matrix - mean) / std
    
    def _run_regression(
        self,
        returns: np.ndarray,
        factor_matrix: np.ndarray,
        factor_ids: List[str],
        factor_data: pd.DataFrame,
    ) -> AttributionResult:
        """Run OLS regression and calculate factor contributions"""
        # Remove NaN rows
        valid_mask = ~np.isnan(returns)
        for i in range(factor_matrix.shape[1]):
            valid_mask &= ~np.isnan(factor_matrix[:, i])
        
        returns_clean = returns[valid_mask]
        factors_clean = factor_matrix[valid_mask]
        
        if len(returns_clean) < self.min_observations:
            return self._empty_result(returns, "0", "0")
        
        # Add constant for intercept
        X = np.column_stack([np.ones(len(factors_clean)), factors_clean])
        y = returns_clean
        
        # OLS regression
        try:
            beta, residuals, rank, s = np.linalg.lstsq(X, y, rcond=None)
        except np.linalg.LinAlgError:
            return self._empty_result(returns, "0", "0")
        
        # Calculate statistics
        n = len(y)
        k = len(factor_ids)
        
        # Predicted values and residuals
        y_pred = X @ beta
        resid = y - y_pred
        
        # R-squared
        ss_res = np.sum(resid ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0
        
        # Adjusted R-squared
        adjusted_r_squared = 1 - (1 - r_squared) * (n - 1) / (n - k - 1) if n > k + 1 else 0
        
        # Standard errors and t-statistics
        mse = ss_res / (n - k - 1) if n > k + 1 else 0
        try:
            var_beta = mse * np.linalg.inv(X.T @ X)
            se_beta = np.sqrt(np.diag(var_beta))
            t_stats = beta / se_beta
            
            # P-values (two-tailed)
            if _scipy_available and stats is not None:
                p_values = 2 * (1 - stats.t.cdf(np.abs(t_stats), n - k - 1))
            else:
                p_values = np.ones(len(beta))
        except (np.linalg.LinAlgError, ValueError):
            t_stats = np.zeros(len(beta))
            p_values = np.ones(len(beta))
        
        # F-statistic
        ms_model = (ss_tot - ss_res) / k if k > 0 else 0
        f_statistic = ms_model / mse if mse > 0 else 0
        if _scipy_available and stats is not None and k > 0 and n > k + 1:
            f_p_value = 1 - stats.f.cdf(f_statistic, k, n - k - 1)
        else:
            f_p_value = 1
        
        # Factor contributions
        factor_contributions = []
        total_return = np.mean(returns_clean) * 252  # Annualized
        
        for i, fid in enumerate(factor_ids):
            # Get factor metadata
            factor_name = fid
            category = "unknown"
            
            # Calculate contribution
            exposure = np.mean(factors_clean[:, i])
            contribution = beta[i + 1] * exposure  # +1 for intercept
            
            factor_contributions.append(FactorContribution(
                factor_id=fid,
                factor_name=factor_name,
                category=category,
                contribution=contribution,
                exposure=exposure,
                return_attribution=contribution * total_return,
                t_statistic=t_stats[i + 1] if i + 1 < len(t_stats) else 0,
                p_value=p_values[i + 1] if i + 1 < len(p_values) else 1,
            ))
        
        # Residual (unexplained return)
        residual = total_return - sum(fc.return_attribution for fc in factor_contributions)
        
        return AttributionResult(
            total_return=total_return,
            factor_contributions=factor_contributions,
            residual=residual,
            r_squared=r_squared,
            adjusted_r_squared=adjusted_r_squared,
            f_statistic=f_statistic,
            f_p_value=f_p_value,
            num_observations=n,
            period_start="",
            period_end="",
        )
    
    def _empty_result(self, returns: np.ndarray, period_start: str, period_end: str) -> AttributionResult:
        """Return empty attribution result"""
        total_return = np.mean(returns) * 252 if len(returns) > 0 else 0
        return AttributionResult(
            total_return=total_return,
            factor_contributions=[],
            residual=total_return,
            r_squared=0,
            adjusted_r_squared=0,
            f_statistic=0,
            f_p_value=1,
            num_observations=len(returns),
            period_start=period_start,
            period_end=period_end,
        )


# Singleton instance
_attribution_engine: Optional[AttributionEngine] = None


def get_attribution_engine() -> AttributionEngine:
    """Get or create the singleton AttributionEngine instance"""
    global _attribution_engine
    if _attribution_engine is None:
        _attribution_engine = AttributionEngine()
    return _attribution_engine
