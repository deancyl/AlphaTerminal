"""
Portfolio Dependencies and Helper Functions

This module contains shared dependencies and helper functions used across
the portfolio router modules. Extracted from portfolio.py for better code
organization and reusability.

Functions:
- verify_portfolio_key: Portfolio API key verification
- require_auth_for_sensitive_ops: Auth wrapper for sensitive operations
- _insert_transaction: Insert transaction records
- _transfer_between_accounts: Atomic transfer between accounts
- _row2dict: Convert database rows to dictionaries
- _get_all_descendants: Recursively get all descendant account IDs
- _classify_asset: Classify asset by symbol and name
- _save_snapshot_impl: Save portfolio snapshot implementation
"""

import os
import logging
from datetime import datetime, date
from typing import Optional

from fastapi import HTTPException, Header, Depends

from app.db.database import _get_conn, _lock
from app.middleware import require_api_key

logger = logging.getLogger(__name__)


# ── 认证保护 ──────────────────────────────────────────────
# 使用 PORTFOLIO_API_KEY 环境变量保护敏感操作
# 未配置时保持开放（开发环境）

def verify_portfolio_key(api_key: str = None, x_forwarded_for: str = Header(None)):
    """Portfolio API 密钥校验（可选）"""
    configured_key = os.environ.get("PORTFOLIO_API_KEY", "")
    # 未配置 key 时跳过认证（本机开发环境）
    if not configured_key:
        return True
    if api_key != configured_key:
        raise HTTPException(status_code=401, detail="Invalid Portfolio API key")
    return True


def require_auth_for_sensitive_ops(api_key: str = None):
    """敏感操作认证（DELETE、include_children）"""
    return verify_portfolio_key(api_key)


# ── 事务流水工具 ─────────────────────────────────────────────

def _insert_transaction(
    conn,
    portfolio_id: int,
    txn_type: str,
    amount: float,
    balance_after: float,
    counterparty_id: Optional[int] = None,
    related_symbol: Optional[str] = None,
    note: Optional[str] = None,
    operator: str = "system",
) -> int:
    """写入一笔资金流水记录，返回自增 ID。"""
    now = datetime.now().isoformat()
    cur = conn.execute(
        """INSERT INTO transactions
           (portfolio_id, type, amount, balance_after, counterparty_id,
            related_symbol, note, created_at, operator)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (portfolio_id, txn_type, amount, balance_after,
         counterparty_id, related_symbol, note, now, operator),
    )
    return cur.lastrowid


def _transfer_between_accounts(
    from_pid: int, to_pid: int, amount: float, note: Optional[str] = None
) -> dict:
    """
    原子划转：从账户A扣款，账户B入账，写入两条对立流水。
    返回划转结果。
    """
    with _lock:
        conn = _get_conn()
        try:
            # 读取双方现金余额
            rows = conn.execute(
                "SELECT id, cash_balance FROM portfolios WHERE id IN (?,?)",
                (from_pid, to_pid),
            ).fetchall()
            # 验证两个账户都存在
            if len(rows) != 2:
                raise ValueError("账户不存在")
            
            balance_map = {r[0]: r[1] for r in rows}
            bal_from = balance_map[from_pid]
            bal_to   = balance_map[to_pid]

            if bal_from < amount:
                raise ValueError(f"账户 {from_pid} 现金余额 ({bal_from}) 不足")

            new_bal_from = bal_from - amount
            new_bal_to   = bal_to   + amount

            conn.execute(
                "UPDATE portfolios SET cash_balance=? WHERE id=?",
                (new_bal_from, from_pid),
            )
            conn.execute(
                "UPDATE portfolios SET cash_balance=? WHERE id=?",
                (new_bal_to, to_pid),
            )

            # 写流水（from 侧）
            _insert_transaction(conn, from_pid, "transfer_out",
                                amount, new_bal_from, counterparty_id=to_pid, note=note)
            # 写流水（to 侧）
            _insert_transaction(conn, to_pid, "transfer_in",
                                amount, new_bal_to, counterparty_id=from_pid, note=note)

            conn.commit()
        finally:
            conn.close()

    return {"from": from_pid, "to": to_pid, "amount": amount,
            "balance_from": new_bal_from, "balance_to": new_bal_to}


# ── 数据库工具 ────────────────────────────────────────────────

def _row2dict(rows, cols):
    """Convert database rows to list of dictionaries."""
    return [dict(zip(cols, r)) for r in rows]


def _get_all_descendants(conn, portfolio_id: int, visited: set = None) -> list:
    """
    递归获取所有后代账户ID（子孙，不含自身）。
    使用 visited set 阻断环形嵌套。
    """
    if visited is None:
        visited = set()
    if portfolio_id in visited:
        return []
    visited.add(portfolio_id)
    result = []
    cursor = conn.execute("SELECT id FROM portfolios WHERE parent_id=?", (portfolio_id,))
    children = [row[0] for row in cursor.fetchall()]
    for child_id in children:
        result.append(child_id)
        result.extend(_get_all_descendants(conn, child_id, visited))
    return result


# ── 资产分类工具 ────────────────────────────────────────────────

def _classify_asset(symbol: str, name: str = "") -> dict:
    """
    根据 symbol + name 推断底层资产类型与细分板块。
    返回: { category, sub_category, is_index }
    """
    sym = symbol.strip().lower()
    name_lower = name.lower()
    raw_code = sym.removeprefix("sh").removeprefix("sz").removeprefix("hk").removeprefix("us").removeprefix("jp").removeprefix("bj")

    # ── 固收：国债/国开债/地方债 ────────────────────────────────
    if any(kw in name_lower for kw in ["国债", "国开", "地方债", "政金债", "债券", "债"]):
        return {"category": "bond", "sub_category": "利率债", "is_index": False}

    # ── 商品期货 ────────────────────────────────────────────────
    if raw_code.upper() in ("AU", "AG", "CU", "AL", "ZN", "PB", "NI", "SN",
                             "RU", "RB", "HC", "I", "J", "JM", "焦煤",
                             "原油", "燃油", "沥青", "棕榈", "豆油", "菜油",
                             "棉花", "白糖", "苹果", "红枣"):
        return {"category": "futures", "sub_category": "商品期货", "is_index": False}
    if any(kw in name_lower for kw in ["黄金", "白银", "铜", "铝", "锌", "镍", "螺纹", "铁矿石", "焦炭", "原油"]):
        return {"category": "futures", "sub_category": "商品期货", "is_index": False}

    # ── 货币基金 / 现金管理 ────────────────────────────────────
    if raw_code.startswith("51") and len(raw_code) == 6:
        return {"category": "money_fund", "sub_category": "货币基金", "is_index": False}

    # ── 宽基指数 ETF（代码特征）─────────────────────────────────
    if raw_code.startswith("51") or raw_code.startswith("15") or raw_code.startswith("56"):
        return {"category": "etf", "sub_category": "宽基ETF", "is_index": True}
    if raw_code in ("000001", "000300", "000016", "000688", "000905", "000852",
                    "399001", "399006", "399100", "399005", "399673"):
        return {"category": "index", "sub_category": "A股指数", "is_index": True}

    # ── 港股 ────────────────────────────────────────────────────
    if sym.startswith("hk"):
        return {"category": "hk_stock", "sub_category": "港股", "is_index": False}

    # ── A股（sh6 / sz0,3 开头个股）───────────────────────────────
    if raw_code.startswith("6") or raw_code.startswith("0") or raw_code.startswith("3"):
        return {"category": "a_stock", "sub_category": "A股个股", "is_index": False}

    return {"category": "other", "sub_category": "其他", "is_index": False}


# ── 快照保存实现 ────────────────────────────────────────────────

def _save_snapshot_impl(portfolio_id: int):
    """
    保存当日净值快照（同步函数，供 scheduler 直接调用）
    计算: total_asset = Σ(shares * latest_close)，total_cost = Σ(shares * avg_cost)
    Phase 4 Fix: 优先从 position_summary 读取（lot-based 系统），fallback 到 positions
    """
    from app.utils.response import success_response
    
    today = date.today().isoformat()
    with _lock:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT symbol, total_shares as shares, avg_cost FROM position_summary WHERE portfolio_id=? AND total_shares > 0",
            (portfolio_id,)
        ).fetchall()
        
        if not rows:
            rows = conn.execute(
                "SELECT symbol, shares, avg_cost FROM positions WHERE portfolio_id=?",
                (portfolio_id,)
            ).fetchall()
        conn.close()

    if not rows:
        return success_response({"ok": False, "message": "无持仓，无须保存"})

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

    return success_response({
        "ok": True, "date": today,
        "total_asset": round(total_asset, 2),
        "total_cost": round(total_cost, 2),
        "pnl_pct": round((total_asset-total_cost)/total_cost*100, 2) if total_cost else 0.0
    })


# ── 导出符号 ────────────────────────────────────────────────

__all__ = [
    "verify_portfolio_key",
    "require_auth_for_sensitive_ops",
    "_insert_transaction",
    "_transfer_between_accounts",
    "_row2dict",
    "_get_all_descendants",
    "_classify_asset",
    "_save_snapshot_impl",
    "_get_conn",
    "_lock",
    "logger",
]
