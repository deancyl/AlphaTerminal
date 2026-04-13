"""
P3 多账户模拟组合 — 路由层
CRUD: 账户 / 持仓 / 净值历史
"""
import time
import logging
from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/portfolio", tags=["portfolio"])

# ── Pydantic 模型 ──────────────────────────────────────────────

class PortfolioIn(BaseModel):
    name: str
    type: str = "main"   # 'main' | 'special_plan'

class PositionIn(BaseModel):
    portfolio_id: int
    symbol: str
    shares: int
    avg_cost: float

class PositionUpdate(BaseModel):
    shares: Optional[int] = None
    avg_cost: Optional[float] = None

# ── 响应格式标准化（可选使用）─────────────────────────────
def _ok(data, msg="success"):
    return {"code": 0, "message": msg, "data": data, "timestamp": int(time.time() * 1000)}

# ── 数据库工具 ────────────────────────────────────────────────

from app.db.database import _get_conn, _lock

def _row2dict(rows, cols):
    return [dict(zip(cols, r)) for r in rows]

# ── 账户 CRUD ─────────────────────────────────────────────────

@router.get("/")
async def list_portfolios():
    """所有账户列表"""
    with _lock:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT id, name, type, created_at, total_cost FROM portfolios ORDER BY id"
        ).fetchall()
        conn.close()
    return {"portfolios": _row2dict(rows, ["id", "name", "type", "created_at", "total_cost"])}

@router.post("/")
async def create_portfolio(body: PortfolioIn):
    """新建账户"""
    now = datetime.now().isoformat()
    with _lock:
        conn = _get_conn()
        try:
            cur = conn.execute(
                "INSERT INTO portfolios (name, type, created_at, total_cost) VALUES (?,?,?,0)",
                (body.name, body.type, now)
            )
            conn.commit()
            pid = cur.lastrowid
        except Exception as e:
            conn.close()
            raise HTTPException(400, f"创建账户失败: {e}")
        conn.close()
    return {"id": pid, "name": body.name, "type": body.type, "created_at": now, "total_cost": 0.0}

@router.delete("/{portfolio_id}")
async def delete_portfolio(portfolio_id: int):
    """删除账户（连带持仓和快照）"""
    with _lock:
        conn = _get_conn()
        cur = conn.execute("DELETE FROM portfolios WHERE id=?", (portfolio_id,))
        conn.commit()
        deleted = cur.rowcount
        conn.close()
    if not deleted:
        raise HTTPException(404, "账户不存在")
    return {"ok": True}

# ── 持仓 CRUD ─────────────────────────────────────────────────

@router.get("/{portfolio_id}/positions")
async def list_positions(portfolio_id: int):
    """账户当前持仓"""
    with _lock:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT id, symbol, shares, avg_cost, updated_at FROM positions WHERE portfolio_id=?",
            (portfolio_id,)
        ).fetchall()
        conn.close()
    return {"positions": [{"id": r[0], "symbol": r[1], "shares": r[2],
                            "avg_cost": r[3], "updated_at": r[4]} for r in rows]}

@router.post("/positions")
async def upsert_position(body: PositionIn):
    """
    建仓或调仓：INSERT OR REPLACE
    shares=0 表示清仓（删除持仓）
    """
    now = datetime.now().isoformat()
    with _lock:
        conn = _get_conn()
        if body.shares == 0:
            conn.execute(
                "DELETE FROM positions WHERE portfolio_id=? AND symbol=?",
                (body.portfolio_id, body.symbol)
            )
            conn.commit()
            conn.close()
            return {"ok": True, "action": "cleared"}
        conn.execute(
            "INSERT OR REPLACE INTO positions (portfolio_id, symbol, shares, avg_cost, updated_at) "
            "VALUES (?,?,?,?,?)",
            (body.portfolio_id, body.symbol, body.shares, body.avg_cost, now)
        )
        conn.commit()
        conn.close()
    return {"ok": True, "action": "upserted"}

@router.delete("/{portfolio_id}/positions/{symbol}")
async def delete_position(portfolio_id: int, symbol: str):
    """清仓指定标的"""
    with _lock:
        conn = _get_conn()
        cur = conn.execute(
            "DELETE FROM positions WHERE portfolio_id=? AND symbol=?",
            (portfolio_id, symbol)
        )
        conn.commit()
        conn.close()
    return {"ok": True}

# ── 实时浮动盈亏（依赖 SpotCache） ─────────────────────────────

@router.get("/{portfolio_id}/pnl")
async def portfolio_pnl(portfolio_id: int):
    """
    实时浮动盈亏计算（专业增强版）
    增加: 名称、权重%、今日涨跌幅、市场、PE/PB、换手率
    依赖 SpotCache（后台每3分钟刷新的全市场实时行情）
    """
    from app.services.sentiment_engine import SpotCache

    with _lock:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT symbol, shares, avg_cost FROM positions WHERE portfolio_id=?",
            (portfolio_id,)
        ).fetchall()
        # 获取持仓股票的基本面数据（PE/PB等）
        stock_meta = {}
        meta_rows = conn.execute(
            "SELECT symbol, name, per, pb, mktcap, turnover FROM market_all_stocks"
        ).fetchall()
        for r in meta_rows:
            stock_key = r[0].lower().replace("sh", "").replace("sz", "").replace("hk", "").replace("us", "")
            stock_meta[stock_key] = {"name": r[1], "per": r[2], "pb": r[3], "mktcap": r[4], "turnover": r[5]}

        stock_meta[stock_key] = {"name": r[1], "per": r[2], "pb": r[3], "mktcap": r[4], "turnover": r[5]}
        conn.close()

    if not rows:
        return {"positions": [], "total_pnl": 0.0, "total_cost": 0.0, "total_value": 0.0}

    spot = SpotCache.get_stocks()
    price_map = {s["code"]: s for s in spot}

    result = []
    total_cost = 0.0
    total_value = 0.0
    for symbol, shares, avg_cost in rows:
        info = price_map.get(symbol, {})
        current_price = info.get("price", avg_cost)
        change_pct   = info.get("change_pct", 0.0)
        market_value = shares * current_price
        cost_total   = shares * avg_cost
        pnl         = market_value - cost_total
        pnl_pct    = (pnl / cost_total * 100) if cost_total > 0 else 0.0

        sym_upper = symbol.upper().replace("SH", "").replace("SZ", "").replace("HK", "").replace("US", "")
        if sym_upper.startswith("6") or sym_upper.startswith("0") or sym_upper.startswith("3"):
            market = "A股"
        elif "hk" in symbol.lower():
            market = "港股"
        elif "us" in symbol.lower():
            market = "美股"
        else:
            market = "其他"

        meta = stock_meta.get(symbol, {})
        result.append({
            "symbol":       symbol,
            "name":         meta.get("name", symbol),
            "shares":       shares,
            "avg_cost":     round(avg_cost, 3),
            "price":        round(current_price, 3),
            "change_pct":   round(change_pct, 2),
            "market_value": round(market_value, 2),
            "cost_total":   round(cost_total, 2),
            "pnl":         round(pnl, 2),
            "pnl_pct":    round(pnl_pct, 2),
            "weight":       0.0,
            "market":       market,
            "pe":          round(meta.get("per"), 2) if meta.get("per") else None,
            "pb":          round(meta.get("pb"), 2) if meta.get("pb") else None,
            "turnover":    round(meta.get("turnover"), 2) if meta.get("turnover") else None,
        })
        total_cost  += cost_total
        total_value += market_value

    # 第二遍：计算权重
    for pos in result:
        pos["weight"] = round(pos["market_value"] / total_value * 100, 2) if total_value > 0 else 0.0

    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0
    return {
        "positions":    result,
        "total_cost":  round(total_cost, 2),
        "total_value": round(total_value, 2),
        "total_pnl":   round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
    }




@router.get("/{portfolio_id}/snapshots")
async def get_snapshots(
    portfolio_id: int,
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date:   Optional[str] = Query(None, description="YYYY-MM-DD"),
):
    """净值历史快照"""
    with _lock:
        conn = _get_conn()
        if start_date and end_date:
            rows = conn.execute(
                "SELECT date, total_asset, total_cost FROM portfolio_snapshots "
                "WHERE portfolio_id=? AND date BETWEEN ? AND ? ORDER BY date ASC",
                (portfolio_id, start_date, end_date)
            ).fetchall()
        elif start_date:
            rows = conn.execute(
                "SELECT date, total_asset, total_cost FROM portfolio_snapshots "
                "WHERE portfolio_id=? AND date>=? ORDER BY date ASC",
                (portfolio_id, start_date)
            ).fetchall()
        elif end_date:
            rows = conn.execute(
                "SELECT date, total_asset, total_cost FROM portfolio_snapshots "
                "WHERE portfolio_id=? AND date<=? ORDER BY date ASC",
                (portfolio_id, end_date)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT date, total_asset, total_cost FROM portfolio_snapshots "
                "WHERE portfolio_id=? ORDER BY date ASC LIMIT 365"
                , (portfolio_id,)
            ).fetchall()
        conn.close()
    return {
        "snapshots": [
            {"date": r[0], "total_asset": r[1], "total_cost": r[2],
             "pnl_pct": round((r[1]-r[2])/r[2]*100, 2) if r[2] else 0.0}
            for r in rows
        ]
    }

@router.post("/{portfolio_id}/snapshots")
async def save_snapshot(portfolio_id: int):
    """手动保存当日快照（供路由调用）"""
    return _save_snapshot_impl(portfolio_id)


def _save_snapshot_impl(portfolio_id: int):
    """
    保存当日净值快照（同步函数，供 scheduler 直接调用）
    计算: total_asset = Σ(shares * latest_close)，total_cost = Σ(shares * avg_cost)
    """
    today = date.today().isoformat()
    with _lock:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT symbol, shares, avg_cost FROM positions WHERE portfolio_id=?",
            (portfolio_id,)
        ).fetchall()
        conn.close()

    if not rows:
        return {"ok": False, "message": "无持仓，无须保存"}

    # 从 market_data_realtime（SpotCache 刷新的实时表）取最新价格
    from app.db.database import get_latest_prices
    symbols = [r[0] for r in rows]
    prices  = {s["symbol"]: s["price"] for s in get_latest_prices(symbols)}

    total_asset = 0.0
    total_cost  = 0.0
    for symbol, shares, avg_cost in rows:
        price = prices.get(symbol, avg_cost)
        total_asset += shares * price
        total_cost  += shares * avg_cost

    with _lock:
        conn = _get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO portfolio_snapshots (portfolio_id, date, total_asset, total_cost) "
            "VALUES (?,?,?,?)",
            (portfolio_id, today, round(total_asset, 2), round(total_cost, 2))
        )
        conn.commit()
        conn.close()

    return {
        "ok": True, "date": today,
        "total_asset": round(total_asset, 2),
        "total_cost": round(total_cost, 2),
        "pnl_pct": round((total_asset-total_cost)/total_cost*100, 2) if total_cost else 0.0
    }
