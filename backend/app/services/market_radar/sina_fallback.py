"""
Sina Fallback - Shared utility for fetching market data from Sina Finance API.

Used as fallback when Eastmoney API is blocked by proxy.
"""

import logging
import json
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="sina_fallback_")

try:
    from curl_cffi import requests as curl_requests

    HAS_CURL_CFFI = True
except ImportError:
    import requests as curl_requests

    HAS_CURL_CFFI = False

from app.config.settings import get_settings


def _get_proxies():
    settings = get_settings()
    proxy = settings.get_proxy_url()
    if proxy:
        return {"http": proxy, "https": proxy}
    return None


_PROXIES = _get_proxies()


def fetch_all_stocks_sina_sync(page_size: int = 500) -> List[Dict]:
    """
    Fetch all A-share stocks from Sina API (works through proxy).

    Args:
        page_size: Number of stocks per page (default 500)

    Returns:
        List of stock dictionaries with keys:
        - symbol: Stock code (e.g., "sh600519")
        - name: Stock name
        - price: Latest price
        - change_pct: Change percentage
        - volume: Trading volume
        - amount: Trading amount
        - market_cap: Market capitalization
        - high: Daily high
        - low: Daily low
        - pre_close: Previous close
    """
    try:
        all_stocks = []
        page = 1

        while True:
            url = f"http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page={page}&num={page_size}&sort=changepercent&asc=0&node=hs_a"

            if HAS_CURL_CFFI:
                response = curl_requests.get(
                    url, timeout=15, impersonate="chrome120", proxies=_PROXIES
                )
            else:
                response = curl_requests.get(url, timeout=15, proxies=_PROXIES)

            if response.status_code != 200:
                break

            data = json.loads(response.text)
            if not data:
                break

            for item in data:
                try:
                    symbol = item.get("symbol", "")
                    code = item.get("code", "")

                    # Skip Beijing Stock Exchange stocks
                    if symbol.startswith("bj"):
                        continue

                    all_stocks.append(
                        {
                            "symbol": symbol,
                            "name": item.get("name", ""),
                            "price": float(item.get("trade", 0) or 0),
                            "change_pct": float(item.get("changepercent", 0) or 0),
                            "volume": float(item.get("volume", 0) or 0),
                            "amount": float(item.get("amount", 0) or 0),
                            "market_cap": float(item.get("mktcap", 0) or 0) * 10000,
                            "high": float(item.get("high", 0) or 0),
                            "low": float(item.get("low", 0) or 0),
                            "pre_close": float(item.get("settlement", 0) or 0),
                        }
                    )
                except (ValueError, TypeError):
                    continue

            if len(data) < page_size:
                break
            page += 1

        logger.info(f"[Sina] Fetched {len(all_stocks)} stocks")
        return all_stocks

    except Exception as e:
        logger.error(f"[Sina] Error fetching stocks: {e}", exc_info=True)
        return []


def fetch_sectors_sina_sync() -> List[Dict]:
    """
    Get static sector list as fallback.

    Used when Eastmoney sector API is blocked.

    Returns:
        List of sector dictionaries with keys:
        - name: Sector name
        - code: Sector code
    """
    return [
        {"name": "银行", "code": "BK0477"},
        {"name": "证券", "code": "BK0478"},
        {"name": "保险", "code": "BK0479"},
        {"name": "白酒", "code": "BK0480"},
        {"name": "医药", "code": "BK0481"},
        {"name": "半导体", "code": "BK0482"},
        {"name": "新能源", "code": "BK0483"},
        {"name": "汽车", "code": "BK0484"},
        {"name": "房地产", "code": "BK0485"},
        {"name": "电力", "code": "BK0486"},
        {"name": "煤炭", "code": "BK0487"},
        {"name": "石油", "code": "BK0488"},
        {"name": "钢铁", "code": "BK0489"},
        {"name": "有色金属", "code": "BK0490"},
        {"name": "化工", "code": "BK0491"},
        {"name": "建材", "code": "BK0492"},
        {"name": "机械", "code": "BK0493"},
        {"name": "电子", "code": "BK0494"},
        {"name": "通信", "code": "BK0495"},
        {"name": "计算机", "code": "BK0496"},
        {"name": "传媒", "code": "BK0497"},
        {"name": "零售", "code": "BK0498"},
        {"name": "食品饮料", "code": "BK0499"},
        {"name": "家电", "code": "BK0500"},
        {"name": "纺织服装", "code": "BK0501"},
        {"name": "轻工制造", "code": "BK0502"},
        {"name": "农林牧渔", "code": "BK0503"},
        {"name": "公用事业", "code": "BK0504"},
        {"name": "交通运输", "code": "BK0505"},
        {"name": "建筑装饰", "code": "BK0506"},
    ]


# Async wrappers
async def fetch_all_stocks_sina() -> List[Dict]:
    """Async wrapper for Sina stocks fetching."""
    import asyncio

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, fetch_all_stocks_sina_sync)


async def fetch_sectors_sina() -> List[Dict]:
    """Async wrapper for static sectors."""
    return fetch_sectors_sina_sync()
