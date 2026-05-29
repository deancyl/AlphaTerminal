"""
Multi-Asset Matrix API - 四屏联动矩阵

提供跨周期、跨品种的联动四屏视图
"""

import logging
from fastapi import APIRouter
from app.utils.errors import success_response
from app.utils.error_decorator import handle_errors

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/multi-asset-matrix", tags=["multi-asset-matrix"])


@router.get("/health")
@handle_errors(module="multi_asset_matrix")
async def health_check():
    """
    Multi-Asset Matrix 健康检查
    
    四屏联动矩阵组件状态
    """
    return success_response({
        "status": "ok",
        "service": "multi-asset-matrix",
        "panels": [
            {"id": "sse_index", "name": "上证指数", "status": "ready"},
            {"id": "bond_yield", "name": "十年期国债收益率", "status": "ready"},
            {"id": "hs300_future", "name": "沪深300股指期货", "status": "ready"},
            {"id": "usdcny", "name": "人民币汇率", "status": "ready"}
        ],
        "crosshair_sync": True
    })