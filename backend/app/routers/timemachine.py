"""
Time-Machine Replay API Router.

Provides endpoints for historical K-line playback with paper trading.
"""
import asyncio
import logging
import uuid
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Dict, Optional, List, Any
from threading import Lock

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.utils.response import success_response, error_response
from app.services.timemachine.playback_engine import (
    PlaybackEngine,
    DailyPlaybackEngine,
    Bar
)
from app.services.timemachine.paper_trading import (
    PaperPortfolio,
    PaperTradingError
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/timemachine", tags=["timemachine"])


class SessionStatus(str, Enum):
    CREATED = "created"
    PLAYING = "playing"
    PAUSED = "paused"
    ENDED = "ended"


class SessionCreateRequest(BaseModel):
    symbol: str = Field(..., description="Stock symbol, e.g., sh600519")
    start_date: str = Field(..., description="Start date, YYYY-MM-DD")
    end_date: str = Field(..., description="End date, YYYY-MM-DD")
    initial_capital: float = Field(1000000, ge=1000, le=1e9, description="Initial capital")
    speed: int = Field(1, ge=1, le=100, description="Bars per second during playback")
    interval: str = Field("daily", description="K-line interval: daily or minute")
    
    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v):
        if not v:
            raise ValueError('symbol is required')
        return v.lower()
    
    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_date(cls, v):
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError('date must be in YYYY-MM-DD format')


class PlayRequest(BaseModel):
    action: str = Field("play", description="play or pause")


class StepRequest(BaseModel):
    bars: int = Field(1, ge=1, le=1000, description="Number of bars to step forward")


class SeekRequest(BaseModel):
    target_bar: int = Field(..., ge=0, description="Target bar index to seek to")


class SpeedRequest(BaseModel):
    speed: float = Field(..., ge=0.1, le=10.0, description="Playback speed multiplier")


class TradeRequest(BaseModel):
    action: str = Field(..., description="buy or sell")
    quantity: float = Field(..., gt=0, description="Number of shares")
    price: Optional[float] = Field(None, ge=0, description="Execution price (null = market)")
    
    @field_validator('action')
    @classmethod
    def validate_action(cls, v):
        if v.lower() not in ('buy', 'sell'):
            raise ValueError('action must be buy or sell')
        return v.lower()


class TimeMachineSession:
    """
    Time-machine replay session.
    
    Manages:
    - K-line data
    - Playback state
    - Paper trading portfolio
    """
    
    SESSION_TTL = 1800  # 30 minutes
    
    def __init__(
        self,
        session_id: str,
        symbol: str,
        start_date: date,
        end_date: date,
        initial_capital: float,
        speed: int,
        interval: str
    ):
        self.session_id = session_id
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.speed = speed
        self.interval = interval
        
        self.bars: List[Bar] = []
        self.current_bar_index = 0
        self.status = SessionStatus.CREATED
        self.portfolio = PaperPortfolio(initial_capital=initial_capital)
        self.engine: Optional[PlaybackEngine] = None
        self.last_activity = datetime.now()
        self._playback_task: Optional[asyncio.Task] = None
    
    def touch(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.now()
    
    def is_expired(self) -> bool:
        """Check if session has expired."""
        return (datetime.now() - self.last_activity).total_seconds() > self.SESSION_TTL
    
    def current_bar(self) -> Optional[Bar]:
        """Get current bar."""
        if 0 <= self.current_bar_index < len(self.bars):
            return self.bars[self.current_bar_index]
        return None
    
    def current_price(self) -> float:
        """Get current close price."""
        bar = self.current_bar()
        return bar.close if bar else 0.0
    
    def current_date(self) -> str:
        """Get current date string."""
        bar = self.current_bar()
        return bar.date if bar else ""
    
    def is_finished(self) -> bool:
        """Check if playback has reached the end."""
        return self.current_bar_index >= len(self.bars) - 1
    
    def to_dict(self, include_bars: bool = False) -> Dict[str, Any]:
        """Serialize session state."""
        current_prices = {self.symbol: self.current_price()}
        
        result = {
            "session_id": self.session_id,
            "symbol": self.symbol,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "interval": self.interval,
            "current_date": self.current_date(),
            "current_bar": self.current_bar_index,
            "total_bars": len(self.bars),
            "status": self.status.value,
            "speed": self.speed,
            "portfolio": self.portfolio.to_dict(current_prices),
            "is_finished": self.is_finished(),
        }
        
        # Include bars data for session creation response
        if include_bars:
            result["bars"] = [
                {
                    "date": b.date,
                    "open": b.open,
                    "high": b.high,
                    "low": b.low,
                    "close": b.close,
                    "volume": b.volume,
                    "amount": b.amount,
                    "change_pct": b.change_pct,
                }
                for b in self.bars
            ]
        
        return result


class SessionManager:
    """Manages time-machine sessions with TTL cleanup."""
    
    _instance = None
    _lock = Lock()
    _sessions: Dict[str, TimeMachineSession] = {}
    _cleanup_task: Optional[asyncio.Task] = None
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance
    
    def create_session(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        initial_capital: float,
        speed: int,
        interval: str
    ) -> TimeMachineSession:
        """Create a new session."""
        session_id = f"tm_{uuid.uuid4().hex[:8]}"
        
        session = TimeMachineSession(
            session_id=session_id,
            symbol=symbol,
            start_date=date.fromisoformat(start_date),
            end_date=date.fromisoformat(end_date),
            initial_capital=initial_capital,
            speed=speed,
            interval=interval
        )
        
        self._sessions[session_id] = session
        return session
    
    def get_session(self, session_id: str) -> Optional[TimeMachineSession]:
        """Get session by ID."""
        return self._sessions.get(session_id)
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self._sessions:
            session = self._sessions[session_id]
            if session._playback_task:
                session._playback_task.cancel()
            del self._sessions[session_id]
            return True
        return False
    
    def cleanup_expired(self):
        """Remove expired sessions."""
        expired = [sid for sid, s in self._sessions.items() if s.is_expired()]
        for sid in expired:
            self.delete_session(sid)
        if expired:
            logger.info(f"[SessionManager] Cleaned up {len(expired)} expired sessions")


_session_manager = SessionManager()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return success_response({
        "status": "ok",
        "active_sessions": len(_session_manager._sessions)
    })


@router.get("/history/{symbol}")
async def get_history(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Get historical K-line data up to a date."""
    try:
        engine = DailyPlaybackEngine()
        
        if not start_date:
            start_date = (date.today() - timedelta(days=365)).isoformat()
        if not end_date:
            end_date = date.today().isoformat()
        
        bars = await engine.get_bars(
            symbol=symbol.lower(),
            start_date=date.fromisoformat(start_date),
            end_date=date.fromisoformat(end_date)
        )
        
        return success_response({
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "interval": engine.get_interval(),
            "bars": [
                {
                    "date": b.date,
                    "open": b.open,
                    "high": b.high,
                    "low": b.low,
                    "close": b.close,
                    "volume": b.volume,
                    "amount": b.amount,
                    "change_pct": b.change_pct,
                }
                for b in bars
            ],
            "total": len(bars)
        })
        
    except Exception as e:
        logger.error(f"[TimeMachine] Failed to get history for {symbol}: {e}")
        return error_response(f"Failed to get history: {str(e)}")


@router.post("/session/create")
async def create_session(request: SessionCreateRequest):
    """Create a new time-machine replay session."""
    try:
        _session_manager.cleanup_expired()
        
        session = _session_manager.create_session(
            symbol=request.symbol,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            speed=request.speed,
            interval=request.interval
        )
        
        if request.interval == "daily":
            session.engine = DailyPlaybackEngine()
        else:
            raise HTTPException(400, "Minute-level playback not yet implemented")
        
        session.bars = await session.engine.get_bars(
            symbol=request.symbol,
            start_date=date.fromisoformat(request.start_date),
            end_date=date.fromisoformat(request.end_date)
        )
        
        if not session.bars:
            _session_manager.delete_session(session.session_id)
            return error_response("No data available for the specified date range")
        
        session.status = SessionStatus.PAUSED
        session.current_bar_index = 0
        
        logger.info(f"[TimeMachine] Created session {session.session_id} for {request.symbol}")
        
        return success_response(session.to_dict(include_bars=True))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[TimeMachine] Failed to create session: {e}")
        return error_response(f"Failed to create session: {str(e)}")


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """Get session state."""
    session = _session_manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found or expired")
    
    session.touch()
    return success_response(session.to_dict())


@router.post("/session/{session_id}/play")
async def play_pause(session_id: str, request: PlayRequest):
    """Start or pause playback."""
    session = _session_manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found or expired")
    
    session.touch()
    
    if request.action == "pause":
        if session._playback_task:
            session._playback_task.cancel()
            session._playback_task = None
        session.status = SessionStatus.PAUSED
        return success_response(session.to_dict())
    
    if session.status == SessionStatus.PLAYING:
        return success_response(session.to_dict())
    
    if session.is_finished():
        raise HTTPException(400, "Playback already finished")
    
    session.status = SessionStatus.PLAYING
    
    async def playback_loop():
        try:
            while session.status == SessionStatus.PLAYING and not session.is_finished():
                session.current_bar_index += 1
                await asyncio.sleep(1.0 / session.speed)
        except asyncio.CancelledError:
            pass
        finally:
            if session.status == SessionStatus.PLAYING:
                session.status = SessionStatus.PAUSED
    
    session._playback_task = asyncio.create_task(playback_loop())
    
    return success_response(session.to_dict())


@router.post("/session/{session_id}/step")
async def step_forward(session_id: str, request: StepRequest):
    """Step forward N bars."""
    session = _session_manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found or expired")
    
    session.touch()
    
    if session.status == SessionStatus.PLAYING:
        raise HTTPException(400, "Cannot step while playing. Pause first.")
    
    new_index = min(session.current_bar_index + request.bars, len(session.bars) - 1)
    session.current_bar_index = new_index
    
    return success_response(session.to_dict())


@router.post("/session/{session_id}/seek")
async def seek_to(session_id: str, request: SeekRequest):
    """Seek to a specific bar in the playback."""
    session = _session_manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found or expired")
    
    session.touch()
    
    if session.status == SessionStatus.PLAYING:
        raise HTTPException(400, "Cannot seek while playing. Pause first.")
    
    max_bar = len(session.bars) - 1
    session.current_bar_index = max(0, min(request.target_bar, max_bar))
    
    return success_response({
        "success": True,
        "current_bar": session.current_bar_index,
        "total_bars": len(session.bars)
    })


@router.post("/session/{session_id}/speed")
async def set_speed(session_id: str, request: SpeedRequest):
    """Set playback speed multiplier."""
    session = _session_manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found or expired")
    
    session.touch()
    session.speed = request.speed
    
    return success_response({
        "success": True,
        "speed": session.speed
    })


@router.post("/session/{session_id}/trade")
async def execute_trade(session_id: str, request: TradeRequest):
    """Execute a paper trade."""
    session = _session_manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found or expired")
    
    session.touch()
    
    if session.status == SessionStatus.ENDED:
        raise HTTPException(400, "Session has ended")
    
    price = request.price if request.price else session.current_price()
    
    if price <= 0:
        raise HTTPException(400, "Cannot determine execution price")
    
    try:
        trade = session.portfolio.execute_trade(
            action=request.action,
            symbol=session.symbol,
            quantity=request.quantity,
            price=price,
            current_date=session.current_date(),
            current_bar_index=session.current_bar_index
        )
        
        logger.info(f"[TimeMachine] Trade executed: {trade.action.value} {trade.quantity} @ {trade.price}")
        
        return success_response({
            "success": True,
            "trade": {
                "id": trade.id,
                "date": trade.date,
                "action": trade.action.value,
                "price": round(trade.price, 2),
                "quantity": trade.quantity,
                "value": round(trade.value, 2),
                "commission": round(trade.commission, 2),
                "pnl": round(trade.pnl, 2),
            },
            "portfolio": session.portfolio.to_dict({session.symbol: session.current_price()})
        })
        
    except PaperTradingError as e:
        raise HTTPException(400, str(e))


@router.get("/session/{session_id}/portfolio")
async def get_portfolio(session_id: str):
    """Get paper portfolio state."""
    session = _session_manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found or expired")
    
    session.touch()
    
    return success_response({
        "portfolio": session.portfolio.to_dict({session.symbol: session.current_price()}),
        "trades": session.portfolio.trades_to_dict()
    })


@router.delete("/session/{session_id}")
async def end_session(session_id: str):
    """End and delete a session."""
    session = _session_manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found or expired")
    
    session.status = SessionStatus.ENDED
    _session_manager.delete_session(session_id)
    
    logger.info(f"[TimeMachine] Session {session_id} ended")
    
    return success_response({"message": "Session ended successfully"})
