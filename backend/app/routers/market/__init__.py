"""
Market Router - Aggregated from domain modules.

This module provides a unified router for all market-related endpoints,
split across multiple domain modules for maintainability.

Modules:
- dependencies.py: Shared utilities, caches, constants
- overview.py: Market overview, macro data (5 endpoints)
- quotes.py: Quote, quote_detail, order_book (4 endpoints)
- history.py: Price history, futures (2 endpoints)
- symbols.py: Symbol registry, search (5 endpoints)
- sectors.py: Sector data (2 endpoints)
- source.py: Data source management (10 endpoints)
- system.py: System info (2 endpoints)

Total: 30+ endpoints
"""
from fastapi import APIRouter

from .dependencies import (
    _MACRO_CACHE,
    _MACRO_CACHE_TTL,
    _MACRO_CACHE_LOCK,
    _LAST_FETCH_TIME,
    _REFRESH_SEMAPHORE,
    _REALTIME_CACHE,
    _CACHE_TTL,
    _ALL_STOCK_NAMES,
    _STOCK_NAMES_LOADED,
    _STOCK_LOAD_LOCK,
    WIND_SYMBOLS,
    INDEX_SYMBOLS,
    CHINA_ALL_SYMBOLS,
    RATE_SYMBOLS,
    GLOBAL_SYMBOLS,
    DERIVATIVE_SYMBOLS,
    SINA_HEADERS,
    _MARKET_PREFIX,
    _SYMBOL_REGISTRY,
    _SYMBOL_LOOKUP_STATIC,
    _normalize_symbol,
    _unprefix,
    _clean_symbol,
    _serialize_price_row,
    _serialize_price_rows,
    _inject_change_pct,
    _apply_adjustment,
    _fetch_from_sina,
    _parse_cnyusd,
    _parse_hf_gold,
    _parse_hkhsi,
    _parse_hf_cl,
    _parse_hkvhsi,
    _get_cnyusd_approx,
    _fetch_macro_data,
    _get_macro_data,
    _get_cached_wind,
    _get_combined_lookup,
    _pinyin_fallback,
    _load_all_stock_names,
    logger,
)

from .overview import router as overview_router
from .quotes import router as quotes_router
from .history import router as history_router
from .symbols import router as symbols_router
from .sectors import router as sectors_router
from .source import router as source_router
from .system import router as system_router

router = APIRouter(tags=["market"])

router.include_router(overview_router)
router.include_router(quotes_router)
router.include_router(history_router)
router.include_router(symbols_router)
router.include_router(sectors_router)
router.include_router(source_router)
router.include_router(system_router)

__all__ = [
    "router",
    "_MACRO_CACHE",
    "_MACRO_CACHE_TTL",
    "_MACRO_CACHE_LOCK",
    "_LAST_FETCH_TIME",
    "_REFRESH_SEMAPHORE",
    "_REALTIME_CACHE",
    "_CACHE_TTL",
    "_ALL_STOCK_NAMES",
    "_STOCK_NAMES_LOADED",
    "_STOCK_LOAD_LOCK",
    "WIND_SYMBOLS",
    "INDEX_SYMBOLS",
    "CHINA_ALL_SYMBOLS",
    "RATE_SYMBOLS",
    "GLOBAL_SYMBOLS",
    "DERIVATIVE_SYMBOLS",
    "SINA_HEADERS",
    "_MARKET_PREFIX",
    "_SYMBOL_REGISTRY",
    "_SYMBOL_LOOKUP_STATIC",
    "_normalize_symbol",
    "_unprefix",
    "_clean_symbol",
    "_serialize_price_row",
    "_serialize_price_rows",
    "_inject_change_pct",
    "_apply_adjustment",
    "_fetch_from_sina",
    "_parse_cnyusd",
    "_parse_hf_gold",
    "_parse_hkhsi",
    "_parse_hf_cl",
    "_parse_hkvhsi",
    "_get_cnyusd_approx",
    "_fetch_macro_data",
    "_get_macro_data",
    "_get_cached_wind",
    "_get_combined_lookup",
    "_pinyin_fallback",
    "_load_all_stock_names",
    "logger",
]
