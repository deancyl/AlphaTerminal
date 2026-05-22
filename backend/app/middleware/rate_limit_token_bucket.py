"""
Token Bucket Rate Limiter

Implements the Token Bucket algorithm for rate limiting with burst support.

Algorithm:
- Tokens are added at a fixed rate (refill_rate tokens/second)
- Bucket has a maximum capacity (burst_capacity)
- Each request consumes one token
- If bucket is empty, request is denied

Formula:
    tokens = min(capacity, last_tokens + elapsed * rate)

Benefits over Fixed Window Counter:
- Allows burst traffic up to capacity
- Smoother rate limiting
- No sudden reset at window boundaries

v0.6.61: Initial implementation for 150 req/min requirement.
"""
import sqlite3
import time
import threading
import logging
from typing import Tuple, Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Thread-local storage for connections
_local = threading.local()


def _get_connection() -> sqlite3.Connection:
    """Get thread-local SQLite connection."""
    if not hasattr(_local, 'conn') or _local.conn is None:
        _local.conn = sqlite3.connect('database.db', timeout=30.0)
        _local.conn.execute('PRAGMA journal_mode=WAL')
        _local.conn.execute('''
            CREATE TABLE IF NOT EXISTS token_buckets (
                key TEXT PRIMARY KEY,
                tokens REAL NOT NULL,
                last_refreshed REAL NOT NULL
            )
        ''')
        _local.conn.commit()
    return _local.conn


class TokenBucketRateLimiter:
    """
    Token Bucket Rate Limiter with SQLite backend.
    
    Usage:
        limiter = TokenBucketRateLimiter()
        
        # Check if request allowed (150 req/min = 2.5 tokens/sec)
        allowed, remaining, limit, reset = limiter.is_allowed(
            key="192.168.1.1:/api/v1/market/overview",
            refill_rate=2.5,  # tokens per second
            burst_capacity=150  # max tokens
        )
    """
    
    def is_allowed(
        self,
        key: str,
        refill_rate: float,
        burst_capacity: int
    ) -> Tuple[bool, int, int, int]:
        """
        Check if request is allowed under token bucket rate limit.
        
        Args:
            key: Unique identifier (e.g., "ip:endpoint")
            refill_rate: Tokens added per second (e.g., 2.5 for 150 req/min)
            burst_capacity: Maximum tokens in bucket (burst allowance)
            
        Returns:
            Tuple of (allowed, remaining_tokens, capacity, reset_time)
        """
        conn = _get_connection()
        cursor = conn.cursor()
        now = time.time()
        
        try:
            # Get current bucket state
            cursor.execute(
                'SELECT tokens, last_refreshed FROM token_buckets WHERE key = ?',
                (key,)
            )
            row = cursor.fetchone()
            
            if row is None:
                # New bucket - start full
                tokens = float(burst_capacity)
                cursor.execute(
                    'INSERT INTO token_buckets (key, tokens, last_refreshed) VALUES (?, ?, ?)',
                    (key, tokens, now)
                )
                conn.commit()
                return True, burst_capacity - 1, burst_capacity, int(now + 60)
            
            last_tokens, last_refreshed = row
            elapsed = now - last_refreshed
            
            # Token bucket formula: tokens = min(capacity, last_tokens + elapsed * rate)
            new_tokens = min(
                burst_capacity,
                last_tokens + elapsed * refill_rate
            )
            
            if new_tokens < 1.0:
                # Not enough tokens
                # Calculate time until next token available
                if refill_rate > 0:
                    time_until_token = (1.0 - new_tokens) / refill_rate
                    reset_time = int(now + time_until_token)
                else:
                    # No refill - tokens will never be available
                    reset_time = int(now + 86400)  # 24 hours
                return False, 0, burst_capacity, reset_time
            
            # Consume one token
            new_tokens -= 1.0
            
            cursor.execute(
                'UPDATE token_buckets SET tokens = ?, last_refreshed = ? WHERE key = ?',
                (new_tokens, now, key)
            )
            conn.commit()
            
            return True, int(new_tokens), burst_capacity, int(now + 60)
            
        except sqlite3.Error as e:
            logger.warning(f"[TokenBucket] SQLite error for {key}: {e}", exc_info=True)
            # Fail-open: allow request on error
            return True, burst_capacity, burst_capacity, int(now + 60)
    
    def get_bucket_state(self, key: str) -> Optional[dict]:
        """Get current bucket state for debugging."""
        conn = _get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                'SELECT tokens, last_refreshed FROM token_buckets WHERE key = ?',
                (key,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "tokens": row[0],
                    "last_refreshed": row[1],
                    "age_seconds": time.time() - row[1]
                }
            return None
        except sqlite3.Error:
            return None
    
    def get_stats(self) -> dict:
        """Get rate limit statistics."""
        conn = _get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT COUNT(*) FROM token_buckets')
            total_keys = cursor.fetchone()[0]
            
            cursor.execute('SELECT key, tokens, last_refreshed FROM token_buckets LIMIT 100')
            entries = {}
            for row in cursor.fetchall():
                entries[row[0]] = {
                    "tokens": row[1],
                    "last_refreshed": row[2]
                }
            
            return {
                "total_keys": total_keys,
                "entries": entries,
                "algorithm": "token_bucket"
            }
        except sqlite3.Error:
            return {"total_keys": 0, "entries": {}, "algorithm": "token_bucket"}
    
    def reset(self, key: Optional[str] = None):
        """Reset rate limit for a key or all keys."""
        conn = _get_connection()
        cursor = conn.cursor()
        try:
            if key:
                cursor.execute('DELETE FROM token_buckets WHERE key = ?', (key,))
            else:
                cursor.execute('DELETE FROM token_buckets')
            conn.commit()
        except sqlite3.Error:
            pass


# Global instance
_token_bucket_limiter: Optional[TokenBucketRateLimiter] = None


def get_token_bucket_limiter() -> TokenBucketRateLimiter:
    """Get the global token bucket rate limiter instance."""
    global _token_bucket_limiter
    if _token_bucket_limiter is None:
        _token_bucket_limiter = TokenBucketRateLimiter()
    return _token_bucket_limiter
