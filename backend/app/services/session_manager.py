"""
Session Manager Service

Session management with TTL enforcement and config binding.

Key Features:
- Session creation with config binding
- TTL enforcement (30 minutes default)
- Background cleanup thread for expired sessions
- Session stats tracking (tokens, cost)
- Thread-safe operations
"""
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from threading import RLock

from app.db import session_db

logger = logging.getLogger(__name__)

DEFAULT_SESSION_TTL_MINUTES = 30
CLEANUP_INTERVAL_SECONDS = 60


@dataclass
class SessionState:
    """Session state container"""
    session_id: str
    user_id: Optional[str] = None
    config_version: int = 1
    bound_models: List[str] = field(default_factory=list)
    created_at: str = ""
    last_active_at: str = ""
    expires_at: str = ""
    message_count: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    
    def is_expired(self) -> bool:
        return datetime.now() > datetime.fromisoformat(self.expires_at)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "config_version": self.config_version,
            "bound_models": self.bound_models,
            "created_at": self.created_at,
            "last_active_at": self.last_active_at,
            "expires_at": self.expires_at,
            "message_count": self.message_count,
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost_usd
        }


class SessionManager:
    """
    Session management with TTL enforcement.
    
    Features:
    - Create/get sessions with config binding
    - TTL enforcement with background cleanup
    - Usage tracking (tokens, cost)
    """
    
    def __init__(self, ttl_minutes: int = DEFAULT_SESSION_TTL_MINUTES):
        self._lock = RLock()
        self._ttl_minutes = ttl_minutes
        self._cleanup_thread: Optional[threading.Thread] = None
        self._shutdown = False
        
        self._start_cleanup_thread()
        logger.info(f"[SessionManager] Initialized with TTL={ttl_minutes}min")
    
    def _start_cleanup_thread(self):
        """Start background cleanup thread (daemon)"""
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name="SessionCleanup"
        )
        self._cleanup_thread.start()
    
    def _cleanup_loop(self):
        """Background cleanup loop"""
        while not self._shutdown:
            try:
                time.sleep(CLEANUP_INTERVAL_SECONDS)
                deleted = session_db.cleanup_expired_sessions()
                if deleted > 0:
                    logger.debug(f"[SessionManager] Cleaned up {deleted} expired sessions")
            except Exception as e:
                logger.error(f"[SessionManager] Cleanup error: {e}")
    
    def create_or_get_session(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        config_version: int = 1
    ) -> SessionState:
        """
        Create a new session or get existing one.
        
        Args:
            session_id: Optional session ID (generates UUID if not provided)
            user_id: Optional user ID
            config_version: Config version to bind
            
        Returns:
            SessionState
        """
        if session_id:
            existing = self.get_session(session_id)
            if existing and not existing.is_expired():
                self.touch_session(session_id)
                return existing
        
        session_data = session_db.create_session(
            user_id=user_id,
            config_version=config_version,
            ttl_hours=self._ttl_minutes // 60 or 1
        )
        
        return SessionState(
            session_id=session_data["session_id"],
            user_id=session_data.get("user_id"),
            config_version=session_data.get("config_version", 1),
            bound_models=session_data.get("bound_models", []),
            created_at=session_data["created_at"],
            last_active_at=session_data["last_active_at"],
            expires_at=session_data["expires_at"],
            message_count=session_data.get("message_count", 0),
            total_tokens=session_data.get("total_tokens", 0),
            total_cost_usd=session_data.get("total_cost_usd", 0.0)
        )
    
    def get_session(self, session_id: str) -> Optional[SessionState]:
        """
        Get session by ID.
        
        Args:
            session_id: Session ID
            
        Returns:
            SessionState or None
        """
        data = session_db.get_session(session_id)
        if not data:
            return None
        
        return SessionState(
            session_id=data["session_id"],
            user_id=data.get("user_id"),
            config_version=data.get("config_version", 1),
            bound_models=data.get("bound_models", []),
            created_at=data["created_at"],
            last_active_at=data["last_active_at"],
            expires_at=data["expires_at"],
            message_count=data.get("message_count", 0),
            total_tokens=data.get("total_tokens", 0),
            total_cost_usd=data.get("total_cost_usd", 0.0)
        )
    
    def get_bound_model(self, session_id: str, provider: str) -> Optional[str]:
        """
        Get the bound model for a provider in this session.
        
        Args:
            session_id: Session ID
            provider: Provider name
            
        Returns:
            Model ID or None
        """
        session = self.get_session(session_id)
        if not session:
            return None
        
        for binding in session.bound_models:
            if ":" in binding:
                p, m = binding.split(":", 1)
                if p == provider:
                    return m
        
        return None
    
    def bind_model(self, session_id: str, provider: str, model_id: str) -> bool:
        """
        Bind a model to the session.
        
        Args:
            session_id: Session ID
            provider: Provider name
            model_id: Model ID
            
        Returns:
            Success status
        """
        session = self.get_session(session_id)
        if not session:
            return False
        
        binding = f"{provider}:{model_id}"
        bound_models = session.bound_models.copy()
        
        existing_idx = None
        for i, b in enumerate(bound_models):
            if b.startswith(f"{provider}:"):
                existing_idx = i
                break
        
        if existing_idx is not None:
            bound_models[existing_idx] = binding
        else:
            bound_models.append(binding)
        
        return session_db.update_session_models(session_id, bound_models)
    
    def update_session_usage(
        self,
        session_id: str,
        tokens: int,
        cost_usd: float
    ) -> bool:
        """
        Update session usage stats.
        
        Args:
            session_id: Session ID
            tokens: Tokens to add
            cost_usd: Cost to add
            
        Returns:
            Success status
        """
        return session_db.update_session_stats(
            session_id,
            tokens_added=tokens,
            cost_added=cost_usd
        )
    
    def touch_session(self, session_id: str) -> bool:
        """
        Update session last active time.
        
        Args:
            session_id: Session ID
            
        Returns:
            Success status
        """
        return session_db.update_session_activity(session_id)
    
    def extend_session(self, session_id: str, additional_minutes: int = 30) -> bool:
        """
        Extend session TTL.
        
        Args:
            session_id: Session ID
            additional_minutes: Minutes to add
            
        Returns:
            Success status
        """
        return session_db.extend_session(
            session_id,
            additional_hours=additional_minutes // 60 or 1
        )
    
    def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """
        Get session statistics.
        
        Args:
            session_id: Session ID
            
        Returns:
            Stats dict
        """
        from app.db.token_usage_db import get_session_totals
        return get_session_totals(session_id) or {}
    
    def get_active_sessions(self, limit: int = 100) -> List[SessionState]:
        """
        Get all active sessions.
        
        Args:
            limit: Max sessions to return
            
        Returns:
            List of SessionState
        """
        sessions = session_db.get_active_sessions(limit)
        return [
            SessionState(
                session_id=s["session_id"],
                user_id=s.get("user_id"),
                config_version=s.get("config_version", 1),
                bound_models=s.get("bound_models", []),
                created_at=s["created_at"],
                last_active_at=s["last_active_at"],
                expires_at=s["expires_at"],
                message_count=s.get("message_count", 0),
                total_tokens=s.get("total_tokens", 0),
                total_cost_usd=s.get("total_cost_usd", 0.0)
            )
            for s in sessions
        ]
    
    def get_user_sessions(self, user_id: str) -> List[SessionState]:
        """
        Get all sessions for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of SessionState
        """
        sessions = session_db.get_sessions_by_user(user_id)
        return [
            SessionState(
                session_id=s["session_id"],
                user_id=s.get("user_id"),
                config_version=s.get("config_version", 1),
                bound_models=s.get("bound_models", []),
                created_at=s["created_at"],
                last_active_at=s["last_active_at"],
                expires_at=s["expires_at"],
                message_count=s.get("message_count", 0),
                total_tokens=s.get("total_tokens", 0),
                total_cost_usd=s.get("total_cost_usd", 0.0)
            )
            for s in sessions
        ]
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Success status
        """
        return session_db.delete_session(session_id)
    
    def get_global_stats(self) -> Dict[str, Any]:
        """
        Get global session statistics.
        
        Returns:
            Stats dict
        """
        return session_db.get_session_stats()
    
    def shutdown(self):
        """Shutdown cleanup thread"""
        self._shutdown = True


_manager_instance: Optional[SessionManager] = None
_manager_lock = threading.Lock()


def get_session_manager() -> SessionManager:
    """Get singleton SessionManager instance"""
    global _manager_instance
    if _manager_instance is None:
        with _manager_lock:
            if _manager_instance is None:
                _manager_instance = SessionManager()
    return _manager_instance
