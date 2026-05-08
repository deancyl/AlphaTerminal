"""
回测引擎 API
"""
import json
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.db.database import _get_conn, _db_path

logger = logging.getLogger(__name__)

router = APIRouter()

# ── 安全限制 ─────────────────────────────────────────────────────────
MAX_PARAMS_DEPTH = 5      # JSON 最大嵌套深度
MAX_PARAMS_KEYS = 50      # 最大键数量
MAX_PARAMS_SIZE = 10000   # 最大 JSON 字符串长度


def _validate_params_depth(obj, current_depth=0):
    """递归检查 JSON 深度，防止深层嵌套 DoS"""
    if current_depth > MAX_PARAMS_DEPTH:
        raise HTTPException(400, f"params 嵌套深度超过限制 ({MAX_PARAMS_DEPTH})")
    if isinstance(obj, dict):
        for v in obj.values():
            _validate_params_depth(v, current_depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            _validate_params_depth(item, current_depth + 1)


def _count_keys(obj, count=0):
    """递归计算 JSON 对象中的键数量"""
    if isinstance(obj, dict):
        count += len(obj)
        for v in obj.values():
            count = _count_keys(v, count)
    elif isinstance(obj, list):
        for item in obj:
            count = _count_keys(item, count)
    return count


def _validate_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """验证 params JSON 复杂度，防止 DoS 攻击"""
    if params is None:
        return {}
    
    # 检查序列化后大小
    json_str = json.dumps(params)
    if len(json_str) > MAX_PARAMS_SIZE:
        raise HTTPException(400, f"params JSON 大小超过限制 ({MAX_PARAMS_SIZE} 字节)")
    
    # 检查键数量
    if _count_keys(params) > MAX_PARAMS_KEYS:
        raise HTTPException(400, f"params 键数量超过限制 ({MAX_PARAMS_KEYS})")
    
    # 检查嵌套深度
    _validate_params_depth(params)
    
    return params


def _extract_strategy_params(strategy_type: str, raw_params: Dict[str, Any]) -> tuple:
    """根据策略类型提取参数，返回 (fast_ma, slow_ma)"""
    defaults = {
        "ma_crossover": ("fast_ma", 5, "slow_ma", 20),
        "rsi_oversold": ("rsi_period", 14, "rsi_buy", 30),
        "bollinger_bands": ("bb_period", 20, "bb_std", 2),
    }
    if strategy_type in defaults:
        k1, v1, k2, v2 = defaults[strategy_type]
        return raw_params.get(k1, v1), raw_params.get(k2, v2)
    return raw_params.get("fast_ma", 5), raw_params.get("slow_ma", 20)


def _validate_dates(start_date: str, end_date: str) -> tuple:
    """验证日期范围，返回 (is_valid, error_message, days_span)"""
    from datetime import datetime as dt
    MAX_YEARS = 10
    try:
        start = dt.strptime(start_date, "%Y-%m-%d")
        end = dt.strptime(end_date, "%Y-%m-%d")
        days_span = (end - start).days
        if days_span < 0:
            return False, "start_date 不能晚于 end_date", 0
        if days_span > MAX_YEARS * 365:
            return False, f"时间跨度不能超过 {MAX_YEARS} 年（约 {MAX_YEARS*365} 天），当前跨度 {days_span} 天", days_span
        return True, "", days_span
    except ValueError:
        return False, "日期格式错误，请使用 YYYY-MM-DD", 0


def _validate_capital(initial_capital: float) -> tuple:
    """验证初始资金，返回 (is_valid, error_message, capital)"""
    MIN_CAPITAL = 100.0
    MAX_CAPITAL = 1e9
    try:
        capital = float(initial_capital)
        if not (MIN_CAPITAL <= capital <= MAX_CAPITAL):
            return False, f"initial_capital 必须介于 {MIN_CAPITAL} ~ {MAX_CAPITAL}，当前 {capital}", 0.0
        return True, "", capital
    except (TypeError, ValueError):
        return False, f"initial_capital 必须是有效数字，当前 {initial_capital}", 0.0


def _calc_ma(data, period):
    """计算移动平均线"""
    return [None] * (period - 1) + [
        round(sum(data[i-period+1:i+1]) / period, 2) for i in range(period - 1, len(data))
    ]


def _calc_rsi(closes, period=14):
    """计算 RSI 指标"""
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    
    if sum(losses[:period]) == 0:
        return [50.0] * len(closes)
    
    ag = sum(gains[:period]) / period
    al = sum(losses[:period]) / period
    rs = ag / al if al != 0 else 0
    
    avg_gain = [None] * period + [100 - 100/(1+rs)]
    avg_loss = [None] * period + [0]
    
    for i in range(period, len(gains)):
        ag = (ag*(period-1) + gains[i]) / period
        al = (al*(period-1) + losses[i]) / period
        rs = ag / al if al != 0 else 0
        avg_gain.append(100 - 100/(1+rs) if al != 0 else 50.0)
        avg_loss.append(0)
    
    return avg_gain + [None] * (len(closes) - len(avg_gain))


def _calc_bollinger(closes, period=20, multiplier=2):
    """计算布林带指标"""
    mid = _calc_ma(closes, period)
    upper, lower = [None] * len(closes), [None] * len(closes)
    for i in range(period - 1, len(closes)):
        if mid[i] is not None:
            std = (sum((closes[j] - mid[i])**2 for j in range(i-period+1, i+1)) / period) ** 0.5
            upper[i] = round(mid[i] + multiplier * std, 2)
            lower[i] = round(mid[i] - multiplier * std, 2)
    return mid, upper, lower


def _generate_signals(strategy_type: str, closes: list, raw_params: dict) -> list:
    """根据策略类型生成交易信号"""
    signals = [0] * len(closes)
    
    if strategy_type == "ma_crossover":
        fast_ma = raw_params.get("fast_ma", 5)
        slow_ma = raw_params.get("slow_ma", 20)
        fast_ma_vals = _calc_ma(closes, fast_ma)
        slow_ma_vals = _calc_ma(closes, slow_ma)
        for i in range(slow_ma, len(closes)):
            if fast_ma_vals[i] is None:
                continue
            if fast_ma_vals[i] > slow_ma_vals[i] and fast_ma_vals[i-1] <= slow_ma_vals[i-1]:
                signals[i] = 1
            elif fast_ma_vals[i] < slow_ma_vals[i] and fast_ma_vals[i-1] >= slow_ma_vals[i-1]:
                signals[i] = -1
    
    elif strategy_type == "rsi_oversold":
        rsi_period = raw_params.get("rsi_period", 14)
        rsi_buy = raw_params.get("rsi_buy", 30)
        rsi_sell = raw_params.get("rsi_sell", 70)
        rsi_vals = _calc_rsi(closes, rsi_period)
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
        mid, upper, lower = _calc_bollinger(closes, 20, 2)
        for i in range(1, len(closes)):
            if lower[i] is None:
                continue
            if closes[i-1] <= lower[i-1] and closes[i] > lower[i]:
                signals[i] = 1
            elif closes[i-1] >= upper[i-1] and closes[i] < upper[i]:
                signals[i] = -1
    
    return signals


def _simulate_trades(signals: list, closes: list, rows: list, initial_capital: float) -> tuple:
    """模拟交易，返回 (trades, wins, losses, final_capital)"""
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
                    "entry_date": rows[i][0],
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
                "exit_date": rows[i][0],
                "exit_price": round(exit_price, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round((exit_price - entry_price) / entry_price * 100, 2)
            })
            position = 0
    
    # 平仓剩余持仓
    if position > 0:
        exit_price = closes[-1]
        pnl = (exit_price - entry_price) * position
        if pnl > 0:
            wins += 1
        else:
            losses += 1
        capital += position * exit_price
        trades[-1].update({
            "exit_date": rows[-1][0],
            "exit_price": round(exit_price, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round((exit_price - entry_price) / entry_price * 100, 2)
        })
    
    return trades, wins, losses, capital


def _calculate_metrics(trades: list, wins: int, losses: int, final_capital: float, 
                       initial_capital: float, row_count: int, benchmark_return_pct: float) -> dict:
    """计算回测统计指标"""
    total_return = final_capital - float(initial_capital)
    total_return_pct = round(total_return / float(initial_capital) * 100, 2)
    total_trades = wins + losses
    win_rate = round(wins / total_trades * 100, 2) if total_trades > 0 else 0
    
    # 计算权益曲线和最大回撤
    equity = float(initial_capital)
    peak = equity
    max_drawdown = 0.0
    equity_curve = []
    
    for t in trades:
        equity += t["pnl"]
        equity_curve.append({
            "date": t.get("exit_date", t.get("entry_date")),
            "value": round(equity, 2)
        })
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_drawdown:
            max_drawdown = dd
    
    # 计算年化收益
    years = row_count / 252
    annualized_return = (final_capital / float(initial_capital)) ** (1 / years) - 1 if years > 0 else 0
    
    # 计算夏普比率
    sharpe_ratio = 0
    if len(equity_curve) >= 2:
        returns = []
        for i in range(1, len(equity_curve)):
            prev_val = equity_curve[i-1]["value"]
            curr_val = equity_curve[i]["value"]
            if prev_val > 0:
                ret = (curr_val - prev_val) / prev_val
                returns.append(ret)
        if returns:
            import statistics
            daily_vol = statistics.stdev(returns) if len(returns) > 1 else 0
            annualized_vol = daily_vol * (252 ** 0.5)
            sharpe_ratio = round(annualized_return / annualized_vol, 2) if annualized_vol > 0 else 0
    
    return {
        "total_return": round(total_return, 2),
        "total_return_pct": total_return_pct,
        "win_rate": round(win_rate, 2),
        "max_drawdown": round(max_drawdown, 2),
        "max_drawdown_pct": round((max_drawdown / initial_capital) * 100, 2),
        "sharpe_ratio": sharpe_ratio,
        "annualized_return_pct": round(annualized_return * 100, 2),
        "wins": wins,
        "losses": losses,
        "total_trades": total_trades,
        "equity_curve": equity_curve,
        "benchmark_return_pct": benchmark_return_pct
    }


class BacktestRequest(BaseModel):
    symbol: str
    period: str = "daily"
    start_date: str
    end_date: str
    initial_capital: float = 100000
    strategy_type: str = "ma_crossover"
    params: Optional[Dict[str, Any]] = None


class StrategyCreateRequest(BaseModel):
    name: str
    description: str = ""
    strategy_type: str = "ma_crossover"
    params: Dict[str, Any] = {}


# ═══════════════════════════════════════════════════════════════
# 策略管理
# ═══════════════════════════════════════════════════════════════

@router.get("/strategies")
async def get_strategies():
    """获取所有回测策略"""
    conn = _get_conn()
    try:
        # 检查表是否存在
        table_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='backtest_strategies'"
        ).fetchone()
        
        if not table_exists:
            return {"code": 0, "data": {"strategies": []}}
        
        rows = conn.execute("""
            SELECT id, name, description, type, params, created_at, updated_at
            FROM backtest_strategies ORDER BY created_at DESC
        """).fetchall()
        
        strategies = []
        for r in rows:
            strategies.append({
                "id": r[0],
                "name": r[1],
                "description": r[2],
                "type": r[3],
                "params": json.loads(r[4]) if r[4] else {},
                "created_at": r[5],
                "updated_at": r[6]
            })
        
        return {"code": 0, "data": {"strategies": strategies}}
    except Exception as e:
        logger.error(f"[Backtest] 获取策略列表失败: {e}")
        return {"code": 0, "data": {"strategies": []}}
    finally:
        conn.close()


@router.post("/strategies")
async def create_strategy(req: StrategyCreateRequest):
    """创建新策略"""
    # 验证 params 复杂度
    params = _validate_params(req.params)
    
    conn = _get_conn()
    try:
        now = datetime.now().isoformat()
        conn.execute("""
            INSERT INTO backtest_strategies (name, description, type, params, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (req.name, req.description, req.strategy_type, 
              json.dumps(params), now, now))
        conn.commit()
        
        strategy_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        
        return {"code": 0, "data": {"id": strategy_id, "message": "Strategy created"}}
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# 回测执行
# ═══════════════════════════════════════════════════════════════

@router.post("/run")
async def run_backtest(req: BacktestRequest):
    """执行回测"""
    # ── 第一步：入参解析与校验 ───────────────────────────────────
    db_symbol = req.symbol.replace("sh", "").replace("sz", "")
    strategy_type = req.strategy_type or "ma_crossover"
    raw_params = _validate_params(req.params)
    fast_ma, slow_ma = _extract_strategy_params(strategy_type, raw_params)
    
    # 日期校验
    dates_valid, dates_error, _ = _validate_dates(req.start_date, req.end_date)
    if not dates_valid:
        return {"code": 1, "message": dates_error}
    
    # 资金校验
    capital_valid, capital_error, initial_capital = _validate_capital(req.initial_capital)
    if not capital_valid:
        return {"code": 1, "message": capital_error}
    
    # ── 第二步：获取历史数据 ──────────────────────────────────────
    conn = _get_conn()
    try:
        rows = conn.execute("""
            SELECT date, open, high, low, close, volume
            FROM market_data_daily
            WHERE symbol = ? AND date >= ? AND date <= ?
            ORDER BY date ASC
        """, (db_symbol, req.start_date, req.end_date)).fetchall()
        
        if len(rows) == 0:
            return {"code": 1, "message": f"本地数据库无 {req.symbol} 在此时段的日K数据，请先通过行情模块或脚本源回填历史数据。"}
        if len(rows) < slow_ma:
            return {"code": 1, "message": f"数据条数({len(rows)})不足以计算慢线({slow_ma}周期)，请扩大回测窗口。"}
        
        # ── 基准收益率 ────────────────────────────────────────────
        first_close = float(rows[0][4])
        last_close = float(rows[-1][4])
        benchmark_return_pct = 0.0 if first_close <= 0 else round(
            (last_close - first_close) / first_close * 100, 2
        )
        
        # ── 提取价格序列 ──────────────────────────────────────────
        closes = [float(r[4]) for r in rows]
        
        # ── 策略信号生成 ──────────────────────────────────────────
        signals = _generate_signals(strategy_type, closes, raw_params)
        
        # ── 模拟交易 ──────────────────────────────────────────────
        trades, wins, losses, final_capital = _simulate_trades(
            signals, closes, rows, initial_capital
        )
        
        # ── 统计指标 ──────────────────────────────────────────────
        metrics = _calculate_metrics(
            trades, wins, losses, final_capital,
            initial_capital, len(rows), benchmark_return_pct
        )
        
        # ── 保存到数据库 ──────────────────────────────────────────
        try:
            conn.execute("""
                INSERT INTO backtest_results 
                (strategy_id, portfolio_id, start_date, end_date, 
                 initial_capital, final_capital, total_return, annual_return,
                 sharpe_ratio, max_drawdown, win_rate, trades_count, details, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                None, None,
                req.start_date, req.end_date,
                initial_capital,
                round(final_capital, 2),
                metrics["total_return_pct"],
                metrics["annualized_return_pct"],
                metrics["sharpe_ratio"],
                metrics["max_drawdown_pct"],
                metrics["win_rate"],
                metrics["total_trades"],
                json.dumps({
                    "symbol": req.symbol,
                    "trades": trades,
                    "equity_curve": metrics["equity_curve"],
                    "strategy_type": strategy_type,
                    "wins": wins,
                    "losses": losses,
                    "benchmark_return_pct": benchmark_return_pct
                }),
                datetime.now().isoformat()
            ))
            conn.commit()
        except Exception as e:
            logger.warning(f"[Backtest] 保存结果到数据库失败: {e}")
        
        # ── 返回结果 ──────────────────────────────────────────────
        return {
            "code": 0,
            "data": {
                "symbol": req.symbol,
                "start_date": req.start_date,
                "end_date": req.end_date,
                "initial_capital": initial_capital,
                "final_capital": round(final_capital, 2),
                "total_return": metrics["total_return"],
                "total_return_pct": metrics["total_return_pct"],
                "max_drawdown": metrics["max_drawdown"],
                "max_drawdown_pct": metrics["max_drawdown_pct"],
                "wins": wins,
                "losses": losses,
                "win_rate": metrics["win_rate"],
                "trades_count": metrics["total_trades"],
                "sharpe_ratio": metrics["sharpe_ratio"],
                "annualized_return_pct": metrics["annualized_return_pct"],
                "benchmark_return_pct": benchmark_return_pct,
                "strategy_type": strategy_type,
                "trades": trades,
                "equity_curve": metrics["equity_curve"],
            }
        }
    finally:
        conn.close()


@router.get("/results")
async def get_backtest_results(limit: int = 10):
    """获取回测结果"""
    conn = _get_conn()
    try:
        rows = conn.execute("""
            SELECT id, strategy_id, portfolio_id, start_date, end_date, 
                   initial_capital, final_capital, total_return, 
                   max_drawdown, win_rate, trades_count, created_at
            FROM backtest_results ORDER BY created_at DESC LIMIT ?
        """, (limit,)).fetchall()
        
        results = []
        for r in rows:
            results.append({
                "id": r[0],
                "strategy_id": r[1],
                "portfolio_id": r[2],
                "start_date": r[3],
                "end_date": r[4],
                "initial_capital": r[5],
                "final_capital": r[6],
                "total_return": r[7],
                "max_drawdown": r[8],
                "win_rate": r[9],
                "trades_count": r[10],
                "created_at": r[11]
            })
        
        return {"code": 0, "data": {"results": results}}
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# Walk-Forward Analysis
# ═══════════════════════════════════════════════════════════════

class WalkForwardRequest(BaseModel):
    symbol: str
    start_date: str
    end_date: str
    strategy_type: str = "ma_crossover"
    initial_capital: float = 100000
    train_window_days: int = 252
    test_window_days: int = 63
    step_days: int = 63
    mode: str = "rolling"
    param_grid: Optional[Dict[str, List[Any]]] = None


@router.post("/walkforward/analyze")
async def walkforward_analyze(req: WalkForwardRequest):
    """Walk-Forward Analysis for out-of-sample validation"""
    from app.services.backtest.walk_forward import WalkForwardAnalyzer
    
    db_symbol = req.symbol.replace("sh", "").replace("sz", "")
    
    dates_valid, dates_error, _ = _validate_dates(req.start_date, req.end_date)
    if not dates_valid:
        return {"code": 1, "message": dates_error}
    
    capital_valid, capital_error, initial_capital = _validate_capital(req.initial_capital)
    if not capital_valid:
        return {"code": 1, "message": capital_error}
    
    conn = _get_conn()
    try:
        rows = conn.execute("""
            SELECT date, open, high, low, close, volume
            FROM market_data_daily
            WHERE symbol = ? AND date >= ? AND date <= ?
            ORDER BY date ASC
        """, (db_symbol, req.start_date, req.end_date)).fetchall()
        
        if len(rows) < 126:
            return {"code": 1, "message": f"数据不足({len(rows)}天)，Walk-Forward需要至少6个月数据"}
        
        data = [{"date": r[0], "close": float(r[4])} for r in rows]
        
        default_param_grid = {
            "ma_crossover": {
                "fast_ma": [5, 10, 15],
                "slow_ma": [20, 30, 60]
            },
            "rsi_oversold": {
                "rsi_period": [7, 14, 21],
                "rsi_buy": [25, 30, 35],
                "rsi_sell": [65, 70, 75]
            },
            "bollinger_bands": {
                "bb_period": [15, 20, 25],
                "bb_std": [1.5, 2.0, 2.5]
            }
        }
        
        param_grid = req.param_grid or default_param_grid.get(req.strategy_type, {})
        
        analyzer = WalkForwardAnalyzer(
            train_window_days=req.train_window_days,
            test_window_days=req.test_window_days,
            step_days=req.step_days,
            mode=req.mode
        )
        
        result = analyzer.analyze(
            data=data,
            strategy_type=req.strategy_type,
            param_grid=param_grid,
            initial_capital=initial_capital,
            symbol=req.symbol
        )
        
        windows_data = []
        for w in result.windows:
            windows_data.append({
                "window_index": w.window_index,
                "train_start": w.train_start,
                "train_end": w.train_end,
                "test_start": w.test_start,
                "test_end": w.test_end,
                "train_return_pct": w.train_return_pct,
                "train_sharpe": w.train_sharpe,
                "test_return_pct": w.test_return_pct,
                "test_sharpe": w.test_sharpe,
                "return_gap": w.return_gap,
                "is_overfitted": w.is_overfitted,
                "best_params": w.best_params
            })
        
        return {
            "code": 0,
            "data": {
                "symbol": result.symbol,
                "strategy_type": result.strategy_type,
                "window_mode": result.window_mode,
                "total_windows": result.total_windows,
                "avg_test_return_pct": result.avg_test_return_pct,
                "avg_test_sharpe": result.avg_test_sharpe,
                "avg_test_max_dd_pct": result.avg_test_max_dd_pct,
                "avg_test_win_rate": result.avg_test_win_rate,
                "avg_train_return_pct": result.avg_train_return_pct,
                "avg_return_gap": result.avg_return_gap,
                "overfitting_windows": result.overfitting_windows,
                "overfitting_ratio": result.overfitting_ratio,
                "overfitting_severity": result.overfitting_severity,
                "consistency_score": result.consistency_score,
                "recommendation": result.recommendation,
                "confidence": result.confidence,
                "windows": windows_data
            }
        }
    finally:
        conn.close()
