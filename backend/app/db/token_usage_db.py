"""
Token Usage DB Helpers

CRUD operations for token usage logging and aggregation.
"""
import json
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import uuid

logger = logging.getLogger(__name__)


def _get_conn():
    import os
    _db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        'database.db'
    )
    conn = sqlite3.connect(_db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError:
        conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def log_token_usage(
    model_id: str,
    provider: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    cost_usd: float,
    session_id: str = None,
    user_id: str = None,
    duration_ms: int = None,
    metadata: Dict[str, Any] = None
) -> str:
    request_id = str(uuid.uuid4())
    conn = _get_conn()
    try:
        conn.execute("""
            INSERT INTO token_usage_logs 
            (request_id, session_id, model_id, provider, prompt_tokens, completion_tokens,
             total_tokens, cost_usd, duration_ms, user_id, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request_id, session_id, model_id, provider, prompt_tokens, completion_tokens,
            total_tokens, cost_usd, duration_ms, user_id,
            json.dumps(metadata) if metadata else None,
            datetime.now().isoformat()
        ))
        conn.commit()
        return request_id
    finally:
        conn.close()


def get_usage_by_session(session_id: str) -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        rows = conn.execute("""
            SELECT * FROM token_usage_logs 
            WHERE session_id = ? 
            ORDER BY created_at DESC
        """, (session_id,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_usage_by_user(user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        rows = conn.execute("""
            SELECT * FROM token_usage_logs 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (user_id, limit)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_usage_by_model(model_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        rows = conn.execute("""
            SELECT * FROM token_usage_logs 
            WHERE model_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (model_id, limit)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_usage_by_date_range(start_date: str, end_date: str, limit: int = 1000) -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        rows = conn.execute("""
            SELECT * FROM token_usage_logs 
            WHERE created_at >= ? AND created_at <= ? 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (start_date, end_date, limit)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_session_totals(session_id: str) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    try:
        row = conn.execute("""
            SELECT 
                COUNT(*) as request_count,
                SUM(prompt_tokens) as total_prompt_tokens,
                SUM(completion_tokens) as total_completion_tokens,
                SUM(total_tokens) as total_tokens,
                SUM(cost_usd) as total_cost_usd,
                AVG(duration_ms) as avg_duration_ms
            FROM token_usage_logs 
            WHERE session_id = ?
        """, (session_id,)).fetchone()
        
        if not row or row['request_count'] == 0:
            return None
        
        return {
            "session_id": session_id,
            "request_count": row['request_count'],
            "total_prompt_tokens": row['total_prompt_tokens'] or 0,
            "total_completion_tokens": row['total_completion_tokens'] or 0,
            "total_tokens": row['total_tokens'] or 0,
            "total_cost_usd": row['total_cost_usd'] or 0.0,
            "avg_duration_ms": row['avg_duration_ms']
        }
    finally:
        conn.close()


def get_daily_totals(date: str = None) -> Dict[str, Any]:
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    
    conn = _get_conn()
    try:
        row = conn.execute("""
            SELECT 
                COUNT(*) as request_count,
                SUM(prompt_tokens) as total_prompt_tokens,
                SUM(completion_tokens) as total_completion_tokens,
                SUM(total_tokens) as total_tokens,
                SUM(cost_usd) as total_cost_usd
            FROM token_usage_logs 
            WHERE date(created_at) = ?
        """, (date,)).fetchone()
        
        return {
            "date": date,
            "request_count": row['request_count'] or 0,
            "total_prompt_tokens": row['total_prompt_tokens'] or 0,
            "total_completion_tokens": row['total_completion_tokens'] or 0,
            "total_tokens": row['total_tokens'] or 0,
            "total_cost_usd": row['total_cost_usd'] or 0.0
        }
    finally:
        conn.close()


def get_model_totals(model_id: str = None, days: int = 30) -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        if model_id:
            rows = conn.execute("""
                SELECT 
                    model_id,
                    provider,
                    COUNT(*) as request_count,
                    SUM(prompt_tokens) as total_prompt_tokens,
                    SUM(completion_tokens) as total_completion_tokens,
                    SUM(total_tokens) as total_tokens,
                    SUM(cost_usd) as total_cost_usd,
                    AVG(duration_ms) as avg_duration_ms
                FROM token_usage_logs 
                WHERE model_id = ? AND date(created_at) >= ?
                GROUP BY model_id, provider
            """, (model_id, start_date)).fetchall()
        else:
            rows = conn.execute("""
                SELECT 
                    model_id,
                    provider,
                    COUNT(*) as request_count,
                    SUM(prompt_tokens) as total_prompt_tokens,
                    SUM(completion_tokens) as total_completion_tokens,
                    SUM(total_tokens) as total_tokens,
                    SUM(cost_usd) as total_cost_usd,
                    AVG(duration_ms) as avg_duration_ms
                FROM token_usage_logs 
                WHERE date(created_at) >= ?
                GROUP BY model_id, provider
                ORDER BY total_cost_usd DESC
            """, (start_date,)).fetchall()
        
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_provider_totals(days: int = 30) -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        rows = conn.execute("""
            SELECT 
                provider,
                COUNT(*) as request_count,
                SUM(prompt_tokens) as total_prompt_tokens,
                SUM(completion_tokens) as total_completion_tokens,
                SUM(total_tokens) as total_tokens,
                SUM(cost_usd) as total_cost_usd
            FROM token_usage_logs 
            WHERE date(created_at) >= ?
            GROUP BY provider
            ORDER BY total_cost_usd DESC
        """, (start_date,)).fetchall()
        
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_usage_trend(days: int = 7) -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        rows = conn.execute("""
            SELECT 
                date(created_at) as date,
                COUNT(*) as request_count,
                SUM(prompt_tokens) as total_prompt_tokens,
                SUM(completion_tokens) as total_completion_tokens,
                SUM(total_tokens) as total_tokens,
                SUM(cost_usd) as total_cost_usd
            FROM token_usage_logs 
            WHERE date(created_at) >= ?
            GROUP BY date(created_at)
            ORDER BY date ASC
        """, (start_date,)).fetchall()
        
        return [dict(row) for row in rows]
    finally:
        conn.close()


def save_usage_aggregate(
    aggregate_type: str,
    aggregate_key: str,
    total_requests: int,
    total_prompt_tokens: int,
    total_completion_tokens: int,
    total_cost_usd: float,
    model_id: str = None,
    provider: str = None,
    user_id: str = None,
    avg_duration_ms: float = None
) -> int:
    conn = _get_conn()
    try:
        cursor = conn.execute("""
            INSERT OR REPLACE INTO usage_aggregates 
            (aggregate_type, aggregate_key, model_id, provider, user_id, 
             total_requests, total_prompt_tokens, total_completion_tokens, 
             total_cost_usd, avg_duration_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            aggregate_type, aggregate_key, model_id, provider, user_id,
            total_requests, total_prompt_tokens, total_completion_tokens,
            total_cost_usd, avg_duration_ms, datetime.now().isoformat()
        ))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_aggregates_by_type(aggregate_type: str, limit: int = 100) -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        rows = conn.execute("""
            SELECT * FROM usage_aggregates 
            WHERE aggregate_type = ? 
            ORDER BY total_cost_usd DESC 
            LIMIT ?
        """, (aggregate_type, limit)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def init_token_table():
    pass
