"""
Audit Chain Service Tests

Tests for the audit chain implementation in backend/app/services/audit_chain.py
Covers hash computation, chain verification, statistics, and convenience functions.
"""

import pytest
import json
import hashlib
import hmac
import sqlite3
import tempfile
import os
from datetime import datetime
from unittest.mock import patch, MagicMock
from pathlib import Path

from app.services.audit_chain import (
    compute_hash,
    get_prev_hash_and_index,
    log_audit_event,
    verify_chain,
    get_chain_stats,
    log_buy,
    log_sell,
    log_cash_operation,
    GENESIS_HASH,
    SEC_RETENTION_DAYS,
    AUDIT_HMAC_KEY,
    AuditChainRecord,
)


class TestHashComputation:
    """Tests for the compute_hash function."""

    def test_hash_is_64_characters(self):
        """HMAC-SHA256 should produce 64-character hex string."""
        fields = {
            "timestamp": "2024-01-01T00:00:00",
            "actor_id": "test_user",
            "action": "buy",
        }
        result = compute_hash(GENESIS_HASH, fields)
        assert len(result) == 64

    def test_hash_is_hexadecimal(self):
        """Hash should only contain hexadecimal characters."""
        fields = {
            "timestamp": "2024-01-01T00:00:00",
            "actor_id": "test_user",
            "action": "buy",
        }
        result = compute_hash(GENESIS_HASH, fields)
        assert all(c in "0123456789abcdef" for c in result)

    def test_hash_determinism(self):
        """Same inputs should produce same hash."""
        fields = {
            "timestamp": "2024-01-01T00:00:00",
            "actor_id": "test_user",
            "action": "buy",
            "resource_type": "position",
            "resource_id": "1:600519",
            "outcome": "success",
        }
        hash1 = compute_hash(GENESIS_HASH, fields)
        hash2 = compute_hash(GENESIS_HASH, fields)
        assert hash1 == hash2

    def test_hash_uniqueness_different_fields(self):
        """Different field values should produce different hashes."""
        fields1 = {
            "timestamp": "2024-01-01T00:00:00",
            "actor_id": "user1",
            "action": "buy",
        }
        fields2 = {
            "timestamp": "2024-01-01T00:00:00",
            "actor_id": "user2",
            "action": "buy",
        }
        hash1 = compute_hash(GENESIS_HASH, fields1)
        hash2 = compute_hash(GENESIS_HASH, fields2)
        assert hash1 != hash2

    def test_hash_uniqueness_different_prev_hash(self):
        """Different prev_hash should produce different hashes."""
        fields = {
            "timestamp": "2024-01-01T00:00:00",
            "actor_id": "test_user",
            "action": "buy",
        }
        hash1 = compute_hash(GENESIS_HASH, fields)
        hash2 = compute_hash("a" * 64, fields)
        assert hash1 != hash2

    def test_hash_key_ordering_independent(self):
        """Hash should be independent of field key ordering (canonical JSON)."""
        fields1 = {"a": 1, "b": 2, "c": 3}
        fields2 = {"c": 3, "a": 1, "b": 2}
        hash1 = compute_hash(GENESIS_HASH, fields1)
        hash2 = compute_hash(GENESIS_HASH, fields2)
        assert hash1 == hash2

    def test_hash_with_none_values(self):
        """Hash should handle None values in fields."""
        fields = {
            "timestamp": "2024-01-01T00:00:00",
            "actor_id": "test_user",
            "action": "buy",
            "before_state": None,
            "after_state": None,
        }
        result = compute_hash(GENESIS_HASH, fields)
        assert len(result) == 64

    def test_hash_with_nested_dict(self):
        """Hash should handle nested dictionary values."""
        fields = {
            "timestamp": "2024-01-01T00:00:00",
            "actor_id": "test_user",
            "action": "buy",
            "after_state": {
                "portfolio_id": 1,
                "symbol": "sh600519",
                "shares": 100,
                "price": 1800.00,
            },
        }
        result = compute_hash(GENESIS_HASH, fields)
        assert len(result) == 64

    def test_hash_uses_hmac(self):
        """Verify hash is computed using HMAC-SHA256."""
        fields = {"test": "data"}
        prev_hash = GENESIS_HASH

        # Compute expected hash manually
        canonical = json.dumps(fields, sort_keys=True, default=str, ensure_ascii=False)
        payload = prev_hash + canonical
        expected = hmac.new(
            AUDIT_HMAC_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        result = compute_hash(prev_hash, fields)
        assert result == expected


class TestConstants:
    """Tests for module constants."""

    def test_genesis_hash_is_64_zeros(self):
        """Genesis hash should be 64 zero characters."""
        assert GENESIS_HASH == "0" * 64
        assert len(GENESIS_HASH) == 64

    def test_sec_retention_days_is_7_years(self):
        """SEC retention should be 7 years (2555 days)."""
        assert SEC_RETENTION_DAYS == 2555

    def test_hmac_key_from_environment(self):
        """HMAC key should be configurable via environment variable."""
        # Default key when not set
        assert AUDIT_HMAC_KEY == "default-key-change-in-production"


class TestAuditChainRecord:
    """Tests for the AuditChainRecord dataclass."""

    def test_record_creation(self):
        """Should create record with all fields."""
        record = AuditChainRecord(
            id=1,
            timestamp="2024-01-01T00:00:00",
            actor_id="user1",
            action="buy",
            resource_type="position_lot",
            resource_id="1:sh600519",
            outcome="success",
            before_state=None,
            after_state={"shares": 100},
            prev_hash=GENESIS_HASH,
            record_hash="a" * 64,
            chain_index=0,
        )

        assert record.id == 1
        assert record.actor_id == "user1"
        assert record.action == "buy"
        assert record.chain_index == 0

    def test_record_optional_fields(self):
        """Should handle optional fields (ip_address, user_agent)."""
        record = AuditChainRecord(
            id=1,
            timestamp="2024-01-01T00:00:00",
            actor_id="user1",
            action="buy",
            resource_type="position_lot",
            resource_id="1:sh600519",
            outcome="success",
            before_state=None,
            after_state=None,
            prev_hash=GENESIS_HASH,
            record_hash="a" * 64,
            chain_index=0,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )

        assert record.ip_address == "192.168.1.1"
        assert record.user_agent == "Mozilla/5.0"


class TestGetPrevHashAndIndex:
    """Tests for get_prev_hash_and_index function."""

    @pytest.fixture
    def mock_connection(self):
        """Create a mock database connection."""
        conn = MagicMock(spec=sqlite3.Connection)
        return conn

    def test_returns_genesis_for_empty_table(self, mock_connection):
        """Should return GENESIS_HASH and 0 for empty table."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_connection.execute.return_value = mock_cursor

        prev_hash, chain_index = get_prev_hash_and_index(mock_connection)

        assert prev_hash == GENESIS_HASH
        assert chain_index == 0

    def test_returns_last_record_hash(self, mock_connection):
        """Should return last record's hash and incremented index."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("abc123", 5)
        mock_connection.execute.return_value = mock_cursor

        prev_hash, chain_index = get_prev_hash_and_index(mock_connection)

        assert prev_hash == "abc123"
        assert chain_index == 6


class TestLogAuditEvent:
    """Tests for log_audit_event function."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row

        # Create audit_logs table
        conn.execute("""
            CREATE TABLE audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                agent_id TEXT,
                action TEXT,
                resource TEXT,
                details TEXT,
                ip_address TEXT,
                user_agent TEXT,
                prev_hash TEXT,
                record_hash TEXT,
                chain_index INTEGER
            )
        """)
        conn.commit()

        yield path

        conn.close()
        os.unlink(path)

    def test_log_event_returns_record_id(self, temp_db):
        """Should return the ID of the inserted record."""
        with patch("app.services.audit_chain.AUDIT_DB_PATH", Path(temp_db)):
            record_id = log_audit_event(
                actor_id="user1",
                action="buy",
                resource_type="position",
                resource_id="1:sh600519",
                outcome="success",
            )

            assert record_id == 1

    def test_log_event_creates_chain_record(self, temp_db):
        """Should create record with hash chain fields."""
        with patch("app.services.audit_chain.AUDIT_DB_PATH", Path(temp_db)):
            record_id = log_audit_event(
                actor_id="user1",
                action="buy",
                resource_type="position",
                resource_id="1:sh600519",
                outcome="success",
            )

            # Verify record
            conn = sqlite3.connect(temp_db)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM audit_logs WHERE id = ?", (record_id,)
            ).fetchone()
            conn.close()

            assert row is not None
            assert row["prev_hash"] == GENESIS_HASH
            assert row["chain_index"] == 0
            assert len(row["record_hash"]) == 64

    def test_log_event_chain_continuation(self, temp_db):
        """Should properly chain records together."""
        with patch("app.services.audit_chain.AUDIT_DB_PATH", Path(temp_db)):
            # First record
            id1 = log_audit_event(
                actor_id="user1",
                action="buy",
                resource_type="position",
                resource_id="1:sh600519",
                outcome="success",
            )

            # Second record
            id2 = log_audit_event(
                actor_id="user1",
                action="sell",
                resource_type="position",
                resource_id="1:sh600519",
                outcome="success",
            )

            # Get records
            conn = sqlite3.connect(temp_db)
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM audit_logs ORDER BY id").fetchall()
            conn.close()

            assert len(rows) == 2
            assert rows[0]["chain_index"] == 0
            assert rows[1]["chain_index"] == 1
            assert rows[1]["prev_hash"] == rows[0]["record_hash"]


class TestVerifyChain:
    """Tests for verify_chain function."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row

        # Create audit_logs table
        conn.execute("""
            CREATE TABLE audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                agent_id TEXT,
                action TEXT,
                resource TEXT,
                details TEXT,
                ip_address TEXT,
                user_agent TEXT,
                prev_hash TEXT,
                record_hash TEXT,
                chain_index INTEGER
            )
        """)
        conn.commit()

        yield path

        conn.close()
        os.unlink(path)

    def test_verify_empty_chain(self, temp_db):
        """Should return valid for empty chain."""
        with patch("app.services.audit_chain.AUDIT_DB_PATH", Path(temp_db)):
            result = verify_chain()

            assert result["valid"] is True
            assert result["checked_records"] == 0

    def test_verify_single_record(self, temp_db):
        """Should verify single record chain."""
        with patch("app.services.audit_chain.AUDIT_DB_PATH", Path(temp_db)):
            log_audit_event(
                actor_id="user1",
                action="buy",
                resource_type="position",
                resource_id="1:sh600519",
                outcome="success",
            )

            result = verify_chain()

            assert result["valid"] is True
            assert result["checked_records"] == 1

    def test_verify_multiple_records(self, temp_db):
        """Should verify chain with multiple records."""
        with patch("app.services.audit_chain.AUDIT_DB_PATH", Path(temp_db)):
            for i in range(5):
                log_audit_event(
                    actor_id="user1",
                    action="buy",
                    resource_type="position",
                    resource_id=f"1:stock{i}",
                    outcome="success",
                )

            result = verify_chain()

            assert result["valid"] is True
            assert result["checked_records"] == 5

    def test_detect_tampered_hash(self, temp_db):
        """Should detect tampered record hash."""
        with patch("app.services.audit_chain.AUDIT_DB_PATH", Path(temp_db)):
            log_audit_event(
                actor_id="user1",
                action="buy",
                resource_type="position",
                resource_id="1:sh600519",
                outcome="success",
            )

            # Tamper with the hash
            conn = sqlite3.connect(temp_db)
            conn.execute(
                "UPDATE audit_logs SET record_hash = ? WHERE id = 1",
                ("tampered_hash_00000000000000000000000000000000",),
            )
            conn.commit()
            conn.close()

            result = verify_chain()

            assert result["valid"] is False
            assert result["error_type"] == "hash_mismatch"

    def test_detect_broken_chain(self, temp_db):
        """Should detect broken chain link."""
        with patch("app.services.audit_chain.AUDIT_DB_PATH", Path(temp_db)):
            # First record
            log_audit_event(
                actor_id="user1",
                action="buy",
                resource_type="position",
                resource_id="1:sh600519",
                outcome="success",
            )

            # Second record
            log_audit_event(
                actor_id="user1",
                action="sell",
                resource_type="position",
                resource_id="1:sh600519",
                outcome="success",
            )

            # Break the chain by modifying prev_hash of second record
            conn = sqlite3.connect(temp_db)
            conn.execute(
                "UPDATE audit_logs SET prev_hash = ? WHERE id = 2",
                ("broken_prev_hash_00000000000000000000000000000",),
            )
            conn.commit()
            conn.close()

            result = verify_chain()

            assert result["valid"] is False
            assert result["error_type"] == "prev_hash_mismatch"

    def test_verify_with_from_id(self, temp_db):
        """Should verify chain starting from specified ID."""
        with patch("app.services.audit_chain.AUDIT_DB_PATH", Path(temp_db)):
            for i in range(10):
                log_audit_event(
                    actor_id="user1",
                    action="buy",
                    resource_type="position",
                    resource_id=f"1:stock{i}",
                    outcome="success",
                )

            result = verify_chain(from_id=1)

            assert result["valid"] is True
            assert result["checked_records"] == 10


class TestGetChainStats:
    """Tests for get_chain_stats function."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row

        # Create audit_logs table
        conn.execute("""
            CREATE TABLE audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                agent_id TEXT,
                action TEXT,
                resource TEXT,
                details TEXT,
                ip_address TEXT,
                user_agent TEXT,
                prev_hash TEXT,
                record_hash TEXT,
                chain_index INTEGER
            )
        """)
        conn.commit()

        yield path

        conn.close()
        os.unlink(path)

    def test_stats_empty_chain(self, temp_db):
        """Should return correct stats for empty chain."""
        with patch("app.services.audit_chain.AUDIT_DB_PATH", Path(temp_db)):
            stats = get_chain_stats()

            assert stats["total_records"] == 0
            assert stats["chain_index_min"] is None
            assert stats["chain_index_max"] is None
            assert stats["first_record"] is None
            assert stats["last_record"] is None

    def test_stats_with_records(self, temp_db):
        """Should return correct stats for chain with records."""
        with patch("app.services.audit_chain.AUDIT_DB_PATH", Path(temp_db)):
            for i in range(5):
                log_audit_event(
                    actor_id="user1",
                    action="buy",
                    resource_type="position",
                    resource_id=f"1:stock{i}",
                    outcome="success",
                )

            stats = get_chain_stats()

            assert stats["total_records"] == 5
            assert stats["chain_index_min"] == 0
            assert stats["chain_index_max"] == 4
            assert stats["first_record"] is not None
            assert stats["last_record"] is not None

    def test_stats_includes_genesis_hash(self, temp_db):
        """Stats should include genesis hash constant."""
        with patch("app.services.audit_chain.AUDIT_DB_PATH", Path(temp_db)):
            stats = get_chain_stats()

            assert stats["genesis_hash"] == GENESIS_HASH

    def test_stats_includes_retention_days(self, temp_db):
        """Stats should include SEC retention days."""
        with patch("app.services.audit_chain.AUDIT_DB_PATH", Path(temp_db)):
            stats = get_chain_stats()

            assert stats["retention_days"] == SEC_RETENTION_DAYS


class TestConvenienceFunctions:
    """Tests for convenience logging functions."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row

        # Create audit_logs table
        conn.execute("""
            CREATE TABLE audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                agent_id TEXT,
                action TEXT,
                resource TEXT,
                details TEXT,
                ip_address TEXT,
                user_agent TEXT,
                prev_hash TEXT,
                record_hash TEXT,
                chain_index INTEGER
            )
        """)
        conn.commit()

        yield path

        conn.close()
        os.unlink(path)

    def test_log_buy(self, temp_db):
        """Should log buy transaction with correct fields."""
        with patch("app.services.audit_chain.AUDIT_DB_PATH", Path(temp_db)):
            record_id = log_buy(
                portfolio_id=1,
                symbol="sh600519",
                shares=100,
                price=1800.00,
                actor_id="user1",
            )

            conn = sqlite3.connect(temp_db)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM audit_logs WHERE id = ?", (record_id,)
            ).fetchone()
            conn.close()

            assert row["action"] == "buy"
            assert row["agent_id"] == "user1"
            details = json.loads(row["details"])
            assert details["resource_type"] == "position_lot"

    def test_log_sell(self, temp_db):
        """Should log sell transaction with correct fields."""
        with patch("app.services.audit_chain.AUDIT_DB_PATH", Path(temp_db)):
            record_id = log_sell(
                portfolio_id=1,
                symbol="sh600519",
                shares=100,
                price=1850.00,
                realized_pnl=5000.00,
                actor_id="user1",
            )

            conn = sqlite3.connect(temp_db)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM audit_logs WHERE id = ?", (record_id,)
            ).fetchone()
            conn.close()

            assert row["action"] == "sell"
            details = json.loads(row["details"])
            assert details["after_state"]["realized_pnl"] == 5000.00

    def test_log_cash_operation(self, temp_db):
        """Should log cash operation with correct fields."""
        with patch("app.services.audit_chain.AUDIT_DB_PATH", Path(temp_db)):
            record_id = log_cash_operation(
                portfolio_id=1,
                operation="deposit",
                amount=10000.00,
                balance_after=10000.00,
                actor_id="user1",
            )

            conn = sqlite3.connect(temp_db)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM audit_logs WHERE id = ?", (record_id,)
            ).fetchone()
            conn.close()

            assert row["action"] == "deposit"
            details = json.loads(row["details"])
            assert details["resource_type"] == "cash"

    def test_log_buy_with_optional_fields(self, temp_db):
        """Should include optional fields in buy log."""
        with patch("app.services.audit_chain.AUDIT_DB_PATH", Path(temp_db)):
            record_id = log_buy(
                portfolio_id=1,
                symbol="sh600519",
                shares=100,
                price=1800.00,
                actor_id="user1",
                order_id="ORD123",
                ip_address="192.168.1.1",
            )

            conn = sqlite3.connect(temp_db)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM audit_logs WHERE id = ?", (record_id,)
            ).fetchone()
            conn.close()

            assert row["ip_address"] == "192.168.1.1"
            details = json.loads(row["details"])
            assert details["after_state"]["order_id"] == "ORD123"


class TestChainIntegrity:
    """Tests for chain integrity and tamper detection."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row

        # Create audit_logs table
        conn.execute("""
            CREATE TABLE audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                agent_id TEXT,
                action TEXT,
                resource TEXT,
                details TEXT,
                ip_address TEXT,
                user_agent TEXT,
                prev_hash TEXT,
                record_hash TEXT,
                chain_index INTEGER
            )
        """)
        conn.commit()

        yield path

        conn.close()
        os.unlink(path)

    def test_chain_detects_deletion(self, temp_db):
        """Should detect when a record is deleted from chain."""
        with patch("app.services.audit_chain.AUDIT_DB_PATH", Path(temp_db)):
            # Create 3 records
            id1 = log_audit_event(
                actor_id="user1",
                action="buy",
                resource_type="position",
                resource_id="1:stock1",
                outcome="success",
            )
            id2 = log_audit_event(
                actor_id="user1",
                action="buy",
                resource_type="position",
                resource_id="1:stock2",
                outcome="success",
            )
            id3 = log_audit_event(
                actor_id="user1",
                action="buy",
                resource_type="position",
                resource_id="1:stock3",
                outcome="success",
            )

            # Delete middle record
            conn = sqlite3.connect(temp_db)
            conn.execute("DELETE FROM audit_logs WHERE id = ?", (id2,))
            conn.commit()
            conn.close()

            result = verify_chain()

            # Chain should be broken because prev_hash of record 3 won't match
            assert result["valid"] is False

    def test_chain_detects_insertion(self, temp_db):
        """Should detect when a record is inserted into chain."""
        with patch("app.services.audit_chain.AUDIT_DB_PATH", Path(temp_db)):
            # Create 2 records
            log_audit_event(
                actor_id="user1",
                action="buy",
                resource_type="position",
                resource_id="1:stock1",
                outcome="success",
            )
            log_audit_event(
                actor_id="user1",
                action="buy",
                resource_type="position",
                resource_id="1:stock2",
                outcome="success",
            )

            # Insert a fake record
            conn = sqlite3.connect(temp_db)
            conn.execute(
                """
                INSERT INTO audit_logs 
                (timestamp, agent_id, action, resource, details, prev_hash, record_hash, chain_index)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    "2024-01-01T00:00:00",
                    "hacker",
                    "transfer",
                    "cash:1",
                    "{}",
                    GENESIS_HASH,
                    "fake_hash_000000000000000000000000000000000000",
                    0,
                ),
            )
            conn.commit()
            conn.close()

            result = verify_chain()

            # Chain should be invalid due to hash mismatch
            assert result["valid"] is False

    def test_genesis_record_validation(self, temp_db):
        """Should validate genesis record has correct prev_hash."""
        with patch("app.services.audit_chain.AUDIT_DB_PATH", Path(temp_db)):
            # Create a record
            log_audit_event(
                actor_id="user1",
                action="buy",
                resource_type="position",
                resource_id="1:stock1",
                outcome="success",
            )

            # Modify genesis record's prev_hash
            conn = sqlite3.connect(temp_db)
            conn.execute(
                "UPDATE audit_logs SET prev_hash = ? WHERE chain_index = 0",
                ("invalid_genesis_000000000000000000000000000000",),
            )
            conn.commit()
            conn.close()

            result = verify_chain()

            assert result["valid"] is False
            assert result["error_type"] == "genesis_hash_invalid"


class TestEdgeCases:
    """Edge case tests for audit chain."""

    def test_compute_hash_with_unicode(self):
        """Should handle unicode characters in fields."""
        fields = {
            "timestamp": "2024-01-01T00:00:00",
            "actor_id": "用户1",  # Chinese characters
            "action": "买入",  # Chinese characters
        }
        result = compute_hash(GENESIS_HASH, fields)
        assert len(result) == 64

    def test_compute_hash_with_special_characters(self):
        """Should handle special characters in fields."""
        fields = {
            "timestamp": "2024-01-01T00:00:00",
            "actor_id": "user@example.com",
            "action": "buy-100_shares",
            "resource_id": "sh600519:2024-01-01",
        }
        result = compute_hash(GENESIS_HASH, fields)
        assert len(result) == 64

    def test_compute_hash_with_datetime_object(self):
        """Should handle datetime objects (via default=str)."""
        fields = {
            "timestamp": datetime(2024, 1, 1, 12, 0, 0),
            "actor_id": "user1",
        }
        result = compute_hash(GENESIS_HASH, fields)
        assert len(result) == 64

    def test_empty_fields(self):
        """Should handle empty fields dictionary."""
        fields = {}
        result = compute_hash(GENESIS_HASH, fields)
        assert len(result) == 64

    def test_large_nested_state(self):
        """Should handle large nested state objects."""
        large_state = {
            f"field_{i}": {
                "nested": {
                    "value": i,
                    "data": list(range(100)),
                }
            }
            for i in range(50)
        }

        fields = {
            "timestamp": "2024-01-01T00:00:00",
            "actor_id": "user1",
            "action": "complex_operation",
            "after_state": large_state,
        }

        result = compute_hash(GENESIS_HASH, fields)
        assert len(result) == 64
