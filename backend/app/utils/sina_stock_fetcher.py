"""
Shared Sina stock fetcher utility for fetching all A-share stocks.
Used by stocks.py, data_fetcher.py, and market_radar/treemap_builder.py.

PROVEN WORKING: Based on _fetch_all_stocks_sina_sync() from treemap_builder.py
which successfully fetches ~5000 stocks.

Usage:
    from app.utils.sina_stock_fetcher import fetch_all_stocks_sina

    stocks = fetch_all_stocks_sina(max_pages=20)
    print(f"Fetched {len(stocks)} stocks")
"""

import logging
import json
import time
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

try:
    from curl_cffi import requests as curl_requests

    HAS_CURL_CFFI = True
except ImportError:
    import requests as curl_requests

    HAS_CURL_CFFI = False

from app.services.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerConfig,
)

_SINA_STOCK_CB = CircuitBreaker(
    name="sina_stock_fetcher",
    config=CircuitBreakerConfig(failure_threshold=5, timeout=60.0),
)

_SINA_API_URL = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"


def _get_proxies() -> Optional[Dict]:
    """Get proxy configuration from settings."""
    try:
        from app.config.settings import get_settings

        settings = get_settings()
        proxy = settings.HTTP_PROXY or settings.http_proxy
        if proxy:
            return {"http": proxy, "https": proxy}
    except Exception as e:
        logger.debug(f"[SinaStockFetcher] Could not get proxy settings: {e}")
    return None


def _safe_float(value, default=0.0):
    """Parse float value safely, handling empty/null cases."""
    if value in ("", None, "-", "--"):
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def fetch_all_stocks_sina(
    page_size: int = 500,
    max_pages: int = 20,
    timeout: int = 15,
    exclude_bj: bool = True,
    delay: float = 0.3,
    nodes: List[str] = ["hs_a"],
) -> List[Dict]:
    """
    Fetch all A-share stocks from Sina Finance API.

    Default uses hs_a node which contains all A-share stocks (Shanghai + Shenzhen + Beijing).
    This is more efficient than fetching from sh_a and sz_a separately.

    Args:
        page_size: Number of stocks per page (default 500)
        max_pages: Maximum pages to fetch per market (default 20)
        timeout: Request timeout in seconds
        exclude_bj: Exclude Beijing Stock Exchange stocks (bj prefix)
        delay: Delay between pages in seconds (rate limiting)
        nodes: API nodes to fetch from (default ["hs_a"] for all A-shares)

    Returns:
        List of stock dicts with symbol, code, name, price, change_pct, etc.
    """
    if _SINA_STOCK_CB.state == CircuitState.OPEN:
        logger.warning("[SinaStockFetcher] Circuit breaker OPEN, skipping fetch")
        return []

    all_stocks = []
    proxies = _get_proxies()

    for node in nodes:
        for page in range(1, max_pages + 1):
            try:
                url = f"{_SINA_API_URL}?page={page}&num={page_size}&sort=symbol&asc=1&node={node}&_s_r_a=page"

                if HAS_CURL_CFFI:
                    response = curl_requests.get(
                        url, timeout=timeout, impersonate="chrome120", proxies=proxies
                    )
                else:
                    response = curl_requests.get(url, timeout=timeout, proxies=proxies)

                if response.status_code != 200:
                    logger.warning(
                        f"[SinaStockFetcher] {node} page {page}: {response.status_code}"
                    )
                    break

                data = json.loads(response.text)
                if not data or not isinstance(data, list):
                    logger.info(f"[SinaStockFetcher] {node} page {page} empty")
                    break

                for item in data:
                    symbol = item.get("symbol", "")
                    if exclude_bj and symbol.startswith("bj"):
                        continue

                    all_stocks.append(
                        {
                            "symbol": symbol,
                            "code": item.get("code", ""),
                            "name": item.get("name", ""),
                            "price": _safe_float(item.get("trade")),
                            "change_pct": _safe_float(item.get("changepercent")),
                            "volume": _safe_float(item.get("volume")),
                            "amount": _safe_float(item.get("amount")),
                            "market_cap": _safe_float(item.get("mktcap")) * 10000,
                            "high": _safe_float(item.get("high")),
                            "low": _safe_float(item.get("low")),
                            "pre_close": _safe_float(item.get("settlement")),
                            "pe": (
                                _safe_float(item.get("per"))
                                if item.get("per") not in ("", None, "-", "--")
                                else None
                            ),
                            "pb": (
                                _safe_float(item.get("pb"))
                                if item.get("pb") not in ("", None, "-", "--")
                                else None
                            ),
                            "turnover": _safe_float(item.get("turnoverratio")),
                        }
                    )

                logger.debug(
                    f"[SinaStockFetcher] {node} page {page}: +{len(data)}, total {len(all_stocks)}"
                )

                if len(data) < page_size:
                    logger.info(f"[SinaStockFetcher] {node} last page at {page}")
                    break

                if delay > 0 and page < max_pages:
                    time.sleep(delay)

            except Exception as e:
                logger.error(
                    f"[SinaStockFetcher] {node} page {page} failed: {e}", exc_info=True
                )
                continue

    if len(all_stocks) > 100:
        _SINA_STOCK_CB.record_success()
        logger.info(f"[SinaStockFetcher] Fetched {len(all_stocks)} stocks")
    else:
        _SINA_STOCK_CB.record_failure()
        logger.warning(
            f"[SinaStockFetcher] Only {len(all_stocks)} stocks, recording failure"
        )

    return all_stocks


def get_circuit_breaker_status() -> Dict:
    """Get circuit breaker status for monitoring."""
    return {
        "state": _SINA_STOCK_CB.state.name,
        "failure_count": (
            _SINA_STOCK_CB._stats.consecutive_failures
            if hasattr(_SINA_STOCK_CB, "_stats")
            else 0
        ),
        "last_failure_time": (
            _SINA_STOCK_CB._stats.last_failure_time
            if hasattr(_SINA_STOCK_CB, "_stats")
            else None
        ),
    }


def reset_circuit_breaker() -> Dict:
    """Reset circuit breaker to CLOSED state."""
    try:
        _SINA_STOCK_CB._state = CircuitState.CLOSED
        _SINA_STOCK_CB._stats.consecutive_failures = 0
        logger.info("[SinaStockFetcher] Circuit breaker reset")
        return {"success": True, "state": "CLOSED"}
    except Exception as e:
        logger.error(f"[SinaStockFetcher] Reset failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
