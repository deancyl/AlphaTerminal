"""
Playback Engine - Abstract base class and implementations for K-line replay.

Supports:
- Daily K-line replay (using akshare stock_zh_a_hist)
- Future: Minute-level replay (abstract interface ready)
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional, Dict, Any
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
        self,
        symbol: str,
        start_date: date,
        end_date: date
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
        self,
        symbol: str,
        start_date: date,
        end_date: date
    ) -> List[Bar]:
        code = symbol[2:] if symbol.startswith(('sh', 'sz')) else symbol
        
        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")
        
        def _fetch():
            try:
                df = self.ak.stock_zh_a_hist(
                    symbol=code,
                    period="daily",
                    adjust=self.adjust,
                    start_date=start_str,
                    end_date=end_str,
                )
                
                if df is None or df.empty:
                    return []
                
                bars = []
                for _, row in df.iterrows():
                    bars.append(Bar(
                        date=str(row.get('日期', '')),
                        open=float(row.get('开盘', 0) or 0),
                        high=float(row.get('最高', 0) or 0),
                        low=float(row.get('最低', 0) or 0),
                        close=float(row.get('收盘', 0) or 0),
                        volume=float(row.get('成交量', 0) or 0),
                        amount=float(row.get('成交额', 0) or 0),
                        change_pct=float(row.get('涨跌幅', 0) or 0),
                        turnover=float(row.get('换手率', 0) or 0),
                    ))
                return bars
                
            except Exception as e:
                logger.error(f"[DailyPlaybackEngine] Failed to fetch bars for {symbol}: {e}")
                return []
        
        loop = asyncio.get_running_loop()
        bars = await asyncio.wait_for(
            loop.run_in_executor(_executor, _fetch),
            timeout=30.0
        )
        
        logger.info(f"[DailyPlaybackEngine] Fetched {len(bars)} bars for {symbol} ({start_date} to {end_date})")
        return bars


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
        self,
        symbol: str,
        start_date: date,
        end_date: date
    ) -> List[Bar]:
        raise NotImplementedError("Minute-level playback is not yet implemented")
