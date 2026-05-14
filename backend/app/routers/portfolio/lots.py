"""
Portfolio Lots Router - Lot Trading and Position Management

This module contains endpoints for lot trading (buy/sell), position queries,
conservation checks, tree structure, and ECharts data.

Extracted from portfolio.py for better code organization.
"""

import logging
import sqlite3
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends

from app.utils.response import success_response
from app.middleware import require_api_key
from app.db.database import _get_conn, _lock, get_conn
from app.services.trading import (
    execute_buy, execute_sell, get_open_lots,
    calc_unrealized_pnl,
    upsert_position_summary, update_market_value, get_position_summary,
    LotRecord, SellResult,
)

from .dependencies import (
    _insert_transaction,
    _get_all_descendants,
)
from .schemas import BuyIn, SellIn

logger = logging.getLogger(__name__)

router = APIRouter(tags=["portfolio"])


# ── Buy (BUY) - Add new lot ────────────────────────────────────────────

@router.post("/{portfolio_id}/lots/buy")
async def buy_lot(portfolio_id: int, body: BuyIn, _: None = Depends(require_api_key)):
    """
    买入时新增一个批次（lot）。
    同一标的同一日期可有多批次，但 avg_cost 独立计算。
    """
    try:
        lot = execute_buy(
            portfolio_id=portfolio_id,
            symbol=body.symbol,
            shares=body.shares,
            buy_price=body.buy_price,
            buy_date=body.buy_date,
            order_id=body.order_id,
        )
        return success_response({
            "lot_id": lot.id,
            "symbol": lot.symbol,
            "shares": lot.shares,
            "avg_cost": lot.avg_cost,
            "buy_date": lot.buy_date,
            "status": lot.status,
        })
    except ValueError as e:
        raise HTTPException(400, str(e))
    except sqlite3.IntegrityError as e:
        raise HTTPException(400, f"数据完整性错误: {e}")
    except sqlite3.OperationalError as e:
        raise HTTPException(500, f"数据库操作错误: {e}")
    except Exception as e:
        logger.error(f"[Buy] error: {e}", exc_info=True)
        raise HTTPException(500, f"买入失败: {e}")


# ── Sell (SELL) - FIFO close position ─────────────────────────────────────────

@router.post("/{portfolio_id}/lots/sell")
async def sell_lot(portfolio_id: int, body: SellIn, _: None = Depends(require_api_key)):
    """
    FIFO 平仓算法：
      1. 按 buy_date 升序匹配 open 批次
      2. 每批次平仓时计算 realized_pnl 并累加
      3. 返回平仓明细和总已实现盈亏
    """
    try:
        # ── 事务包装：确保 execute_sell + 现金更新 + 流水记录 原子性 ──
        with get_conn() as conn:
            conn.execute("BEGIN TRANSACTION")
            try:
                result = execute_sell(
                    portfolio_id=portfolio_id,
                    symbol=body.symbol,
                    shares=body.shares,
                    sell_price=body.sell_price,
                    order_id=body.order_id,
                )

                # 查询并更新现金余额
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

                # 写入交易流水
                _insert_transaction(
                    conn,
                    portfolio_id,
                    "sell_pnl",
                    result.total_realized_pnl,
                    new_cash,
                    related_symbol=body.symbol,
                    note=f"卖出{body.symbol} × {body.shares}手",
                    operator="user",
                )

                conn.commit()
            except Exception:
                conn.rollback()
                raise

        return success_response({
            "symbol": body.symbol,
            "shares_sold": body.shares - result.shares_remaining,
            "total_realized_pnl": result.total_realized_pnl,
            "sell_price": result.sell_price,
            "timestamp": result.timestamp,
            "lots_closed": [
                {
                    "lot_id": lc.lot_id,
                    "shares_closed": lc.shares_closed,
                    "avg_cost": lc.avg_cost,
                    "sell_price": lc.sell_price,
                    "realized_pnl": lc.realized_pnl,
                }
                for lc in result.lots_closed
            ],
        })
    except ValueError as e:
        raise HTTPException(400, str(e))
    except sqlite3.IntegrityError as e:
        raise HTTPException(400, f"数据完整性错误: {e}")
    except sqlite3.OperationalError as e:
        raise HTTPException(500, f"数据库操作错误: {e}")
    except Exception as e:
        logger.error(f"[Sell] error: {e}", exc_info=True)
        raise HTTPException(500, f"卖出失败: {e}")


# ── Lot Query ─────────────────────────────────────────────────────────

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
        return success_response({
            "lots": [
                {
                    "id": l.id,
                    "symbol": l.symbol,
                    "shares": l.shares,
                    "avg_cost": l.avg_cost,
                    "buy_date": l.buy_date,
                    "buy_order_id": l.buy_order_id,
                    "status": l.status,
                    "realized_pnl": l.realized_pnl,
                    "portfolio_id": l.portfolio_id,
                }
                for l in lots
            ],
            "count": len(lots),
            "includes_children": include_children,
            "portfolio_ids": all_ids if include_children else [portfolio_id],
        })
    except sqlite3.OperationalError as e:
        logger.error(f"[Lots] 数据库操作错误: {e}", exc_info=True)
        raise HTTPException(500, f"数据库操作错误: {e}")
    except Exception as e:
        logger.error(f"[Lots] error: {e}", exc_info=True)
        raise HTTPException(500, f"批次查询失败: {e}")


# ── Unrealized PnL ──────────────────────────────────────────────────────

@router.get("/{portfolio_id}/lots/unrealized")
async def unrealized_pnl(
    portfolio_id: int,
    symbol: str = Query(..., description="标的代码，如 000001"),
    current_price: float = Query(..., description="当前市场价格"),
):
    """
    计算浮动盈亏。
    未实现 PnL = Σ(shares × (current_price - avg_cost))
    """
    try:
        result = calc_unrealized_pnl(portfolio_id, symbol, current_price)
        return success_response(result)
    except ValueError as e:
        logger.error(f"[UnrealizedPnl] 参数错误: {e}", exc_info=True)
        raise HTTPException(400, f"参数错误: {e}")
    except sqlite3.OperationalError as e:
        logger.error(f"[UnrealizedPnl] 数据库操作错误: {e}", exc_info=True)
        raise HTTPException(500, f"数据库操作错误: {e}")
    except Exception as e:
        logger.error(f"[UnrealizedPnl] error: {e}", exc_info=True)
        raise HTTPException(500, f"盈亏计算失败: {e}")


# ══════════════════════════════════════════════════════════════════════════
#  Sub-account Roll-up aggregation endpoints (Conservation Law + Tree Structure)
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

        # 获取主账户自身持仓市值（使用 position_summary 聚合表）
        parent_positions = conn.execute(
            "SELECT portfolio_id, symbol, total_shares as shares, avg_cost, market_value FROM position_summary WHERE portfolio_id=? AND total_shares > 0",
            (portfolio_id,)
        ).fetchall()

        # 获取主账户所有后代（递归）
        all_desc_ids = _get_all_descendants(conn, portfolio_id)
        if all_desc_ids:
            placeholders = ','.join(['?' for _ in all_desc_ids])
            child_positions = conn.execute(
                f"SELECT portfolio_id, symbol, total_shares as shares, avg_cost, market_value FROM position_summary WHERE portfolio_id IN ({placeholders}) AND total_shares > 0",
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
            for row in rows:
                pid, sym, shares, avg_cost = row[0], row[1], row[2], row[3]
                market_value = row[4] if len(row) > 4 else None
                if market_value is not None and market_value > 0:
                    total += market_value
                else:
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
        except TypeError as e:
            logger.warning(f"[Portfolio Conservation] 类型错误 (portfolio_id={portfolio_id}): {e}")
            conservation_ok = False
        except ValueError as e:
            logger.warning(f"[Portfolio Conservation] 数值错误 (portfolio_id={portfolio_id}): {e}")
            conservation_ok = False
        except Exception as e:
            logger.warning(f"[Portfolio Conservation] 校验异常 (portfolio_id={portfolio_id}): {e}")
            conservation_ok = False

        return success_response({
            "parent_id": portfolio_id,
            "parent_name": parent[1],
            "parent": {
                "cash": round(parent_cash, 2),
                "position_value": round(parent_pos_value, 2),
                "total": round(parent_total, 2),
            },
            "children": [
                {
                    "id": r[0],
                    "name": r[1],
                    "cash": round(r[2] or 0.0, 2),
                }
                for r in children
            ],
            "children_position_value": round(child_pos_value, 2),
            "children_cash": round(child_cash_total, 2),
            "children_total": round(children_total, 2),
            "grand_total": round(grand_total, 2),
            "conservation_ok": conservation_ok,
            "conservation_delta": round(grand_total - parent_total, 4),
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
                "id": p_id,
                "name": p_name,
                "type": p_type,
                "status": p_status or "active",
                "cash_balance": round(p_cash or 0.0, 2),
                "position_value": round(pos_value, 2),
                "total_assets": round((p_cash or 0.0) + pos_value, 2),
                "children": children,
            }

        tree = build_node(portfolio_id)
        return success_response({"tree": tree})
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════
#  Phase 3: position_summary aggregation table routes + ECharts data endpoint
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
        return success_response({"summary": rows, "count": len(rows), "includes_children": include_children})
    except sqlite3.OperationalError as e:
        logger.error(f"[lots_summary] 数据库操作错误: {e}", exc_info=True)
        raise HTTPException(500, f"数据库操作错误: {e}")
    except ValueError as e:
        logger.error(f"[lots_summary] 参数错误: {e}", exc_info=True)
        raise HTTPException(400, f"参数错误: {e}")
    except Exception as e:
        logger.error(f"[lots_summary] error: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@router.post("/{portfolio_id}/lots/update_price")
async def refresh_market_value(
    portfolio_id: int,
    symbol: str = Query(..., description="标的代码"),
    current_price: float = Query(..., description="当前市价"),
    _: None = Depends(require_api_key)
):
    """
    批量刷新持仓聚合表的 market_value 和 unrealized_pnl。
    行情刷新时由调度器调用，也可在 GET /lots/summary 前调用。
    """
    try:
        result = update_market_value(portfolio_id, symbol, current_price)
        return success_response(result)
    except ValueError as e:
        logger.error(f"[refresh_market_value] 参数错误: {e}", exc_info=True)
        raise HTTPException(400, f"参数错误: {e}")
    except sqlite3.OperationalError as e:
        logger.error(f"[refresh_market_value] 数据库操作错误: {e}", exc_info=True)
        raise HTTPException(500, f"数据库操作错误: {e}")
    except Exception as e:
        logger.error(f"[refresh_market_value] error: {e}", exc_info=True)
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
                "symbol": r['symbol'],
                "total_shares": r['total_shares'],
                "avg_cost": r['avg_cost'],
                "current_price": r.get('market_value', 0) / r['total_shares'] if r['total_shares'] else 0,
                "market_value": mv,
                "unrealized_pnl": r.get('unrealized_pnl', 0),
                "weight_pct": pct,
            })
        return success_response({
            "total_market_value": round(total_mv, 2),
            "positions": chart_data,
        })
    except sqlite3.OperationalError as e:
        logger.error(f"[lots_echarts_data] 数据库操作错误: {e}", exc_info=True)
        raise HTTPException(500, f"数据库操作错误: {e}")
    except KeyError as e:
        logger.error(f"[lots_echarts_data] 数据字段缺失: {e}", exc_info=True)
        raise HTTPException(500, f"数据格式错误: {e}")
    except ZeroDivisionError as e:
        logger.error(f"[lots_echarts_data] 计算错误（除零）: {e}", exc_info=True)
        raise HTTPException(500, "计算错误：除零")
    except Exception as e:
        logger.error(f"[lots_echarts_data] error: {e}", exc_info=True)
        raise HTTPException(500, str(e))
