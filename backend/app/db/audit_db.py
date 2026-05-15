"""
Audit Database Service - Audit log operations with SQLite persistence

Tables:
- audit_logs: id, timestamp, agent_id, action, resource, details, ip_address, user_agent
"""

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from app.db.database import _get_conn, _lock


def init_audit_table():
    """Initialize audit_logs table (called from database.py init_tables)"""
    with _lock:
        conn = _get_conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    resource TEXT,
                    details TEXT,
                    ip_address TEXT,
                    user_agent TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_agent ON audit_logs(agent_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_logs(resource)")
            conn.commit()
        finally:
            conn.close()


def log_audit(
    agent_id: str,
    action: str,
    resource: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> int:
    """
    Log an audit event
    
    Args:
        agent_id: Agent/token ID performing the action
        action: Action type (e.g., 'create_token', 'run_backtest', 'get_price')
        resource: Resource being accessed (e.g., '/api/agent/v1/markets')
        details: Additional details as dict
        ip_address: Client IP address
        user_agent: Client user agent
    
    Returns:
        Log entry ID
    """
    now = datetime.now().isoformat()
    details_str = json.dumps(details, ensure_ascii=False) if details else None
    
    with _lock:
        conn = _get_conn()
        try:
            cursor = conn.execute("""
                INSERT INTO audit_logs
                (timestamp, agent_id, action, resource, details, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (now, agent_id, action, resource, details_str, ip_address, user_agent))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"[AuditDB] Log failed: {e}")
            return -1
        finally:
            conn.close()


def get_audit_logs(
    agent_id: Optional[str] = None,
    action: Optional[str] = None,
    resource: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict]:
    """
    Query audit logs with filters
    
    Args:
        agent_id: Filter by agent ID
        action: Filter by action type
        resource: Filter by resource
        start_time: Filter by start time
        end_time: Filter by end time
        limit: Max results
        offset: Offset for pagination
    
    Returns:
        List of audit log entries
    """
    conn = _get_conn()
    try:
        conditions = []
        params = []
        
        if agent_id:
            conditions.append("agent_id = ?")
            params.append(agent_id)
        if action:
            conditions.append("action = ?")
            params.append(action)
        if resource:
            conditions.append("resource LIKE ?")
            params.append(f"%{resource}%")
        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time.isoformat())
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time.isoformat())
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        query = f"""
            SELECT * FROM audit_logs
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        
        rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(row) for row in rows]
    except Exception as e:
        logger.error(f"[AuditDB] Query failed: {e}")
        return []
    finally:
        conn.close()


def count_audit_logs(
    agent_id: Optional[str] = None,
    action: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> int:
    """Count audit logs with filters"""
    conn = _get_conn()
    try:
        conditions = []
        params = []
        
        if agent_id:
            conditions.append("agent_id = ?")
            params.append(agent_id)
        if action:
            conditions.append("action = ?")
            params.append(action)
        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time.isoformat())
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time.isoformat())
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        query = f"SELECT COUNT(*) as cnt FROM audit_logs WHERE {where_clause}"
        row = conn.execute(query, params).fetchone()
        
        return row["cnt"] if row else 0
    except Exception as e:
        logger.error(f"[AuditDB] Count failed: {e}")
        return 0
    finally:
        conn.close()


def delete_old_logs(days: int = 90) -> int:
    """Delete audit logs older than N days"""
    with _lock:
        conn = _get_conn()
        try:
            cutoff = datetime.now()
            from datetime import timedelta
            cutoff_str = (cutoff - timedelta(days=days)).isoformat()
            
            cursor = conn.execute(
                "DELETE FROM audit_logs WHERE timestamp < ?",
                (cutoff_str,)
            )
            conn.commit()
            deleted = cursor.rowcount
            if deleted > 0:
                logger.info(f"[AuditDB] Deleted {deleted} old audit logs (older than {days} days)")
            return deleted
        except Exception as e:
            logger.error(f"[AuditDB] Delete old logs failed: {e}")
            return 0
        finally:
            conn.close()


def get_agent_activity_summary(agent_id: str, days: int = 7) -> Dict:
    """Get activity summary for an agent"""
    conn = _get_conn()
    try:
        cutoff = datetime.now()
        from datetime import timedelta
        cutoff_str = (cutoff - timedelta(days=days)).isoformat()
        
        rows = conn.execute("""
            SELECT action, COUNT(*) as cnt
            FROM audit_logs
            WHERE agent_id = ? AND timestamp >= ?
            GROUP BY action
            ORDER BY cnt DESC
        """, (agent_id, cutoff_str)).fetchall()
        
        total = conn.execute("""
            SELECT COUNT(*) as cnt
            FROM audit_logs
            WHERE agent_id = ? AND timestamp >= ?
        """, (agent_id, cutoff_str)).fetchone()
        
        return {
            "agent_id": agent_id,
            "period_days": days,
            "total_actions": total["cnt"] if total else 0,
            "actions_by_type": {row["action"]: row["cnt"] for row in rows},
        }
    except Exception as e:
        logger.error(f"[AuditDB] Get summary failed: {e}")
        return {"agent_id": agent_id, "period_days": days, "total_actions": 0, "actions_by_type": {}}
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> Dict:
    """Convert sqlite3.Row to dict with JSON parsing"""
    result = dict(row)
    
    if result.get("details"):
        try:
            result["details"] = json.loads(result["details"])
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"[AUDIT_DB] Failed to parse details JSON: {type(e).__name__}: {e}")
    
    return result
