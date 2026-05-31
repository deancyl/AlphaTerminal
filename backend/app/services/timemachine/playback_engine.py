"""
Playback Engine - Abstract base class and implementations for K-line replay.

Supports:
- Daily K-line replay (using akshare stock_zh_a_hist)
- Future: Minute-level replay (abstract interface ready)
"""

import asyncio
import httpx
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import List
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="timemachine_")

_akshare = None


def _get_akshare():
    global _akshare
    if _akshare is None:
        import akshare as ak

        _akshare = ak
    return _akshare


@dataclass
class Bar:
    """Single K-line bar data."""

    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float = 0.0
    change_pct: float = 0.0
    turnover: float = 0.0


class PlaybackEngine(ABC):
    """
    Abstract playback engine for K-line replay.

    Subclasses implement specific data sources (daily/minute).
    """

    @abstractmethod
    async def get_bars(
        self, symbol: str, start_date: date, end_date: date
    ) -> List[Bar]:
        """
        Fetch K-line bars for the given date range.

        Args:
            symbol: Stock symbol (e.g., "sh600519")
            start_date: Start date
            end_date: End date

        Returns:
            List of Bar objects sorted by date ascending
        """
        pass

    @abstractmethod
    def get_interval(self) -> str:
        """Return the interval type (e.g., "daily", "minute")."""
        pass

    @abstractmethod
    def get_interval_seconds(self) -> int:
        """Return the interval in seconds (for playback timing)."""
        pass


class DailyPlaybackEngine(PlaybackEngine):
    """
    Daily K-line playback engine using akshare.

    Uses stock_zh_a_hist() for historical daily data.
    """

    def __init__(self, adjust: str = "qfq"):
        """
        Args:
            adjust: Adjustment type - "qfq" (前复权), "hfq" (后复权), "" (不复权)
        """
        self.adjust = adjust
        self._ak = None

    @property
    def ak(self):
        if self._ak is None:
            self._ak = _get_akshare()
        return self._ak

    def get_interval(self) -> str:
        return "daily"

    def get_interval_seconds(self) -> int:
        return 86400

    async def get_bars(
        self, symbol: str, start_date: date, end_date: date
    ) -> List[Bar]:
        """
        Fetch K-line data with 3-tier fallback chain.
        
        Uses timemachine_fetcher for:
        - Level 1: market_data_daily table (local SQLite)
        - Level 2: DataCache (memory + SQLite)
        - Level 3: akshare (real-time)
        - Fallback: Mock data generator
        """
        from app.services.timemachine.timemachine_fetcher import fetch_kline_with_fallback
        from app.services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
        
        # Get or create circuit breaker
        if not hasattr(self, '_cb'):
            self._cb = CircuitBreaker(
                "timemachine_playback",
                CircuitBreakerConfig(failure_threshold=5, timeout=60, success_threshold=2)
            )
        
        try:
            # Use 3-tier fallback chain
            result = await fetch_kline_with_fallback(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                circuit_breaker=self._cb
            )
            
            bars_data = result.get("bars", [])
            
            if not bars_data:
                logger.warning(f"[DailyPlaybackEngine] No bars for {symbol} from fallback chain")
                return []
            
            # Convert to Bar objects
            bars = []
            for bar_dict in bars_data:
                bars.append(
                    Bar(
                        date=str(bar_dict.get("date", "")),
                        open=float(bar_dict.get("open", 0) or 0),
                        high=float(bar_dict.get("high", 0) or 0),
                        low=float(bar_dict.get("low", 0) or 0),
                        close=float(bar_dict.get("close", 0) or 0),
                        volume=float(bar_dict.get("volume", 0) or 0),
                        amount=float(bar_dict.get("amount", 0) or 0),
                        change_pct=float(bar_dict.get("change_pct", 0) or 0),
                        turnover=float(bar_dict.get("turnover", 0) or 0),
                    )
                )
            
            logger.info(
                f"[DailyPlaybackEngine] Fetched {len(bars)} bars for {symbol} "
                f"({start_date} to {end_date}) via {result.get('source_type', 'unknown')}"
            )
            return bars
            
        except Exception as e:
            logger.error(f"[DailyPlaybackEngine] Fallback chain failed for {symbol}: {e}", exc_info=True)
            return []


class MinutePlaybackEngine(PlaybackEngine):
    """
    Minute-level K-line playback engine (placeholder for future implementation).

    Will use intraday data source when available.
    """

    def get_interval(self) -> str:
        return "minute"

    def get_interval_seconds(self) -> int:
        return 60

    async def get_bars(
        self, symbol: str, start_date: date, end_date: date
    ) -> List[Bar]:
        raise NotImplementedError("Minute-level playback is not yet implemented")
