"""
ML Model Management API

Provides endpoints for model registration, training, and prediction.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.utils.response import success_response, error_response, ErrorCode
from app.middleware import require_api_key

logger = logging.getLogger(__name__)

router = APIRouter()


class ModelCreateRequest(BaseModel):
    model_id: str = Field(..., min_length=1, max_length=100)
    model_type: str = Field(default="LightGBM", pattern="^(LightGBM|HIST|GATE|GRU|LSTM|MLP|XGBoost|CatBoost|Custom)$")
    provider: str = Field(default="qlib", pattern="^(qlib|sklearn|custom)$")
    feature_set: str = Field(default="Alpha158", pattern="^(Alpha158|Alpha360|Custom)$")
    params: Optional[Dict[str, Any]] = Field(default=None)


class ModelTrainRequest(BaseModel):
    model_id: str = Field(..., min_length=1)
    symbol: str = Field(..., min_length=1, max_length=20, pattern="^(sh|sz)[0-9]{6}$")
    start_date: str = Field(..., description="Training start date YYYY-MM-DD")
    end_date: str = Field(..., description="Training end date YYYY-MM-DD")
    feature_set: str = Field(default="Alpha158")
    params: Optional[Dict[str, Any]] = Field(default=None)
    target: str = Field(default="return_1d", description="Prediction target")


class ModelPredictRequest(BaseModel):
    model_id: str = Field(..., min_length=1)
    symbol: str = Field(..., min_length=1, max_length=20)
    start_date: str = Field(..., description="Prediction start date YYYY-MM-DD")
    end_date: str = Field(..., description="Prediction end date YYYY-MM-DD")


class ModelResponse(BaseModel):
    model_id: str
    model_type: str
    provider: str
    feature_set: str
    created_at: str
    updated_at: str
    metrics: Dict[str, float] = {}
    params: Dict[str, Any] = {}
    is_loaded: bool = False


@router.get("/models")
async def list_models():
    """List all available ML models."""
    from app.services.qlib.model_loader import get_model_loader
    
    loader = get_model_loader()
    models = loader.list_models()
    
    result = []
    for m in models:
        result.append({
            "model_id": m.model_id,
            "model_type": m.model_type.value,
            "provider": m.provider.value,
            "feature_set": m.feature_set,
            "created_at": m.created_at.isoformat(),
            "updated_at": m.updated_at.isoformat(),
            "metrics": m.metrics,
            "params": m.params,
            "is_loaded": m.is_loaded,
        })
    
    return success_response({"models": result, "total": len(result)})


@router.post("/models")
async def create_model(req: ModelCreateRequest, _: None = Depends(require_api_key)):
    """Register a new ML model."""
    from app.services.qlib.model_loader import get_model_loader, ModelType, ModelProvider
    
    loader = get_model_loader()
    
    existing = loader.load_model(req.model_id)
    if existing is not None:
        return error_response(ErrorCode.BAD_REQUEST, f"Model {req.model_id} already exists")
    
    try:
        model_type = ModelType(req.model_type)
        provider = ModelProvider(req.provider)
        
        return success_response({
            "model_id": req.model_id,
            "model_type": req.model_type,
            "provider": req.provider,
            "feature_set": req.feature_set,
            "message": "Model registered. Use /train to train the model.",
        })
        
    except ValueError as e:
        return error_response(ErrorCode.BAD_REQUEST, f"Invalid model type or provider: {e}")


@router.get("/models/{model_id}")
async def get_model(model_id: str):
    """Get model details."""
    from app.services.qlib.model_loader import get_model_loader
    
    loader = get_model_loader()
    models = loader.list_models()
    
    for m in models:
        if m.model_id == model_id:
            return success_response({
                "model_id": m.model_id,
                "model_type": m.model_type.value,
                "provider": m.provider.value,
                "feature_set": m.feature_set,
                "created_at": m.created_at.isoformat(),
                "updated_at": m.updated_at.isoformat(),
                "metrics": m.metrics,
                "params": m.params,
                "is_loaded": m.is_loaded,
            })
    
    return error_response(ErrorCode.NOT_FOUND, f"Model {model_id} not found")


@router.delete("/models/{model_id}")
async def delete_model(model_id: str, _: None = Depends(require_api_key)):
    """Delete a model."""
    from app.services.qlib.model_loader import get_model_loader
    
    loader = get_model_loader()
    
    if loader.delete_model(model_id):
        return success_response({"message": f"Model {model_id} deleted"})
    else:
        return error_response(ErrorCode.NOT_FOUND, f"Model {model_id} not found")


@router.post("/train")
async def train_model(req: ModelTrainRequest, _: None = Depends(require_api_key)):
    """Train a model on historical data."""
    import pandas as pd
    from app.db.database import _get_conn
    from app.services.qlib.model_loader import get_model_loader, ModelType
    from app.services.qlib.feature_pipeline import FeaturePipeline, FeatureSet
    
    loader = get_model_loader()
    
    db_symbol = req.symbol.replace("sh", "").replace("sz", "")
    
    conn = _get_conn()
    try:
        rows = conn.execute("""
            SELECT date, open, high, low, close, volume
            FROM market_data_daily
            WHERE symbol = ? AND date >= ? AND date <= ?
            ORDER BY date ASC
        """, (db_symbol, req.start_date, req.end_date)).fetchall()
        
        if len(rows) < 100:
            return error_response(ErrorCode.BAD_REQUEST, 
                f"Insufficient data ({len(rows)} rows). Need at least 100 rows for training.")
        
        df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        
        feature_set = FeatureSet.ALPHA158 if req.feature_set == "Alpha158" else FeatureSet.ALPHA360
        pipeline = FeaturePipeline(feature_set)
        features = pipeline.generate_features(df)
        
        df["return_1d"] = df["close"].pct_change().shift(-1)
        df["return_5d"] = df["close"].pct_change(5).shift(-5)
        
        target_col = req.target if req.target in df.columns else "return_1d"
        target = df[target_col].dropna()
        
        features = features.loc[target.index]
        
        train_size = int(len(features) * 0.8)
        X_train = features.iloc[:train_size]
        y_train = target.iloc[:train_size]
        
        try:
            model_type = ModelType(req.model_id.split("_")[0]) if "_" in req.model_id else ModelType.LIGHTGBM
        except ValueError:
            model_type = ModelType.LIGHTGBM
        
        model = loader.train_model(
            model_type=model_type,
            X_train=X_train,
            y_train=y_train,
            params=req.params,
            model_id=req.model_id,
        )
        
        if model is None:
            return error_response(ErrorCode.INTERNAL_ERROR, "Training failed")
        
        X_test = features.iloc[train_size:]
        y_test = target.iloc[train_size:]
        
        predictions = loader.predict(req.model_id, X_test)
        
        if predictions is not None:
            mse = ((predictions - y_test.values) ** 2).mean()
            mae = abs(predictions - y_test.values).mean()
            
            loader._save_model_metadata(req.model_id, loader._model_info.get(req.model_id))
            
            return success_response({
                "model_id": req.model_id,
                "symbol": req.symbol,
                "train_samples": len(X_train),
                "test_samples": len(X_test),
                "metrics": {
                    "mse": round(mse, 6),
                    "mae": round(mae, 6),
                },
                "feature_count": len(features.columns),
                "training_date": datetime.now().isoformat(),
            })
        else:
            return success_response({
                "model_id": req.model_id,
                "symbol": req.symbol,
                "train_samples": len(X_train),
                "message": "Model trained successfully",
            })
            
    finally:
        conn.close()


@router.post("/predict")
async def predict_model(req: ModelPredictRequest, _: None = Depends(require_api_key)):
    """Generate predictions using a trained model."""
    import pandas as pd
    import numpy as np
    from app.db.database import _get_conn
    from app.services.qlib.model_loader import get_model_loader
    from app.services.qlib.feature_pipeline import FeaturePipeline, FeatureSet
    
    loader = get_model_loader()
    
    model = loader.load_model(req.model_id)
    if model is None:
        return error_response(ErrorCode.NOT_FOUND, f"Model {req.model_id} not found")
    
    db_symbol = req.symbol.replace("sh", "").replace("sz", "")
    
    conn = _get_conn()
    try:
        rows = conn.execute("""
            SELECT date, open, high, low, close, volume
            FROM market_data_daily
            WHERE symbol = ? AND date >= ? AND date <= ?
            ORDER BY date ASC
        """, (db_symbol, req.start_date, req.end_date)).fetchall()
        
        if len(rows) == 0:
            return error_response(ErrorCode.NOT_FOUND, f"No data for {req.symbol} in date range")
        
        df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        
        pipeline = FeaturePipeline(FeatureSet.ALPHA158)
        features = pipeline.generate_features(df)
        
        predictions = loader.predict(req.model_id, features)
        
        if predictions is None:
            return error_response(ErrorCode.INTERNAL_ERROR, "Prediction failed")
        
        signals = []
        threshold = 0.5
        for pred in predictions:
            if pred > threshold:
                signals.append(1)
            elif pred < -threshold:
                signals.append(-1)
            else:
                signals.append(0)
        
        result_df = pd.DataFrame({
            "date": df.index.astype(str),
            "close": df["close"],
            "prediction": predictions,
            "signal": signals,
        })
        
        return success_response({
            "model_id": req.model_id,
            "symbol": req.symbol,
            "predictions": result_df.to_dict(orient="records"),
            "total": len(predictions),
        })
        
    finally:
        conn.close()


@router.get("/health")
async def ml_health_check():
    """Health check for ML module."""
    from app.services.qlib.qlib_init import is_qlib_available
    from app.services.qlib.model_loader import get_model_loader
    
    qlib_available = is_qlib_available()
    loader = get_model_loader()
    models = loader.list_models()
    
    return success_response({
        "status": "healthy",
        "qlib_available": qlib_available,
        "models_count": len(models),
        "models_dir": str(loader.model_dir),
    })


# ═══════════════════════════════════════════════════════════════
# Phase 2: Portfolio Optimization & Factor Analysis Endpoints
# ═══════════════════════════════════════════════════════════════

import asyncio
import numpy as np


class PortfolioOptimizeRequest(BaseModel):
    """Portfolio optimization request."""
    symbols: List[str] = Field(..., min_items=1, max_items=50, description="List of stock symbols")
    start_date: str = Field(..., description="Start date YYYY-MM-DD")
    end_date: str = Field(..., description="End date YYYY-MM-DD")
    method: str = Field(default="mvo", pattern="^(gmv|mvo|rp|inv)$", 
                        description="Optimization method: gmv=Global Min Variance, mvo=Mean-Variance, rp=Risk Parity, inv=Inverse Volatility")
    risk_aversion: float = Field(default=1.0, ge=0, le=10, description="Risk aversion parameter (higher = more conservative)")
    turnover_limit: float = Field(default=0.2, ge=0, le=1, description="Maximum turnover from current weights")
    target_return: Optional[float] = Field(default=None, description="Target return for optimization")
    max_weight: float = Field(default=0.3, ge=0.01, le=1.0, description="Maximum weight per asset")


class FactorAnalysisRequest(BaseModel):
    """Factor exposure analysis request."""
    symbol: str = Field(..., pattern="^(sh|sz)[0-9]{6}$", description="Stock symbol")
    start_date: str = Field(..., description="Start date YYYY-MM-DD")
    end_date: str = Field(..., description="End date YYYY-MM-DD")
    factors: List[str] = Field(default=["momentum", "value", "quality", "size", "volatility"],
                               description="Factors to analyze")


class RiskMetricsRequest(BaseModel):
    """Risk metrics calculation request."""
    daily_returns: List[float] = Field(..., min_items=10, description="Daily returns series")
    freq: str = Field(default="day", pattern="^(day|week|month)$")
    annual_periods: int = Field(default=252, description="Periods per year for annualization")


@router.post("/optimize")
async def optimize_portfolio(req: PortfolioOptimizeRequest, _: None = Depends(require_api_key)):
    """
    Optimize portfolio weights using specified method.
    
    Methods:
    - gmv: Global Minimum Variance (minimize risk only)
    - mvo: Mean-Variance Optimization (balance return vs risk)
    - rp: Risk Parity (equal risk contribution)
    - inv: Inverse Volatility (weight inversely proportional to volatility)
    """
    import pandas as pd
    from app.db.database import _get_conn
    
    PORTFOLIO_OPT_TIMEOUT = 30  # seconds
    
    try:
        result = await asyncio.wait_for(
            _run_portfolio_optimization(req),
            timeout=PORTFOLIO_OPT_TIMEOUT
        )
        return success_response(result)
    except asyncio.TimeoutError:
        return error_response(ErrorCode.TIMEOUT, f"Portfolio optimization timed out after {PORTFOLIO_OPT_TIMEOUT}s")
    except Exception as e:
        logger.error(f"[ML] Portfolio optimization error: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, str(e))


async def _run_portfolio_optimization(req: PortfolioOptimizeRequest) -> Dict:
    """Execute portfolio optimization."""
    import pandas as pd
    from app.db.database import _get_conn
    
    # Fetch historical data for all symbols
    conn = _get_conn()
    try:
        all_data = {}
        for symbol in req.symbols:
            db_symbol = symbol.replace("sh", "").replace("sz", "")
            rows = conn.execute("""
                SELECT date, close
                FROM market_data_daily
                WHERE symbol = ? AND date >= ? AND date <= ?
                ORDER BY date ASC
            """, (db_symbol, req.start_date, req.end_date)).fetchall()
            
            if len(rows) < 30:
                raise ValueError(f"Insufficient data for {symbol}: {len(rows)} rows")
            
            df = pd.DataFrame(rows, columns=["date", "close"])
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
            all_data[symbol] = df["close"]
        
        # Build price DataFrame
        prices = pd.DataFrame(all_data)
        
        # Calculate returns
        returns = prices.pct_change().dropna()
        
        # Calculate expected returns and covariance
        expected_returns = returns.mean() * 252  # Annualized
        cov_matrix = returns.cov() * 252  # Annualized
        
        # Optimize based on method
        if req.method == "gmv":
            weights = _optimize_gmv(cov_matrix, req.max_weight)
        elif req.method == "mvo":
            weights = _optimize_mvo(expected_returns, cov_matrix, req.risk_aversion, req.max_weight)
        elif req.method == "rp":
            weights = _optimize_risk_parity(cov_matrix, req.max_weight)
        else:  # inv
            weights = _optimize_inverse_vol(returns, req.max_weight)
        
        # Calculate portfolio metrics
        portfolio_return = sum(weights.get(s, 0) * expected_returns.get(s, 0) for s in req.symbols)
        portfolio_volatility = np.sqrt(np.dot(
            list(weights.values()),
            np.dot(cov_matrix.values, list(weights.values()))
        )) if len(weights) > 0 else 0
        sharpe_ratio = portfolio_return / portfolio_volatility if portfolio_volatility > 0 else 0
        
        return {
            "weights": weights,
            "expected_return": round(portfolio_return * 100, 2),
            "expected_volatility": round(portfolio_volatility * 100, 2),
            "sharpe_ratio": round(sharpe_ratio, 3),
            "method": req.method,
            "symbols_count": len(req.symbols),
            "optimization_date": datetime.now().isoformat(),
        }
    finally:
        conn.close()


def _optimize_gmv(cov_matrix, max_weight: float) -> Dict[str, float]:
    """Global Minimum Variance optimization."""
    import numpy as np
    from scipy.optimize import minimize
    
    n = len(cov_matrix)
    symbols = list(cov_matrix.columns)
    
    def objective(w):
        return np.dot(w, np.dot(cov_matrix.values, w))
    
    constraints = [
        {"type": "eq", "fun": lambda w: np.sum(w) - 1},  # Sum to 1
    ]
    bounds = [(0, max_weight) for _ in range(n)]  # Long only, max weight
    
    x0 = np.ones(n) / n  # Equal weight initial
    result = minimize(objective, x0, method="SLSQP", bounds=bounds, constraints=constraints)
    
    return {s: round(w, 4) for s, w in zip(symbols, result.x) if w > 0.001}


def _optimize_mvo(expected_returns, cov_matrix, risk_aversion: float, max_weight: float) -> Dict[str, float]:
    """Mean-Variance Optimization."""
    import numpy as np
    from scipy.optimize import minimize
    
    n = len(cov_matrix)
    symbols = list(cov_matrix.columns)
    returns = expected_returns.values
    
    def objective(w):
        portfolio_return = np.dot(w, returns)
        portfolio_variance = np.dot(w, np.dot(cov_matrix.values, w))
        # Maximize return - risk_aversion * variance
        return -portfolio_return + risk_aversion * portfolio_variance
    
    constraints = [
        {"type": "eq", "fun": lambda w: np.sum(w) - 1},
    ]
    bounds = [(0, max_weight) for _ in range(n)]
    
    x0 = np.ones(n) / n
    result = minimize(objective, x0, method="SLSQP", bounds=bounds, constraints=constraints)
    
    return {s: round(w, 4) for s, w in zip(symbols, result.x) if w > 0.001}


def _optimize_risk_parity(cov_matrix, max_weight: float) -> Dict[str, float]:
    """Risk Parity optimization - equal risk contribution."""
    import numpy as np
    from scipy.optimize import minimize
    
    n = len(cov_matrix)
    symbols = list(cov_matrix.columns)
    
    def risk_contribution(w):
        portfolio_var = np.dot(w, np.dot(cov_matrix.values, w))
        marginal_contrib = np.dot(cov_matrix.values, w)
        risk_contrib = w * marginal_contrib / np.sqrt(portfolio_var) if portfolio_var > 0 else np.zeros(n)
        return risk_contrib
    
    def objective(w):
        rc = risk_contribution(w)
        target_risk = 1.0 / n  # Equal risk contribution
        return np.sum((rc - target_risk) ** 2)
    
    constraints = [
        {"type": "eq", "fun": lambda w: np.sum(w) - 1},
    ]
    bounds = [(0.001, max_weight) for _ in range(n)]
    
    x0 = np.ones(n) / n
    result = minimize(objective, x0, method="SLSQP", bounds=bounds, constraints=constraints)
    
    return {s: round(w, 4) for s, w in zip(symbols, result.x) if w > 0.001}


def _optimize_inverse_vol(returns, max_weight: float) -> Dict[str, float]:
    """Inverse Volatility optimization."""
    symbols = list(returns.columns)
    vols = returns.std() * np.sqrt(252)  # Annualized volatility
    
    # Weight inversely proportional to volatility
    inv_vols = 1.0 / vols
    weights = inv_vols / inv_vols.sum()
    
    # Apply max weight constraint
    weights = weights.clip(upper=max_weight)
    weights = weights / weights.sum()  # Renormalize
    
    return {s: round(w, 4) for s, w in zip(symbols, weights.values) if w > 0.001}


@router.post("/factors")
async def analyze_factors(req: FactorAnalysisRequest, _: None = Depends(require_api_key)):
    """
    Analyze factor exposures for a given symbol.
    
    Returns:
    - Factor exposures (beta coefficients)
    - IC and Rank IC for each factor
    - R-squared and model statistics
    """
    import pandas as pd
    from app.db.database import _get_conn
    
    FACTOR_ANALYSIS_TIMEOUT = 30  # seconds
    
    try:
        result = await asyncio.wait_for(
            _run_factor_analysis(req),
            timeout=FACTOR_ANALYSIS_TIMEOUT
        )
        return success_response(result)
    except asyncio.TimeoutError:
        return error_response(ErrorCode.TIMEOUT, f"Factor analysis timed out after {FACTOR_ANALYSIS_TIMEOUT}s")
    except Exception as e:
        logger.error(f"[ML] Factor analysis error: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, str(e))


async def _run_factor_analysis(req: FactorAnalysisRequest) -> Dict:
    """Execute factor analysis."""
    import pandas as pd
    from scipy import stats
    from app.db.database import _get_conn
    
    conn = _get_conn()
    try:
        # Fetch stock data
        db_symbol = req.symbol.replace("sh", "").replace("sz", "")
        rows = conn.execute("""
            SELECT date, close, volume
            FROM market_data_daily
            WHERE symbol = ? AND date >= ? AND date <= ?
            ORDER BY date ASC
        """, (db_symbol, req.start_date, req.end_date)).fetchall()
        
        if len(rows) < 60:
            raise ValueError(f"Insufficient data for factor analysis: {len(rows)} rows")
        
        df = pd.DataFrame(rows, columns=["date", "close", "volume"])
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        
        # Calculate stock returns
        df["return"] = df["close"].pct_change()
        df = df.dropna()
        
        # Calculate factor exposures
        factor_data = {}
        exposures = {}
        ic_values = {}
        
        # Momentum factor (12-1 month return)
        if "momentum" in req.factors:
            df["momentum"] = df["close"].pct_change(252).shift(21)  # 12M return, 1M lag
            factor_data["momentum"] = df["momentum"]
        
        # Value factor (inverse of price level, proxy)
        if "value" in req.factors:
            df["value"] = -np.log(df["close"])  # Lower price = higher value
            factor_data["value"] = df["value"]
        
        # Quality factor (return stability)
        if "quality" in req.factors:
            df["quality"] = -df["return"].rolling(60).std()  # Lower volatility = higher quality
            factor_data["quality"] = df["quality"]
        
        # Size factor (log market cap proxy via volume)
        if "size" in req.factors:
            df["size"] = -np.log(df["volume"] + 1)  # Lower volume = smaller
            factor_data["size"] = df["size"]
        
        # Volatility factor
        if "volatility" in req.factors:
            df["volatility"] = df["return"].rolling(20).std()
            factor_data["volatility"] = df["volatility"]
        
        # Calculate exposures and IC
        for factor_name, factor_series in factor_data.items():
            # Align data
            aligned = pd.DataFrame({
                "return": df["return"],
                "factor": factor_series
            }).dropna()
            
            if len(aligned) < 30:
                continue
            
            # Calculate beta (exposure)
            slope, intercept, r_value, p_value, std_err = stats.linregress(
                aligned["factor"], aligned["return"]
            )
            exposures[factor_name] = {
                "beta": round(slope, 4),
                "t_stat": round(slope / std_err, 3) if std_err > 0 else 0,
                "p_value": round(p_value, 4),
                "r_squared": round(r_value ** 2, 4),
            }
            
            # Calculate IC (Information Coefficient)
            ic = aligned["factor"].corr(aligned["return"])
            rank_ic = aligned["factor"].corr(aligned["return"], method="spearman")
            ic_values[factor_name] = {
                "ic": round(ic, 4),
                "rank_ic": round(rank_ic, 4),
            }
        
        return {
            "symbol": req.symbol,
            "start_date": req.start_date,
            "end_date": req.end_date,
            "exposures": exposures,
            "ic_values": ic_values,
            "data_points": len(df),
            "analysis_date": datetime.now().isoformat(),
        }
    finally:
        conn.close()


@router.post("/risk-metrics")
async def calculate_risk_metrics(req: RiskMetricsRequest):
    """
    Calculate portfolio risk metrics.
    
    Returns:
    - Annualized return
    - Annualized volatility
    - Sharpe ratio
    - Max drawdown
    - Win rate
    """
    import numpy as np
    
    returns = np.array(req.daily_returns)
    
    if len(returns) < 2:
        return error_response(ErrorCode.BAD_REQUEST, "Need at least 2 return values")
    
    # Annualization factor
    ann_factor = req.annual_periods
    
    # Calculate metrics
    mean_return = np.mean(returns)
    std_return = np.std(returns, ddof=1)
    
    ann_return = mean_return * ann_factor
    ann_volatility = std_return * np.sqrt(ann_factor)
    sharpe_ratio = ann_return / ann_volatility if ann_volatility > 0 else 0
    
    # Max drawdown
    cumulative = np.cumprod(1 + returns)
    running_max = np.maximum.accumulate(cumulative)
    drawdowns = (cumulative - running_max) / running_max
    max_drawdown = np.min(drawdowns)
    
    # Win rate
    win_rate = np.sum(returns > 0) / len(returns) * 100
    
    return success_response({
        "annualized_return": round(ann_return * 100, 2),
        "annualized_volatility": round(ann_volatility * 100, 2),
        "sharpe_ratio": round(sharpe_ratio, 3),
        "max_drawdown": round(max_drawdown * 100, 2),
        "win_rate": round(win_rate, 1),
        "total_trades": len(returns),
        "freq": req.freq,
    })


@router.get("/methods")
async def list_optimization_methods():
    """List available portfolio optimization methods."""
    return success_response({
        "methods": [
            {
                "id": "gmv",
                "name": "Global Minimum Variance",
                "description": "Minimize portfolio variance without considering returns",
                "best_for": "Risk-averse investors in volatile markets",
            },
            {
                "id": "mvo",
                "name": "Mean-Variance Optimization",
                "description": "Balance expected return vs risk using risk aversion parameter",
                "best_for": "Investors seeking optimal risk-return tradeoff",
            },
            {
                "id": "rp",
                "name": "Risk Parity",
                "description": "Equal risk contribution from each asset",
                "best_for": "Diversified portfolios with balanced risk",
            },
            {
                "id": "inv",
                "name": "Inverse Volatility",
                "description": "Weight inversely proportional to volatility",
                "best_for": "Simple risk-adjusted allocation",
            },
        ],
        "factors": [
            {"id": "momentum", "name": "动量因子", "description": "过去12个月收益率（排除最近1个月）"},
            {"id": "value", "name": "价值因子", "description": "价格水平的倒数"},
            {"id": "quality", "name": "质量因子", "description": "收益稳定性"},
            {"id": "size", "name": "规模因子", "description": "市值规模"},
            {"id": "volatility", "name": "波动率因子", "description": "20日收益波动率"},
        ],
    })
