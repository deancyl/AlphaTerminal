"""
Unit tests for Agent Token Database Service.

Tests cover:
- Database initialization
- Token CRUD operations
- Audit logging
- Database indexes
- Thread safety
- Debug logging
"""

import os
import tempfile
import uuid
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

# Save original env state for cleanup
_AGENT_DB_DEBUG_ORIGINAL = os.environ.get("AGENT_DB_DEBUG", None)

# Set debug mode before import
os.environ["AGENT_DB_DEBUG"] = "true"

from app.db.agent_db import (
    AgentDB,
    AgentToken,
    AuditLog,
    get_agent_db,
    init_agent_db,
)


@pytest.fixture(autouse=True)
def cleanup_agent_db_debug_env():
    """Ensure AGENT_DB_DEBUG is cleaned up after each test."""
    yield
    # Restore original state
    if _AGENT_DB_DEBUG_ORIGINAL is None:
        os.environ.pop("AGENT_DB_DEBUG", None)
    else:
        os.environ["AGENT_DB_DEBUG"] = _AGENT_DB_DEBUG_ORIGINAL


def cleanup_env():
    """Module-level cleanup function."""
    if _AGENT_DB_DEBUG_ORIGINAL is None:
        os.environ.pop("AGENT_DB_DEBUG", None)
    else:
        os.environ["AGENT_DB_DEBUG"] = _AGENT_DB_DEBUG_ORIGINAL


# Register cleanup at module level
import atexit
atexit.register(cleanup_env)


class TestAgentTokenDataclass:
    """Test AgentToken dataclass."""

    def test_agent_token_creation(self):
        """Test basic AgentToken creation."""
        token = AgentToken(
            id="test-id",
            name="test-token",
            token_hash="hash123",
            token_prefix="AGT1_abc",
            scopes=["R", "W"],
        )
        assert token.id == "test-id"
        assert token.name == "test-token"
        assert token.token_hash == "hash123"
        assert token.scopes == ["R", "W"]
        assert token.is_active is True
        assert token.paper_only is True
        assert token.rate_limit == 120
        assert token.request_count == 0

    def test_agent_token_with_custom_values(self):
        """Test AgentToken with custom values."""
        token = AgentToken(
            id="test-id",
            name="test-token",
            token_hash="hash123",
            token_prefix="AGT1_abc",
            scopes=["R"],
            markets=["ASTOCK", "HKSTOCK"],
            instruments=["000001", "600519"],
            paper_only=False,
            rate_limit=60,
            request_count=10,
            expires_at=(datetime.now() + timedelta(days=7)).isoformat(),
        )
        assert token.markets == ["ASTOCK", "HKSTOCK"]
        assert token.instruments == ["000001", "600519"]
        assert token.paper_only is False
        assert token.rate_limit == 60
        assert token.request_count == 10
        assert token.expires_at is not None

    def test_agent_token_to_dict(self):
        """Test AgentToken serialization."""
        token = AgentToken(
            id="test-id",
            name="test-token",
            token_hash="hash123",
            token_prefix="AGT1_abc",
            scopes=["R", "W"],
            markets=["ASTOCK"],
        )
        data = token.to_dict()
        assert data["id"] == "test-id"
        assert data["name"] == "test-token"
        assert data["scopes"] == ["R", "W"]
        assert data["markets"] == ["ASTOCK"]

    def test_agent_token_from_dict(self):
        """Test AgentToken deserialization."""
        data = {
            "id": "test-id",
            "name": "test-token",
            "token_hash": "hash123",
            "token_prefix": "AGT1_abc",
            "scopes": ["R"],
            "markets": ["ASTOCK"],
            "instruments": ["*"],
            "paper_only": True,
            "rate_limit": 120,
            "rate_limit_window_start": None,
            "request_count": 5,
            "expires_at": None,
            "created_at": datetime.now().isoformat(),
            "last_used_at": None,
            "is_active": True,
        }
        token = AgentToken.from_dict(data)
        assert token.id == "test-id"
        assert token.name == "test-token"
        assert token.scopes == ["R"]
        assert token.request_count == 5


class TestAuditLogDataclass:
    """Test AuditLog dataclass."""

    def test_audit_log_creation(self):
        """Test basic AuditLog creation."""
        log = AuditLog(
            token_id="test-token-id",
            action="verify",
            resource="/api/v1/market",
            details={"status": "success"},
            ip_address="127.0.0.1",
            user_agent="TestAgent/1.0",
        )
        assert log.token_id == "test-token-id"
        assert log.action == "verify"
        assert log.resource == "/api/v1/market"
        assert log.details == {"status": "success"}
        assert log.ip_address == "127.0.0.1"
        assert log.user_agent == "TestAgent/1.0"
        assert log.timestamp is not None

    def test_audit_log_to_dict(self):
        """Test AuditLog serialization."""
        log = AuditLog(
            id=1,
            token_id="test-token-id",
            action="create",
            resource="/api/v1/tokens",
            details={"name": "test"},
        )
        data = log.to_dict()
        assert data["id"] == 1
        assert data["token_id"] == "test-token-id"
        assert data["action"] == "create"


class TestAgentDB:
    """Test AgentDB class."""

    @pytest.fixture
    def agent_db(self, tmp_path):
        """Create an AgentDB instance for testing."""
        db_path = str(tmp_path / "test_agent_tokens.db")

        # Reset singleton and thread-local storage
        AgentDB._instance = None
        import threading
        if hasattr(threading.local(), 'conn'):
            delattr(threading.local(), 'conn')

        with patch("app.db.agent_db.DB_PATH", db_path):
            with patch("app.db.agent_db._thread_local", threading.local()):
                db = AgentDB()
                yield db
                # Cleanup
                AgentDB._instance = None

    def test_init_db(self, agent_db):
        """Test database initialization."""
        assert agent_db._initialized is True
        # Check tables exist by trying to query them
        tokens = agent_db.list_tokens(active_only=False)
        assert isinstance(tokens, list)

    def test_save_token(self, agent_db):
        """Test saving a token."""
        token = AgentToken(
            id=str(uuid.uuid4()),
            name="test-agent",
            token_hash="hash_" + str(uuid.uuid4()),
            token_prefix="AGT1_abc",
            scopes=["R", "W"],
            markets=["ASTOCK"],
        )

        result = agent_db.save_token(token)
        assert result is True

        # Verify token was saved
        retrieved = agent_db.get_token_by_hash(token.token_hash)
        assert retrieved is not None
        assert retrieved.id == token.id
        assert retrieved.name == token.name

    def test_save_token_duplicate_hash(self, agent_db):
        """Test saving token with duplicate hash fails."""
        token1 = AgentToken(
            id=str(uuid.uuid4()),
            name="agent1",
            token_hash="duplicate_hash",
            token_prefix="AGT1_abc",
            scopes=["R"],
        )
        token2 = AgentToken(
            id=str(uuid.uuid4()),
            name="agent2",
            token_hash="duplicate_hash",  # Same hash
            token_prefix="AGT1_def",
            scopes=["W"],
        )

        result1 = agent_db.save_token(token1)
        assert result1 is True

        result2 = agent_db.save_token(token2)
        assert result2 is False  # Should fail due to unique constraint

    def test_get_token_by_hash(self, agent_db):
        """Test getting token by hash."""
        token = AgentToken(
            id=str(uuid.uuid4()),
            name="test-agent",
            token_hash="test_hash_123",
            token_prefix="AGT1_abc",
            scopes=["R"],
        )
        agent_db.save_token(token)

        retrieved = agent_db.get_token_by_hash("test_hash_123")
        assert retrieved is not None
        assert retrieved.id == token.id

        # Test non-existent hash
        not_found = agent_db.get_token_by_hash("non_existent_hash")
        assert not_found is None

    def test_get_token_by_id(self, agent_db):
        """Test getting token by ID."""
        token_id = str(uuid.uuid4())
        token = AgentToken(
            id=token_id,
            name="test-agent",
            token_hash="hash_" + token_id,
            token_prefix="AGT1_abc",
            scopes=["R"],
        )
        agent_db.save_token(token)

        retrieved = agent_db.get_token_by_id(token_id)
        assert retrieved is not None
        assert retrieved.name == "test-agent"

        # Test non-existent ID
        not_found = agent_db.get_token_by_id("non-existent-id")
        assert not_found is None

    def test_list_tokens(self, agent_db):
        """Test listing tokens."""
        # Create multiple tokens
        for i in range(3):
            token = AgentToken(
                id=str(uuid.uuid4()),
                name=f"agent-{i}",
                token_hash=f"hash_{i}_{uuid.uuid4()}",
                token_prefix=f"AGT1_{i}",
                scopes=["R"],
            )
            agent_db.save_token(token)

        tokens = agent_db.list_tokens(active_only=False)
        assert len(tokens) == 3

    def test_list_tokens_active_only(self, agent_db):
        """Test listing active tokens only."""
        # Create active token
        token1 = AgentToken(
            id=str(uuid.uuid4()),
            name="active-agent",
            token_hash="hash_active",
            token_prefix="AGT1_active",
            scopes=["R"],
            is_active=True,
        )
        agent_db.save_token(token1)

        # Create inactive token
        token2 = AgentToken(
            id=str(uuid.uuid4()),
            name="inactive-agent",
            token_hash="hash_inactive",
            token_prefix="AGT1_inactive",
            scopes=["R"],
            is_active=False,
        )
        agent_db.save_token(token2)

        active_tokens = agent_db.list_tokens(active_only=True)
        assert len(active_tokens) == 1
        assert active_tokens[0].name == "active-agent"

        all_tokens = agent_db.list_tokens(active_only=False)
        assert len(all_tokens) == 2

    def test_update_token(self, agent_db):
        """Test updating a token."""
        token = AgentToken(
            id=str(uuid.uuid4()),
            name="original-name",
            token_hash="hash_update_test",
            token_prefix="AGT1_abc",
            scopes=["R"],
            request_count=0,
        )
        agent_db.save_token(token)

        token.name = "updated-name"
        token.request_count = 5
        token.last_used_at = datetime.now().isoformat()

        result = agent_db.update_token(token)
        assert result is True

        # Verify update
        retrieved = agent_db.get_token_by_id(token.id)
        assert retrieved.name == "updated-name"
        assert retrieved.request_count == 5
        assert retrieved.last_used_at is not None

    def test_update_token_not_found(self, agent_db):
        """Test updating non-existent token."""
        token = AgentToken(
            id="non-existent-id",
            name="test",
            token_hash="hash",
            token_prefix="AGT1",
            scopes=["R"],
        )
        result = agent_db.update_token(token)
        assert result is False

    def test_revoke_token(self, agent_db):
        """Test revoking a token."""
        token = AgentToken(
            id=str(uuid.uuid4()),
            name="test-agent",
            token_hash="hash_revoke_test",
            token_prefix="AGT1_abc",
            scopes=["R"],
            is_active=True,
        )
        agent_db.save_token(token)

        result = agent_db.revoke_token(token.id)
        assert result is True

        # Verify revoked
        retrieved = agent_db.get_token_by_id(token.id)
        assert retrieved.is_active is False

    def test_revoke_token_not_found(self, agent_db):
        """Test revoking non-existent token."""
        result = agent_db.revoke_token("non-existent-id")
        assert result is False

    def test_log_audit(self, agent_db):
        """Test logging audit event."""
        token_id = str(uuid.uuid4())
        result = agent_db.log_audit(
            token_id=token_id,
            action="verify",
            resource="/api/v1/market",
            details={"status": "success"},
            ip_address="127.0.0.1",
            user_agent="TestAgent/1.0",
        )
        assert result is True

        # Verify audit log was created
        logs = agent_db.get_audit_logs(token_id=token_id)
        assert len(logs) == 1
        assert logs[0].action == "verify"
        assert logs[0].resource == "/api/v1/market"

    def test_get_audit_logs(self, agent_db):
        """Test getting audit logs."""
        token_id = str(uuid.uuid4())

        # Create multiple audit logs
        for i in range(5):
            agent_db.log_audit(
                token_id=token_id,
                action=f"action_{i}",
                resource=f"/api/v1/resource_{i}",
            )

        logs = agent_db.get_audit_logs(token_id=token_id)
        assert len(logs) == 5

        # Test limit
        logs_limited = agent_db.get_audit_logs(token_id=token_id, limit=2)
        assert len(logs_limited) == 2

    def test_get_audit_logs_with_action_filter(self, agent_db):
        """Test getting audit logs with action filter."""
        token_id = str(uuid.uuid4())

        agent_db.log_audit(token_id=token_id, action="verify", resource="/api/v1/test")
        agent_db.log_audit(token_id=token_id, action="create", resource="/api/v1/test")
        agent_db.log_audit(token_id=token_id, action="verify", resource="/api/v1/test")

        logs = agent_db.get_audit_logs(token_id=token_id, action="verify")
        assert len(logs) == 2
        assert all(log.action == "verify" for log in logs)

    def test_delete_expired_tokens(self, agent_db):
        """Test deleting expired tokens."""
        # Create expired token
        expired_token = AgentToken(
            id=str(uuid.uuid4()),
            name="expired-agent",
            token_hash="hash_expired",
            token_prefix="AGT1_exp",
            scopes=["R"],
            expires_at=(datetime.now() - timedelta(days=1)).isoformat(),
        )
        agent_db.save_token(expired_token)

        # Create valid token
        valid_token = AgentToken(
            id=str(uuid.uuid4()),
            name="valid-agent",
            token_hash="hash_valid",
            token_prefix="AGT1_val",
            scopes=["R"],
            expires_at=(datetime.now() + timedelta(days=7)).isoformat(),
        )
        agent_db.save_token(valid_token)

        deleted = agent_db.delete_expired_tokens()
        assert deleted == 1

        # Verify only valid token remains
        tokens = agent_db.list_tokens(active_only=False)
        assert len(tokens) == 1
        assert tokens[0].name == "valid-agent"

    def test_get_token_count(self, agent_db):
        """Test getting token count."""
        # Create tokens
        for i in range(3):
            token = AgentToken(
                id=str(uuid.uuid4()),
                name=f"agent-{i}",
                token_hash=f"hash_count_{i}",
                token_prefix=f"AGT1_{i}",
                scopes=["R"],
                is_active=(i < 2),  # First 2 active, last inactive
            )
            agent_db.save_token(token)

        active_count = agent_db.get_token_count(active_only=True)
        assert active_count == 2

        total_count = agent_db.get_token_count(active_only=False)
        assert total_count == 3


class TestAgentDBSingleton:
    """Test AgentDB singleton pattern."""

    def test_singleton_returns_same_instance(self, tmp_path):
        """Test that get_agent_db returns same instance."""
        db_path = str(tmp_path / "test_singleton.db")

        AgentDB._instance = None
        import threading
        if hasattr(threading.local(), 'conn'):
            delattr(threading.local(), 'conn')

        with patch("app.db.agent_db.DB_PATH", db_path):
            with patch("app.db.agent_db._thread_local", threading.local()):
                db1 = get_agent_db()
                db2 = get_agent_db()

                assert db1 is db2

                AgentDB._instance = None


class TestDatabaseIndexes:
    """Test database indexes."""

    @pytest.fixture
    def agent_db(self, tmp_path):
        """Create an AgentDB instance for testing."""
        db_path = str(tmp_path / "test_indexes.db")

        AgentDB._instance = None
        import threading
        if hasattr(threading.local(), 'conn'):
            delattr(threading.local(), 'conn')

        with patch("app.db.agent_db.DB_PATH", db_path):
            with patch("app.db.agent_db._thread_local", threading.local()):
                db = AgentDB()
                yield db
                AgentDB._instance = None

    def test_indexes_exist(self, agent_db):
        """Test that indexes are created."""
        import sqlite3

        from app.db.agent_db import _get_thread_conn

        conn = _get_thread_conn()

        # Get list of indexes
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='agent_tokens'"
        )
        indexes = [row[0] for row in cursor.fetchall()]

        # Check expected indexes exist
        assert "idx_agent_token_hash" in indexes
        assert "idx_agent_token_id" in indexes
        assert "idx_agent_token_expires" in indexes
        assert "idx_agent_token_active" in indexes

        # Check audit log indexes
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='agent_audit_logs'"
        )
        audit_indexes = [row[0] for row in cursor.fetchall()]

        assert "idx_audit_token_id" in audit_indexes
        assert "idx_audit_action" in audit_indexes
        assert "idx_audit_timestamp" in audit_indexes


class TestConcurrency:
    """Test thread safety."""

    @pytest.fixture
    def agent_db(self, tmp_path):
        """Create an AgentDB instance for testing."""
        db_path = str(tmp_path / "test_concurrent.db")

        AgentDB._instance = None
        import threading
        if hasattr(threading.local(), 'conn'):
            delattr(threading.local(), 'conn')

        with patch("app.db.agent_db.DB_PATH", db_path):
            with patch("app.db.agent_db._thread_local", threading.local()):
                db = AgentDB()
                yield db
                AgentDB._instance = None

    def test_concurrent_token_creation(self, agent_db):
        """Test concurrent token creation."""
        import threading

        results = []

        def create_token(name):
            token = AgentToken(
                id=str(uuid.uuid4()),
                name=name,
                token_hash=f"hash_{name}_{uuid.uuid4()}",
                token_prefix=f"AGT1_{name}",
                scopes=["R"],
            )
            result = agent_db.save_token(token)
            results.append(result)

        threads = [
            threading.Thread(target=create_token, args=(f"agent-{i}",))
            for i in range(10)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(results)
        tokens = agent_db.list_tokens(active_only=False)
        assert len(tokens) == 10

    def test_concurrent_read_write(self, agent_db):
        """Test concurrent read and write operations."""
        import threading

        # Create initial token
        token = AgentToken(
            id=str(uuid.uuid4()),
            name="initial",
            token_hash="hash_initial",
            token_prefix="AGT1_init",
            scopes=["R"],
        )
        agent_db.save_token(token)

        errors = []

        def read_tokens():
            try:
                for _ in range(10):
                    agent_db.list_tokens(active_only=False)
            except sqlite3.Error as e:
                errors.append(e)
            except Exception as e:
                errors.append(e)

        def write_tokens():
            try:
                for i in range(5):
                    new_token = AgentToken(
                        id=str(uuid.uuid4()),
                        name=f"writer-{i}",
                        token_hash=f"hash_writer_{i}_{uuid.uuid4()}",
                        token_prefix=f"AGT1_w{i}",
                        scopes=["W"],
                    )
                    agent_db.save_token(new_token)
            except sqlite3.Error as e:
                errors.append(e)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=read_tokens),
            threading.Thread(target=write_tokens),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


class TestDebugLogging:
    """Test debug logging functionality."""

    @pytest.fixture
    def agent_db(self, tmp_path):
        """Create an AgentDB instance for testing."""
        db_path = str(tmp_path / "test_debug.db")

        AgentDB._instance = None
        import threading
        if hasattr(threading.local(), 'conn'):
            delattr(threading.local(), 'conn')

        with patch("app.db.agent_db.DB_PATH", db_path):
            with patch("app.db.agent_db._thread_local", threading.local()):
                db = AgentDB()
                yield db
                AgentDB._instance = None

    def test_debug_mode_enabled(self, agent_db):
        """Test that debug mode is enabled."""
        from app.db.agent_db import DEBUG_MODE

        assert DEBUG_MODE is True

    def test_operations_are_logged(self, agent_db, caplog):
        """Test that operations produce log output."""
        import logging

        # Set capture level
        caplog.set_level(logging.DEBUG, logger="app.db.agent_db")

        # Perform operation
        token = AgentToken(
            id=str(uuid.uuid4()),
            name="test-logging",
            token_hash="hash_logging_test",
            token_prefix="AGT1_log",
            scopes=["R"],
        )
        agent_db.save_token(token)

        # Check logs contain expected messages
        assert any("save" in record.message.lower() for record in caplog.records)
        assert any("token" in record.message.lower() for record in caplog.records)


class TestModuleFunctions:
    """Test module-level convenience functions."""

    def test_init_agent_db(self, tmp_path):
        """Test init_agent_db function."""
        db_path = str(tmp_path / "test_module.db")

        AgentDB._instance = None
        import threading
        if hasattr(threading.local(), 'conn'):
            delattr(threading.local(), 'conn')

        with patch("app.db.agent_db.DB_PATH", db_path):
            with patch("app.db.agent_db._thread_local", threading.local()):
                init_agent_db()

                db = get_agent_db()
                assert db._initialized is True

                AgentDB._instance = None

    def test_get_agent_db(self, tmp_path):
        """Test get_agent_db function."""
        db_path = str(tmp_path / "test_get.db")

        AgentDB._instance = None
        import threading
        if hasattr(threading.local(), 'conn'):
            delattr(threading.local(), 'conn')

        with patch("app.db.agent_db.DB_PATH", db_path):
            with patch("app.db.agent_db._thread_local", threading.local()):
                db = get_agent_db()
                assert isinstance(db, AgentDB)

                AgentDB._instance = None
