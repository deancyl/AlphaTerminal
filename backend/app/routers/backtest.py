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
    
    # 获取历史数据
    conn = _get_conn()
    try:
        rows = conn.execute("""
            SELECT date, open, high, low, close, volume
            FROM market_data_daily
            WHERE symbol = ? AND date >= ? AND date <= ?
            ORDER BY date ASC
        """, (req.symbol, req.start_date, req.end_date)).fetchall()
        
        if len(rows) < 30:
            return {"code": 1, "message": f"数据不足，需至少30条，实际{len(rows)}条"}
        
        # 解析参数
        fast_ma = (req.params or {}).get('fast_ma', 5)
        slow_ma = (req.params or {}).get('slow_ma', 20)
        
        # 计算均线
        closes = [r[4] for r in rows]
        
        def calc_ma(data, period):
            result = []
            for i in range(len(data)):
                if i < period - 1:
                    result.append(None)
                else:
                    avg = sum(data[i-period+1:i+1]) / period
                    result.append(round(avg, 2))
            return result
        
        fast_ma_values = calc_ma(closes, fast_ma)
        slow_ma_values = calc_ma(closes, slow_ma)
        
        # 模拟交易
        capital = req.initial_capital
        position = 0  # 持仓股数
        entry_price = 0
        trades = []
        pnl_total = 0
        wins = 0
        losses = 0
        
        for i in range(slow_ma, len(closes)):
            if fast_ma_values[i] is None or slow_ma_values[i] is None:
                continue
                
            # 金叉买入
            if fast_ma_values[i] > slow_ma_values[i] and fast_ma_values[i-1] <= slow_ma_values[i-1]:
                if position == 0 and capital > 0:
                    shares = int(capital * 0.9 / closes[i])  # 90%仓位
                    if shares > 0:
                        position = shares
                        entry_price = closes[i]
                        capital -= shares * entry_price
                        trades.append({
                            "entry_date": rows[i][0],
                            "entry_price": entry_price,
                            "shares": shares,
                            "type": "long"
                        })
            
            # 死叉卖出
            elif fast_ma_values[i] < slow_ma_values[i] and fast_ma_values[i-1] >= slow_ma_values[i-1]:
                if position > 0:
                    exit_price = closes[i]
                    pnl = (exit_price - entry_price) * position
                    pnl_total += pnl
                    if pnl > 0:
                        wins += 1
                    else:
                        losses += 1
                    capital += position * exit_price
                    trades[-1].update({
                        "exit_date": rows[i][0],
                        "exit_price": exit_price,
                        "pnl": round(pnl, 2),
                        "pnl_pct": round((exit_price - entry_price) / entry_price * 100, 2)
                    })
                    position = 0
        
        # 计算最终收益
        if position > 0:
            final_price = closes[-1]
            pnl = (final_price - entry_price) * position
            pnl_total += pnl
            if pnl > 0:
                wins += 1
            else:
                losses += 1
            capital += position * final_price
            trades[-1].update({
                "exit_date": rows[-1][0],
                "exit_price": final_price,
                "pnl": round(pnl, 2),
                "pnl_pct": round((final_price - entry_price) / entry_price * 100, 2)
            })
        
        total_return = capital - req.initial_capital
        total_return_pct = (total_return / req.initial_capital) * 100
        total_trades = wins + losses
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        # 计算最大回撤 (简化版)
        max_capital = req.initial_capital
        max_drawdown = 0
        for t in trades:
            if 'pnl' in t:
                max_capital += t['pnl']
                drawdown = (max_capital - req.initial_capital - max_drawdown)
                if drawdown < max_drawdown:
                    max_drawdown = abs(drawdown)
        
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
                "wins": wins,
                "losses": losses,
                "win_rate": round(win_rate, 2),
                "trades_count": total_trades,
                "trades": trades[-10:]  # 返回最近10笔交易
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
