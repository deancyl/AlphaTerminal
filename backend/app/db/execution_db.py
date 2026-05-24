"""
Execution history persistence for strategy execution engine.
v0.6.126 - Architecture Refactoring
"""
import sqlite3
import json
from datetime import datetime
from typing import Dict, Any, Optional

from app.db.database import _get_thread_conn

# Table schema
CREATE_EXECUTION_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS execution_history (
    execution_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT DEFAULT NULL,
    result TEXT DEFAULT NULL,
    error TEXT DEFAULT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_execution_status ON execution_history(status);
CREATE INDEX IF NOT EXISTS idx_execution_start ON execution_history(start_time DESC);
"""

def init_execution_history_table():
    """Initialize execution_history table."""
    conn = _get_thread_conn()
    conn.executescript(CREATE_EXECUTION_HISTORY_TABLE)
    conn.commit()

def save_execution_result(
    execution_id: str,
    status: str,
    start_time: datetime,
    end_time: Optional[datetime] = None,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None
):
    """Save execution result to database."""
    conn = _get_thread_conn()
    conn.execute(
        """INSERT OR REPLACE INTO execution_history
           (execution_id, status, start_time, end_time, result, error, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
        (
            execution_id,
            status,
            start_time.isoformat(),
            end_time.isoformat() if end_time else None,
            json.dumps(result) if result else None,
            error
        )
    )
    conn.commit()

def get_execution_result(execution_id: str) -> Optional[Dict[str, Any]]:
    """Get execution result by ID."""
    conn = _get_thread_conn()
    row = conn.execute(
        "SELECT * FROM execution_history WHERE execution_id = ?",
        (execution_id,)
    ).fetchone()
    if row:
        result = dict(row)
        if result.get("result"):
            result["result"] = json.loads(result["result"])
        return result
    return None

def get_all_executions(status: Optional[str] = None, limit: int = 100) -> list:
    """Get all executions, optionally filtered by status."""
    conn = _get_thread_conn()
    if status:
        rows = conn.execute(
            "SELECT * FROM execution_history WHERE status = ? ORDER BY start_time DESC LIMIT ?",
            (status, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM execution_history ORDER BY start_time DESC LIMIT ?",
            (limit,)
        ).fetchall()
    return [dict(row) for row in rows]