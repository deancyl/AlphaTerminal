"""
Strategy Execution Audit Trail

This module provides comprehensive audit logging for all strategy executions,
including:
- User identification
- Code hash for integrity verification
- Execution timestamps
- Security validation results
- Execution outcomes

All audit records are stored in the database for compliance and security review.

Author: AlphaTerminal Security Team
Version: 1.0
"""

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

AUDIT_DB_PATH = Path(__file__).parent.parent.parent.parent / "cache" / "strategy_audit.db"


@dataclass
class AuditRecord:
    """Audit record for strategy execution."""
    record_id: str
    user_id: str
    code_hash: str
    code_length: int
    timestamp: str
    action: str
    is_validated: bool
    validation_errors: List[str] = field(default_factory=list)
    execution_status: str = "pending"
    execution_time_ms: float = 0.0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def compute_code_hash(code: str) -> str:
    """Compute SHA-256 hash of strategy code."""
    return hashlib.sha256(code.encode('utf-8')).hexdigest()


def init_audit_db():
    """Initialize audit database."""
    AUDIT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(AUDIT_DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS strategy_audit (
            record_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            code_hash TEXT NOT NULL,
            code_length INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            action TEXT NOT NULL,
            is_validated INTEGER NOT NULL,
            validation_errors TEXT,
            execution_status TEXT NOT NULL,
            execution_time_ms REAL,
            error_message TEXT,
            metadata TEXT
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_id ON strategy_audit(user_id)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_timestamp ON strategy_audit(timestamp)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_code_hash ON strategy_audit(code_hash)
    """)
    
    conn.commit()
    conn.close()


def log_strategy_execution(
    user_id: str,
    code: str,
    action: str = "execute",
    is_validated: bool = True,
    validation_errors: Optional[List[str]] = None,
    execution_status: str = "success",
    execution_time_ms: float = 0.0,
    error_message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Log a strategy execution to the audit trail.
    
    Args:
        user_id: User who executed the strategy
        code: Strategy code
        action: Action type (execute, validate, compile)
        is_validated: Whether code passed security validation
        validation_errors: List of validation errors if any
        execution_status: Execution result (success, failed, timeout, security_error)
        execution_time_ms: Execution time in milliseconds
        error_message: Error message if execution failed
        metadata: Additional metadata
        
    Returns:
        Record ID of the audit entry
    """
    import uuid
    
    init_audit_db()
    
    record_id = str(uuid.uuid4())
    code_hash = compute_code_hash(code)
    timestamp = datetime.now().isoformat()
    
    record = AuditRecord(
        record_id=record_id,
        user_id=user_id,
        code_hash=code_hash,
        code_length=len(code),
        timestamp=timestamp,
        action=action,
        is_validated=is_validated,
        validation_errors=validation_errors or [],
        execution_status=execution_status,
        execution_time_ms=execution_time_ms,
        error_message=error_message,
        metadata=metadata or {},
    )
    
    conn = sqlite3.connect(str(AUDIT_DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO strategy_audit (
            record_id, user_id, code_hash, code_length, timestamp,
            action, is_validated, validation_errors, execution_status,
            execution_time_ms, error_message, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record.record_id,
        record.user_id,
        record.code_hash,
        record.code_length,
        record.timestamp,
        record.action,
        1 if record.is_validated else 0,
        json.dumps(record.validation_errors),
        record.execution_status,
        record.execution_time_ms,
        record.error_message,
        json.dumps(record.metadata),
    ))
    
    conn.commit()
    conn.close()
    
    logger.info(f"[Audit] Strategy execution logged: {record_id} by {user_id}")
    
    return record_id


def get_audit_records(
    user_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    action: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve audit records.
    
    Args:
        user_id: Filter by user ID
        limit: Maximum number of records to return
        offset: Offset for pagination
        action: Filter by action type
        
    Returns:
        List of audit records
    """
    init_audit_db()
    
    conn = sqlite3.connect(str(AUDIT_DB_PATH))
    cursor = conn.cursor()
    
    query = "SELECT * FROM strategy_audit WHERE 1=1"
    params = []
    
    if user_id:
        query += " AND user_id = ?"
        params.append(user_id)
    
    if action:
        query += " AND action = ?"
        params.append(action)
    
    query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    records = []
    for row in rows:
        records.append({
            "record_id": row[0],
            "user_id": row[1],
            "code_hash": row[2],
            "code_length": row[3],
            "timestamp": row[4],
            "action": row[5],
            "is_validated": bool(row[6]),
            "validation_errors": json.loads(row[7]) if row[7] else [],
            "execution_status": row[8],
            "execution_time_ms": row[9],
            "error_message": row[10],
            "metadata": json.loads(row[11]) if row[11] else {},
        })
    
    return records


def get_audit_stats() -> Dict[str, Any]:
    """
    Get audit statistics.
    
    Returns:
        Dictionary with audit statistics
    """
    init_audit_db()
    
    conn = sqlite3.connect(str(AUDIT_DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM strategy_audit")
    total_executions = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT user_id) FROM strategy_audit")
    unique_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM strategy_audit WHERE execution_status = 'security_error'")
    security_errors = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM strategy_audit WHERE execution_status = 'timeout'")
    timeouts = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM strategy_audit WHERE is_validated = 0")
    validation_failures = cursor.fetchone()[0]
    
    cursor.execute("SELECT AVG(execution_time_ms) FROM strategy_audit WHERE execution_status = 'success'")
    avg_execution_time = cursor.fetchone()[0] or 0
    
    conn.close()
    
    return {
        "total_executions": total_executions,
        "unique_users": unique_users,
        "security_errors": security_errors,
        "timeouts": timeouts,
        "validation_failures": validation_failures,
        "avg_execution_time_ms": round(avg_execution_time, 2),
    }


def check_suspicious_activity(user_id: str, window_hours: int = 24) -> Dict[str, Any]:
    """
    Check for suspicious activity patterns.
    
    Args:
        user_id: User ID to check
        window_hours: Time window in hours
        
    Returns:
        Dictionary with suspicious activity indicators
    """
    init_audit_db()
    
    conn = sqlite3.connect(str(AUDIT_DB_PATH))
    cursor = conn.cursor()
    
    cutoff = datetime.now().timestamp() - (window_hours * 3600)
    cutoff_str = datetime.fromtimestamp(cutoff).isoformat()
    
    cursor.execute("""
        SELECT COUNT(*) FROM strategy_audit 
        WHERE user_id = ? AND timestamp >= ?
    """, (user_id, cutoff_str))
    recent_count = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM strategy_audit 
        WHERE user_id = ? AND execution_status = 'security_error' AND timestamp >= ?
    """, (user_id, cutoff_str))
    security_error_count = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM strategy_audit 
        WHERE user_id = ? AND execution_status = 'timeout' AND timestamp >= ?
    """, (user_id, cutoff_str))
    timeout_count = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(DISTINCT code_hash) FROM strategy_audit 
        WHERE user_id = ? AND timestamp >= ?
    """, (user_id, cutoff_str))
    unique_codes = cursor.fetchone()[0]
    
    conn.close()
    
    is_suspicious = (
        security_error_count > 3 or
        timeout_count > 5 or
        (recent_count > 50 and unique_codes < 5)
    )
    
    return {
        "user_id": user_id,
        "window_hours": window_hours,
        "recent_executions": recent_count,
        "security_errors": security_error_count,
        "timeouts": timeout_count,
        "unique_codes": unique_codes,
        "is_suspicious": is_suspicious,
    }


if __name__ == "__main__":
    print("=" * 80)
    print("Strategy Audit Trail Tests")
    print("=" * 80)
    
    init_audit_db()
    
    test_code = """
def on_bar(ctx, bar):
    if bar['close'] > bar['open']:
        ctx.buy(bar['close'], 100)
"""
    
    print("\nTest 1: Log successful execution")
    record_id = log_strategy_execution(
        user_id="test_user",
        code=test_code,
        action="execute",
        is_validated=True,
        execution_status="success",
        execution_time_ms=123.45,
    )
    print(f"  Record ID: {record_id}")
    
    print("\nTest 2: Log security error")
    record_id = log_strategy_execution(
        user_id="attacker",
        code="import os\nos.system('rm -rf /')",
        action="execute",
        is_validated=False,
        validation_errors=["Forbidden import: os"],
        execution_status="security_error",
    )
    print(f"  Record ID: {record_id}")
    
    print("\nTest 3: Get audit stats")
    stats = get_audit_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("\nTest 4: Check suspicious activity")
    suspicious = check_suspicious_activity("attacker")
    print(f"  Is suspicious: {suspicious['is_suspicious']}")
    print(f"  Security errors: {suspicious['security_errors']}")
    
    print("\n" + "=" * 80)
    print("Audit trail tests completed!")
