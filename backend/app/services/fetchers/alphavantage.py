"""
alphavantage.py — Alphavantage 海外数据源 fetcher

支持：
- 美股实时行情（FX & Stock Quote）
- 外汇实时报价
- K线历史数据

API Key: 从环境变量 ALPHA_VANTAGE_API_KEY 读取
文档: https://www.alphavantage.co/documentation/

注意：
- 免费 tier: 25 req/day (5 req/min)
- 支持 FX (USD/CNY 等) 和 US Stock (IBM, AAPL 等)
- symbol 格式: "IBM", "AAPL" (美股), "USD/CNY" (外汇)
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from typing import Optional, List

from .base import BaseMarketFetcher
from ..http_client import ValidatedHTTPClient
from ..circuit_breaker import CircuitBreaker
from ..data_validator import QuoteData, KlineData, MarketType, DataType

logger = logging.getLogger(__name__)

BASE_URL = "https://www.alphavantage.co/query"
API_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY", "")

# Alphavantage → 标准 MarketType 映射
SYMBOL_TO_MARKET = {
    "forex": MarketType.FOREX,
    "crypto": MarketType.US,
}

# 常见美股 → AShare 代码映射（Alphavantage 格式）
US_SYMBOLS = {
    "IBM", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA",
    "JPM", "GS", "MS", "BAC", "WFC",
    "JNJ", "UNH", "PFE", "ABBV",
    "XOM", "CVX", "COP",
    "DIS", "NFLX", "CMCSA",
}

# 外汇对
FOREX_PAIRS = {"USD/CNY", "EUR/USD", "USD/JPY", "GBP/USD", "USD/HKD"}


def _is_forex(symbol: str) -> bool:
    return "/" in symbol.upper() or symbol.upper() in {"USDCNY", "EURUSD", "USDJPY", "GBPUDS", "USDHKD"}


def _is_us_stock(symbol: str) -> bool:
    s = symbol.upper()
    return s in US_SYMBOLS or (len(s) <= 5 and s.isalpha())


class AlphavantageFetcher(BaseMarketFetcher):
    """
    Alphavantage API fetcher。
    支持：美股、外汇、加密货币、K线。
    """

    name = "alphavantage"
    display_name = "Alphavantage (US/FX)"

    supports_quote = True
    supports_kline = True
    supports_order_book = False
    supports_futures = False
    supports_hk = False
    supports_us = True

    # Alphavantage rate limit: 5 req/min, 25 req/day
    _rate_limit_delay: float = 12.0  # 2 req per 12s to be safe
    _last_request_time: float = 0.0

    def __init__(
        self,
        proxy: Optional[str] = None,
        cb: Optional[CircuitBreaker] = None,
        api_key: str = API_KEY,
    ):
        self.proxy = proxy
        self.cb = cb
        self.api_key = api_key
        self._http: Optional[ValidatedHTTPClient] = None

    async def _get_http(self) -> ValidatedHTTPClient:
        if self._http is None:
            self._http = ValidatedHTTPClient(
                proxy=self.proxy,
                timeout=15.0,
                max_retries=3,
                circuit_breaker=self.cb,
            )
        return self._http

    def _rate_limit(self):
        """简单时间窗口限速（5 req/min）"""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._rate_limit_delay:
            time.sleep(self._rate_limit_delay - elapsed)
        self._last_request_time = time.time()

    # ── Quote ────────────────────────────────────────────────────────────

    async def get_quote(self, symbol: str) -> Optional[QuoteData]:
        """
        获取美股或外汇实时报价。

        美股: function=GLOBAL_QUOTE&symbol=IBM
        外汇: function=CURRENCY_EXCHANGE_RATE&from_currency=USD&to_currency=CNY
        """
        try:
            if _is_forex(symbol):
                return await self._get_forex_quote(symbol)
            else:
                return await self._get_stock_quote(symbol)
        except Exception as e:
            logger.error(f"[Alphavantage] get_quote({symbol}) failed: {e}")
            if self.cb:
                self.cb.record_failure()
            return None

    async def _get_stock_quote(self, symbol: str) -> Optional[QuoteData]:
        """美股报价"""
        http = await self._get_http()
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": symbol.upper(),
            "apikey": self.api_key,
        }

        resp = await http.get_with_retry(BASE_URL, params=params)
        data = resp.json()

        # Alphavantage 全局错误检测
        if "Note" in data or "Information" in data:
            logger.warning(f"[Alphavantage] API 调用受限 (rate limit): {data}")
            if self.cb:
                self.cb.record_failure()
            return None

        if "Error Message" in data:
            logger.error(f"[Alphavantage] Symbol 无效: {symbol}: {data}")
            return None

        quote = data.get("Global Quote", {})
        if not quote:
            logger.warning(f"[Alphavantage] 空行情: {symbol}")
            return None

        try:
            price = float(quote.get("05. price", 0))
            prev_close = float(quote.get("08. previous close", 0))
            change_pct = float(quote.get("10. change percent", "0").rstrip("%"))
            change = float(quote.get("09. change", 0))
            volume = float(quote.get("06. volume", 0))
            high = float(quote.get("03. high", 0))
            low = float(quote.get("04. low", 0))
            open_price = float(quote.get("02. open", prev_close))

            return QuoteData(
                symbol=symbol.upper(),
                name=symbol.upper(),
                market=MarketType.US,
                price=price,
                prev_close=prev_close,
                open=open_price,
                high=high,
                low=low,
                change_pct=round(change_pct, 4),
                change=round(change, 4),
                volume=volume,
                timestamp=int(quote.get("07. latest trading day", 0) or time.time()),
                data_type=DataType.STOCK,
                source="alphavantage",
            )
        except (ValueError, KeyError) as e:
            logger.error(f"[Alphavantage] 解析失败 {symbol}: {e}, quote={quote}")
            return None

    async def _get_forex_quote(self, symbol: str) -> Optional[QuoteData]:
        """外汇报价"""
        http = await self._get_http()

        # 解析 symbol (e.g. "USD/CNY" or "USDCNY")
        parts = symbol.replace("=", "/").upper().split("/")
        if len(parts) != 2:
            parts = [symbol[:3], symbol[3:]]
        from_cur, to_cur = parts[0], parts[1]

        params = {
            "function": "CURRENCY_EXCHANGE_RATE",
            "from_currency": from_cur,
            "to_currency": to_cur,
            "apikey": self.api_key,
        }

        resp = await http.get_with_retry(BASE_URL, params=params)
        data = resp.json()

        if "Note" in data or "Information" in data:
            logger.warning(f"[Alphavantage] FX API rate limit: {data}")
            return None

        if "Error Message" in data:
            logger.error(f"[Alphavantage] FX symbol 无效: {symbol}: {data}")
            return None

        rate_data = data.get("Realtime Currency Exchange Rate", {})
        if not rate_data:
            return None

        try:
            from_rate = float(rate_data.get("5. Exchange Rate", 0))
            inv_rate = 1.0 / from_rate if from_rate else 0
            prev_close = inv_rate  # Alphavantage FX 没有昨日收盘，用实时汇率近似

            return QuoteData(
                symbol=symbol.upper(),
                name=f"{from_cur}/{to_cur}",
                market=MarketType.FOREX,
                price=from_rate,
                prev_close=prev_close,
                open=from_rate,
                high=from_rate,
                low=from_rate,
                change_pct=0.0,   # FX 无涨跌幅概念
                change=0.0,
                volume=0.0,
                timestamp=int(time.time()),
                data_type=DataType.REALTIME,
                source="alphavantage",
            )
        except (ValueError, KeyError) as e:
            logger.error(f"[Alphavantage] FX 解析失败 {symbol}: {e}")
            return None

    # ── K-line ────────────────────────────────────────────────────────────

    async def get_kline(
        self,
        symbol: str,
        period: str = "day",
        output_size: str = "compact",  # "compact"=100条, "full"=20年
    ) -> Optional[List[dict]]:
        """
        获取美股历史 K 线。

        period → Alphavantage:
        - minute / day → TIME_SERIES_INTRADAY (仅美股交易时段)
        - day / week / month → TIME_SERIES_DAILY / WEEKLY / MONTHLY
        """
        if _is_forex(symbol):
            return await self._get_forex_kline(symbol, period)

        http = await self._get_http()
        interval_map = {
            "minute": "5min",
            "day": None,
            "week": None,
            "month": None,
        }

        if period == "day":
            func = "TIME_SERIES_DAILY"
            key = "Time Series (Daily)"
        elif period == "week":
            func = "TIME_SERIES_WEEKLY"
            key = "Weekly Time Series"
        elif period == "month":
            func = "TIME_SERIES_MONTHLY"
            key = "Monthly Time Series"
        else:
            func = "TIME_SERIES_INTRADAY"
            interval = interval_map.get(period, "5min")
            key = f"Time Series ({interval})"

        params = {
            "function": func,
            "symbol": symbol.upper(),
            "apikey": self.api_key,
            "outputsize": output_size,
        }
        if interval:
            params["interval"] = interval

        resp = await http.get_with_retry(BASE_URL, params=params)
        data = resp.json()

        if "Note" in data or "Information" in data:
            logger.warning(f"[Alphavantage] K线 API 受限: {data}")
            return None

        series = data.get(key, {})
        if not series:
            logger.warning(f"[Alphavantage] 空 K线数据: {symbol}, key={key}")
            return None

        klines = []
        for date_str, vals in series.items():
            try:
                klines.append({
                    "symbol": symbol.upper(),
                    "date": date_str,
                    "period": period,
                    "open": float(vals.get("1. open", 0)),
                    "high": float(vals.get("2. high", 0)),
                    "low": float(vals.get("3. low", 0)),
                    "close": float(vals.get("4. close", 0)),
                    "volume": float(vals.get("5. volume", 0)),
                    "timestamp": int(datetime.fromisoformat(date_str).timestamp()),
                    "source": "alphavantage",
                })
            except (ValueError, KeyError):
                continue

        logger.info(f"[Alphavantage] get_kline({symbol}, {period}): {len(klines)} 条")
        return klines

    async def _get_forex_kline(self, symbol: str, period: str) -> Optional[List[dict]]:
        """外汇 K线"""
        http = await self._get_http()
        parts = symbol.replace("=", "/").upper().split("/")
        if len(parts) != 2:
            return None
        from_cur, to_cur = parts[0], parts[1]

        func_map = {
            "day": "FX_DAILY",
            "week": "FX_WEEKLY",
            "month": "FX_MONTHLY",
        }
        func = func_map.get(period, "FX_DAILY")
        params = {
            "function": func,
            "from_symbol": from_cur,
            "to_symbol": to_cur,
            "apikey": self.api_key,
        }

        resp = await http.get_with_retry(BASE_URL, params=params)
        data = resp.json()

        if "Note" in data or "Information" in data:
            return None

        key = {"FX_DAILY": "Time Series FX (Daily)", "FX_WEEKLY": "Weekly FX Rates", "FX_MONTHLY": "Monthly FX Rates"}.get(func, "")
        series = data.get(key, {})

        klines = []
        for date_str, vals in series.items():
            try:
                klines.append({
                    "symbol": symbol.upper(),
                    "date": date_str,
                    "period": period,
                    "open": float(vals.get("1. open", 0)),
                    "high": float(vals.get("2. high", 0)),
                    "low": float(vals.get("3. low", 0)),
                    "close": float(vals.get("4. close", 0)),
                    "volume": 0.0,
                    "timestamp": int(datetime.fromisoformat(date_str).timestamp()),
                    "source": "alphavantage",
                })
            except (ValueError, KeyError):
                continue
        return klines

    # ── Health ────────────────────────────────────────────────────────────

    async def ping(self) -> bool:
        """健康检查：用 IBM 报价验证连通性"""
        try:
            result = await self._get_stock_quote("IBM")
            return result is not None
        except Exception:
            return False

    async def close(self):
        if self._http:
            await self._http.close()
