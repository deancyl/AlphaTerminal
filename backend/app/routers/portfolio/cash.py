"""
Portfolio Cash and Transaction Routes

This module contains endpoints for cash management and transaction history:
- POST /transfer - Transfer between accounts (deprecated)
- POST /transfer/direct - Direct transfer between accounts
- GET /{portfolio_id}/cash - Get cash balance
- POST /{portfolio_id}/cash/deposit - Deposit cash
- POST /{portfolio_id}/cash/withdraw - Withdraw cash
- GET /{portfolio_id}/transactions - List transactions

Extracted from portfolio.py for better code organization.
"""

import asyncio
import sqlite3
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends

from app.utils.response import success_response
from app.middleware import require_api_key
from .schemas import TransactionIn, TransferIn, CashOpIn
from .dependencies import (
    _get_conn,
    _lock,
    _insert_transaction,
    _transfer_between_accounts,
    _row2dict,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["portfolio"])

# Timeout constant for all portfolio endpoints
PORTFOLIO_TIMEOUT = 30  # seconds


# ══════════════════════════════════════════════════════════════
#  Phase 1 扩展：资金流水 + 现金余额管理
# ══════════════════════════════════════════════════════════════

@router.post("/transfer")
async def transfer(body: TransactionIn, _: None = Depends(require_api_key)):
    """
    资金划转（子账户间）
    body.type = 'transfer_out' / 'transfer_in'（通常前端只传一方）
    为简化操作，提供 /transfer 接口：from_pid / to_pid / amount
    """
    raise HTTPException(400, "transfer 需要明确 from_pid 和 to_pid，请使用 /transfer/direct 接口")


@router.post("/transfer/direct")
async def transfer_direct(body: TransferIn, _: None = Depends(require_api_key)):
    """直接划转：原子操作，同时更新两个账户的 cash_balance 并写流水"""
    async def _inner():
        if body.amount <= 0:
            raise HTTPException(400, "划转金额必须为正数")
        result = _transfer_between_accounts(
            body.from_portfolio_id,
            body.to_portfolio_id,
            body.amount,
            body.note,
        )
        return success_response(result)
    
    try:
        return await asyncio.wait_for(_inner(), timeout=PORTFOLIO_TIMEOUT)
    except asyncio.TimeoutError:
        raise HTTPException(504, "Transfer direct timeout")
    except ValueError as e:
        raise HTTPException(400, str(e))
    except sqlite3.IntegrityError as e:
        raise HTTPException(400, f"数据完整性错误: {e}")
    except sqlite3.OperationalError as e:
        raise HTTPException(500, f"数据库操作错误: {e}")
    except Exception as e:
        logger.exception("Unexpected error in transfer_direct")
        raise HTTPException(500, f"划转失败: {e}")


@router.get("/{portfolio_id}/cash")
async def get_cash(portfolio_id: int):
    """查询账户现金余额"""
    async def _inner():
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
        return success_response({"portfolio_id": row[0], "name": row[1], "cash_balance": row[2]})
    
    try:
        return await asyncio.wait_for(_inner(), timeout=PORTFOLIO_TIMEOUT)
    except asyncio.TimeoutError:
        raise HTTPException(504, "Get cash timeout")


@router.post("/{portfolio_id}/cash/deposit")
async def cash_deposit(portfolio_id: int, body: CashOpIn, _: None = Depends(require_api_key)):
    """充值：账户现金增加 + 写 deposit 流水"""
    async def _inner():
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
                return success_response({"portfolio_id": portfolio_id, "cash_balance": new_balance})
            finally:
                conn.close()
    
    try:
        return await asyncio.wait_for(_inner(), timeout=PORTFOLIO_TIMEOUT)
    except asyncio.TimeoutError:
        raise HTTPException(504, "Cash deposit timeout")


@router.post("/{portfolio_id}/cash/withdraw")
async def cash_withdraw(portfolio_id: int, body: CashOpIn, _: None = Depends(require_api_key)):
    """提现：账户现金减少 + 写 withdraw 流水"""
    async def _inner():
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
                return success_response({"portfolio_id": portfolio_id, "cash_balance": new_balance})
            finally:
                conn.close()
    
    try:
        return await asyncio.wait_for(_inner(), timeout=PORTFOLIO_TIMEOUT)
    except asyncio.TimeoutError:
        raise HTTPException(504, "Cash withdraw timeout")


@router.get("/{portfolio_id}/transactions")
async def list_transactions(
    portfolio_id: int,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    txn_type: Optional[str] = Query(None, description="过滤类型: deposit/withdraw/transfer_in/transfer_out/dividend/fee"),
):
    """资金流水记录查询"""
    async def _inner():
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
        return success_response({"transactions": _row2dict(rows, cols), "total": len(rows)})
    
    try:
        return await asyncio.wait_for(_inner(), timeout=PORTFOLIO_TIMEOUT)
    except asyncio.TimeoutError:
        raise HTTPException(504, "List transactions timeout")
