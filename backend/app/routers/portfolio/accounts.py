"""
Portfolio Account CRUD endpoints.
"""

import asyncio
from app.utils.executor import get_executor
from datetime import datetime
import logging
import sqlite3

from fastapi import APIRouter, HTTPException, Depends

from app.utils.errors import success_response
from app.db.database import _get_conn, _lock
from app.middleware import require_api_key

logger = logging.getLogger(__name__)

from .schemas import PortfolioIn
from .dependencies import _row2dict, _get_all_descendants
from app.utils.error_decorator import handle_errors

router = APIRouter(tags=["portfolio"])

# Timeout constant for all portfolio endpoints
PORTFOLIO_TIMEOUT = 30  # seconds

# Use centralized executor from utils/executor.py


# ── 账户 CRUD ─────────────────────────────────────────────────


@router.get("/")
@handle_errors(module="portfolio_accounts")
async def list_portfolios():
    """所有账户列表（WAL 模式并发读，无需应用层锁）"""

    def _sync_work():
        conn = _get_conn()
        try:
            rows = conn.execute(
                """SELECT id, name, type, parent_id, created_at, total_cost, cash_balance,
                          currency, asset_class, strategy, benchmark, status, initial_capital, description
                   FROM portfolios ORDER BY id"""
            ).fetchall()
        finally:
            conn.close()
        return {
            "portfolios": _row2dict(
                rows,
                [
                    "id",
                    "name",
                    "type",
                    "parent_id",
                    "created_at",
                    "total_cost",
                    "cash_balance",
                    "currency",
                    "asset_class",
                    "strategy",
                    "benchmark",
                    "status",
                    "initial_capital",
                    "description",
                ],
            )
        }

    async def _inner():
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(get_executor(), _sync_work)
        return success_response(data)

    try:
        return await asyncio.wait_for(_inner(), timeout=PORTFOLIO_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning(
            "[accounts] list_portfolios timeout after %ds",
            PORTFOLIO_TIMEOUT,
            exc_info=True,
        )
        raise HTTPException(504, "List portfolios timeout")


@router.post("/")
@handle_errors(module="portfolio_accounts")
async def create_portfolio(body: PortfolioIn, _: None = Depends(require_api_key)):
    """新建账户"""

    def _sync_work():
        now = datetime.now().isoformat()
        with _lock:
            conn = _get_conn()
            try:
                if body.parent_id is not None:
                    if body.parent_id == 0:
                        raise HTTPException(400, "parent_id 不能为 0（自身）")
                    children_of_parent = _get_all_descendants(conn, body.parent_id)
                    if body.parent_id in children_of_parent:
                        raise HTTPException(
                            400,
                            f"parent_id ({body.parent_id}) 不能指向自身的后代节点，检测到环形嵌套",
                        )
                cur = conn.execute(
                    """INSERT INTO portfolios (name, type, parent_id, created_at, total_cost,
                            currency, asset_class, strategy, benchmark, status, initial_capital,
                            description, cash_balance)
                     VALUES (?,?,?,?,0,?,?,?,?,?,?,?,0.0)""",
                    (
                        body.name,
                        body.type,
                        body.parent_id,
                        now,
                        body.currency,
                        body.asset_class,
                        body.strategy,
                        body.benchmark,
                        body.status,
                        body.initial_capital,
                        body.description,
                    ),
                )
                conn.commit()
                pid = cur.lastrowid
            except HTTPException:
                raise
            except sqlite3.IntegrityError as e:
                logger.warning(
                    "[accounts] create_portfolio integrity error: %s", e, exc_info=True
                )
                raise HTTPException(400, f"数据完整性错误: {e}")
            except sqlite3.OperationalError as e:
                logger.error(
                    "[accounts] create_portfolio operational error: %s",
                    e,
                    exc_info=True,
                )
                raise HTTPException(500, f"数据库操作错误: {e}")
            except ValueError as e:
                logger.warning(
                    "[accounts] create_portfolio value error: %s", e, exc_info=True
                )
                raise HTTPException(400, f"参数错误: {e}")
            except Exception as e:
                logger.exception("Unexpected error in create_portfolio")
                raise HTTPException(500, f"创建账户失败: {e}")
            finally:
                conn.close()
        return {
            "id": pid,
            "name": body.name,
            "type": body.type,
            "parent_id": body.parent_id,
            "created_at": now,
            "total_cost": 0.0,
            "currency": body.currency,
            "asset_class": body.asset_class,
            "strategy": body.strategy,
            "benchmark": body.benchmark,
            "status": body.status,
            "initial_capital": body.initial_capital,
            "description": body.description,
        }

    async def _inner():
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(get_executor(), _sync_work)
        return success_response(data)

    try:
        return await asyncio.wait_for(_inner(), timeout=PORTFOLIO_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning(
            "[accounts] create_portfolio timeout after %ds",
            PORTFOLIO_TIMEOUT,
            exc_info=True,
        )
        raise HTTPException(504, "Create portfolio timeout")


@router.delete("/{portfolio_id}")
@handle_errors(module="portfolio_accounts")
async def delete_portfolio(portfolio_id: int, _: None = Depends(require_api_key)):
    """删除账户（连带持仓和快照）- 需认证"""

    def _sync_work():
        with _lock:
            conn = _get_conn()
            cur = conn.execute("DELETE FROM portfolios WHERE id=?", (portfolio_id,))
            conn.commit()
            deleted = cur.rowcount
            conn.close()
        if not deleted:
            raise HTTPException(404, "账户不存在")
        return {"ok": True}

    async def _inner():
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(get_executor(), _sync_work)
        return success_response(data)

    try:
        return await asyncio.wait_for(_inner(), timeout=PORTFOLIO_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning(
            "[accounts] delete_portfolio timeout after %ds",
            PORTFOLIO_TIMEOUT,
            exc_info=True,
        )
        raise HTTPException(504, "Delete portfolio timeout")
