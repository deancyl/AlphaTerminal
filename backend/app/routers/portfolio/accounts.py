"""
Portfolio Account CRUD endpoints.
"""
from datetime import datetime
import logging
import sqlite3

from fastapi import APIRouter, HTTPException, Depends

from app.utils.response import success_response
from app.db.database import _get_conn, _lock

logger = logging.getLogger(__name__)

# Import from sibling modules
from .schemas import PortfolioIn
from .dependencies import require_auth_for_sensitive_ops, _row2dict, _get_all_descendants

router = APIRouter(tags=["portfolio"])


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
    return success_response({"portfolios": _row2dict(rows, ["id", "name", "type", "parent_id", "created_at", "total_cost",
                                            "cash_balance", "currency", "asset_class", "strategy", "benchmark",
                                            "status", "initial_capital", "description"])})


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
        except sqlite3.IntegrityError as e:
            raise HTTPException(400, f"数据完整性错误: {e}")
        except sqlite3.OperationalError as e:
            raise HTTPException(500, f"数据库操作错误: {e}")
        except ValueError as e:
            raise HTTPException(400, f"参数错误: {e}")
        except Exception as e:
            logger.exception("Unexpected error in create_portfolio")
            raise HTTPException(500, f"创建账户失败: {e}")
        finally:
            conn.close()
    return success_response({"id": pid, "name": body.name, "type": body.type, "parent_id": body.parent_id,
            "created_at": now, "total_cost": 0.0, "currency": body.currency,
            "asset_class": body.asset_class, "strategy": body.strategy,
            "benchmark": body.benchmark, "status": body.status,
            "initial_capital": body.initial_capital, "description": body.description})


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
    return success_response({"ok": True})
