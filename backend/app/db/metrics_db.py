"""
API Metrics Database Module

Provides SQLite persistence for historical API response time metrics.
Used by performance monitoring dashboard for historical data queries.
"""

import sqlite3
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from contextlib import contextmanager

from app.db.database import _get_thread_conn, _lock


# Flag to track if table has been initialized
_TABLE_INITIALIZED = False


def _init_table(conn: sqlite3.Connection) -> None:
    """Initialize metrics table with indexes (only once)"""
    global _TABLE_INITIALIZED
    if _TABLE_INITIALIZED:
        return
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS api_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            method TEXT NOT NULL,
            response_time_ms REAL NOT NULL,
            status_code INTEGER NOT NULL
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_metrics_endpoint ON api_metrics(endpoint, timestamp)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON api_metrics(timestamp)')
    conn.commit()
    _TABLE_INITIALIZED = True


def _get_connection() -> sqlite3.Connection:
    """Get thread-local database connection from main database module"""
    conn = _get_thread_conn()
    _init_table(conn)
    return conn


def record_metric(endpoint: str, method: str, response_time_ms: float, status_code: int) -> None:
    """
    Record a single API metric.
    
    Args:
        endpoint: API endpoint path (e.g., "/api/v1/market/quote/sh600519")
        method: HTTP method (GET, POST, etc.)
        response_time_ms: Response time in milliseconds
        status_code: HTTP status code (200, 404, 500, etc.)
    """
    with _lock:
        conn = _get_connection()
        conn.execute(
            'INSERT INTO api_metrics (timestamp, endpoint, method, response_time_ms, status_code) VALUES (?, ?, ?, ?, ?)',
            (datetime.now().isoformat(), endpoint, method, response_time_ms, status_code)
        )
        conn.commit()


def get_metrics_history(endpoint: Optional[str] = None, hours: int = 24) -> List[Dict]:
    """
    Get metrics history for the last N hours.
    
    Args:
        endpoint: Optional endpoint filter
        hours: Number of hours to look back (default: 24)
    
    Returns:
        List of metric records with all fields
    """
    conn = _get_connection()
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    
    if endpoint:
        rows = conn.execute(
            'SELECT * FROM api_metrics WHERE endpoint = ? AND timestamp >= ? ORDER BY timestamp DESC LIMIT 1000',
            (endpoint, cutoff)
        ).fetchall()
    else:
        rows = conn.execute(
            'SELECT * FROM api_metrics WHERE timestamp >= ? ORDER BY timestamp DESC LIMIT 10000',
            (cutoff,)
        ).fetchall()
    
    return [dict(row) for row in rows]


def get_endpoint_stats(hours: int = 24) -> List[Dict]:
    """
    Get aggregated stats per endpoint.
    
    Args:
        hours: Number of hours to aggregate (default: 24)
    
    Returns:
        List of endpoint stats with count, avg, max, min response times
    """
    conn = _get_connection()
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    
    rows = conn.execute('''
        SELECT 
            endpoint,
            method,
            COUNT(*) as request_count,
            AVG(response_time_ms) as avg_ms,
            MAX(response_time_ms) as max_ms,
            MIN(response_time_ms) as min_ms
        FROM api_metrics
        WHERE timestamp >= ?
        GROUP BY endpoint, method
        ORDER BY avg_ms DESC
    ''', (cutoff,)).fetchall()
    
    return [dict(row) for row in rows]


def cleanup_old_metrics(days: int = 7) -> int:
    """
    Remove metrics older than N days.
    
    Args:
        days: Number of days to retain (default: 7)
    
    Returns:
        Number of deleted rows
    """
    with _lock:
        conn = _get_connection()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        cursor = conn.execute('DELETE FROM api_metrics WHERE timestamp < ?', (cutoff,))
        conn.commit()
        return cursor.rowcount


@contextmanager
def get_metrics_db():
    """Context manager for metrics database operations"""
    conn = _get_connection()
    try:
        yield conn
    finally:
        # Connection is thread-local, don't close it
        pass
