"""
Strategy API - Strategy CRUD, backtest and optimization
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from app.middleware import require_api_key
from pydantic import BaseModel, Field, field_validator
from app.utils.error_decorator import handle_errors
from app.utils.error_sanitizer import sanitize_error
from app.utils.executor import get_executor
from app.utils.errors import ErrorCode, error_response

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

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError(f"Invalid date format: {v}, expected YYYY-MM-DD")


class OptimizeRequest(BaseModel):
    code: str
    symbol: str
    start_date: str
    end_date: str
    initial_capital: float = Field(default=100000.0, gt=0)
    param_grid: Dict[str, List[Any]]
    metric: str = "sharpe_ratio"

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError(f"Invalid date format: {v}, expected YYYY-MM-DD")


class StrategyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    code: str = Field(..., max_length=50000)
    market: str = Field(
        default="AStock", pattern="^(AStock|HKStock|USStock|Crypto|Forex|Futures)$"
    )
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


class StrategyASTCondition(BaseModel):
    type: str
    indicator: str
    params: Dict[str, Any] = {}
    direction: str = "cross_above"
    threshold: Optional[float] = None
    band: Optional[str] = None
    multiplier: Optional[float] = None


class StrategyASTAction(BaseModel):
    type: str
    quantity: Optional[int] = None
    percent: Optional[int] = None
    signal: Optional[Any] = None


class StrategyAST(BaseModel):
    type: str = "strategy"
    name: str
    description: Optional[str] = ""
    market: str = "AStock"
    conditions: List[StrategyASTCondition]
    actions: List[StrategyASTAction]
    riskManagement: Optional[Dict[str, float]] = None


class CompileRequest(BaseModel):
    ast: StrategyAST


class CompileResponse(BaseModel):
    code: str
    valid: bool
    errors: List[str] = []


class StrategyConditionAST(BaseModel):
    type: str
    indicator: str
    params: Dict[str, Any] = {}
    direction: str
    threshold: Optional[float] = None
    band: Optional[str] = None
    multiplier: Optional[float] = None


class StrategyActionAST(BaseModel):
    type: str
    quantity: Optional[int] = None
    signal: Optional[Any] = None


class StrategyAST(BaseModel):
    type: str = "strategy"
    name: str
    description: Optional[str] = ""
    conditions: List[StrategyConditionAST]
    actions: List[StrategyActionAST]
    riskManagement: Optional[Dict[str, Any]] = None


class CompileResponse(BaseModel):
    code: str
    valid: bool
    errors: List[str] = []


@router.post("/validate")
@handle_errors(module="strategy")
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
        logger.error(f"[Strategy] Validation error: {e}", exc_info=True)
        return CodeValidateResponse(
            is_valid=False,
            errors=[f"Validation failed: {sanitize_error(e)}"],
            warnings=[],
            security_score=0,
        )


def _generate_python_code(ast: StrategyAST) -> str:
    """
    Generate Python DSL code from Strategy AST.

    Supports Top 5 strategies:
    - MA Cross (MA金叉)
    - MACD Cross (MACD金叉)
    - RSI Oversold (RSI超买超卖)
    - Bollinger Bands (布林带突破)
    - Volume Surge (成交量异动)
    """
    lines = []

    # Header annotations
    lines.append(f"# @name {ast.name}")
    if ast.description:
        lines.append(f"# @description {ast.description}")

    # Risk management
    if ast.riskManagement:
        stop_loss = ast.riskManagement.get("stopLossPct", 2.0)
        take_profit = ast.riskManagement.get("takeProfitPct", 6.0)
        lines.append(f"# @strategy stopLossPct {stop_loss}")
        lines.append(f"# @strategy takeProfitPct {take_profit}")

    lines.append("")

    # Generate indicator calculations and signals
    buy_signals = []
    sell_signals = []
    indicators = {}

    for idx, condition in enumerate(ast.conditions):
        cond_var = f"cond_{idx}"

        if condition.indicator == "MA":
            # MA Cross strategy
            fast = condition.params.get("fast_period", 5)
            slow = condition.params.get("slow_period", 20)
            lines.append(f"ma_fast_{idx} = df['close'].rolling({fast}).mean()")
            lines.append(f"ma_slow_{idx} = df['close'].rolling({slow}).mean()")
            indicators[f"ma_fast_{idx}"] = f"ma_fast_{idx}"
            indicators[f"ma_slow_{idx}"] = f"ma_slow_{idx}"

            if condition.direction == "cross_above":
                lines.append(
                    f"{cond_var} = (ma_fast_{idx} > ma_slow_{idx}) & (ma_fast_{idx}.shift(1) <= ma_slow_{idx}.shift(1))"
                )
                buy_signals.append(cond_var)
            elif condition.direction == "cross_below":
                lines.append(
                    f"{cond_var} = (ma_fast_{idx} < ma_slow_{idx}) & (ma_fast_{idx}.shift(1) >= ma_slow_{idx}.shift(1))"
                )
                sell_signals.append(cond_var)

        elif condition.indicator == "MACD":
            # MACD Cross strategy
            fast = condition.params.get("fast_period", 12)
            slow = condition.params.get("slow_period", 26)
            signal = condition.params.get("signal_period", 9)
            lines.append(
                f"ema_fast_{idx} = df['close'].ewm(span={fast}, adjust=False).mean()"
            )
            lines.append(
                f"ema_slow_{idx} = df['close'].ewm(span={slow}, adjust=False).mean()"
            )
            lines.append(f"dif_{idx} = ema_fast_{idx} - ema_slow_{idx}")
            lines.append(
                f"dea_{idx} = dif_{idx}.ewm(span={signal}, adjust=False).mean()"
            )
            lines.append(f"histogram_{idx} = (dif_{idx} - dea_{idx}) * 2")
            indicators[f"dif_{idx}"] = f"dif_{idx}"
            indicators[f"dea_{idx}"] = f"dea_{idx}"
            indicators[f"histogram_{idx}"] = f"histogram_{idx}"

            if condition.direction == "cross_above":
                lines.append(
                    f"{cond_var} = (dif_{idx} > dea_{idx}) & (dif_{idx}.shift(1) <= dea_{idx}.shift(1))"
                )
                buy_signals.append(cond_var)
            elif condition.direction == "cross_below":
                lines.append(
                    f"{cond_var} = (dif_{idx} < dea_{idx}) & (dif_{idx}.shift(1) >= dea_{idx}.shift(1))"
                )
                sell_signals.append(cond_var)

        elif condition.indicator == "RSI":
            # RSI strategy
            period = condition.params.get("period", 14)
            threshold = condition.threshold or 30
            lines.append(f"delta_{idx} = df['close'].diff()")
            lines.append(f"gain_{idx} = delta_{idx}.where(delta_{idx} > 0, 0)")
            lines.append(f"loss_{idx} = -delta_{idx}.where(delta_{idx} < 0, 0)")
            lines.append(f"avg_gain_{idx} = gain_{idx}.rolling(window={period}).mean()")
            lines.append(f"avg_loss_{idx} = loss_{idx}.rolling(window={period}).mean()")
            lines.append(f"rs_{idx} = avg_gain_{idx} / avg_loss_{idx}")
            lines.append(f"rsi_{idx} = 100 - (100 / (1 + rs_{idx}))")
            indicators[f"rsi_{idx}"] = f"rsi_{idx}"

            if condition.direction == "below":
                # RSI < threshold (oversold)
                lines.append(f"{cond_var} = rsi_{idx} < {threshold}")
                buy_signals.append(cond_var)
            elif condition.direction == "above":
                # RSI > threshold (overbought)
                lines.append(f"{cond_var} = rsi_{idx} > {threshold}")
                sell_signals.append(cond_var)

        elif condition.indicator == "BOLL":
            # Bollinger Bands strategy
            period = condition.params.get("period", 20)
            std_dev = condition.params.get("std_dev", 2)
            band = condition.band or "lower"
            lines.append(f"middle_{idx} = df['close'].rolling({period}).mean()")
            lines.append(f"std_{idx} = df['close'].rolling({period}).std()")
            lines.append(f"upper_{idx} = middle_{idx} + {std_dev} * std_{idx}")
            lines.append(f"lower_{idx} = middle_{idx} - {std_dev} * std_{idx}")
            indicators[f"upper_{idx}"] = f"upper_{idx}"
            indicators[f"middle_{idx}"] = f"middle_{idx}"
            indicators[f"lower_{idx}"] = f"lower_{idx}"

            if band == "lower":
                # Price breaks lower band
                lines.append(
                    f"{cond_var} = (df['close'] < lower_{idx}) & (df['close'].shift(1) >= lower_{idx}.shift(1))"
                )
                buy_signals.append(cond_var)
            elif band == "upper":
                # Price breaks upper band
                lines.append(
                    f"{cond_var} = (df['close'] > upper_{idx}) & (df['close'].shift(1) <= upper_{idx}.shift(1))"
                )
                sell_signals.append(cond_var)

        elif condition.indicator == "VOLUME":
            # Volume surge strategy
            period = condition.params.get("period", 20)
            multiplier = condition.multiplier or 2.0
            lines.append(f"avg_vol_{idx} = df['volume'].rolling({period}).mean()")
            lines.append(f"{cond_var} = df['volume'] > avg_vol_{idx} * {multiplier}")
            indicators[f"avg_vol_{idx}"] = f"avg_vol_{idx}"
            buy_signals.append(cond_var)

    lines.append("")

    # Combine signals
    if buy_signals:
        lines.append(f"buy = {' | '.join(buy_signals)}")
    else:
        lines.append("buy = pd.Series(False, index=df.index)")

    if sell_signals:
        lines.append(f"sell = {' | '.join(sell_signals)}")
    else:
        lines.append("sell = pd.Series(False, index=df.index)")

    # Output
    lines.append("")
    lines.append("output = {")
    indicators_str = ", ".join([f"'{k}': {v}" for k, v in indicators.items()])
    lines.append(f"    'indicators': {{{indicators_str}}},")
    lines.append("    'signals': {'buy': buy, 'sell': sell}")
    lines.append("}")

    return "\n".join(lines)


@router.post("/compile")
@handle_errors(module="strategy")
async def compile_strategy(request: CompileRequest):
    """
    Compile Strategy AST to Python DSL code.

    Converts visual strategy builder JSON AST to executable Python code
    that can be used with the backtest engine.

    Supported indicators:
    - MA: Moving Average crossover
    - MACD: MACD crossover
    - RSI: RSI threshold
    - BOLL: Bollinger Bands breakout
    - VOLUME: Volume surge
    """
    try:
        ast = request.ast

        # Validate AST
        if not ast.conditions:
            return {
                "code": 0,
                "data": {
                    "code": "",
                    "valid": False,
                    "errors": ["至少需要一个策略条件"],
                },
            }

        # Generate Python code
        python_code = _generate_python_code(ast)

        # Validate generated code
        from app.services.strategy import StrategyValidator

        is_valid, error = StrategyValidator.validate(python_code)

        if not is_valid:
            return {
                "code": 0,
                "data": {
                    "code": python_code,
                    "valid": False,
                    "errors": [f"生成的代码验证失败: {error}"],
                },
            }

        return {
            "code": 0,
            "data": {
                "code": python_code,
                "valid": True,
                "errors": [],
            },
        }
    except Exception as e:
        logger.error(f"[Strategy] Compile error: {e}", exc_info=True)
        return {
            "code": 0,
            "data": {
                "code": "",
                "valid": False,
                "errors": [f"编译失败: {sanitize_error(e)}"],
            },
        }


def _get_history_data(symbol: str, start_date: str, end_date: str) -> Optional[Dict]:
    """获取历史数据"""
    try:
        db_symbol = symbol.replace("sh", "").replace("sz", "")
        conn = None
        try:
            from app.db.database import _get_conn

            conn = _get_conn()
            rows = conn.execute(
                """
                SELECT date, open, high, low, close, volume
                FROM market_data_daily
                WHERE symbol = ? AND date >= ? AND date <= ?
                ORDER BY date ASC
            """,
                (db_symbol, start_date, end_date),
            ).fetchall()

            if len(rows) == 0:
                return None

            import pandas as pd

            df = pd.DataFrame(
                {
                    "open": [float(r[1]) for r in rows],
                    "high": [float(r[2]) for r in rows],
                    "low": [float(r[3]) for r in rows],
                    "close": [float(r[4]) for r in rows],
                    "volume": [float(r[5]) for r in rows],
                },
                index=pd.to_datetime([r[0] for r in rows]),
            )

            return df
        finally:
            if conn:
                conn.close()
    except Exception as e:
        logger.warning(f"[Strategy] Failed to get history: {e}", exc_info=True)
        return None


def _simulate_trades(df, signals, initial_capital=100000.0, commission=0.001):
    """模拟交易"""
    capital = initial_capital
    position = 0
    entry_price = 0.0
    trades = []

    for i in range(1, len(df)):
        signal = signals.iloc[i] if hasattr(signals, "iloc") else signals[i]
        close = df.iloc[i]["close"]

        if signal == 1 and position == 0 and capital > 0:
            shares = int(capital * 0.9 / close)
            if shares > 0:
                position = shares
                entry_price = close
                capital -= shares * entry_price * (1 + commission)
                trades.append(
                    {
                        "type": "BUY",
                        "price": entry_price,
                        "shares": shares,
                        "index": i,
                    }
                )

        elif signal == -1 and position > 0:
            proceeds = position * close * (1 - commission)
            pnl = proceeds - position * entry_price
            capital += proceeds
            trades.append(
                {
                    "type": "SELL",
                    "price": close,
                    "shares": position,
                    "pnl": pnl,
                    "index": i,
                }
            )
            position = 0

    final_value = capital + position * df.iloc[-1]["close"] if position > 0 else capital
    return {
        "final_value": final_value,
        "total_return": (final_value - initial_capital) / initial_capital,
        "trades": trades,
    }


@router.post("/backtest")
@handle_errors(module="strategy")
async def run_backtest(request: BacktestRequest, _: None = Depends(require_api_key)):
    """运行策略回测"""
    # P0: Add 30s timeout protection
    STRATEGY_TIMEOUT = 30.0
    loop = asyncio.get_running_loop()
    
    try:
        from app.services.strategy import (
            create_indicator_strategy,
            StrategyValidator,
            detect_regime,
            analyze_backtest_result,
        )

        # P0: Timeout validation
        is_valid, error = await asyncio.wait_for(
            loop.run_in_executor(get_executor(), StrategyValidator.validate, request.code),
            timeout=STRATEGY_TIMEOUT
        )
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"策略代码验证失败: {error}")

        strategy = create_indicator_strategy(request.code)

        # P0: Timeout history fetch
        df = await asyncio.wait_for(
            loop.run_in_executor(get_executor(), _get_history_data, request.symbol, request.start_date, request.end_date),
            timeout=STRATEGY_TIMEOUT
        )
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"未找到数据: {request.symbol}")

        signals = strategy.to_signal_df(df)
        signal_values = signals["signal"]

        result = _simulate_trades(
            df, signal_values, request.initial_capital, request.commission
        )

        import pandas as pd

        equity = [1.0]
        position = 0
        for i in range(1, len(df)):
            sig = (
                signal_values.iloc[i]
                if hasattr(signal_values, "iloc")
                else signal_values[i]
            )
            if position == 0 and sig == 1:
                position = 1
            elif position > 0 and sig == -1:
                position = 0
            ret = (df.iloc[i]["close"] / df.iloc[i - 1]["close"] - 1) if position else 0
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
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Strategy] Backtest error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=sanitize_error(e))


@router.post("/optimize")
@handle_errors(module="strategy")
async def optimize_strategy(
    request: OptimizeRequest, _: None = Depends(require_api_key)
):
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
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Strategy] Optimize error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=sanitize_error(e))


@router.get("/templates")
@handle_errors(module="strategy")
async def list_templates():
    """获取内置策略模板"""
    from app.services.strategy import EXAMPLE_STRATEGIES

    return {"code": 0, "data": {"templates": list(EXAMPLE_STRATEGIES.keys())}}


# ── Strategy CRUD Endpoints ───────────────────────────────────────────────────


@router.get("/strategies")
@handle_errors(module="strategy")
async def list_strategies():
    """获取所有策略列表"""
    if USE_DB_PERSISTENCE:
        from app.db.strategy_db import list_strategies as db_list, count_strategies

        strategies = db_list()
        total = count_strategies()
        result = []
        for s in strategies:
            result.append(
                {
                    "id": s.get("id", ""),
                    "name": s.get("name", ""),
                    "description": s.get("description", ""),
                    "market": s.get("market", "AStock"),
                    "created_at": s.get("created_at", ""),
                    "updated_at": s.get("updated_at", ""),
                }
            )
        return {"code": 0, "data": {"strategies": result, "total": total}}
    else:
        strategies = []
        for sid, data in _strategies_db.items():
            strategies.append(
                {
                    "id": sid,
                    "name": data.get("name", ""),
                    "description": data.get("description", ""),
                    "market": data.get("market", "AStock"),
                    "created_at": data.get("created_at", ""),
                    "updated_at": data.get("updated_at", ""),
                }
            )
        return {"code": 0, "data": {"strategies": strategies, "total": len(strategies)}}


@router.post("/strategies")
@handle_errors(module="strategy")
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
            raise HTTPException(status_code=400, detail=sanitize_error(e))
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

    return {"code": 0, "message": "策略创建成功", "data": {"id": strategy_id}}


@router.get("/strategies/{strategy_id}")
@handle_errors(module="strategy")
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
@handle_errors(module="strategy")
async def update_strategy(
    strategy_id: str, request: StrategyUpdate, _: None = Depends(require_api_key)
):
    """更新策略"""
    if USE_DB_PERSISTENCE:
        from app.db.strategy_db import update_strategy as db_update

        if request.code is not None:
            from app.services.strategy import StrategyValidator

            is_valid, error = StrategyValidator.validate(request.code)
            if not is_valid:
                raise HTTPException(
                    status_code=400, detail=f"策略代码验证失败: {error}"
                )

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

        return {"code": 0, "message": "策略更新成功", "data": {"id": strategy_id}}
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
                raise HTTPException(
                    status_code=400, detail=f"策略代码验证失败: {error}"
                )
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

        return {"code": 0, "message": "策略更新成功", "data": {"id": strategy_id}}


@router.delete("/strategies/{strategy_id}")
@handle_errors(module="strategy")
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

    return {"code": 0, "message": "策略删除成功"}


@router.post("/strategies/{strategy_id}/backtest")
@handle_errors(module="strategy")
async def backtest_saved_strategy(
    strategy_id: str, request: BacktestRequest, _: None = Depends(require_api_key)
):
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
