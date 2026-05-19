"""
Time-Machine Replay Services

This module provides services for historical K-line replay with paper trading.
"""
from .playback_engine import PlaybackEngine, DailyPlaybackEngine, Bar
from .paper_trading import (
    PaperPortfolio,
    Position,
    Trade,
    TradeAction,
    PaperTradingError
)

__all__ = [
    "PlaybackEngine",
    "DailyPlaybackEngine",
    "Bar",
    "PaperPortfolio",
    "Position",
    "Trade",
    "TradeAction",
    "PaperTradingError",
]
