"""
Order Management System (OMS) Router

API endpoints for order management:
- POST /orders - Create new order
- GET /orders/{order_id} - Get order details
- GET /orders/{order_id}/status - Get order status
- POST /orders/{order_id}/submit - Submit order to broker
- POST /orders/{order_id}/cancel - Cancel order
- POST /orders/{order_id}/fill - Process fill (internal)
- GET /portfolios/{portfolio_id}/orders - List portfolio orders
"""

import asyncio
import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field, field_validator

from app.utils.response import success_response, error_response
from app.middleware import require_api_key
from app.services.oms import (
    OrderExecutionEngine,
    OrderStatus,
    Order,
    is_valid_transition,
)
from app.services.oms.order_status import get_allowed_transitions
from app.services.oms.order_engine import InvalidStateTransitionError, OrderNotFoundError

logger = logging.getLogger(__name__)

OMS_TIMEOUT = 30

router = APIRouter(prefix="/api/v1", tags=["oms"])


def get_oms_engine() -> OrderExecutionEngine:
    return OrderExecutionEngine()


class OrderCreate(BaseModel):
    portfolio_id: int = Field(..., ge=1)
    symbol: str = Field(..., min_length=1, max_length=20)
    side: str = Field(..., pattern="^(buy|sell)$")
    quantity: int = Field(..., gt=0)
    price: Optional[float] = Field(default=None, ge=0)
    order_type: str = Field(default="limit", pattern="^(market|limit|stop)$")
    
    @field_validator('order_type')
    @classmethod
    def validate_order_type(cls, v: str, info) -> str:
        if v == 'limit' and info.data.get('price') is None:
            raise ValueError('Limit order requires price')
        return v


class OrderFill(BaseModel):
    filled_quantity: int = Field(..., gt=0)
    fill_price: float = Field(..., gt=0)


class OrderCancel(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)


@router.post("/orders")
async def create_order(
    order_data: OrderCreate,
    oms: OrderExecutionEngine = Depends(get_oms_engine),
):
    async def _inner():
        order = oms.create_order(
            portfolio_id=order_data.portfolio_id,
            symbol=order_data.symbol,
            side=order_data.side,
            quantity=order_data.quantity,
            price=order_data.price,
            order_type=order_data.order_type,
        )
        return success_response(order.to_dict())
    
    return await asyncio.wait_for(_inner(), timeout=OMS_TIMEOUT)


@router.get("/orders/{order_id}")
async def get_order(
    order_id: int,
    oms: OrderExecutionEngine = Depends(get_oms_engine),
):
    async def _inner():
        order = oms.get_order(order_id)
        if order is None:
            raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
        return success_response(order.to_dict())
    
    return await asyncio.wait_for(_inner(), timeout=OMS_TIMEOUT)


@router.get("/orders/{order_id}/status")
async def get_order_status(
    order_id: int,
    oms: OrderExecutionEngine = Depends(get_oms_engine),
):
    async def _inner():
        status = oms.get_order_status(order_id)
        if status is None:
            raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
        
        order = oms.get_order(order_id)
        return success_response({
            "order_id": order_id,
            "status": status.value,
            "filled_quantity": order.filled_quantity if order else 0,
            "avg_fill_price": order.avg_fill_price if order else 0.0,
            "remaining_quantity": (order.quantity - order.filled_quantity) if order else 0,
            "allowed_transitions": [s.value for s in get_allowed_transitions(status)],
        })
    
    return await asyncio.wait_for(_inner(), timeout=OMS_TIMEOUT)


@router.post("/orders/{order_id}/submit")
async def submit_order(
    order_id: int,
    oms: OrderExecutionEngine = Depends(get_oms_engine),
):
    async def _inner():
        order = oms.get_order(order_id)
        if order is None:
            raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
        
        if not is_valid_transition(order.status, OrderStatus.SUBMITTED):
            allowed = [s.value for s in get_allowed_transitions(order.status)]
            raise HTTPException(
                status_code=400,
                detail=f"Cannot submit order in {order.status.value} state. Allowed: {allowed}"
            )
        
        try:
            updated_order = oms.submit_order(order)
            return success_response(updated_order.to_dict())
        except InvalidStateTransitionError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    return await asyncio.wait_for(_inner(), timeout=OMS_TIMEOUT)


@router.post("/orders/{order_id}/cancel")
async def cancel_order(
    order_id: int,
    cancel_data: OrderCancel = OrderCancel(),
    oms: OrderExecutionEngine = Depends(get_oms_engine),
):
    async def _inner():
        try:
            order = oms.cancel_order(order_id)
            return success_response(order.to_dict())
        except OrderNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except InvalidStateTransitionError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    return await asyncio.wait_for(_inner(), timeout=OMS_TIMEOUT)


@router.post("/orders/{order_id}/fill")
async def process_fill(
    order_id: int,
    fill_data: OrderFill,
    oms: OrderExecutionEngine = Depends(get_oms_engine),
):
    async def _inner():
        try:
            order = oms.process_fill(
                order_id=order_id,
                filled_quantity=fill_data.filled_quantity,
                fill_price=fill_data.fill_price,
            )
            return success_response(order.to_dict())
        except OrderNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except InvalidStateTransitionError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    return await asyncio.wait_for(_inner(), timeout=OMS_TIMEOUT)


@router.get("/portfolios/{portfolio_id}/orders")
async def list_portfolio_orders(
    portfolio_id: int,
    status: Optional[str] = Query(None, pattern="^(staged|submitted|validated|pending|partial|filled|cancelled|rejected|expired)$"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    oms: OrderExecutionEngine = Depends(get_oms_engine),
):
    async def _inner():
        status_enum = OrderStatus(status) if status else None
        orders = oms.get_orders_by_portfolio(
            portfolio_id=portfolio_id,
            status=status_enum,
            limit=limit,
            offset=offset,
        )
        
        return success_response({
            "orders": [o.to_dict() for o in orders],
            "pagination": {
                "portfolio_id": portfolio_id,
                "status_filter": status,
                "limit": limit,
                "offset": offset,
                "count": len(orders),
            }
        })
    
    return await asyncio.wait_for(_inner(), timeout=OMS_TIMEOUT)


@router.get("/portfolios/{portfolio_id}/orders/open")
async def list_open_orders(
    portfolio_id: int,
    oms: OrderExecutionEngine = Depends(get_oms_engine),
):
    async def _inner():
        orders = oms.get_open_orders(portfolio_id)
        return success_response({
            "orders": [o.to_dict() for o in orders],
            "count": len(orders),
        })
    
    return await asyncio.wait_for(_inner(), timeout=OMS_TIMEOUT)


@router.get("/orders/statuses")
async def list_order_statuses():
    return success_response({
        "statuses": [
            {"value": s.value, "terminal": len(get_allowed_transitions(s)) == 0}
            for s in OrderStatus
        ],
        "transitions": {
            s.value: [t.value for t in get_allowed_transitions(s)]
            for s in OrderStatus
        }
    })