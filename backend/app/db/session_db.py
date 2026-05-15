"""
Session Management DB Helpers

CRUD operations for copilot session management.
"""
import json
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import uuid

logger = logging.getLogger(__name__)

DEFAULT_SESSION_TTL_HOURS = 24


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


def create_session(
    user_id: str = None,
    bound_models: List[str] = None,
    config_version: int = 1,
    ttl_hours: int = DEFAULT_SESSION_TTL_HOURS
) -> Dict[str, Any]:
    session_id = str(uuid.uuid4())
    now = datetime.now()
    expires_at = now + timedelta(hours=ttl_hours)
    
    conn = _get_conn()
    try:
        conn.execute("""
            INSERT INTO copilot_sessions 
            (session_id, user_id, config_version, bound_models, created_at, last_active_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id, user_id, config_version,
            json.dumps(bound_models) if bound_models else None,
            now.isoformat(), now.isoformat(), expires_at.isoformat()
        ))
        conn.commit()
        
        return {
            "session_id": session_id,
            "user_id": user_id,
            "config_version": config_version,
            "bound_models": bound_models or [],
            "created_at": now.isoformat(),
            "last_active_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "message_count": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0
        }
    finally:
        conn.close()


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM copilot_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        
        if not row:
            return None
        
        return {
            "session_id": row['session_id'],
            "user_id": row['user_id'],
            "config_version": row['config_version'],
            "bound_models": json.loads(row['bound_models']) if row['bound_models'] else [],
            "created_at": row['created_at'],
            "last_active_at": row['last_active_at'],
            "expires_at": row['expires_at'],
            "message_count": row['message_count'],
            "total_tokens": row['total_tokens'],
            "total_cost_usd": row['total_cost_usd']
        }
    finally:
        conn.close()


def update_session_activity(session_id: str) -> bool:
    conn = _get_conn()
    try:
        result = conn.execute("""
            UPDATE copilot_sessions 
            SET last_active_at = ? 
            WHERE session_id = ?
        """, (datetime.now().isoformat(), session_id))
        conn.commit()
        return result.rowcount > 0
    finally:
        conn.close()


def update_session_stats(
    session_id: str,
    tokens_added: int = 0,
    cost_added: float = 0.0,
    message_added: int = 1
) -> bool:
    conn = _get_conn()
    try:
        result = conn.execute("""
            UPDATE copilot_sessions 
            SET last_active_at = ?,
                message_count = message_count + ?,
                total_tokens = total_tokens + ?,
                total_cost_usd = total_cost_usd + ?
            WHERE session_id = ?
        """, (
            datetime.now().isoformat(),
            message_added, tokens_added, cost_added, session_id
        ))
        conn.commit()
        return result.rowcount > 0
    finally:
        conn.close()


def update_session_models(session_id: str, bound_models: List[str]) -> bool:
    conn = _get_conn()
    try:
        result = conn.execute("""
            UPDATE copilot_sessions 
            SET bound_models = ?, last_active_at = ? 
            WHERE session_id = ?
        """, (json.dumps(bound_models), datetime.now().isoformat(), session_id))
        conn.commit()
        return result.rowcount > 0
    finally:
        conn.close()


def update_session_config_version(session_id: str, config_version: int) -> bool:
    conn = _get_conn()
    try:
        result = conn.execute("""
            UPDATE copilot_sessions 
            SET config_version = ?, last_active_at = ? 
            WHERE session_id = ?
        """, (config_version, datetime.now().isoformat(), session_id))
        conn.commit()
        return result.rowcount > 0
    finally:
        conn.close()


def extend_session(session_id: str, additional_hours: int = 24) -> bool:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT expires_at FROM copilot_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        
        if not row:
            return False
        
        current_expires = datetime.fromisoformat(row['expires_at'])
        new_expires = max(datetime.now(), current_expires) + timedelta(hours=additional_hours)
        
        result = conn.execute("""
            UPDATE copilot_sessions 
            SET expires_at = ?, last_active_at = ? 
            WHERE session_id = ?
        """, (new_expires.isoformat(), datetime.now().isoformat(), session_id))
        conn.commit()
        return result.rowcount > 0
    finally:
        conn.close()


def is_session_expired(session_id: str) -> Optional[bool]:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT expires_at FROM copilot_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        
        if not row:
            return None
        
        expires_at = datetime.fromisoformat(row['expires_at'])
        return datetime.now() > expires_at
    finally:
        conn.close()


def delete_session(session_id: str) -> bool:
    conn = _get_conn()
    try:
        result = conn.execute(
            "DELETE FROM copilot_sessions WHERE session_id = ?", (session_id,)
        )
        conn.commit()
        return result.rowcount > 0
    finally:
        conn.close()


def get_sessions_by_user(user_id: str, include_expired: bool = False) -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        if include_expired:
            rows = conn.execute("""
                SELECT * FROM copilot_sessions 
                WHERE user_id = ? 
                ORDER BY last_active_at DESC
            """, (user_id,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM copilot_sessions 
                WHERE user_id = ? AND expires_at > ? 
                ORDER BY last_active_at DESC
            """, (user_id, datetime.now().isoformat())).fetchall()
        
        result = []
        for row in rows:
            result.append({
                "session_id": row['session_id'],
                "user_id": row['user_id'],
                "config_version": row['config_version'],
                "bound_models": json.loads(row['bound_models']) if row['bound_models'] else [],
                "created_at": row['created_at'],
                "last_active_at": row['last_active_at'],
                "expires_at": row['expires_at'],
                "message_count": row['message_count'],
                "total_tokens": row['total_tokens'],
                "total_cost_usd": row['total_cost_usd']
            })
        return result
    finally:
        conn.close()


def get_active_sessions(limit: int = 100) -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        rows = conn.execute("""
            SELECT * FROM copilot_sessions 
            WHERE expires_at > ? 
            ORDER BY last_active_at DESC 
            LIMIT ?
        """, (datetime.now().isoformat(), limit)).fetchall()
        
        result = []
        for row in rows:
            result.append({
                "session_id": row['session_id'],
                "user_id": row['user_id'],
                "config_version": row['config_version'],
                "bound_models": json.loads(row['bound_models']) if row['bound_models'] else [],
                "created_at": row['created_at'],
                "last_active_at": row['last_active_at'],
                "expires_at": row['expires_at'],
                "message_count": row['message_count'],
                "total_tokens": row['total_tokens'],
                "total_cost_usd": row['total_cost_usd']
            })
        return result
    finally:
        conn.close()


def cleanup_expired_sessions() -> int:
    conn = _get_conn()
    try:
        result = conn.execute(
            "DELETE FROM copilot_sessions WHERE expires_at < ?",
            (datetime.now().isoformat(),)
        )
        conn.commit()
        deleted_count = result.rowcount
        if deleted_count > 0:
            logger.info(f"[Session] Cleaned up {deleted_count} expired sessions")
        return deleted_count
    finally:
        conn.close()


def get_session_stats() -> Dict[str, Any]:
    conn = _get_conn()
    try:
        total_row = conn.execute(
            "SELECT COUNT(*) as count FROM copilot_sessions"
        ).fetchone()
        
        active_row = conn.execute(
            "SELECT COUNT(*) as count FROM copilot_sessions WHERE expires_at > ?",
            (datetime.now().isoformat(),)
        ).fetchone()
        
        stats_row = conn.execute("""
            SELECT 
                SUM(message_count) as total_messages,
                SUM(total_tokens) as total_tokens,
                SUM(total_cost_usd) as total_cost
            FROM copilot_sessions
        """).fetchone()
        
        return {
            "total_sessions": total_row['count'] if total_row else 0,
            "active_sessions": active_row['count'] if active_row else 0,
            "total_messages": stats_row['total_messages'] or 0,
            "total_tokens": stats_row['total_tokens'] or 0,
            "total_cost_usd": stats_row['total_cost'] or 0.0
        }
    finally:
        conn.close()


def init_session_table():
    pass


def get_session_conversations(session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get conversation history for a session from copilot_conversations table.
    
    Note: The copilot_conversations table is created and managed by the copilot router.
    This function provides read-only access to conversation data for admin purposes.
    """
    conn = _get_conn()
    try:
        # Check if the table exists first
        table_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='copilot_conversations'"
        ).fetchone()
        
        if not table_exists:
            return []
        
        rows = conn.execute("""
            SELECT id, session_id, role, content, created_at
            FROM copilot_conversations
            WHERE session_id = ?
            ORDER BY id ASC
            LIMIT ?
        """, (session_id, limit)).fetchall()
        
        result = []
        for row in rows:
            result.append({
                "id": row['id'],
                "session_id": row['session_id'],
                "role": row['role'],
                "content": row['content'],
                "created_at": row['created_at']
            })
        return result
    except Exception as e:
        logger.warning(f"[SessionDB] get_session_conversations error: {e}")
        return []
    finally:
        conn.close()
