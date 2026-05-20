"""
Audit Router - SEC Rule 17a-4 Compliance API

Provides endpoints for:
- Chain integrity verification
- Audit statistics
- Audit log queries
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional

from app.services.audit_chain import (
    verify_chain,
    get_chain_stats,
    log_audit_event,
)
from app.db.audit_db import get_audit_logs, get_audit_logs_keyset, count_audit_logs
from app.utils.error_decorator import handle_errors

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("/verify")
@handle_errors(module="audit")
async def verify_audit_chain(
    from_id: Optional[int] = Query(None, ge=1, description="Start ID for verification"),
    to_id: Optional[int] = Query(None, ge=1, description="End ID for verification"),
):
    """
    Verify audit chain integrity.
    
    Checks:
    1. Each record's prev_hash matches the previous record's record_hash
    2. Each record's record_hash can be recomputed from its fields
    3. Chain index is sequential
    
    Returns:
        - valid: bool - Whether the chain is valid
        - checked_records: int - Number of records checked
        - first_invalid_id: Optional[int] - ID of first invalid record (if any)
        - error_type: Optional[str] - Type of error (if any)
    """
    result = verify_chain(from_id=from_id, to_id=to_id)
    return result


@router.get("/stats")
@handle_errors(module="audit")
async def get_audit_stats():
    """
    Get audit chain statistics.
    
    Returns:
        - total_records: int - Total number of audit records
        - chain_index_min: int - Minimum chain index
        - chain_index_max: int - Maximum chain index
        - first_record: dict - First record in chain
        - last_record: dict - Last record in chain
        - genesis_hash: str - Genesis hash (64 zeros)
        - retention_days: int - SEC Rule 17a-4 retention period
    """
    stats = get_chain_stats()
    return stats


@router.get("/logs")
@handle_errors(module="audit")
async def query_audit_logs(
    after_timestamp: Optional[str] = Query(None, description="Cursor: get logs before this timestamp (ISO format)"),
    after_id: Optional[int] = Query(None, ge=1, description="Cursor: get logs with id less than this (for same timestamp)"),
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset for pagination (deprecated, use after_timestamp/after_id)"),
):
    """
    Query audit logs with keyset pagination for O(1) performance.
    
    Keyset pagination uses cursor (after_timestamp, after_id) instead of OFFSET.
    This provides constant-time performance even for deep pages.
    
    Args:
        after_timestamp: Cursor timestamp - get logs before this time
        after_id: Cursor ID - for disambiguating same-timestamp records
        agent_id: Filter by agent ID
        action: Filter by action type
        limit: Max results (1-1000)
        offset: DEPRECATED - use cursor instead
        
    Returns:
        - logs: List of audit log entries
        - has_more: Boolean indicating if more results exist
        - next_after_timestamp: Cursor timestamp for next page
        - next_after_id: Cursor ID for next page
        - total: Total count matching filters (for UI display)
    """
    if after_timestamp and after_id is not None:
        logs = get_audit_logs_keyset(
            after_timestamp=after_timestamp,
            after_id=after_id,
            limit=limit,
            agent_id=agent_id,
            action=action,
        )
    else:
        logs = get_audit_logs(
            agent_id=agent_id,
            action=action,
            limit=limit,
            offset=offset,
        )
    
    total = count_audit_logs(agent_id=agent_id, action=action)
    has_more = len(logs) == limit
    
    next_after_timestamp = logs[-1]["timestamp"] if logs else None
    next_after_id = logs[-1]["id"] if logs else None
    
    return {
        "logs": logs,
        "has_more": has_more,
        "next_after_timestamp": next_after_timestamp,
        "next_after_id": next_after_id,
        "total": total,
        "limit": limit,
    }


@router.get("/health")
@handle_errors(module="audit")
async def audit_health():
    """
    Health check for audit system.
    
    Returns:
        - status: str - "ok" if audit system is healthy
        - chain_valid: bool - Whether chain verification passes
        - retention_days: int - SEC Rule 17a-4 retention period
    """
    result = verify_chain()
    return {
        "status": "ok" if result["valid"] else "degraded",
        "chain_valid": result["valid"],
        "checked_records": result["checked_records"],
        "retention_days": 2555,
    }
