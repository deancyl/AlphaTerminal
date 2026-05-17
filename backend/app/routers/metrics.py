"""
Prometheus Metrics Endpoint

Exposes cache and data source metrics in Prometheus text format.
"""

from fastapi import APIRouter, Response
from app.services.cache_metrics import get_cache_metrics

router = APIRouter(prefix="/metrics", tags=["monitoring"])


@router.get("")
async def get_metrics():
    """
    Get Prometheus-formatted metrics.
    
    Returns cache hit rates, data source latencies, and error rates.
    """
    metrics = get_cache_metrics()
    prometheus_output = metrics.to_prometheus()
    
    return Response(
        content=prometheus_output,
        media_type="text/plain; version=0.0.4; charset=utf-8"
    )