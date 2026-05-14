"""
Strategy API - Strategy CRUD, backtest and optimization
"""
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from app.middleware import require_api_key
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/strategy", tags=["strategy"])

USE_DB_PERSISTENCE = True


class BacktestRequest(BaseModel):
    code: str
    symbol: str
    start_date: str
    end_date: str
    initial_capital: float = Field(default=100000.0, gt=0)
    commission: float = Field(default=0.001, ge=0, le=0.1)
    slippage: float = Field(default=0.001, ge=0, le=0.1)

    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError(f'Invalid date format: {v}, expected YYYY-MM-DD')


class OptimizeRequest(BaseModel):
    code: str
    symbol: str
    start_date: str
    end_date: str
    initial_capital: float = Field(default=100000.0, gt=0)
    param_grid: Dict[str, List[Any]]
    metric: str = "sharpe_ratio"

    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError(f'Invalid date format: {v}, expected YYYY-MM-DD')


class StrategyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    code: str = Field(..., max_length=50000)
    market: str = Field(default="AStock", pattern="^(AStock|HKStock|USStock|Crypto|Forex|Futures)$")
    parameters: Dict[str, Any] = {}
    stop_loss_pct: float = Field(default=2.0, ge=0, le=100)
    take_profit_pct: float = Field(default=6.0, ge=0, le=100)


class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    code: Optional[str] = None
    market: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None


class CodeValidateRequest(BaseModel):
    code: str


class CodeValidateResponse(BaseModel):
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    security_score: int = 100


@router.post("/validate")
async def validate_strategy_code(request: CodeValidateRequest):
    """
    Validate strategy code without executing it.
    
    Performs comprehensive security validation including:
    - AST-based security analysis
    - Forbidden import detection
    - Dangerous function call detection
    - Infinite loop detection
    - Memory bomb detection
    
    Returns validation result without executing the code.
    """
    try:
        from app.services.strategy.ast_validator import get_security_report
        
        report = get_security_report(request.code)
        
        security_score = 100
        if report.violations:
            security_score = max(0, 100 - len(report.violations) * 20)
        if report.warnings:
            security_score = max(0, security_score - len(report.warnings) * 5)
        
        return CodeValidateResponse(
            is_valid=report.is_valid,
            errors=[str(v) for v in report.violations],
            warnings=[str(w) for w in report.warnings],
            security_score=security_score,
        )
    except Exception as e:
        logger.error(f"[Strategy] Validation error: {e}")
        return CodeValidateResponse(
            is_valid=False,
            errors=[f"Validation failed: {str(e)}"],
            warnings=[],
            security_score=0,
        )


def _get_history_data(symbol: str, start_date: str, end_date: str) -> Optional[Dict]:
    """获取历史数据"""
    try:
        db_symbol = symbol.replace("sh", "").replace("sz", "")
        conn = None
        try:
            from app.db.database import _get_conn
            conn = _get_conn()
            rows = conn.execute("""
                SELECT date, open, high, low, close, volume
                FROM market_data_daily
                WHERE symbol = ? AND date >= ? AND date <= ?
                ORDER BY date ASC
            """, (db_symbol, start_date, end_date)).fetchall()

            if len(rows) == 0:
                return None

            import pandas as pd
            df = pd.DataFrame({
                "open": [float(r[1]) for r in rows],
                "high": [float(r[2]) for r in rows],
                "low": [float(r[3]) for r in rows],
                "close": [float(r[4]) for r in rows],
                "volume": [float(r[5]) for r in rows],
            }, index=pd.to_datetime([r[0] for r in rows]))

            return df
        finally:
            if conn:
                conn.close()
    except Exception as e:
        logger.warning(f"[Strategy] Failed to get history: {e}")
        return None


def _simulate_trades(df, signals, initial_capital=100000.0, commission=0.001):
    """模拟交易"""
    capital = initial_capital
    position = 0
    entry_price = 0.0
    trades = []

    for i in range(1, len(df)):
        signal = signals.iloc[i] if hasattr(signals, 'iloc') else signals[i]
        close = df.iloc[i]["close"]

        if signal == 1 and position == 0 and capital > 0:
            shares = int(capital * 0.9 / close)
            if shares > 0:
                position = shares
                entry_price = close
                capital -= shares * entry_price * (1 + commission)
                trades.append({
                    "type": "BUY",
                    "price": entry_price,
                    "shares": shares,
                    "index": i,
                })

        elif signal == -1 and position > 0:
            proceeds = position * close * (1 - commission)
            pnl = proceeds - position * entry_price
            capital += proceeds
            trades.append({
                "type": "SELL",
                "price": close,
                "shares": position,
                "pnl": pnl,
                "index": i,
            })
            position = 0

    final_value = capital + position * df.iloc[-1]["close"] if position > 0 else capital
    return {
        "final_value": final_value,
        "total_return": (final_value - initial_capital) / initial_capital,
        "trades": trades,
    }


@router.post("/backtest")
async def run_backtest(request: BacktestRequest, _: None = Depends(require_api_key)):
    """运行策略回测"""
    try:
        from app.services.strategy import (
            create_indicator_strategy,
            StrategyValidator,
            detect_regime,
            analyze_backtest_result,
        )

        is_valid, error = StrategyValidator.validate(request.code)
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"策略代码验证失败: {error}")

        strategy = create_indicator_strategy(request.code)

        df = _get_history_data(request.symbol, request.start_date, request.end_date)
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"未找到数据: {request.symbol}")

        signals = strategy.to_signal_df(df)
        signal_values = signals["signal"]

        result = _simulate_trades(df, signal_values, request.initial_capital, request.commission)

        import pandas as pd
        equity = [1.0]
        position = 0
        for i in range(1, len(df)):
            sig = signal_values.iloc[i] if hasattr(signal_values, 'iloc') else signal_values[i]
            if position == 0 and sig == 1:
                position = 1
            elif position > 0 and sig == -1:
                position = 0
            ret = (df.iloc[i]["close"] / df.iloc[i-1]["close"] - 1) if position else 0
            equity.append(equity[-1] * (1 + ret))

        equity_series = pd.Series(equity, index=df.index)
        perf = analyze_backtest_result(equity_series, result["trades"])

        regime = detect_regime(df)

        return {
            "code": 0,
            "data": {
                **perf,
                "regime": {
                    "regime": regime.regime.value,
                    "confidence": regime.confidence,
                    "indicators": regime.indicators,
                },
                "trades_count": len(result["trades"]),
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Strategy] Backtest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/optimize")
async def optimize_strategy(request: OptimizeRequest, _: None = Depends(require_api_key)):
    """参数优化"""
    try:
        from app.services.strategy import (
            create_indicator_strategy,
            StrategyValidator,
            quick_optimize,
            OptimizationMethod,
        )

        is_valid, error = StrategyValidator.validate(request.code)
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"策略代码验证失败: {error}")

        strategy = create_indicator_strategy(request.code)

        df = _get_history_data(request.symbol, request.start_date, request.end_date)
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"未找到数据: {request.symbol}")

        method = OptimizationMethod.GRID

        report = quick_optimize(
            strategy_code=request.code,
            data=df,
            parameter_space=request.param_grid,
            metric=request.metric,
            method=method,
        )

        return {
            "code": 0,
            "data": {
                "total_variants": report.total_variants,
                "successful_variants": report.successful_variants,
                "best_score": report.best_score,
                "best_params": report.best_params,
                "optimization_time_seconds": report.optimization_time_seconds,
                "ranking": [
                    {
                        "rank": r.rank,
                        "params": r.params,
                        "score": r.score,
                        "metrics": r.metrics,
                    }
                    for r in report.all_results[:10]
                ],
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Strategy] Optimize error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates")
async def list_templates():
    """获取内置策略模板"""
    from app.services.strategy import EXAMPLE_STRATEGIES
    return {
        "code": 0,
        "data": {
            "templates": list(EXAMPLE_STRATEGIES.keys())
        }
    }


# ── Strategy CRUD Endpoints ───────────────────────────────────────────────────

@router.get("/strategies")
async def list_strategies():
    """获取所有策略列表"""
    if USE_DB_PERSISTENCE:
        from app.db.strategy_db import list_strategies as db_list, count_strategies
        strategies = db_list()
        total = count_strategies()
        result = []
        for s in strategies:
            result.append({
                "id": s.get("id", ""),
                "name": s.get("name", ""),
                "description": s.get("description", ""),
                "market": s.get("market", "AStock"),
                "created_at": s.get("created_at", ""),
                "updated_at": s.get("updated_at", ""),
            })
        return {"code": 0, "data": {"strategies": result, "total": total}}
    else:
        strategies = []
        for sid, data in _strategies_db.items():
            strategies.append({
                "id": sid,
                "name": data.get("name", ""),
                "description": data.get("description", ""),
                "market": data.get("market", "AStock"),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
            })
        return {"code": 0, "data": {"strategies": strategies, "total": len(strategies)}}


@router.post("/strategies")
async def create_strategy(request: StrategyCreate, _: None = Depends(require_api_key)):
    """创建新策略"""
    from app.services.strategy import StrategyValidator
    
    is_valid, error = StrategyValidator.validate(request.code)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"策略代码验证失败: {error}")
    
    strategy_id = str(uuid.uuid4())
    
    if USE_DB_PERSISTENCE:
        from app.db.strategy_db import create_strategy as db_create
        try:
            db_create(
                strategy_id=strategy_id,
                name=request.name,
                description=request.description,
                code=request.code,
                market=request.market,
                parameters=request.parameters,
                stop_loss_pct=request.stop_loss_pct,
                take_profit_pct=request.take_profit_pct,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        now = datetime.now().isoformat()
        _strategies_db[strategy_id] = {
            "id": strategy_id,
            "name": request.name,
            "description": request.description,
            "code": request.code,
            "market": request.market,
            "parameters": request.parameters,
            "stop_loss_pct": request.stop_loss_pct,
            "take_profit_pct": request.take_profit_pct,
            "created_at": now,
            "updated_at": now,
        }
    
    return {
        "code": 0,
        "message": "策略创建成功",
        "data": {"id": strategy_id}
    }


@router.get("/strategies/{strategy_id}")
async def get_strategy(strategy_id: str):
    """获取策略详情"""
    if USE_DB_PERSISTENCE:
        from app.db.strategy_db import get_strategy as db_get
        strategy = db_get(strategy_id)
        if strategy is None:
            raise HTTPException(status_code=404, detail="策略不存在")
        return {"code": 0, "data": strategy}
    else:
        if strategy_id not in _strategies_db:
            raise HTTPException(status_code=404, detail="策略不存在")
        return {"code": 0, "data": _strategies_db[strategy_id]}


@router.put("/strategies/{strategy_id}")
async def update_strategy(strategy_id: str, request: StrategyUpdate, _: None = Depends(require_api_key)):
    """更新策略"""
    if USE_DB_PERSISTENCE:
        from app.db.strategy_db import update_strategy as db_update, get_strategy as db_get
        
        if request.code is not None:
            from app.services.strategy import StrategyValidator
            is_valid, error = StrategyValidator.validate(request.code)
            if not is_valid:
                raise HTTPException(status_code=400, detail=f"策略代码验证失败: {error}")
        
        updated = db_update(
            strategy_id=strategy_id,
            name=request.name,
            description=request.description,
            code=request.code,
            market=request.market,
            parameters=request.parameters,
            stop_loss_pct=request.stop_loss_pct,
            take_profit_pct=request.take_profit_pct,
        )
        
        if updated is None:
            raise HTTPException(status_code=404, detail="策略不存在")
        
        return {
            "code": 0,
            "message": "策略更新成功",
            "data": {"id": strategy_id}
        }
    else:
        if strategy_id not in _strategies_db:
            raise HTTPException(status_code=404, detail="策略不存在")
        
        data = _strategies_db[strategy_id]
        
        if request.name is not None:
            data["name"] = request.name
        if request.description is not None:
            data["description"] = request.description
        if request.code is not None:
            from app.services.strategy import StrategyValidator
            is_valid, error = StrategyValidator.validate(request.code)
            if not is_valid:
                raise HTTPException(status_code=400, detail=f"策略代码验证失败: {error}")
            data["code"] = request.code
        if request.market is not None:
            data["market"] = request.market
        if request.parameters is not None:
            data["parameters"] = request.parameters
        if request.stop_loss_pct is not None:
            data["stop_loss_pct"] = request.stop_loss_pct
        if request.take_profit_pct is not None:
            data["take_profit_pct"] = request.take_profit_pct
        
        data["updated_at"] = datetime.now().isoformat()
        
        return {
            "code": 0,
            "message": "策略更新成功",
            "data": {"id": strategy_id}
        }


@router.delete("/strategies/{strategy_id}")
async def delete_strategy(strategy_id: str, _: None = Depends(require_api_key)):
    """删除策略"""
    if USE_DB_PERSISTENCE:
        from app.db.strategy_db import delete_strategy as db_delete
        success = db_delete(strategy_id, soft_delete=True)
        if not success:
            raise HTTPException(status_code=404, detail="策略不存在")
    else:
        if strategy_id not in _strategies_db:
            raise HTTPException(status_code=404, detail="策略不存在")
        del _strategies_db[strategy_id]
    
    return {
        "code": 0,
        "message": "策略删除成功"
    }


@router.post("/strategies/{strategy_id}/backtest")
async def backtest_saved_strategy(strategy_id: str, request: BacktestRequest, _: None = Depends(require_api_key)):
    """运行已保存策略的回测"""
    if USE_DB_PERSISTENCE:
        from app.db.strategy_db import get_strategy as db_get
        strategy_data = db_get(strategy_id)
        if strategy_data is None:
            raise HTTPException(status_code=404, detail="策略不存在")
        request.code = strategy_data["code"]
    else:
        if strategy_id not in _strategies_db:
            raise HTTPException(status_code=404, detail="策略不存在")
        strategy_data = _strategies_db[strategy_id]
        request.code = strategy_data["code"]

    return await run_backtest(request)
