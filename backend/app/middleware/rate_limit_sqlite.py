"""
SQLite-backed rate limiter for multi-worker deployments.

Uses SQLite with WAL mode for concurrent access across multiple worker processes.
"""

import sqlite3
import time
import threading
from typing import Tuple, Optional

# Thread-local storage for connections
_local = threading.local()


def _get_connection() -> sqlite3.Connection:
    """Get thread-local SQLite connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect("database.db", timeout=30.0)
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                key TEXT PRIMARY KEY,
                count INTEGER NOT NULL,
                reset_at REAL NOT NULL
            )
        """)
        _local.conn.commit()
    return _local.conn


class SQLiteRateLimiter:
    """SQLite-backed rate limiter for multi-worker deployments."""

    def is_allowed(
        self, key: str, limit: int, period: int
    ) -> Tuple[bool, int, int, int]:
        """Check if request is allowed under rate limit.

        Args:
            key: Unique identifier (e.g., "ip:endpoint")
            limit: Maximum requests allowed
            period: Time window in seconds

        Returns:
            Tuple of (allowed, remaining, limit, reset_time)
        """
        conn = _get_connection()
        cursor = conn.cursor()
        now = time.time()
        reset_at = now + period

        try:
            # Clean expired entries
            cursor.execute("DELETE FROM rate_limits WHERE reset_at < ?", (now,))

            # Get current entry
            cursor.execute(
                "SELECT count, reset_at FROM rate_limits WHERE key = ?", (key,)
            )
            row = cursor.fetchone()

            if row is None:
                # New entry
                cursor.execute(
                    "INSERT INTO rate_limits (key, count, reset_at) VALUES (?, 1, ?)",
                    (key, reset_at),
                )
                conn.commit()
                return True, limit - 1, limit, int(reset_at)

            count, stored_reset = row

            # Check if window expired
            if now > stored_reset:
                cursor.execute(
                    "UPDATE rate_limits SET count = 1, reset_at = ? WHERE key = ?",
                    (reset_at, key),
                )
                conn.commit()
                return True, limit - 1, limit, int(reset_at)

            # Check limit
            if count >= limit:
                return False, 0, limit, int(stored_reset)

            # Increment
            cursor.execute(
                "UPDATE rate_limits SET count = count + 1 WHERE key = ?", (key,)
            )
            conn.commit()
            return True, limit - count - 1, limit, int(stored_reset)

        except sqlite3.Error:
            # On error, allow the request (fail-open)
            return True, limit, limit, int(reset_at)

    def get_stats(self) -> dict:
        """Get rate limit statistics."""
        conn = _get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM rate_limits")
            total_keys = cursor.fetchone()[0]

            cursor.execute("SELECT key, count, reset_at FROM rate_limits LIMIT 100")
            entries = {}
            for row in cursor.fetchall():
                entries[row[0]] = {"count": row[1], "reset_at": row[2]}

            return {"total_keys": total_keys, "entries": entries}
        except sqlite3.Error:
            return {"total_keys": 0, "entries": {}}

    def reset(self, key: Optional[str] = None):
        """Reset rate limit for a key or all keys."""
        conn = _get_connection()
        cursor = conn.cursor()
        try:
            if key:
                cursor.execute("DELETE FROM rate_limits WHERE key = ?", (key,))
            else:
                cursor.execute("DELETE FROM rate_limits")
            conn.commit()
        except sqlite3.Error:
            pass


# Global instance
_limiter: Optional[SQLiteRateLimiter] = None


def get_limiter() -> SQLiteRateLimiter:
    """Get the global rate limiter instance."""
    global _limiter
    if _limiter is None:
        _limiter = SQLiteRateLimiter()
    return _limiter
