"""
Backtest Monitor Router - Real-time monitoring for backtest workers.

Provides REST API and WebSocket endpoints for monitoring and controlling
running backtest processes.
"""
import asyncio
import logging
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from app.services.backtest_worker_registry import get_backtest_registry
from app.middleware import require_api_key
from app.utils.response import success_response, error_response, ErrorCode

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/metrics")
async def get_backtest_metrics():
    """Get real-time metrics for all backtest workers."""
    registry = get_backtest_registry()
    metrics = registry.get_metrics()
    summary = registry.get_summary()
    
    return success_response({
        "workers": metrics,
        "summary": summary,
        "timestamp": datetime.now().isoformat()
    })


@router.get("/summary")
async def get_backtest_summary():
    """Get summary statistics for all workers."""
    registry = get_backtest_registry()
    summary = registry.get_summary()
    
    return success_response(summary)


@router.post("/kill/{worker_id}")
async def kill_backtest(worker_id: str, _: None = Depends(require_api_key)):
    """Kill a runaway backtest worker."""
    registry = get_backtest_registry()
    
    worker = registry.get_worker(worker_id)
    if not worker:
        return error_response(ErrorCode.NOT_FOUND, f"Worker {worker_id} not found")
    
    if worker.status != "running":
        return error_response(ErrorCode.BAD_REQUEST, f"Worker {worker_id} is not running (status: {worker.status})")
    
    success = await registry.kill(worker_id)
    
    if success:
        return success_response({
            "worker_id": worker_id,
            "status": "cancelled",
            "message": f"Worker {worker_id} has been killed"
        })
    else:
        return error_response(ErrorCode.INTERNAL_ERROR, f"Failed to kill worker {worker_id}")


@router.post("/cleanup")
async def cleanup_completed_workers(_: None = Depends(require_api_key)):
    """Remove completed/failed workers from registry."""
    registry = get_backtest_registry()
    registry.cleanup_completed()
    
    return success_response({
        "message": "Cleanup completed",
        "active_workers": len(registry.get_all_workers())
    })


@router.websocket("/stream")
async def backtest_stream(websocket: WebSocket):
    """WebSocket for real-time metrics updates (every 1 second)."""
    await websocket.accept()
    registry = get_backtest_registry()
    registry.add_ws_client(websocket)
    
    logger.info("[BacktestMonitor] WebSocket client connected")
    
    try:
        while True:
            metrics = registry.get_metrics()
            summary = registry.get_summary()
            
            await websocket.send_json({
                "type": "backtest_metrics",
                "timestamp": datetime.now().isoformat(),
                "workers": metrics,
                "summary": summary
            })
            
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        logger.info("[BacktestMonitor] WebSocket client disconnected")
    except Exception as e:
        logger.error(f"[BacktestMonitor] WebSocket error: {e}")
    finally:
        registry.remove_ws_client(websocket)


@router.get("/health")
async def health_check():
    """Health check for backtest monitor."""
    registry = get_backtest_registry()
    summary = registry.get_summary()
    
    return success_response({
        "status": "healthy",
        "active_workers": summary["running"],
        "total_workers": summary["total_workers"]
    })
