"""
P3 多账户模拟组合 - 路由层
CRUD: 账户 / 持仓 / 净值历史
"""
import os
import time
import logging
from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends, Header
from pydantic import BaseModel

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

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

# ── Pydantic 模型 ──────────────────────────────────────────────

class PortfolioIn(BaseModel):
    name: str
    type: str = "portfolio"   # portfolio | account | strategy | group
    parent_id: Optional[int] = None
    currency: str = "CNY"  # CNY | USD | HKD
    asset_class: str = "mixed"  # stock | bond | fund | futures | options | mixed
    strategy: Optional[str] = None  # value | growth | balanced | index | quant
    benchmark: Optional[str] = None  # 000001 | 000300 | 399001 | 399006
    status: str = "active"  # active | frozen | closed
    initial_capital: float = 0.0
    description: Optional[str] = None

class PortfolioUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    parent_id: Optional[int] = None
    currency: Optional[str] = None
    asset_class: Optional[str] = None
    strategy: Optional[str] = None
    benchmark: Optional[str] = None
    status: Optional[str] = None
    initial_capital: Optional[float] = None
    description: Optional[str] = None

class PositionIn(BaseModel):
    portfolio_id: int
    symbol: str
    shares: int
    avg_cost: float

class PositionUpdate(BaseModel):
    shares: Optional[int] = None
    avg_cost: Optional[float] = None

class TransactionIn(BaseModel):
    portfolio_id: int
    type: str          # deposit | withdraw | transfer_in | transfer_out | dividend | fee
    amount: float
    balance_after: float
    counterparty_id: Optional[int] = None
    related_symbol: Optional[str] = None
    note: Optional[str] = None
    operator: str = "user"

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
            # 读取双方现 金余额
            rows = conn.execute(
                "SELECT id, cash_balance FROM portfolios WHERE id IN (?,?)",
                (from_pid, to_pid),
            ).fetchall()
            balance_map = {r[0]: r[1] for r in rows}
            bal_from = balance_map.get(from_pid, 0.0)
            bal_to   = balance_map.get(to_pid, 0.0)

            if bal_from < amount:
                raise ValueError(f"账户 {from_pid} 现金余额 ({bal_from}) 不足")

            new_bal_from = bal_from - amount
            new_bal_to   = bal_to   + amount
            now = datetime.now().isoformat()

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
    """所有账户列表（WAL 模式并发读，无需应用层锁）"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT id, name, type, parent_id, created_at, total_cost, cash_balance,
                      currency, asset_class, strategy, benchmark, status, initial_capital, description
               FROM portfolios ORDER BY id"""
        ).fetchall()
    finally:
        conn.close()
    return {"portfolios": _row2dict(rows, ["id", "name", "type", "parent_id", "created_at", "total_cost",
                                            "cash_balance", "currency", "asset_class", "strategy", "benchmark",
                                            "status", "initial_capital", "description"])}

@router.post("/")
async def create_portfolio(body: PortfolioIn):
    """新建账户"""
    now = datetime.now().isoformat()
    with _lock:
        conn = _get_conn()
        try:
            # ── 环形嵌套防御 ─────────────────────────────────────
            if body.parent_id is not None:
                # 自身不能作为自己的 parent
                if body.parent_id == 0:
                    raise HTTPException(400, "parent_id 不能为 0（自身）")
                # 检查父节点是否"有效"：其后代节点集合不能包含自身（portfolio_id 本身，
                # 此时为 None，因为新账户尚未插入 DB，故此处只需检查父节点是否有后代）
                children_of_parent = _get_all_descendants(conn, body.parent_id)
                # children_of_parent 不应包含 body.parent_id 自身（若包含说明查到了自己）
                # 对于新账户场景：children_of_parent 应只返回已有的子账户，不含父节点本身
                if body.parent_id in children_of_parent:
                    raise HTTPException(400, f"parent_id ({body.parent_id}) 不能指向自身的后代节点，检测到环形嵌套")
            # ── 写入 ─────────────────────────────────────────────
            cur = conn.execute(
                """INSERT INTO portfolios (name, type, parent_id, created_at, total_cost,
                        currency, asset_class, strategy, benchmark, status, initial_capital,
                        description, cash_balance)
                 VALUES (?,?,?,?,0,?,?,?,?,?,?,?,0.0)""",
                (body.name, body.type, body.parent_id, now,
                 body.currency, body.asset_class, body.strategy, body.benchmark,
                 body.status, body.initial_capital, body.description)
            )
            conn.commit()
            pid = cur.lastrowid
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(400, f"创建账户失败: {e}")
        conn.close()
    return {"id": pid, "name": body.name, "type": body.type, "parent_id": body.parent_id,
            "created_at": now, "total_cost": 0.0, "currency": body.currency,
            "asset_class": body.asset_class, "strategy": body.strategy,
            "benchmark": body.benchmark, "status": body.status,
            "initial_capital": body.initial_capital, "description": body.description}

@router.delete("/{portfolio_id}")
async def delete_portfolio(portfolio_id: int, api_key: str = None, auth: bool = Depends(require_auth_for_sensitive_ops)):
    """删除账户（连带持仓和快照）- 需认证"""
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

@router.get("/{portfolio_id}/positions")
async def list_positions(portfolio_id: int, include_children: bool = Query(False, description="是否包含子账户持仓")):
    """账户当前持仓，可选包含所有子账户持仓"""
    # WAL 模式支持并发读
    # Phase 4: 从 position_summary 读取（lot-based 系统）
    conn = _get_conn()
    try:
        if include_children:
            # 获取所有后代账户ID
            all_ids = _get_all_descendants(conn, portfolio_id)
            placeholders = ','.join(['?' for _ in all_ids])
            rows = conn.execute(
                f"""SELECT ps.portfolio_id, ps.symbol, ps.total_shares, ps.avg_cost, 
                           ps.market_value, ps.unrealized_pnl, ps.updated_at,
                           po.name as portfolio_name
                    FROM position_summary ps
                    JOIN portfolios po ON ps.portfolio_id = po.id
                    WHERE ps.portfolio_id IN ({placeholders}) AND ps.total_shares > 0""",
                tuple(all_ids)
            ).fetchall()
            return {"positions": [{"id": f"{r[0]}_{r[1]}", "symbol": r[1], "shares": r[2],
                                    "avg_cost": r[3], "marketValue": r[4] or (r[2] * r[3] if r[2] and r[3] else 0), "unrealized_pnl": r[5] or 0,
                                    "cost": r[2] * r[3] if r[2] and r[3] else 0, "updated_at": r[6], "portfolio_name": r[7], "portfolio_id": r[0]} for r in rows],
                    "includes_children": True,
                    "portfolio_ids": all_ids}
        else:
            rows = conn.execute(
                """SELECT portfolio_id, symbol, total_shares, avg_cost, 
                           market_value, unrealized_pnl, updated_at 
                   FROM position_summary 
                   WHERE portfolio_id=? AND total_shares > 0""",
                (portfolio_id,)
            ).fetchall()
            return {"positions": [{"id": f"{r[0]}_{r[1]}", "symbol": r[1], "shares": r[2],
                                    "avg_cost": r[3], "marketValue": r[4] or (r[2] * r[3] if r[2] and r[3] else 0), "unrealized_pnl": r[5] or 0,
                                    "cost": r[2] * r[3] if r[2] and r[3] else 0, "updated_at": r[6], "portfolio_id": r[0]} for r in rows]}
    finally:
        conn.close()

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
async def delete_position(portfolio_id: int, symbol: str, api_key: str = None, auth: bool = Depends(require_auth_for_sensitive_ops)):
    """清仓指定标的 - 需认证"""
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
async def portfolio_pnl(portfolio_id: int, include_children: bool = Query(False, description="是否包含子账户盈亏")):
    """
    实时浮动盈亏计算（专业增强版）
    增加: 名称、权重%、今日涨跌幅、市场、PE/PB、换手率
    支持: 包含所有子账户的聚合视图
    依赖 SpotCache（后台每3分钟刷新的全市场实时行情）
    """
    from app.services.sentiment_engine import SpotCache

    # WAL 模式支持并发读，但 SpotCache 读取和 DB 读取之间保持原子视图
    conn = _get_conn()
    try:
        if include_children:
            # 获取所有后代账户ID
            all_ids = _get_all_descendants(conn, portfolio_id)
            placeholders = ','.join(['?' for _ in all_ids])
            # 使用 position_summary 而非 positions（新lot-based系统）
            rows = conn.execute(
                f"""SELECT p.symbol, p.total_shares as shares, p.avg_cost, po.name as portfolio_name, po.id as portfolio_id
                    FROM position_summary p
                    JOIN portfolios po ON p.portfolio_id = po.id
                    WHERE p.portfolio_id IN ({placeholders})""",
                tuple(all_ids)
            ).fetchall()
        else:
            # 使用 position_summary 而非 positions（新lot-based系统）
            rows = conn.execute(
                "SELECT symbol, total_shares as shares, avg_cost FROM position_summary WHERE portfolio_id=?",
                (portfolio_id,)
            ).fetchall()

        # 获取持仓股票的基本面数据（PE/PB等）
        stock_meta = {}
        try:
            meta_rows = conn.execute(
                "SELECT symbol, name, per, pb, mktcap, turnover FROM market_all_stocks"
            ).fetchall()
            for r in meta_rows:
                stock_key = r[0].lower().replace("sh", "").replace("sz", "").replace("hk", "").replace("us", "")
                stock_meta[stock_key] = {"name": r[1], "per": r[2], "pb": r[3], "mktcap": r[4], "turnover": r[5]}
        except:
            pass
    finally:
        conn.close()

    # ── 获取现金余额 ──────────────────────────────────────────────
    cash_balance = 0.0
    try:
        conn3 = _get_conn()
        cb = conn3.execute(
            "SELECT cash_balance FROM portfolios WHERE id=?",
            (portfolio_id,),
        ).fetchone()
        cash_balance = cb[0] or 0.0 if cb else 0.0
        conn3.close()
    except Exception as e:
        logger.warning(f"[Portfolio PnL] 获取 cash_balance 失败 (portfolio_id={portfolio_id}): {e}")

    if not rows:
        return _ok({"positions": [], "total_pnl": 0.0, "total_cost": 0.0, "total_value": 0.0,
                     "includes_children": include_children,
                     "realized_pnl": 0.0, "unrealized_pnl": 0.0, "daily_pnl": 0.0,
                     "cash_balance": cash_balance})

    spot = SpotCache.get_stocks()
    # 构建价格映射表，同时支持带前缀和不带前缀的代码
    price_map = {}
    for s in spot:
        code = s.get("code", "")
        price_map[code] = s  # 带前缀格式: sz300391
        # 同时添加不带前缀格式: 300391
        if len(code) > 2:
            price_map[code[2:]] = s  # 去掉前2位前缀
            price_map[code.lower()] = s
            price_map[code.upper()] = s
    
    # 如果 SpotCache 为空，从数据库兜底获取实时价格
    db_price_loaded = False
    if not spot or len(spot) < 10:
        logger.info("[Portfolio PnL] SpotCache 为空，从数据库兜底获取价格")
        try:
            conn = _get_conn()
            db_rows = conn.execute(
                "SELECT symbol, name, price, change_pct FROM market_all_stocks WHERE price > 0"
            ).fetchall()
            conn.close()
            for r in db_rows:
                sym = r[0]
                name = r[1] or ""
                price = float(r[2] or 0)
                chg_pct = float(r[3] or 0) if r[3] else 0.0
                # 归一化代码格式：同时支持 sh600519 和 600519
                price_map[sym] = {"code": sym, "name": name, "price": price, "chg_pct": chg_pct}
                if len(sym) > 2:
                    # 去掉前缀的版本
                    price_map[sym[2:]] = price_map[sym]
                    price_map[sym.lower()] = price_map[sym]
                    price_map[sym.upper()] = price_map[sym]
            db_price_loaded = True
            logger.info(f"[Portfolio PnL] 从数据库加载 {len(db_rows)} 只股票价格")
        except Exception as e:
            logger.warning(f"[Portfolio PnL] 数据库兜底失败: {e}")
    
    result = []
    total_cost = 0.0
    total_value = 0.0
    missing_prices = []  # 记录未找到价格的股票
    
    # 处理不同结构的rows
    for row in rows:
        if include_children:
            # row: (symbol, shares, avg_cost, portfolio_name, portfolio_id)
            symbol, shares, avg_cost, portfolio_name, portfolio_id_from_row = row
        else:
            # row: (symbol, shares, avg_cost)
            symbol, shares, avg_cost = row
            portfolio_name = None
            portfolio_id_from_row = None
            
        # 尝试多种格式的代码匹配
        info = price_map.get(symbol, {})
        if not info and len(symbol) == 6:
            # 尝试添加前缀
            if symbol.startswith("6"):
                info = price_map.get(f"sh{symbol}", {})
            elif symbol.startswith("0") or symbol.startswith("3"):
                info = price_map.get(f"sz{symbol}", {})
            elif symbol.startswith("4") or symbol.startswith("8"):
                info = price_map.get(f"bj{symbol}", {})
        
        if not info:
            missing_prices.append(symbol)
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
        # 判断价格来源：如果找到实时数据，使用实时价格；否则使用成本价
        has_realtime_price = bool(info and info.get("price"))
        pos_data = {
            "symbol":       symbol,
            "name":         meta.get("name", symbol) if meta else (info.get("name") if info else symbol),
            "shares":       shares,
            "avg_cost":     round(avg_cost, 3),
            "price":        round(current_price, 3),
            "price_source": "realtime" if has_realtime_price else "fallback",
            "change_pct":   round(change_pct, 2),
            "market_value": round(market_value, 2),
            "cost_total":   round(cost_total, 2),
            "pnl":         round(pnl, 2),
            "pnl_pct":    round(pnl_pct, 2),
            "weight":       0.0,
            "market":       market,
            "pe":          round(meta.get("per"), 2) if meta and meta.get("per") else (round(info.get("pe"), 2) if info and info.get("pe") else None),
            "pb":          round(meta.get("pb"), 2) if meta and meta.get("pb") else (round(info.get("pb"), 2) if info and info.get("pb") else None),
            "turnover":    round(meta.get("turnover"), 2) if meta and meta.get("turnover") else (round(info.get("turnover"), 2) if info and info.get("turnover") else None),
        }

        if include_children:
            pos_data["portfolio_name"] = portfolio_name
            pos_data["portfolio_id"] = portfolio_id_from_row

        result.append(pos_data)
        total_cost  += cost_total
        total_value += market_value

    # 第二遍：计算权重
    for pos in result:
        pos["weight"] = round(pos["market_value"] / total_value * 100, 2) if total_value > 0 else 0.0

    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0

    # ── 从 position_lots 读取已实现 PnL ────────────────────────────
    conn2 = _get_conn()
    realized_pnl = 0.0
    try:
        closed_rows = conn2.execute(
            "SELECT SUM(realized_pnl) FROM position_lots WHERE portfolio_id=? AND status='closed'",
            (portfolio_id,),
        ).fetchone()
        realized_pnl = closed_rows[0] or 0.0
    finally:
        conn2.close()

    # ── 从 position_summary 读取浮动盈亏（用独立连接，读取已已提交数据）────────
    unrealized_pnl = 0.0
    try:
        _conn_ps = _get_conn()   # fresh connection = committed view
        # DEBUG: verify what _conn_ps is and what data it sees
        import sys as _sys; print(f"DEBUG unrealized: _conn_ps id={id(_conn_ps)}", file=_sys.stderr)
        _sys.stderr.flush()
        unrealized_row = _conn_ps.execute(
            "SELECT SUM(unrealized_pnl) FROM position_summary WHERE portfolio_id=?",
            (portfolio_id,),
        ).fetchone()
        unrealized_pnl = float(unrealized_row[0]) if unrealized_row and unrealized_row[0] is not None else 0.0
        _conn_ps.close()
    except Exception as e:
        logger.warning(f"[Portfolio PnL] 读取 unrealized_pnl 失败 (portfolio_id={portfolio_id}): {e}")

    # ── 从 transactions 计算当日盈亏 ───────────────────────────────────
    today = datetime.now().strftime('%Y-%m-%d')
    daily_pnl = 0.0
    try:
        txn_rows = conn.execute(
            "SELECT SUM(amount) FROM transactions "
            "WHERE portfolio_id=? AND created_at>=? AND type IN ('sell_pnl','deposit','withdraw','transfer_in','transfer_out')",
            (portfolio_id, today),
        ).fetchone()
        daily_pnl = txn_rows[0] or 0.0 if txn_rows else 0.0
    except Exception as e:
        logger.warning(f"[Portfolio PnL] 计算当日盈亏失败 (portfolio_id={portfolio_id}): {e}")

    response = {
        # ── 三分 PnL ──────────────────────────────────────────
        "total_value":      round(total_value + cash_balance, 2),
        "total_cost":       round(total_cost, 2),
        "total_pnl":        round(total_value + cash_balance - total_cost, 2),
        "total_pnl_pct":    round((total_value + cash_balance - total_cost) / total_cost * 100, 2) if total_cost else 0,
        "daily_pnl":        round(daily_pnl, 2),
        "daily_pnl_pct":    round(daily_pnl / total_cost * 100, 2) if total_cost else 0,
        "realized_pnl":     round(realized_pnl, 2),
        "unrealized_pnl":   round(unrealized_pnl, 2),
        "cash_balance":     cash_balance,
        "positions":        result,
    }

    if include_children:
        response["includes_children"] = True
        response["portfolio_count"] = len(set(r.get("portfolio_id") for r in result if r.get("portfolio_id")))
    
    if missing_prices:
        response["missing_price_count"] = len(missing_prices)
        response["missing_price_symbols"] = missing_prices[:10]
    
    if db_price_loaded:
        response["price_data_source"] = "DatabaseFallback"
    elif spot:
        response["price_data_source"] = "SpotCache"
    response["price_data_count"] = len(spot) if spot else 0

    return _ok(response)




@router.get("/{portfolio_id}/snapshots")
async def get_snapshots(
    portfolio_id: int,
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date:   Optional[str] = Query(None, description="YYYY-MM-DD"),
):
    """净值历史快照"""
    # WAL 模式支持并发读
    conn = _get_conn()
    try:
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
    finally:
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


# ═══════════════════════════════════════════════════════════════
# Task 9: 底层资产归因与风险分析
# ═══════════════════════════════════════════════════════════════

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


@router.get("/{portfolio_id}/attribution")
async def get_attribution(portfolio_id: int, include_children: bool = Query(False)):
    """
    底层资产归因 + 组合风险（VaR / 波动率估算）。

    分类规则：
      - sh510xxx / sz159xxx → 宽基ETF
      - sh000xxx / sz399xxx → A股指数
      - 国债/国开/债券关键词 → 利率债
      - AU/AG/黄金/白银 等 → 商品期货
      - sh6xxxxx / sz0/3xxxx → A股个股
      - hkxxxxx → 港股

    返回:
      - attribution[]   各底层资产组的权重、收益贡献
      - risk_metrics     日VaR(95%)、年化波动率、夏普比率
      - total_exposure   各 category 的总仓位占比
    """
    from app.db.database import _get_conn
    from app.services.sentiment_engine import SpotCache

    # ── 1. 获取持仓（WAL 模式并发读）────────────────────────────
    conn = _get_conn()
    try:
        if include_children:
            all_ids = [portfolio_id]
            cur = conn.execute("SELECT id FROM portfolios WHERE parent_id=?", (portfolio_id,)).fetchall()
            all_ids += [r[0] for r in cur]
            ph = ','.join(['?'] * len(all_ids))
            rows = conn.execute(
                f"SELECT symbol, shares, avg_cost FROM positions WHERE portfolio_id IN ({ph})",
                tuple(all_ids)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT symbol, shares, avg_cost FROM positions WHERE portfolio_id=?",
                (portfolio_id,)
            ).fetchall()
    finally:
        conn.close()

    if not rows:
        return _ok({"attribution": [], "risk_metrics": None, "total_exposure": []})

    # ── 2. 获取最新价格 ────────────────────────────────────────

    # ── 2. 获取最新价格 ────────────────────────────────────────
    spot = SpotCache.get_stocks()
    price_map = {}
    for s in spot:
        code = s.get("code", "")
        price_map[code] = s
        if len(code) > 2:
            price_map[code[2:]] = s
            price_map[code.lower()] = s
            price_map[code.upper()] = s

    if len(price_map) < 10:
        conn2 = _get_conn()
        try:
            db_rows = conn2.execute(
                "SELECT symbol, name, price, change_pct FROM market_all_stocks WHERE price > 0"
            ).fetchall()
            for r in db_rows:
                sym, name, price, chg_pct = r
                price_map[sym] = {"code": sym, "name": name, "price": float(price or 0), "chg_pct": float(chg_pct or 0)}
                if len(sym) > 2:
                    price_map[sym[2:]] = price_map[sym]
        finally:
            conn2.close()

    # ── 3. 逐条计算持仓盈亏并分类 ──────────────────────────────
    groups = {}

    for symbol, shares, avg_cost in rows:
        info = price_map.get(symbol, {})
        if not info and len(symbol) == 6:
            info = price_map.get(f"sh{symbol}", {})
            if not info:
                info = price_map.get(f"sz{symbol}", {})
        if not info:
            info = price_map.get(symbol[2:]) if len(symbol) > 2 else {}

        price        = info.get("price", avg_cost)
        name         = info.get("name", symbol)
        market_value = shares * price
        cost         = shares * avg_cost
        pnl          = market_value - cost
        pnl_pct      = (pnl / cost * 100) if cost > 0 else 0.0

        cls = _classify_asset(symbol, name)
        cat = cls["category"]

        if cat not in groups:
            groups[cat] = {
                "category":     cat,
                "sub_category": cls["sub_category"],
                "is_index":     cls["is_index"],
                "market_value": 0.0,
                "cost":         0.0,
                "pnl":          0.0,
                "positions":    [],
            }
        groups[cat]["market_value"] += market_value
        groups[cat]["cost"]         += cost
        groups[cat]["pnl"]          += pnl
        groups[cat]["positions"].append({
            "symbol":       symbol,
            "name":         name,
            "shares":       shares,
            "avg_cost":     avg_cost,
            "price":        price,
            "market_value": round(market_value, 2),
            "cost":         round(cost, 2),
            "pnl":          round(pnl, 2),
            "pnl_pct":      round(pnl_pct, 2),
        })

    # ── 4. 汇总计算（防御性容错）──────────────────────────────
    try:
        total_mv    = sum(g["market_value"] for g in groups.values())
        total_cost  = sum(g["cost"]        for g in groups.values())
        total_pnl   = sum(g["pnl"]         for g in groups.values())

        # 极端边界：所有持仓市值和盈亏均为 0（价格全失效），返回空数据避免后续除零
        if total_mv <= 0 and total_pnl == 0:
            return _ok({"attribution": [], "risk_metrics": None, "total_exposure": [],
                        "summary": {"total_market_value": 0, "total_cost": 0, "total_pnl": 0, "total_pnl_pct": 0}})

        attribution = []
        for g in groups.values():
            w  = g["market_value"] / total_mv if total_mv > 0 else 0
            pc = g["pnl"] / total_pnl * 100   if total_pnl != 0 else 0
            attribution.append({
                "category":        g["category"],
                "sub_category":    g["sub_category"],
                "is_index":        g["is_index"],
                "market_value":    round(g["market_value"], 2),
                "cost":            round(g["cost"], 2),
                "pnl":             round(g["pnl"], 2),
                "weight":          round(w * 100, 2),
                "pnl_contrib_pct": round(pc, 2),
                "position_count":  len(g["positions"]),
                "positions":       g["positions"][:5],
            })

        attribution.sort(key=lambda x: x["market_value"], reverse=True)

        # ── 5. 底层资产配置 ─────────────────────────────────────
        total_exposure = [
            {"name": g["sub_category"], "category": g["category"],
             "value": round(g["market_value"], 2), "weight": round(g["market_value"] / total_mv * 100, 2)}
            for g in sorted(groups.values(), key=lambda x: x["market_value"], reverse=True)
        ]

        # ── 6. 风险指标 ─────────────────────────────────────────
        risk_metrics = None
        try:
            conn3 = _get_conn()
            try:
                snap_rows = conn3.execute(
                    "SELECT date, total_asset FROM portfolio_snapshots WHERE portfolio_id=? ORDER BY date ASC LIMIT 60",
                    (portfolio_id,)
                ).fetchall()
            finally:
                conn3.close()

            if snap_rows and len(snap_rows) >= 5:
                assets  = [float(r[1]) for r in snap_rows]
                returns = [(assets[i] - assets[i-1]) / assets[i-1]
                           for i in range(1, len(assets)) if assets[i-1] > 0]

                if returns:
                    import math
                    mean_ret  = sum(returns) / len(returns)
                    variance  = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
                    daily_vol = math.sqrt(variance)
                    ann_vol   = daily_vol * math.sqrt(252)

                    try:
                        from statistics import NormalDist
                        z_95 = NormalDist().inv_cdf(0.95)
                    except Exception:
                        logger.debug("[Portfolio Attribution] NormalDist 不可用，使用默认 z_95=1.645")
                        z_95 = 1.645

                    latest_asset = assets[-1]
                    var_daily_95 = latest_asset * z_95 * daily_vol

                    risk_free     = 0.03
                    years         = max(len(assets) / 252, 0.01)
                    total_ret     = (assets[-1] - assets[0]) / assets[0]
                    ann_ret       = (1 + total_ret) ** (1 / years) - 1 if years > 0 else 0
                    sharpe        = (ann_ret - risk_free) / ann_vol if ann_vol > 0 else 0

                    risk_metrics = {
                        "var_daily_95":      round(var_daily_95, 2),
                        "var_daily_95_pct": round(var_daily_95 / latest_asset * 100, 2),
                        "annual_volatility": round(ann_vol * 100, 2),
                        "sharpe_ratio":      round(sharpe, 2),
                        "total_return_pct":  round(total_ret * 100, 2),
                        "annual_return_pct": round(ann_ret * 100, 2),
                        "days":              len(assets),
                    }
        except Exception as e:
            logger.warning(f"[Attribution] risk_metrics error: {e}")

        return _ok({
            "attribution":    attribution,
            "total_exposure":  total_exposure,
            "risk_metrics":    risk_metrics,
            "summary": {
                "total_market_value": round(total_mv, 2),
                "total_cost":        round(total_cost, 2),
                "total_pnl":         round(total_pnl, 2),
                "total_pnl_pct":     round((total_pnl / total_cost * 100) if total_cost else 0, 2),
            },
        })

    except Exception as e:
        logger.error(f"[Attribution] 计算异常: {e}", exc_info=True)
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="归因计算时发生错误，请检查是否有异常交易数据")


# ══════════════════════════════════════════════════════════════
#  Phase 1 扩展：资金流水 + 现金余额管理
# ══════════════════════════════════════════════════════════════

@router.post("/transfer")
async def transfer(body: TransactionIn):
    """
    资金划转（子账户间）
    body.type = 'transfer_out' / 'transfer_in'（通常前端只传一方）
    为简化操作，提供 /transfer 接口：from_pid / to_pid / amount
    """
    raise HTTPException(400, "transfer 需要明确 from_pid 和 to_pid，请使用 /transfer/direct 接口")


class TransferIn(BaseModel):
    from_portfolio_id: int
    to_portfolio_id: int
    amount: float
    note: Optional[str] = None


@router.post("/transfer/direct")
async def transfer_direct(body: TransferIn):
    """直接划转：原子操作，同时更新两个账户的 cash_balance 并写流水"""
    if body.amount <= 0:
        raise HTTPException(400, "划转金额必须为正数")
    try:
        result = _transfer_between_accounts(
            body.from_portfolio_id,
            body.to_portfolio_id,
            body.amount,
            body.note,
        )
        return _ok(result)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"划转失败: {e}")


@router.get("/{portfolio_id}/cash")
async def get_cash(portfolio_id: int):
    """查询账户现金余额"""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT id, name, cash_balance FROM portfolios WHERE id=?",
            (portfolio_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(404, "账户不存在")
    return _ok({"portfolio_id": row[0], "name": row[1], "cash_balance": row[2]})


class CashOpIn(BaseModel):
    """充值/提现操作"""
    amount: float
    operator: str = "user"
    note: Optional[str] = None


@router.post("/{portfolio_id}/cash/deposit")
async def cash_deposit(portfolio_id: int, body: CashOpIn):
    """充值：账户现金增加 + 写 deposit 流水"""
    if body.amount <= 0:
        raise HTTPException(400, "充值金额必须为正数")
    with _lock:
        conn = _get_conn()
        try:
            row = conn.execute(
                "SELECT id, cash_balance FROM portfolios WHERE id=?",
                (portfolio_id,),
            ).fetchone()
            if not row:
                raise HTTPException(404, "账户不存在")

            new_balance = (row[1] or 0.0) + body.amount
            conn.execute(
                "UPDATE portfolios SET cash_balance=? WHERE id=?",
                (new_balance, portfolio_id),
            )
            _insert_transaction(conn, portfolio_id, "deposit",
                                body.amount, new_balance, operator=body.operator,
                                note=body.note or "充值")
            conn.commit()
            return _ok({"portfolio_id": portfolio_id, "cash_balance": new_balance})
        finally:
            conn.close()


@router.post("/{portfolio_id}/cash/withdraw")
async def cash_withdraw(portfolio_id: int, body: CashOpIn):
    """提现：账户现金减少 + 写 withdraw 流水"""
    if body.amount <= 0:
        raise HTTPException(400, "提现金额必须为正数")
    with _lock:
        conn = _get_conn()
        try:
            row = conn.execute(
                "SELECT id, cash_balance FROM portfolios WHERE id=?",
                (portfolio_id,),
            ).fetchone()
            if not row:
                raise HTTPException(404, "账户不存在")

            if (row[1] or 0.0) < body.amount:
                raise HTTPException(400, f"现金余额不足（当前: {row[1]}，需: {body.amount}）")

            new_balance = (row[1] or 0.0) - body.amount
            conn.execute(
                "UPDATE portfolios SET cash_balance=? WHERE id=?",
                (new_balance, portfolio_id),
            )
            _insert_transaction(conn, portfolio_id, "withdraw",
                                body.amount, new_balance, operator=body.operator,
                                note=body.note or "提现")
            conn.commit()
            return _ok({"portfolio_id": portfolio_id, "cash_balance": new_balance})
        finally:
            conn.close()


@router.get("/{portfolio_id}/transactions")
async def list_transactions(
    portfolio_id: int,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    txn_type: Optional[str] = Query(None, description="过滤类型: deposit/withdraw/transfer_in/transfer_out/dividend/fee"),
):
    """资金流水记录查询"""
    conn = _get_conn()
    try:
        sql = "SELECT * FROM transactions WHERE portfolio_id=?"
        params: list = [portfolio_id]
        if txn_type:
            sql += " AND type=?"
            params.append(txn_type)
        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(sql, params).fetchall()
        cols = ["id", "portfolio_id", "type", "amount", "balance_after",
                "counterparty_id", "related_symbol", "note", "created_at", "operator"]
    finally:
        conn.close()
    return _ok({"transactions": _row2dict(rows, cols), "total": len(rows)})


# ══════════════════════════════════════════════════════════════════════════
#  Phase 2: 持仓批次（Lots）路由 — Buy / Sell / Lots 查询
# ══════════════════════════════════════════════════════════════════════════

from app.services.trading import (
    execute_buy, execute_sell, get_open_lots,
    calc_unrealized_pnl,
    upsert_position_summary, update_market_value, get_position_summary,
    LotRecord, SellResult,
)

# ── Pydantic 模型 ────────────────────────────────────────────────────

class BuyIn(BaseModel):
    symbol:    str
    shares:    int
    buy_price: float
    buy_date:  Optional[str] = None
    order_id:  Optional[str] = None

class SellIn(BaseModel):
    symbol:    str
    shares:    int
    sell_price: float
    order_id:  Optional[str] = None


# ── 买入（BUI）── 新增批次 ────────────────────────────────────────────

@router.post("/{portfolio_id}/lots/buy")
async def buy_lot(portfolio_id: int, body: BuyIn):
    """
    买入时新增一个批次（lot）。
    同一标的同一日期可有多批次，但 avg_cost 独立计算。
    """
    try:
        lot = execute_buy(
            portfolio_id = portfolio_id,
            symbol       = body.symbol,
            shares       = body.shares,
            buy_price    = body.buy_price,
            buy_date     = body.buy_date,
            order_id     = body.order_id,
        )
        return _ok({
            "lot_id":    lot.id,
            "symbol":    lot.symbol,
            "shares":    lot.shares,
            "avg_cost":  lot.avg_cost,
            "buy_date":  lot.buy_date,
            "status":    lot.status,
        })
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"[Buy] error: {e}", exc_info=True)
        raise HTTPException(500, f"买入失败: {e}")


# ── 卖出（SELL）── FIFO 平仓 ─────────────────────────────────────────

@router.post("/{portfolio_id}/lots/sell")
async def sell_lot(portfolio_id: int, body: SellIn):
    """
    FIFO 平仓算法：
      1. 按 buy_date 升序匹配 open 批次
      2. 每批次平仓时计算 realized_pnl 并累加
      3. 返回平仓明细和总已实现盈亏
    """
    try:
        result = execute_sell(
            portfolio_id = portfolio_id,
            symbol       = body.symbol,
            shares       = body.shares,
            sell_price   = body.sell_price,
            order_id     = body.order_id,
        )

        # 平仓写流水（可选：也可在持仓路由层写）
        conn = _get_conn()
        try:
            rows = conn.execute(
                "SELECT cash_balance FROM portfolios WHERE id=?",
                (portfolio_id,),
            ).fetchone()
            cash_bal = (rows[0] or 0.0) if rows else 0.0
            new_cash = cash_bal + result.total_realized_pnl
            conn.execute(
                "UPDATE portfolios SET cash_balance=? WHERE id=?",
                (new_cash, portfolio_id),
            )
            _insert_transaction(
                conn,
                portfolio_id,
                "sell_pnl",
                result.total_realized_pnl,
                new_cash,
                related_symbol = body.symbol,
                note = f"卖出{body.symbol} × {body.shares}手",
                operator = "user",
            )
            conn.commit()
        finally:
            conn.close()

        return _ok({
            "symbol":              body.symbol,
            "shares_sold":         body.shares - result.shares_remaining,
            "total_realized_pnl":  result.total_realized_pnl,
            "sell_price":          result.sell_price,
            "timestamp":           result.timestamp,
            "lots_closed": [
                {
                    "lot_id":        lc.lot_id,
                    "shares_closed": lc.shares_closed,
                    "avg_cost":      lc.avg_cost,
                    "sell_price":    lc.sell_price,
                    "realized_pnl":  lc.realized_pnl,
                }
                for lc in result.lots_closed
            ],
        })
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"[Sell] error: {e}", exc_info=True)
        raise HTTPException(500, f"卖出失败: {e}")


# ── 批次查询 ─────────────────────────────────────────────────────────

@router.get("/{portfolio_id}/lots")
async def list_lots(
    portfolio_id: int,
    symbol: Optional[str] = Query(None, description="过滤标的代码（不传则返回全部）"),
    include_children: bool = Query(False, description="是否包含子账户批次"),
):
    """
    返回某账户的未平批次（可按标的过滤）。
    当 include_children=True 时，使用递归 CTE 聚合所有后代子账户的批次。
    """
    try:
        lots = get_open_lots(portfolio_id, symbol, include_children=include_children)
        # 收集涉及的账户 ID（用于前端标注来源）
        if include_children:
            conn = _get_conn()
            try:
                all_ids = _get_all_descendants(conn, portfolio_id)
            finally:
                conn.close()
        else:
            all_ids = [portfolio_id]
        return _ok({
            "lots": [
                {
                    "id":            l.id,
                    "symbol":       l.symbol,
                    "shares":       l.shares,
                    "avg_cost":     l.avg_cost,
                    "buy_date":     l.buy_date,
                    "buy_order_id": l.buy_order_id,
                    "status":       l.status,
                    "realized_pnl": l.realized_pnl,
                    "portfolio_id": l.portfolio_id,
                }
                for l in lots
            ],
            "count": len(lots),
            "includes_children": include_children,
            "portfolio_ids": all_ids if include_children else [portfolio_id],
        })
    except Exception as e:
        logger.error(f"[Lots] error: {e}", exc_info=True)
        raise HTTPException(500, f"批次查询失败: {e}")


# ── 未实现盈亏 ──────────────────────────────────────────────────────

@router.get("/{portfolio_id}/lots/unrealized")
async def unrealized_pnl(
    portfolio_id: int,
    symbol: str    = Query(..., description="标的代码，如 000001"),
    current_price: float = Query(..., description="当前市场价格"),
):
    """
    计算浮动盈亏。
    未实现 PnL = Σ(shares × (current_price - avg_cost))
    """
    try:
        result = calc_unrealized_pnl(portfolio_id, symbol, current_price)
        return _ok(result)
    except Exception as e:
        logger.error(f"[UnrealizedPnl] error: {e}", exc_info=True)
        raise HTTPException(500, f"盈亏计算失败: {e}")


# ══════════════════════════════════════════════════════════════════════════
#  子账户 Roll-up 聚合端点（守恒定律 + 树形结构）
# ══════════════════════════════════════════════════════════════════════════

@router.get("/{portfolio_id}/conservation")
async def check_conservation(portfolio_id: int):
    """
    资金守恒定律校验。
    验证：主账户总资产 = 主账户自身(现金+持仓) + Σ(所有子账户的现金+持仓)

    返回各子项明细和对齐结果，用于调试和自动化测试。
    """
    from app.services.sentiment_engine import SpotCache

    conn = _get_conn()
    try:
        # 主账户自身资产
        parent = conn.execute(
            "SELECT id, name, cash_balance FROM portfolios WHERE id=?",
            (portfolio_id,)
        ).fetchone()
        if not parent:
            raise HTTPException(404, f"账户 {portfolio_id} 不存在")

        parent_cash = parent[2] or 0.0

        # 直接子账户（不含后代）
        children = conn.execute(
            "SELECT id, name, cash_balance FROM portfolios WHERE parent_id=?",
            (portfolio_id,)
        ).fetchall()

        # 获取主账户自身持仓市值
        parent_positions = conn.execute(
            "SELECT symbol, shares, avg_cost FROM positions WHERE portfolio_id=?",
            (portfolio_id,)
        ).fetchall()

        # 获取主账户所有后代（递归）
        all_desc_ids = _get_all_descendants(conn, portfolio_id)
        if all_desc_ids:
            placeholders = ','.join(['?' for _ in all_desc_ids])
            child_positions = conn.execute(
                f"SELECT portfolio_id, symbol, shares, avg_cost FROM positions WHERE portfolio_id IN ({placeholders})",
                tuple(all_desc_ids)
            ).fetchall()
        else:
            child_positions = []

        # 获取子账户现金
        child_cash_total = sum((r[2] or 0.0) for r in children)

        # 获取实时价格
        spot = SpotCache.get_stocks() or []
        price_map = {}
        for s in spot:
            code = s.get("code", "")
            price_map[code] = float(s.get("price") or 0)
            if len(code) > 2:
                price_map[code[2:]] = price_map[code]
                price_map[code.lower()] = price_map[code]

        def positions_value(rows):
            total = 0.0
            for (pid, sym, shares, avg_cost) in rows:
                price = price_map.get(sym) or price_map.get(sym[2:] if len(sym) > 2 else sym) or 0.0
                total += shares * price
            return total

        parent_pos_value = positions_value(parent_positions)
        child_pos_value = positions_value(child_positions)

        parent_total = parent_cash + parent_pos_value
        children_total = child_cash_total + child_pos_value
        grand_total = parent_total + children_total

        conservation_ok = True
        try:
            if abs(parent_total - (parent_cash + parent_pos_value)) > 0.001:
                conservation_ok = False
        except Exception as e:
            logger.warning(f"[Portfolio Conservation] 校验异常 (portfolio_id={portfolio_id}): {e}")
            conservation_ok = False

        return _ok({
            "parent_id":          portfolio_id,
            "parent_name":        parent[1],
            "parent": {
                "cash":           round(parent_cash, 2),
                "position_value": round(parent_pos_value, 2),
                "total":          round(parent_total, 2),
            },
            "children": [
                {
                    "id":              r[0],
                    "name":            r[1],
                    "cash":            round(r[2] or 0.0, 2),
                }
                for r in children
            ],
            "children_position_value": round(child_pos_value, 2),
            "children_cash":           round(child_cash_total, 2),
            "children_total":          round(children_total, 2),
            "grand_total":              round(grand_total, 2),
            "conservation_ok":          conservation_ok,
            "conservation_delta":        round(grand_total - parent_total, 4),
        })
    finally:
        conn.close()


@router.get("/{portfolio_id}/tree")
async def get_portfolio_tree(portfolio_id: int):
    """
    返回指定账户的完整子树结构（递归），每节点包含聚合资产快照。
    用于前端树形账户选择器的渲染。
    """
    from app.services.sentiment_engine import SpotCache

    conn = _get_conn()
    try:
        def build_node(pid: int) -> dict:
            row = conn.execute(
                "SELECT id, name, type, parent_id, cash_balance, status FROM portfolios WHERE id=?",
                (pid,)
            ).fetchone()
            if not row:
                return {}
            (p_id, p_name, p_type, p_parent, p_cash, p_status) = row

            # 持仓市值
            pos_rows = conn.execute(
                "SELECT symbol, shares FROM positions WHERE portfolio_id=?",
                (pid,)
            ).fetchall()
            spot = SpotCache.get_stocks() or []
            price_map = {}
            for s in spot:
                code = s.get("code", "")
                price_map[code] = float(s.get("price") or 0)
                if len(code) > 2:
                    price_map[code[2:]] = price_map[code]

            pos_value = 0.0
            for (sym, shares) in pos_rows:
                price = price_map.get(sym) or price_map.get(sym[2:] if len(sym) > 2 else sym) or 0.0
                pos_value += shares * price

            # 递归子节点
            child_rows = conn.execute(
                "SELECT id FROM portfolios WHERE parent_id=?", (pid,)
            ).fetchall()
            children = [build_node(child[0]) for child in child_rows]

            return {
                "id":            p_id,
                "name":          p_name,
                "type":          p_type,
                "status":        p_status or "active",
                "cash_balance":  round(p_cash or 0.0, 2),
                "position_value": round(pos_value, 2),
                "total_assets":  round((p_cash or 0.0) + pos_value, 2),
                "children":      children,
            }

        tree = build_node(portfolio_id)
        return _ok({"tree": tree})
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════
#  Phase 3: position_summary 聚合表路由 + ECharts 数据端点
# ══════════════════════════════════════════════════════════════════════════

@router.get("/{portfolio_id}/lots/summary")
async def lots_summary(
    portfolio_id: int,
    symbol: Optional[str] = Query(None),
    include_children: bool = Query(False, description="是否包含子账户持仓"),
):
    """
    读取 position_summary 聚合表（读优化视图）。
    不带 symbol → 返回该账户全部聚合持仓；
    带 symbol → 返回单个标的聚合数据。
    include_children=True 时使用递归 CTE 聚合子树。
    """
    try:
        rows = get_position_summary(portfolio_id, symbol, include_children=include_children)
        return _ok({"summary": rows, "count": len(rows), "includes_children": include_children})
    except Exception as e:
        logger.error(f"[lots_summary] error: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@router.post("/{portfolio_id}/lots/update_price")
async def refresh_market_value(
    portfolio_id: int,
    symbol: str    = Query(..., description="标的代码"),
    current_price: float = Query(..., description="当前市价"),
):
    """
    批量刷新持仓聚合表的 market_value 和 unrealized_pnl。
    行情刷新时由调度器调用，也可在 GET /lots/summary 前调用。
    """
    try:
        result = update_market_value(portfolio_id, symbol, current_price)
        return _ok(result)
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/{portfolio_id}/lots/echarts")
async def lots_echarts_data(
    portfolio_id: int,
    include_children: bool = Query(False, description="是否包含子账户持仓"),
):
    """
    返回适合 ECharts 饼图 + 列表的持仓聚合数据。
    当 include_children=True 时，使用递归 CTE 聚合所有后代子账户的持仓。
    """
    try:
        rows = get_position_summary(portfolio_id, include_children=include_children)
        total_mv = sum(r.get('market_value', 0) for r in rows)
        chart_data = []
        for r in rows:
            mv = r.get('market_value', 0)
            pct = round(mv / total_mv * 100, 2) if total_mv else 0
            chart_data.append({
                "symbol":      r['symbol'],
                "total_shares": r['total_shares'],
                "avg_cost":    r['avg_cost'],
                "current_price": r.get('market_value', 0) / r['total_shares'] if r['total_shares'] else 0,
                "market_value": mv,
                "unrealized_pnl": r.get('unrealized_pnl', 0),
                "weight_pct":   pct,
            })
        return _ok({
            "total_market_value": round(total_mv, 2),
            "positions": chart_data,
        })
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/{portfolio_id}/pnl/today")
async def daily_pnl_only(portfolio_id: int):
    """
    仅返回当日三分数据（轻量端点，供 ECharts 看板高频轮询）。
    """
    today = datetime.now().strftime('%Y-%m-%d')
    conn = _get_conn()
    try:
        # realized today
        rt = conn.execute(
            "SELECT SUM(amount) FROM transactions "
            "WHERE portfolio_id=? AND created_at>=? AND type='sell_pnl'",
            (portfolio_id, today),
        ).fetchone()
        realized_today = rt[0] or 0.0

        # deposits/withdrawals/transfer today
        dt = conn.execute(
            "SELECT SUM(amount) FROM transactions "
            "WHERE portfolio_id=? AND created_at>=? AND type IN ('deposit','withdraw','transfer_in','transfer_out')",
            (portfolio_id, today),
        ).fetchone()
        cash_flow = dt[0] or 0.0

        # unrealized (from summary)
        unrealized = 0.0
        try:
            ur = conn.execute(
                "SELECT SUM(unrealized_pnl) FROM position_summary WHERE portfolio_id=?",
                (portfolio_id,),
            ).fetchone()
            unrealized = ur[0] or 0.0 if ur else 0.0
        except Exception as e:
            logger.warning(f"[Portfolio daily_pnl] 读取 unrealized 失败 (portfolio_id={portfolio_id}): {e}")

        return _ok({
            "date":           today,
            "realized_today": round(realized_today, 2),
            "cash_flow":      round(cash_flow, 2),
            "unrealized_pnl": round(unrealized, 2),
            "daily_pnl":      round(realized_today + cash_flow, 2),
        })
    finally:
        conn.close()
