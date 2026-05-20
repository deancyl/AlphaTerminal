"""
Position-related endpoints for Portfolio Router

This module contains all position management endpoints:
- GET /{portfolio_id}/positions - List positions
- POST /positions - Add/update position
- DELETE /{portfolio_id}/positions/{symbol} - Remove position
- GET /{portfolio_id}/pnl - Real-time PnL calculation
- GET /{portfolio_id}/pnl/today - Today's PnL
- GET /{portfolio_id}/snapshots - List snapshots
- POST /{portfolio_id}/snapshots - Create snapshot

Dependencies:
- .schemas: Pydantic models
- app.db.database: Database connection utilities
- app.services.sentiment_engine: SpotCache for real-time prices
"""

import asyncio
import logging
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends

from app.db.database import _get_conn, _lock
from app.utils.response import success_response
from app.middleware import require_api_key

logger = logging.getLogger(__name__)

# Import schemas from .schemas
from .schemas import PositionIn

# Timeout constant for all portfolio endpoints
PORTFOLIO_TIMEOUT = 30  # seconds

# Shared thread pool for non-blocking SQLite operations
_portfolio_executor = ThreadPoolExecutor(max_workers=20, thread_name_prefix="portfolio_")

# ── Helper Functions ─────────────────────────────────────────────

def _row2dict(rows, cols):
    """Convert database rows to list of dictionaries."""
    return [dict(zip(cols, r)) for r in rows]


def _get_all_descendants(conn, portfolio_id: int, visited: set = None) -> list:
    """
    Recursively get all descendant account IDs (children and grandchildren, not self).
    Uses visited set to prevent circular nesting.
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


# ── Router (no prefix - will be mounted under /portfolio) ─────────────────────────────────────────────

router = APIRouter(tags=["portfolio"])


# ── Position CRUD ─────────────────────────────────────────────────

@router.get("/{portfolio_id}/positions")
async def list_positions(
    portfolio_id: int,
    include_children: bool = Query(False, description="是否包含子账户持仓"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of positions to return"),
    offset: int = Query(0, ge=0, description="Number of positions to skip"),
):
    """账户当前持仓，可选包含所有子账户持仓"""
    def _sync_work():
        conn = _get_conn()
        try:
            if include_children:
                all_ids = _get_all_descendants(conn, portfolio_id)
                if not all_ids:
                    return success_response({
                        "positions": [],
                        "pagination": {
                            "limit": limit,
                            "offset": offset,
                            "total": 0,
                            "has_more": False
                        },
                        "includes_children": True,
                        "portfolio_ids": []
                    })
                placeholders = ','.join(['?' for _ in all_ids])
                total_row = conn.execute(
                    f"""SELECT COUNT(*) FROM position_summary ps
                        WHERE ps.portfolio_id IN ({placeholders}) AND ps.total_shares > 0""",
                    tuple(all_ids)
                ).fetchone()
                total_count = total_row[0] if total_row else 0
                rows = conn.execute(
                    f"""SELECT ps.portfolio_id, ps.symbol, ps.total_shares, ps.avg_cost, 
                               ps.market_value, ps.unrealized_pnl, ps.updated_at,
                               po.name as portfolio_name
                        FROM position_summary ps
                        JOIN portfolios po ON ps.portfolio_id = po.id
                        WHERE ps.portfolio_id IN ({placeholders}) AND ps.total_shares > 0
                        ORDER BY ps.symbol ASC
                        LIMIT ? OFFSET ?""",
                    tuple(all_ids) + (limit, offset)
                ).fetchall()
                
                positions = [{"id": f"{r[0]}_{r[1]}", "symbol": r[1], "shares": r[2],
                        "avg_cost": r[3], "marketValue": r[4] or (r[2] * r[3] if r[2] and r[3] else 0), "unrealized_pnl": r[5] or 0,
                        "cost": r[2] * r[3] if r[2] and r[3] else 0, "updated_at": r[6], "portfolio_name": r[7], "portfolio_id": r[0]} for r in rows]
                
                return success_response({
                    "positions": positions,
                    "pagination": {
                        "limit": limit,
                        "offset": offset,
                        "total": total_count,
                        "has_more": offset + len(positions) < total_count
                    },
                    "includes_children": True,
                    "portfolio_ids": all_ids
                })
            else:
                total_row = conn.execute(
                    """SELECT COUNT(*) FROM position_summary
                       WHERE portfolio_id=? AND total_shares > 0""",
                    (portfolio_id,)
                ).fetchone()
                total_count = total_row[0] if total_row else 0
                rows = conn.execute(
                    """SELECT portfolio_id, symbol, total_shares, avg_cost, 
                               market_value, unrealized_pnl, updated_at 
                       FROM position_summary 
                       WHERE portfolio_id=? AND total_shares > 0
                       ORDER BY symbol ASC
                       LIMIT ? OFFSET ?""",
                    (portfolio_id, limit, offset)
                ).fetchall()
                
                positions = [{"id": f"{r[0]}_{r[1]}", "symbol": r[1], "shares": r[2],
                        "avg_cost": r[3], "marketValue": r[4] or (r[2] * r[3] if r[2] and r[3] else 0), "unrealized_pnl": r[5] or 0,
                        "cost": r[2] * r[3] if r[2] and r[3] else 0, "updated_at": r[6], "portfolio_id": r[0]} for r in rows]
                
                return success_response({
                    "positions": positions,
                    "pagination": {
                        "limit": limit,
                        "offset": offset,
                        "total": total_count,
                        "has_more": offset + len(positions) < total_count
                    }
                })
        finally:
            conn.close()
    
    async def _inner():
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_portfolio_executor, _sync_work)
    
    try:
        return await asyncio.wait_for(_inner(), timeout=PORTFOLIO_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning("[positions] list_positions timeout after %ds", PORTFOLIO_TIMEOUT)
        raise HTTPException(504, "List positions timeout")


@router.post("/positions")
async def upsert_position(body: PositionIn, _: None = Depends(require_api_key)):
    """
    建仓或调仓：INSERT OR REPLACE
    shares=0 表示清仓（删除持仓）
    同时同步更新 position_summary 表（新lot-based系统）
    """
    def _sync_work():
        now = datetime.now().isoformat()
        with _lock:
            conn = _get_conn()
            if body.shares == 0:
                conn.execute(
                    "DELETE FROM positions WHERE portfolio_id=? AND symbol=?",
                    (body.portfolio_id, body.symbol)
                )
                conn.execute(
                    "DELETE FROM position_summary WHERE portfolio_id=? AND symbol=?",
                    (body.portfolio_id, body.symbol)
                )
                conn.commit()
                conn.close()
                return success_response({"ok": True, "action": "cleared"})
            conn.execute(
                "INSERT OR REPLACE INTO positions (portfolio_id, symbol, shares, avg_cost, updated_at) "
                "VALUES (?,?,?,?,?)",
                (body.portfolio_id, body.symbol, body.shares, body.avg_cost, now)
            )
            conn.execute(
                "INSERT OR REPLACE INTO position_summary (portfolio_id, symbol, total_shares, avg_cost, market_value, unrealized_pnl, updated_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (body.portfolio_id, body.symbol, body.shares, body.avg_cost, 0, 0, now)
            )
            conn.commit()
            conn.close()
        return success_response({"ok": True, "action": "upserted"})
    
    async def _inner():
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_portfolio_executor, _sync_work)
    
    try:
        return await asyncio.wait_for(_inner(), timeout=PORTFOLIO_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning("[positions] upsert_position timeout after %ds", PORTFOLIO_TIMEOUT)
        raise HTTPException(504, "Upsert position timeout")


def require_auth_for_sensitive_ops(api_key: str = None):
    """敏感操作认证（DELETE、include_children）"""
    import os
    configured_key = os.environ.get("PORTFOLIO_API_KEY", "")
    if not configured_key:
        return True
    if api_key != configured_key:
        raise HTTPException(status_code=401, detail="Invalid Portfolio API key")
    return True


@router.delete("/{portfolio_id}/positions/{symbol}")
async def delete_position(portfolio_id: int, symbol: str, _: None = Depends(require_api_key)):
    """清仓指定标的 - 需认证"""
    def _sync_work():
        with _lock:
            conn = _get_conn()
            cur = conn.execute(
                "DELETE FROM positions WHERE portfolio_id=? AND symbol=?",
                (portfolio_id, symbol)
            )
            conn.commit()
            conn.close()
        return success_response({"ok": True})
    
    async def _inner():
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_portfolio_executor, _sync_work)
    
    try:
        return await asyncio.wait_for(_inner(), timeout=PORTFOLIO_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning("[positions] delete_position timeout after %ds", PORTFOLIO_TIMEOUT)
        raise HTTPException(504, "Delete position timeout")


# ── Real-time PnL (depends on SpotCache) ─────────────────────────────

@router.get("/{portfolio_id}/pnl")
async def portfolio_pnl(portfolio_id: int, include_children: bool = Query(False, description="是否包含子账户盈亏")):
    """
    实时浮动盈亏计算（专业增强版）
    增加: 名称、权重%、今日涨跌幅、市场、PE/PB、换手率
    支持: 包含所有子账户的聚合视图
    依赖 SpotCache（后台每3分钟刷新的全市场实时行情）
    """
    def _sync_work():
        from app.services.sentiment_engine import SpotCache

        conn = _get_conn()
        try:
            if include_children:
                all_ids = _get_all_descendants(conn, portfolio_id)
                placeholders = ','.join(['?' for _ in all_ids])
                rows = conn.execute(
                    f"""SELECT p.symbol, p.total_shares as shares, p.avg_cost, po.name as portfolio_name, po.id as portfolio_id
                        FROM position_summary p
                        JOIN portfolios po ON p.portfolio_id = po.id
                        WHERE p.portfolio_id IN ({placeholders})""",
                    tuple(all_ids)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT symbol, total_shares as shares, avg_cost FROM position_summary WHERE portfolio_id=?",
                    (portfolio_id,)
                ).fetchall()

            stock_meta = {}
            try:
                meta_rows = conn.execute(
                    "SELECT symbol, name, per, pb, mktcap, turnover FROM market_all_stocks"
                ).fetchall()
                for r in meta_rows:
                    stock_key = r[0].lower().replace("sh", "").replace("sz", "").replace("hk", "").replace("us", "")
                    stock_meta[stock_key] = {"name": r[1], "per": r[2], "pb": r[3], "mktcap": r[4], "turnover": r[5]}
            except sqlite3.OperationalError as e:
                logger.warning(f"[Portfolio PnL] 数据库操作错误，无法获取股票元数据: {e}")
            except (httpx.HTTPError, asyncio.TimeoutError, ConnectionError) as e:
        logger.warning(f"[HTTP] stock metadata: {e}")

            cash_balance = 0.0
            try:
                cb = conn.execute(
                    "SELECT cash_balance FROM portfolios WHERE id=?",
                    (portfolio_id,),
                ).fetchone()
                cash_balance = cb[0] or 0.0 if cb else 0.0
            except sqlite3.OperationalError as e:
                logger.warning(f"[Portfolio PnL] 数据库操作错误，无法获取 cash_balance (portfolio_id={portfolio_id}): {e}")
            except Exception as e:
                logger.warning(f"[Portfolio PnL] 获取 cash_balance 失败 (portfolio_id={portfolio_id}): {e}")
        finally:
            conn.close()

        if not rows:
            return {
                "positions": [], "total_pnl": 0.0, "total_cost": 0.0, "total_value": 0.0,
                "includes_children": include_children,
                "realized_pnl": 0.0, "unrealized_pnl": 0.0, "daily_pnl": 0.0,
                "cash_balance": cash_balance
            }

        spot = SpotCache.get_stocks()
        price_map = {}
        for s in spot:
            code = s.get("code", "")
            price_map[code] = s
            if len(code) > 2:
                price_map[code[2:]] = s
                price_map[code.lower()] = s
                price_map[code.upper()] = s
        
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
                    price_map[sym] = {"code": sym, "name": name, "price": price, "chg_pct": chg_pct}
                    if len(sym) > 2:
                        price_map[sym[2:]] = price_map[sym]
                        price_map[sym.lower()] = price_map[sym]
                        price_map[sym.upper()] = price_map[sym]
                db_price_loaded = True
                logger.info(f"[Portfolio PnL] 从数据库加载 {len(db_rows)} 只股票价格")
            except sqlite3.OperationalError as e:
                logger.warning(f"[Portfolio PnL] 数据库操作错误，兜底获取价格失败: {e}")
            except ValueError as e:
                logger.warning(f"[Portfolio PnL] 价格数据格式错误: {e}")
            except Exception as e:
                logger.warning(f"[Portfolio PnL] 数据库兜底失败: {e}")
        
        result = []
        total_cost = 0.0
        total_value = 0.0
        missing_prices = []
        
        for row in rows:
            if include_children:
                symbol, shares, avg_cost, portfolio_name, portfolio_id_from_row = row
            else:
                symbol, shares, avg_cost = row
                portfolio_name = None
                portfolio_id_from_row = None
                
            info = price_map.get(symbol, {})
            if not info and len(symbol) == 6:
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
            
        for pos in result:
            pos["weight"] = round(pos["market_value"] / total_value * 100, 2) if total_value > 0 else 0.0

        total_pnl = total_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0

        conn = _get_conn()
        try:
            closed_rows = conn.execute(
                "SELECT SUM(realized_pnl) FROM position_lots WHERE portfolio_id=? AND status='closed'",
                (portfolio_id,),
            ).fetchone()
            realized_pnl = closed_rows[0] or 0.0

            unrealized_row = conn.execute(
                "SELECT SUM(unrealized_pnl) FROM position_summary WHERE portfolio_id=?",
                (portfolio_id,),
            ).fetchone()
            unrealized_pnl = float(unrealized_row[0]) if unrealized_row and unrealized_row[0] is not None else 0.0

            today = datetime.now().strftime('%Y-%m-%d')
            txn_rows = conn.execute(
                "SELECT SUM(amount) FROM transactions "
                "WHERE portfolio_id=? AND created_at>=? AND type IN ('sell_pnl','deposit','withdraw','transfer_in','transfer_out')",
                (portfolio_id, today),
            ).fetchone()
            daily_pnl = txn_rows[0] or 0.0 if txn_rows else 0.0
        except sqlite3.OperationalError as e:
            logger.warning(f"[Portfolio PnL] 数据库操作错误，无法读取盈亏数据 (portfolio_id={portfolio_id}): {e}")
            realized_pnl = 0.0
            unrealized_pnl = 0.0
            daily_pnl = 0.0
        except ValueError as e:
            logger.warning(f"[Portfolio PnL] 盈亏数据格式错误 (portfolio_id={portfolio_id}): {e}")
            realized_pnl = 0.0
            unrealized_pnl = 0.0
            daily_pnl = 0.0
        except Exception as e:
            logger.warning(f"[Portfolio PnL] 读取盈亏数据失败 (portfolio_id={portfolio_id}): {e}")
            realized_pnl = 0.0
            unrealized_pnl = 0.0
            daily_pnl = 0.0
        finally:
            conn.close()

        response = {
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

        return response
    
    async def _inner():
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(_portfolio_executor, _sync_work)
        return success_response(data)
    
    try:
        return await asyncio.wait_for(_inner(), timeout=PORTFOLIO_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning("[positions] portfolio_pnl timeout after %ds", PORTFOLIO_TIMEOUT)
        raise HTTPException(504, "Portfolio PnL calculation timeout")


# ── Snapshots ─────────────────────────────────────────────────

@router.get("/{portfolio_id}/snapshots")
async def get_snapshots(
    portfolio_id: int,
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date:   Optional[str] = Query(None, description="YYYY-MM-DD"),
):
    """净值历史快照"""
    def _sync_work():
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
    
    async def _inner():
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(_portfolio_executor, _sync_work)
        return success_response(data)
    
    try:
        return await asyncio.wait_for(_inner(), timeout=PORTFOLIO_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning("[positions] get_snapshots timeout after %ds", PORTFOLIO_TIMEOUT)
        raise HTTPException(504, "Get snapshots timeout")


@router.post("/{portfolio_id}/snapshots")
async def save_snapshot(portfolio_id: int, _: None = Depends(require_api_key)):
    """手动保存当日快照（供路由调用）"""
    def _sync_work():
        return _save_snapshot_impl(portfolio_id)
    
    async def _inner():
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_portfolio_executor, _sync_work)
    
    try:
        return await asyncio.wait_for(_inner(), timeout=PORTFOLIO_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning("[positions] save_snapshot timeout after %ds", PORTFOLIO_TIMEOUT)
        raise HTTPException(504, "Save snapshot timeout")


def _save_snapshot_impl(portfolio_id: int):
    """
    保存当日净值快照（同步函数，供 scheduler 直接调用）
    计算: total_asset = Σ(shares * latest_close)，total_cost = Σ(shares * avg_cost)
    Phase 4 Fix: 优先从 position_summary 读取（lot-based 系统），fallback 到 positions
    """
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


# ── Today's PnL (lightweight endpoint) ─────────────────────────────────────────

@router.get("/{portfolio_id}/pnl/today")
async def daily_pnl_only(portfolio_id: int):
    """
    仅返回当日三分数据（轻量端点，供 ECharts 看板高频轮询）。
    """
    def _sync_work():
        today = datetime.now().strftime('%Y-%m-%d')
        conn = _get_conn()
        try:
            rt = conn.execute(
                "SELECT SUM(amount) FROM transactions "
                "WHERE portfolio_id=? AND created_at>=? AND type='sell_pnl'",
                (portfolio_id, today),
            ).fetchone()
            realized_today = rt[0] or 0.0

            dt = conn.execute(
                "SELECT SUM(amount) FROM transactions "
                "WHERE portfolio_id=? AND created_at>=? AND type IN ('deposit','withdraw','transfer_in','transfer_out')",
                (portfolio_id, today),
            ).fetchone()
            cash_flow = dt[0] or 0.0

            unrealized = 0.0
            try:
                ur = conn.execute(
                    "SELECT SUM(unrealized_pnl) FROM position_summary WHERE portfolio_id=?",
                    (portfolio_id,),
                ).fetchone()
                unrealized = ur[0] or 0.0 if ur else 0.0
            except sqlite3.OperationalError as e:
                logger.warning(f"[Portfolio daily_pnl] 数据库操作错误，无法读取 unrealized (portfolio_id={portfolio_id}): {e}")
            except Exception as e:
                logger.warning(f"[Portfolio daily_pnl] 读取 unrealized 失败 (portfolio_id={portfolio_id}): {e}")

            return {
                "date":           today,
                "realized_today": round(realized_today, 2),
                "cash_flow":      round(cash_flow, 2),
                "unrealized_pnl": round(unrealized, 2),
                "daily_pnl":      round(realized_today + cash_flow, 2),
            }
        finally:
            conn.close()
    
    async def _inner():
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(_portfolio_executor, _sync_work)
        return success_response(data)
    
    try:
        return await asyncio.wait_for(_inner(), timeout=PORTFOLIO_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning("[positions] daily_pnl timeout after %ds", PORTFOLIO_TIMEOUT)
        raise HTTPException(504, "Daily PnL timeout")
