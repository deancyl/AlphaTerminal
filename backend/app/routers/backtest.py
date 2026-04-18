"""
回测引擎 API
"""
import json
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.db.database import _get_conn, _db_path

router = APIRouter()


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
    finally:
        conn.close()


@router.post("/strategies")
async def create_strategy(req: StrategyCreateRequest):
    """创建新策略"""
    conn = _get_conn()
    try:
        now = datetime.now().isoformat()
        conn.execute("""
            INSERT INTO backtest_strategies (name, description, type, params, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (req.name, req.description, req.strategy_type, 
              json.dumps(req.params) if req.params else "{}", now, now))
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
    import sqlite3
    
    # 标准化 symbol：移除 sh/sz 前缀（数据库存储无前缀）
    db_symbol = req.symbol.replace("sh", "").replace("sz", "")
    
    # 获取历史数据
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
        
        # 解析参数
        fast_ma = (req.params or {}).get('fast_ma', 5)
        slow_ma = (req.params or {}).get('slow_ma', 20)
        
        # ── 基准收益率（Buy & Hold同期）────────────────────────────────────────
        first_close = float(rows[0][4])
        last_close  = float(rows[-1][4])
        benchmark_return_pct = round((last_close - first_close) / first_close * 100, 2)

        # ── 技术指标计算 ──────────────────────────────────────────────────────
        closes = [float(r[4]) for r in rows]
        highs  = [float(r[2]) for r in rows]
        lows   = [float(r[3]) for r in rows]
        volumes= [float(r[5]) for r in rows]

        def calc_ma(data, period):
            return [None] * (period - 1) + [
                round(sum(data[i-period+1:i+1]) / period, 2) for i in range(period - 1, len(data))
            ]

        def calc_rsi(closes, period=14):
            gains, losses = [], []
            for i in range(1, len(closes)):
                d = closes[i] - closes[i-1]
                gains.append(max(d, 0)); losses.append(max(-d, 0))
            avg_gain = [None] * period; avg_loss = [None] * period
            if sum(losses[:period]) == 0:
                return [50.0] * len(closes)
            ag = sum(gains[:period]) / period; al = sum(losses[:period]) / period
            rs = ag / al if al != 0 else 0
            avg_gain.append(100 - 100/(1+rs)); avg_loss.append(0)
            for i in range(period+1, len(gains)):
                ag = (ag*(period-1) + gains[i-1]) / period
                al = (al*(period-1) + losses[i-1]) / period
                rs = ag / al if al != 0 else 0
                avg_gain.append(100 - 100/(1+rs) if al != 0 else 50.0); avg_loss.append(0)
            return avg_gain + [None] * (len(closes) - len(avg_gain))

        def calc_bollinger(closes, period=20, multiplier=2):
            mid = calc_ma(closes, period)
            upper, lower = [None] * len(closes), [None] * len(closes)
            for i in range(period - 1, len(closes)):
                if mid[i] is not None:
                    std = (sum((closes[j] - mid[i])**2 for j in range(i-period+1, i+1)) / period) ** 0.5
                    upper[i] = round(mid[i] + multiplier * std, 2)
                    lower[i] = round(mid[i] - multiplier * std, 2)
            return mid, upper, lower

        # ── 策略信号生成 ──────────────────────────────────────────────────────
        strategy_type = req.strategy_type or 'ma_crossover'
        signals = [0] * len(closes)  # 1=买入, -1=卖出, 0=持仓

        if strategy_type == 'ma_crossover':
            fast_ma_vals = calc_ma(closes, fast_ma)
            slow_ma_vals = calc_ma(closes, slow_ma)
            for i in range(slow_ma, len(closes)):
                if fast_ma_vals[i] is None: continue
                if fast_ma_vals[i] > slow_ma_vals[i] and fast_ma_vals[i-1] <= slow_ma_vals[i-1]:
                    signals[i] = 1
                elif fast_ma_vals[i] < slow_ma_vals[i] and fast_ma_vals[i-1] >= slow_ma_vals[i-1]:
                    signals[i] = -1

        elif strategy_type == 'rsi_oversold':
            rsi_period = (req.params or {}).get('rsi_period', 14)
            rsi_buy    = (req.params or {}).get('rsi_buy', 30)
            rsi_sell   = (req.params or {}).get('rsi_sell', 70)
            rsi_vals   = calc_rsi(closes, rsi_period)
            in_position = False
            for i in range(1, len(closes)):
                if rsi_vals[i] is None: continue
                if not in_position and rsi_vals[i] < rsi_buy:
                    signals[i] = 1; in_position = True
                elif in_position and rsi_vals[i] > rsi_sell:
                    signals[i] = -1; in_position = False

        elif strategy_type == 'bollinger_bands':
            mid, upper, lower = calc_bollinger(closes, 20, 2)
            for i in range(1, len(closes)):
                if lower[i] is None: continue
                if closes[i-1] <= lower[i-1] and closes[i] > lower[i]:
                    signals[i] = 1
                elif closes[i-1] >= upper[i-1] and closes[i] < upper[i]:
                    signals[i] = -1

        # ── 模拟交易（按信号执行）────────────────────────────────────────────
        capital = float(req.initial_capital)
        position = 0; entry_price = 0.0
        trades = []; wins = 0; losses = 0

        for i in range(1, len(closes)):
            if signals[i] == 1 and position == 0 and capital > 0:
                shares = int(capital * 0.9 / closes[i])
                if shares > 0:
                    position = shares; entry_price = closes[i]
                    capital -= shares * entry_price
                    trades.append({"entry_date": rows[i][0], "entry_price": round(entry_price, 2), "shares": shares, "type": "long"})
            elif signals[i] == -1 and position > 0:
                exit_price = closes[i]
                pnl = (exit_price - entry_price) * position
                if pnl > 0: wins += 1
                else: losses += 1
                capital += position * exit_price
                trades[-1].update({"exit_date": rows[i][0], "exit_price": round(exit_price, 2), "pnl": round(pnl, 2), "pnl_pct": round((exit_price - entry_price) / entry_price * 100, 2)})
                position = 0

        if position > 0:
            exit_price = closes[-1]
            pnl = (exit_price - entry_price) * position
            if pnl > 0: wins += 1
            else: losses += 1
            capital += position * exit_price
            trades[-1].update({"exit_date": rows[-1][0], "exit_price": round(exit_price, 2), "pnl": round(pnl, 2), "pnl_pct": round((exit_price - entry_price) / entry_price * 100, 2)})

        # ── 统计指标 ─────────────────────────────────────────────────────────
        total_return     = capital - float(req.initial_capital)
        total_return_pct= round(total_return / float(req.initial_capital) * 100, 2)
        total_trades     = wins + losses
        win_rate         = round(wins / total_trades * 100, 2) if total_trades > 0 else 0

        equity = float(req.initial_capital); peak = equity; max_drawdown = 0.0; equity_curve = []
        for t in trades:
            equity += t['pnl']
            equity_curve.append({"date": t.get("exit_date", t.get("entry_date")), "value": round(equity, 2)})
            if equity > peak: peak = equity
            dd = peak - equity
            if dd > max_drawdown: max_drawdown = dd

        years            = len(rows) / 252
        annualized_return= (capital / float(req.initial_capital)) ** (1 / years) - 1 if years > 0 else 0
        sharpe_ratio     = round(annualized_return / (max_drawdown / float(req.initial_capital)), 2) if max_drawdown > 0 else 0

        # ── 返回完整交易列表 ──────────────────────────────────────────────────
        return {
            "code": 0,
            "data": {
                "symbol": req.symbol,
                "start_date": req.start_date,
                "end_date": req.end_date,
                "initial_capital": req.initial_capital,
                "final_capital": round(capital, 2),
                "total_return": round(total_return, 2),
                "total_return_pct": round(total_return_pct, 2),
                "max_drawdown": round(max_drawdown, 2),
                "max_drawdown_pct": round((max_drawdown / req.initial_capital) * 100, 2),
                "wins": wins,
                "losses": losses,
                "win_rate": round(win_rate, 2),
                "trades_count": total_trades,
                "sharpe_ratio": sharpe_ratio,
                "annualized_return_pct": round(annualized_return * 100, 2),
                "benchmark_return_pct": benchmark_return_pct,
                "strategy_type": strategy_type,
                "trades": trades,
                "equity_curve": equity_curve,
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
            SELECT id, strategy_id, symbol, start_date, end_date, 
                   initial_capital, final_capital, total_return_pct, 
                   max_drawdown_pct, win_rate, trades_count, created_at
            FROM backtest_results ORDER BY created_at DESC LIMIT ?
        """, (limit,)).fetchall()
        
        results = []
        for r in rows:
            results.append({
                "id": r[0],
                "strategy_id": r[1],
                "symbol": r[2],
                "start_date": r[3],
                "end_date": r[4],
                "initial_capital": r[5],
                "final_capital": r[6],
                "total_return_pct": r[7],
                "max_drawdown_pct": r[8],
                "win_rate": r[9],
                "trades_count": r[10],
                "created_at": r[11]
            })
        
        return {"code": 0, "data": {"results": results}}
    finally:
        conn.close()
