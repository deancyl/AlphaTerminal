"""
Market Radar Services

Provides treemap building and anomaly detection for market heat visualization.

Wave 5-38: Added cache warmup functionality
"""

from .treemap_builder import build_treemap_data, get_sector_stocks
from .anomaly_detector import detect_anomalies, AnomalyType
from .error_codes import (
    MarketRadarErrorCode,
    MarketRadarError,
    success_response,
    error_response,
)
from .cache_warmup import (
    warmup_market_radar_cache,
    schedule_cache_warmup,
    start_background_warmup,
)

__all__ = [
    "build_treemap_data",
    "get_sector_stocks",
    "detect_anomalies",
    "AnomalyType",
    "MarketRadarErrorCode",
    "MarketRadarError",
    "success_response",
    "error_response",
    "warmup_market_radar_cache",
    "schedule_cache_warmup",
    "start_background_warmup",
]
