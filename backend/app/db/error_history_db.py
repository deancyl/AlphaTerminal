"""
Error History Database Module

v0.6.64: 异常历史持久化存储
- 记录所有异常到数据库
- 支持查询和统计
- 7天自动清理
"""
import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "../../database.db")

ERROR_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS error_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    module TEXT NOT NULL,
    function TEXT NOT NULL,
    error_type TEXT NOT NULL,
    error_message TEXT,
    sanitized_message TEXT,
    context TEXT,
    traceback TEXT,
    trace_id TEXT,
    request_path TEXT,
    request_method TEXT,
    resolved INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_error_history_timestamp ON error_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_error_history_module ON error_history(module);
CREATE INDEX IF NOT EXISTS idx_error_history_resolved ON error_history(resolved);
"""


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_error_history_table():
    with get_connection() as conn:
        conn.executescript(ERROR_HISTORY_TABLE)
        conn.commit()


def log_error_to_db(
    module: str,
    function: str,
    error_type: str,
    error_message: str,
    sanitized_message: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    traceback_str: Optional[str] = None,
    trace_id: Optional[str] = None,
    request_path: Optional[str] = None,
    request_method: Optional[str] = None,
) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO error_history 
            (timestamp, module, function, error_type, error_message, sanitized_message, 
             context, traceback, trace_id, request_path, request_method)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().isoformat(),
                module,
                function,
                error_type,
                error_message,
                sanitized_message,
                json.dumps(context) if context else None,
                traceback_str,
                trace_id,
                request_path,
                request_method,
            )
        )
        conn.commit()
        return cursor.lastrowid


def get_error_history(
    limit: int = 100,
    offset: int = 0,
    module: Optional[str] = None,
    resolved: Optional[int] = None,
    since_hours: Optional[int] = None,
) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        query = "SELECT * FROM error_history WHERE 1=1"
        params = []

        if module:
            query += " AND module = ?"
            params.append(module)

        if resolved is not None:
            query += " AND resolved = ?"
            params.append(resolved)

        if since_hours:
            cutoff = datetime.now() - timedelta(hours=since_hours)
            query += " AND timestamp >= ?"
            params.append(cutoff.isoformat())

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def get_error_stats(since_hours: int = 24) -> Dict[str, Any]:
    with get_connection() as conn:
        cutoff = datetime.now() - timedelta(hours=since_hours)

        total = conn.execute(
            "SELECT COUNT(*) FROM error_history WHERE timestamp >= ?",
            (cutoff.isoformat(),)
        ).fetchone()[0]

        by_module = conn.execute(
            """
            SELECT module, COUNT(*) as count 
            FROM error_history 
            WHERE timestamp >= ?
            GROUP BY module 
            ORDER BY count DESC
            LIMIT 10
            """,
            (cutoff.isoformat(),)
        ).fetchall()

        by_type = conn.execute(
            """
            SELECT error_type, COUNT(*) as count 
            FROM error_history 
            WHERE timestamp >= ?
            GROUP BY error_type 
            ORDER BY count DESC
            LIMIT 10
            """,
            (cutoff.isoformat(),)
        ).fetchall()

        unresolved = conn.execute(
            """
            SELECT COUNT(*) FROM error_history 
            WHERE timestamp >= ? AND resolved = 0
            """,
            (cutoff.isoformat(),)
        ).fetchone()[0]

        return {
            "total": total,
            "unresolved": unresolved,
            "by_module": [dict(row) for row in by_module],
            "by_type": [dict(row) for row in by_type],
            "since_hours": since_hours,
        }


def mark_error_resolved(error_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE error_history SET resolved = 1 WHERE id = ?",
            (error_id,)
        )
        conn.commit()
        return cursor.rowcount > 0


def cleanup_old_errors(days: int = 7) -> int:
    with get_connection() as conn:
        cutoff = datetime.now() - timedelta(days=days)
        cursor = conn.execute(
            "DELETE FROM error_history WHERE timestamp < ?",
            (cutoff.isoformat(),)
        )
        conn.commit()
        return cursor.rowcount
