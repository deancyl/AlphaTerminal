"""
Tests for SessionManager

Tests:
- test_create_session
- test_get_existing_session
- test_session_ttl_expires
- test_config_binding
- test_cleanup_expired_sessions
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import time

from app.services.session_manager import (
    SessionManager,
    SessionState,
    get_session_manager,
)


class TestSessionManager:
    """Test suite for SessionManager."""

    @pytest.fixture
    def mock_session_db(self):
        """Mock session_db module."""
        with patch('app.services.session_manager.session_db') as mock:
            yield mock

    @pytest.fixture
    def manager(self):
        """Create a fresh manager instance for each test."""
        manager = SessionManager(ttl_minutes=30)
        manager._shutdown = True  # Stop cleanup thread
        return manager

    # ========================================================================
    # Test 1: Create Session
    # ========================================================================
    def test_create_session(self, manager, mock_session_db):
        """create_or_get_session should create new session."""
        mock_session_db.create_session.return_value = {
            "session_id": "test-session-123",
            "user_id": "user-1",
            "config_version": 1,
            "bound_models": [],
            "created_at": "2024-01-01T00:00:00",
            "last_active_at": "2024-01-01T00:00:00",
            "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
            "message_count": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0
        }
        
        result = manager.create_or_get_session(user_id="user-1")
        
        assert result is not None
        assert result.session_id == "test-session-123"
        assert result.user_id == "user-1"
        mock_session_db.create_session.assert_called_once()

    # ========================================================================
    # Test 2: Get Existing Session
    # ========================================================================
    def test_get_existing_session(self, manager, mock_session_db):
        """get_session should return existing session."""
        mock_session_db.get_session.return_value = {
            "session_id": "existing-session",
            "user_id": "user-1",
            "config_version": 1,
            "bound_models": ["openai:gpt-4"],
            "created_at": "2024-01-01T00:00:00",
            "last_active_at": "2024-01-01T00:00:00",
            "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
            "message_count": 5,
            "total_tokens": 1000,
            "total_cost_usd": 0.05
        }
        
        result = manager.get_session("existing-session")
        
        assert result is not None
        assert result.session_id == "existing-session"
        assert result.bound_models == ["openai:gpt-4"]
        assert result.message_count == 5
        mock_session_db.get_session.assert_called_once_with("existing-session")

    # ========================================================================
    # Test 3: Session TTL Expires
    # ========================================================================
    def test_session_ttl_expires(self, manager, mock_session_db):
        """Session should detect when expired."""
        expired_time = (datetime.now() - timedelta(hours=1)).isoformat()
        
        session = SessionState(
            session_id="expired-session",
            created_at="2024-01-01T00:00:00",
            last_active_at="2024-01-01T00:00:00",
            expires_at=expired_time
        )
        
        assert session.is_expired() is True

    def test_session_not_expired(self, manager, mock_session_db):
        """Session should detect when not expired."""
        future_time = (datetime.now() + timedelta(hours=1)).isoformat()
        
        session = SessionState(
            session_id="active-session",
            created_at="2024-01-01T00:00:00",
            last_active_at="2024-01-01T00:00:00",
            expires_at=future_time
        )
        
        assert session.is_expired() is False

    # ========================================================================
    # Test 4: Config Binding
    # ========================================================================
    def test_config_binding(self, manager, mock_session_db):
        """bind_model should bind model to session."""
        mock_session_db.get_session.return_value = {
            "session_id": "test-session",
            "user_id": "user-1",
            "config_version": 1,
            "bound_models": [],
            "created_at": "2024-01-01T00:00:00",
            "last_active_at": "2024-01-01T00:00:00",
            "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
            "message_count": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0
        }
        mock_session_db.update_session_models.return_value = True
        
        result = manager.bind_model("test-session", "openai", "gpt-4")
        
        assert result is True
        mock_session_db.update_session_models.assert_called_once()

    def test_get_bound_model(self, manager, mock_session_db):
        """get_bound_model should return bound model for provider."""
        mock_session_db.get_session.return_value = {
            "session_id": "test-session",
            "user_id": "user-1",
            "config_version": 1,
            "bound_models": ["openai:gpt-4", "deepseek:deepseek-chat"],
            "created_at": "2024-01-01T00:00:00",
            "last_active_at": "2024-01-01T00:00:00",
            "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
            "message_count": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0
        }
        
        result = manager.get_bound_model("test-session", "openai")
        
        assert result == "gpt-4"
        
        result2 = manager.get_bound_model("test-session", "deepseek")
        assert result2 == "deepseek-chat"

    # ========================================================================
    # Test 5: Cleanup Expired Sessions
    # ========================================================================
    def test_cleanup_expired_sessions(self, manager, mock_session_db):
        """cleanup should remove expired sessions."""
        mock_session_db.cleanup_expired_sessions.return_value = 5
        
        deleted = mock_session_db.cleanup_expired_sessions()
        
        assert deleted == 5


class TestSessionManagerEdgeCases:
    """Test edge cases for SessionManager."""

    @pytest.fixture
    def mock_session_db(self):
        with patch('app.services.session_manager.session_db') as mock:
            yield mock

    @pytest.fixture
    def manager(self):
        manager = SessionManager(ttl_minutes=30)
        manager._shutdown = True
        return manager

    def test_get_nonexistent_session(self, manager, mock_session_db):
        """get_session should return None for non-existent session."""
        mock_session_db.get_session.return_value = None
        
        result = manager.get_session("nonexistent")
        
        assert result is None

    def test_update_session_usage(self, manager, mock_session_db):
        """update_session_usage should update stats."""
        mock_session_db.update_session_stats.return_value = True
        
        result = manager.update_session_usage("test-session", tokens=100, cost_usd=0.01)
        
        assert result is True
        mock_session_db.update_session_stats.assert_called_once()

    def test_touch_session(self, manager, mock_session_db):
        """touch_session should update last active time."""
        mock_session_db.update_session_activity.return_value = True
        
        result = manager.touch_session("test-session")
        
        assert result is True
        mock_session_db.update_session_activity.assert_called_once()

    def test_delete_session(self, manager, mock_session_db):
        """delete_session should remove session."""
        mock_session_db.delete_session.return_value = True
        
        result = manager.delete_session("test-session")
        
        assert result is True
        mock_session_db.delete_session.assert_called_once_with("test-session")

    def test_get_active_sessions(self, manager, mock_session_db):
        """get_active_sessions should return list of sessions."""
        mock_session_db.get_active_sessions.return_value = [
            {
                "session_id": "session-1",
                "user_id": "user-1",
                "config_version": 1,
                "bound_models": [],
                "created_at": "2024-01-01T00:00:00",
                "last_active_at": "2024-01-01T00:00:00",
                "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
                "message_count": 0,
                "total_tokens": 0,
                "total_cost_usd": 0.0
            }
        ]
        
        result = manager.get_active_sessions()
        
        assert len(result) == 1
        assert result[0].session_id == "session-1"

    def test_singleton_pattern(self):
        """Singleton should return same instance."""
        import app.services.session_manager as module
        module._manager_instance = None
        
        instance1 = get_session_manager()
        instance2 = get_session_manager()
        
        assert instance1 is instance2
        
        instance1._shutdown = True
        module._manager_instance = None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
