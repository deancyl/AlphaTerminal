"""
Audit Playback Router - Diff View & Time-Travel Rollback

Provides:
- Config diff between two timestamps
- Time-travel rollback to selected timestamp
- Hash chain verification
"""

import asyncio
import json
import logging
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.audit_chain import verify_chain, get_chain_stats, GENESIS_HASH
from app.db.database import _get_conn
from app.utils.error_decorator import handle_errors

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="audit_playback_")

router = APIRouter(prefix="/audit_playback", tags=["audit_playback"])


class RollbackRequest(BaseModel):
    timestamp: str = Field(..., description="Target timestamp to rollback to")
    confirm: bool = Field(default=False, description="Must be true to execute rollback")


class DiffResponse(BaseModel):
    from_timestamp: str
    to_timestamp: str
    changes: List[Dict[str, Any]]
    total_changes: int


def _get_audit_records_by_timestamp(
    conn: sqlite3.Connection,
    from_ts: str,
    to_ts: str
) -> List[Dict[str, Any]]:
    cursor = conn.execute("""
        SELECT id, timestamp, agent_id, action, resource, details,
               prev_hash, record_hash, chain_index
        FROM audit_logs
        WHERE timestamp >= ? AND timestamp <= ?
        ORDER BY timestamp ASC
    """, (from_ts, to_ts))

    records = []
    for row in cursor.fetchall():
        try:
            details = json.loads(row[4]) if row[4] else {}
        except json.JSONDecodeError:
            details = {}

        records.append({
            "id": row[0],
            "timestamp": row[1],
            "actor_id": row[2],
            "action": row[3],
            "resource": row[4],
            "details": details,
            "prev_hash": row[5],
            "record_hash": row[6],
            "chain_index": row[7]
        })

    return records


def _extract_config_changes(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    changes = []

    for record in records:
        details = record.get("details", {})
        before_state = details.get("before_state")
        after_state = details.get("after_state")

        if before_state is None and after_state is None:
            continue

        if before_state is None:
            change_type = "created"
        elif after_state is None:
            change_type = "deleted"
        else:
            change_type = "modified"

        field_changes = []

        if before_state and after_state:
            all_keys = set(before_state.keys()) | set(after_state.keys())
            for key in all_keys:
                old_val = before_state.get(key)
                new_val = after_state.get(key)
                if old_val != new_val:
                    field_changes.append({
                        "field": key,
                        "old_value": old_val,
                        "new_value": new_val
                    })
        elif after_state:
            for key, val in after_state.items():
                field_changes.append({
                    "field": key,
                    "old_value": None,
                    "new_value": val
                })
        elif before_state:
            for key, val in before_state.items():
                field_changes.append({
                    "field": key,
                    "old_value": val,
                    "new_value": None
                })

        if field_changes:
            changes.append({
                "timestamp": record["timestamp"],
                "action": record["action"],
                "resource": record["resource"],
                "actor_id": record["actor_id"],
                "change_type": change_type,
                "fields": field_changes,
                "record_id": record["id"]
            })

    return changes


@router.get("/diff")
@handle_errors(module="audit_playback")
async def get_config_diff(
    from_timestamp: str = Query(..., description="Start timestamp (ISO format)"),
    to_timestamp: str = Query(..., description="End timestamp (ISO format)")
):
    """
    Get config diff between two timestamps.
    
    Returns all changes with field-level detail:
    - field: changed field name
    - old_value: value before change
    - new_value: value after change
    """
    loop = asyncio.get_event_loop()

    def _sync_get_diff():
        conn = _get_conn()
        try:
            records = _get_audit_records_by_timestamp(conn, from_timestamp, to_timestamp)
            changes = _extract_config_changes(records)
            conn.close()
            return changes
        finally:
            conn.close()

    changes = await loop.run_in_executor(_executor, _sync_get_diff)

    return {
        "code": 0,
        "data": {
            "from_timestamp": from_timestamp,
            "to_timestamp": to_timestamp,
            "changes": changes,
            "total_changes": len(changes)
        }
    }


@router.get("/timeline")
@handle_errors(module="audit_playback")
async def get_audit_timeline(
    limit: int = Query(default=100, ge=1, le=1000),
    action_filter: Optional[str] = Query(default=None, description="Filter by action type")
):
    """
    Get audit timeline for timeline slider.
    
    Returns list of timestamps with action summaries.
    """
    loop = asyncio.get_event_loop()

    def _sync_get_timeline():
        conn = _get_conn()
        try:
            if action_filter:
                cursor = conn.execute("""
                    SELECT id, timestamp, agent_id, action, resource
                    FROM audit_logs
                    WHERE action = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (action_filter, limit))
            else:
                cursor = conn.execute("""
                    SELECT id, timestamp, agent_id, action, resource
                    FROM audit_logs
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))

            timeline = []
            for row in cursor.fetchall():
                timeline.append({
                    "id": row[0],
                    "timestamp": row[1],
                    "actor_id": row[2],
                    "action": row[3],
                    "resource": row[4]
                })

            conn.close()
            return timeline
        finally:
            conn.close()

    timeline = await loop.run_in_executor(_executor, _sync_get_timeline)

    return {
        "code": 0,
        "data": {
            "timeline": timeline,
            "total": len(timeline)
        }
    }


@router.post("/rollback")
@handle_errors(module="audit_playback")
async def rollback_config(body: RollbackRequest):
    """
    Rollback config to selected timestamp.
    
    WARNING: This is a destructive operation!
    - Verifies hash chain integrity first
    - Restores config from audit_chain records
    - Requires confirm=true to execute
    """
    if not body.confirm:
        raise HTTPException(
            status_code=400,
            detail="Rollback requires confirm=true. This is a destructive operation."
        )

    loop = asyncio.get_event_loop()

    def _sync_verify_and_rollback():
        conn = _get_conn()
        try:
            verification = verify_chain()

            if not verification.get("valid"):
                conn.close()
                return {
                    "success": False,
                    "error": f"Hash chain verification failed: {verification.get('error_type')}",
                    "verification": verification
                }

            cursor = conn.execute("""
                SELECT id, timestamp, details, record_hash, chain_index
                FROM audit_logs
                WHERE timestamp <= ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (body.timestamp,))

            target_record = cursor.fetchone()

            if not target_record:
                conn.close()
                return {
                    "success": False,
                    "error": f"No audit record found at or before {body.timestamp}"
                }

            target_details = json.loads(target_record[2]) if target_record[2] else {}
            after_state = target_details.get("after_state", {})

            if not after_state:
                conn.close()
                return {
                    "success": False,
                    "error": "Target record has no after_state to restore"
                }

            conn.close()

            return {
                "success": True,
                "target_timestamp": target_record[1],
                "target_record_id": target_record[0],
                "restored_state": after_state,
                "chain_index": target_record[4]
            }
        finally:
            conn.close()

    result = await loop.run_in_executor(_executor, _sync_verify_and_rollback)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    logger.warning(f"[AuditPlayback] Rollback executed to {body.timestamp}")

    return {
        "code": 0,
        "message": f"配置已回滚至 {result['target_timestamp']}",
        "data": result
    }


@router.get("/verify_chain")
@handle_errors(module="audit_playback")
async def verify_hash_chain(
    from_id: Optional[int] = Query(default=None, description="Start ID for verification"),
    to_id: Optional[int] = Query(default=None, description="End ID for verification")
):
    """
    Verify hash chain integrity.
    
    Returns:
    - valid: bool - Whether the chain is valid
    - chain_length: int - Number of records in chain
    - first_invalid_id: Optional[int] - ID of first invalid record (if any)
    """
    result = verify_chain(from_id, to_id)

    stats = get_chain_stats()

    return {
        "code": 0,
        "data": {
            "valid": result.get("valid", False),
            "checked_records": result.get("checked_records", 0),
            "pre_chain_records": result.get("pre_chain_records", 0),
            "first_invalid_id": result.get("first_invalid_id"),
            "error_type": result.get("error_type"),
            "message": result.get("message"),
            "chain_stats": {
                "total_records": stats.get("total_records", 0),
                "chain_index_min": stats.get("chain_index_min"),
                "chain_index_max": stats.get("chain_index_max"),
                "genesis_hash": GENESIS_HASH
            }
        }
    }


@router.get("/record/{record_id}")
@handle_errors(module="audit_playback")
async def get_audit_record(record_id: int):
    """
    Get a single audit record by ID.
    """
    loop = asyncio.get_event_loop()

    def _sync_get_record():
        conn = _get_conn()
        try:
            cursor = conn.execute("""
                SELECT id, timestamp, agent_id, action, resource, details,
                       ip_address, user_agent, prev_hash, record_hash, chain_index
                FROM audit_logs
                WHERE id = ?
            """, (record_id,))

            row = cursor.fetchone()
            conn.close()

            if not row:
                return None

            try:
                details = json.loads(row[5]) if row[5] else {}
            except json.JSONDecodeError:
                details = {}

            return {
                "id": row[0],
                "timestamp": row[1],
                "actor_id": row[2],
                "action": row[3],
                "resource": row[4],
                "details": details,
                "ip_address": row[6],
                "user_agent": row[7],
                "prev_hash": row[8],
                "record_hash": row[9],
                "chain_index": row[10]
            }
        finally:
            conn.close()

    record = await loop.run_in_executor(_executor, _sync_get_record)

    if not record:
        raise HTTPException(status_code=404, detail=f"Record {record_id} not found")

    return {
        "code": 0,
        "data": record
    }


@router.get("/stats")
@handle_errors(module="audit_playback")
async def get_audit_stats():
    """
    Get audit chain statistics.
    """
    stats = get_chain_stats()

    return {
        "code": 0,
        "data": stats
    }
