"""
trading.py — Phase 2: 持仓批次追踪与 FIFO 平仓引擎
提供：
  - Buy  / Sell  操作（支持多批次）
  - get_open_lots()   — 查询某账户某标的的未平批次
  - execute_sell()   — FIFO 平仓，返回已实现盈亏明细
  - 计算已实现/未实现盈亏
"""
import sqlite3
import logging
from datetime import datetime
from typing import Optional, NamedTuple

logger = logging.getLogger(__name__)

# ── 持仓批次（Lot）数据结构 ──────────────────────────────────────────────
class LotRecord(NamedTuple):
    id:          int
    portfolio_id:int
    symbol:      str
    shares:      int
    avg_cost:    float
    buy_date:    str
    buy_order_id: Optional[str]
    status:      str
    closed_at:    Optional[str]
    realized_pnl: float
    created_at:   str


# ── 平仓结果 ──────────────────────────────────────────────────────────
class CloseLotResult(NamedTuple):
    lot_id:       int
    shares_closed:int
    avg_cost:     float
    sell_price:   float
    realized_pnl: float


class SellResult(NamedTuple):
    total_realized_pnl: float
    lots_closed:        list[CloseLotResult]
    shares_remaining:  int
    sell_price:        float
    timestamp:         str


# ── 数据库工具 ────────────────────────────────────────────────────────
def _get_lots_conn():
    from app.db.database import _get_conn
    return _get_conn()


# ── 核心：FIFO 平仓执行 ─────────────────────────────────────────────────
def execute_sell(
    portfolio_id: int,
    symbol:       str,
    shares:       int,
    sell_price:   float,
    order_id:    Optional[str] = None,
) -> SellResult:
    """
    FIFO 平仓算法
    ─────────────────────────────────────────────────────────────────────
    规则：
      1. 从 status='open' 的批次中，按 buy_date ASC（早的先平）
      2. 依次匹配，每次从批次中减去实际卖出股数
      3. 批次完全平仓（shares→0）时标记 status='closed'
      4. 部分平仓时：avg_cost 不变，仅 shares 减少
      5. realized_pnl 在每笔 lot 平仓时立即计算
    ─────────────────────────────────────────────────────────────────────
    返回：SellResult(total_realized_pnl, lots_closed[], shares_remaining, sell_price, timestamp)
    """
    if shares <= 0:
        raise ValueError(f"卖出股数必须 > 0，实际值: {shares}")

    if sell_price <= 0:
        raise ValueError(f"卖出价格必须 > 0，实际值: {sell_price}")

    now_str = datetime.now().isoformat()
    lots_closed: list[CloseLotResult] = []
    total_realized_pnl = 0.0
    remaining = shares

    conn = _get_lots_conn()
    try:
        # 按 buy_date 升序（老批次优先）
        open_lots = conn.execute(
            """
            SELECT id, shares, avg_cost, buy_date
              FROM position_lots
             WHERE portfolio_id=? AND symbol=? AND status='open'
             ORDER BY buy_date ASC, id ASC
            """,
            (portfolio_id, symbol),
        ).fetchall()

        if not open_lots:
            raise ValueError(f"账户 {portfolio_id} 标的 {symbol} 无持仓批次（无法做空）")

        total_available = sum(r[1] for r in open_lots)
        if total_available < shares:
            raise ValueError(
                f"持仓不足：账户 {portfolio_id} 标的 {symbol} 可用 {total_available} 股，"
                f"请求卖出 {shares} 股"
            )

        for lot_id, lot_shares, lot_avg_cost, lot_buy_date in open_lots:
            if remaining <= 0:
                break

            # 本次从此批次中平掉的股数
            closed = min(lot_shares, remaining)
            pnl_this = closed * (sell_price - lot_avg_cost)

            new_shares = lot_shares - closed
            new_status = 'closed' if new_shares == 0 else 'open'

            conn.execute(
                """
                UPDATE position_lots
                   SET shares=?,
                       status=?,
                       closed_at=?,
                       realized_pnl=realized_pnl + ?
                 WHERE id=?
                """,
                (new_shares, new_status, now_str if new_status == 'closed' else None,
                 pnl_this, lot_id),
            )

            lots_closed.append(CloseLotResult(
                lot_id=lot_id,
                shares_closed=closed,
                avg_cost=lot_avg_cost,
                sell_price=sell_price,
                realized_pnl=round(pnl_this, 2),
            ))
            total_realized_pnl += pnl_this
            remaining -= closed

    finally:
        conn.commit()
        upsert_position_summary(portfolio_id, symbol)   # Phase 3: sync summary
        conn.close()

    return SellResult(
        total_realized_pnl=round(total_realized_pnl, 2),
        lots_closed=lots_closed,
        shares_remaining=remaining,   # 0 表示全部成交
        sell_price=sell_price,
        timestamp=now_str,
    )


# ── 买入：新增批次 ─────────────────────────────────────────────────────
def execute_buy(
    portfolio_id: int,
    symbol:       str,
    shares:       int,
    buy_price:    float,
    buy_date:     Optional[str] = None,
    order_id:    Optional[str] = None,
) -> LotRecord:
    """买入时新增一个批次（lot）。"""
    if shares <= 0:
        raise ValueError(f"买入股数必须 > 0，实际值: {shares}")
    if buy_price <= 0:
        raise ValueError(f"买入价格必须 > 0，实际值: {buy_price}")

    now_str = datetime.now().isoformat()
    buy_date_str = buy_date or now_str[:10]

    conn = _get_lots_conn()
    try:
        cur = conn.execute(
            """
            INSERT INTO position_lots
                (portfolio_id, symbol, shares, avg_cost, buy_date, buy_order_id,
                 status, realized_pnl, created_at)
            VALUES (?,?,?,?,?,?,'open',0,?)
            """,
            (portfolio_id, symbol, shares, buy_price, buy_date_str, order_id, now_str),
        )
        new_id = cur.lastrowid
        conn.commit()
        upsert_position_summary(portfolio_id, symbol)   # Phase 3: sync summary
    finally:
        conn.close()

    return LotRecord(
        id=new_id,
        portfolio_id=portfolio_id,
        symbol=symbol,
        shares=shares,
        avg_cost=buy_price,
        buy_date=buy_date_str,
        buy_order_id=order_id,
        status='open',
        closed_at=None,
        realized_pnl=0.0,
        created_at=now_str,
    )


# ── 批次查询 ──────────────────────────────────────────────────────────
def get_open_lots(portfolio_id: int, symbol: Optional[str] = None) -> list[LotRecord]:
    """
    获取未平批次（可指定标的或全部）。
    返回按 buy_date 升序排列。
    """
    conn = _get_lots_conn()
    try:
        if symbol:
            rows = conn.execute(
                """
                SELECT id, portfolio_id, symbol, shares, avg_cost,
                       buy_date, buy_order_id, status, closed_at,
                       realized_pnl, created_at
                  FROM position_lots
                 WHERE portfolio_id=? AND symbol=? AND status='open'
                 ORDER BY buy_date ASC, id ASC
                """,
                (portfolio_id, symbol),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, portfolio_id, symbol, shares, avg_cost,
                       buy_date, buy_order_id, status, closed_at,
                       realized_pnl, created_at
                  FROM position_lots
                 WHERE portfolio_id=? AND status='open'
                 ORDER BY buy_date ASC, id ASC
                """,
                (portfolio_id,),
            ).fetchall()

        return [LotRecord(*r) for r in rows]
    finally:
        conn.close()


# ── 未实现盈亏汇总 ───────────────────────────────────────────────────
def calc_unrealized_pnl(portfolio_id: int, symbol: str, current_price: float) -> dict:
    """
    计算某账户某标的的浮动盈亏（基于当前市场价格）。
    公式：Σ(shares × (current_price - avg_cost))
    """
    lots = get_open_lots(portfolio_id, symbol)
    if not lots:
        return {"symbol": symbol, "total_shares": 0, "unrealized_pnl": 0.0}

    total_shares = sum(l.shares for l in lots)
    # 加权均价
    total_cost   = sum(l.shares * l.avg_cost for l in lots)
    avg_cost     = total_cost / total_shares if total_shares else 0
    market_value = total_shares * current_price
    unrealized  = market_value - total_cost

    return {
        "symbol":          symbol,
        "total_shares":    total_shares,
        "avg_cost":        round(avg_cost, 3),
        "current_price":   current_price,
        "market_value":   round(market_value, 2),
        "total_cost":      round(total_cost, 2),
        "unrealized_pnl":  round(unrealized, 2),
        "unrealized_pnl_pct": round(unrealized / total_cost * 100, 2) if total_cost else 0,
        "open_lots":       len(lots),
    }

# ── Phase 3: 持仓聚合表（position_summary）读写 ────────────────────────

def upsert_position_summary(portfolio_id: int, symbol: str) -> None:
    """
    当持仓批次发生变动（buy/sell）后，重新计算并 UPSERT position_summary。
    计算逻辑：
      total_shares = Σ(open_lot.shares)
      avg_cost     = Σ(shares×cost) / total_shares
      market_value = Σ(shares × latest_price)   ← 需要外部喂价
      unrealized_pnl = market_value - Σ(shares × avg_cost)
    注：market_value 和 unrealized_pnl 由外部调用方在已知 current_price 时更新。
    """
    conn = _get_lots_conn()
    try:
        rows = conn.execute(
            """
            SELECT shares, avg_cost
              FROM position_lots
             WHERE portfolio_id=? AND symbol=? AND status='open'
            """,
            (portfolio_id, symbol),
        ).fetchall()

        if not rows:
            # 无 open 批次 → 删除聚合记录
            conn.execute(
                "DELETE FROM position_summary WHERE portfolio_id=? AND symbol=?",
                (portfolio_id, symbol),
            )
        else:
            total_shares = sum(r[0] for r in rows)
            total_cost   = sum(r[0] * r[1] for r in rows)
            avg_cost     = total_cost / total_shares if total_shares else 0.0
            now_str      = datetime.now().isoformat()

            conn.execute(
                """
                INSERT INTO position_summary
                    (portfolio_id, symbol, total_shares, avg_cost, market_value, unrealized_pnl, updated_at)
                VALUES (?, ?, ?, ?, 0.0, 0.0, ?)
                ON CONFLICT(portfolio_id, symbol) DO UPDATE SET
                    total_shares=excluded.total_shares,
                    avg_cost=excluded.avg_cost,
                    updated_at=excluded.updated_at
                """,
                (portfolio_id, symbol, total_shares, avg_cost, now_str),
            )
        conn.commit()
    finally:
        conn.close()


def update_market_value(portfolio_id: int, symbol: str, current_price: float) -> dict:
    """
    更新持仓聚合表的市値和浮动盈亏。
    外部调用：行情刷新时批量更新所有 open_lots 的聚合市値。
    """
    conn = _get_lots_conn()
    try:
        row = conn.execute(
            "SELECT total_shares, avg_cost FROM position_summary WHERE portfolio_id=? AND symbol=?",
            (portfolio_id, symbol),
        ).fetchone()

        if not row or row[0] == 0:
            return {"portfolio_id": portfolio_id, "symbol": symbol,
                    "total_shares": 0, "market_value": 0.0, "unrealized_pnl": 0.0}

        total_shares, avg_cost = row
        market_value   = total_shares * current_price
        total_cost     = total_shares * avg_cost
        unrealized_pnl = market_value - total_cost
        now_str        = datetime.now().isoformat()

        conn.execute(
            """
            INSERT INTO position_summary
                (portfolio_id, symbol, total_shares, avg_cost, market_value, unrealized_pnl, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(portfolio_id, symbol) DO UPDATE SET
                market_value=excluded.market_value,
                unrealized_pnl=excluded.unrealized_pnl,
                updated_at=excluded.updated_at
            """,
            (portfolio_id, symbol, total_shares, avg_cost, market_value, unrealized_pnl, now_str),
        )
        conn.commit()
        return {
            "portfolio_id": portfolio_id, "symbol": symbol,
            "total_shares": total_shares, "avg_cost": round(avg_cost, 3),
            "current_price": current_price,
            "market_value": round(market_value, 2),
            "total_cost": round(total_cost, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "updated_at": now_str,
        }
    finally:
        conn.close()


def get_position_summary(portfolio_id: int, symbol: str = None) -> list[dict]:
    """
    读取持仓聚合表（可按 portfolio_id 过滤，symbol 不传则返回全部）。
    """
    conn = _get_lots_conn()
    try:
        if symbol:
            rows = conn.execute(
                "SELECT * FROM position_summary WHERE portfolio_id=? AND symbol=?",
                (portfolio_id, symbol),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM position_summary WHERE portfolio_id=?",
                (portfolio_id,),
            ).fetchall()

        cols = ["portfolio_id", "symbol", "total_shares", "avg_cost",
                "market_value", "unrealized_pnl", "updated_at"]
        return [dict(zip(cols, r)) for r in rows]
    finally:
        conn.close()
