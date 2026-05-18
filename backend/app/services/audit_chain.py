"""
Audit Chain Service - HMAC-SHA256 Hash Chain for SEC Rule 17a-4 Compliance

This module implements a tamper-evident audit trail using hash chains:
- Every audit record links to the previous record via prev_hash
- HMAC-SHA256 provides cryptographic integrity (survives DBA compromise)
- Chain verification detects any tampering or deletion

SEC Rule 17a-4 Requirements:
- 7-year retention (2555 days)
- Tamper-evident storage
- Chain integrity verification

Author: AlphaTerminal Security Team
Version: 1.0
"""

import hashlib
import hmac
import json
import logging
import os
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

# Genesis hash for the first record in the chain
GENESIS_HASH = "0" * 64

# HMAC key from environment (MUST be set in production)
AUDIT_HMAC_KEY = os.environ.get("AUDIT_HMAC_KEY", "default-key-change-in-production")

# SEC Rule 17a-4: 7-year retention
SEC_RETENTION_DAYS = 2555

# Database path (same as main database)
AUDIT_DB_PATH = Path(__file__).parent.parent.parent.parent / "database.db"


# ── Data Structures ───────────────────────────────────────────────────────────

@dataclass
class AuditChainRecord:
    """Audit record with hash chain fields."""
    id: int
    timestamp: str
    actor_id: str
    action: str
    resource_type: str
    resource_id: str
    outcome: str
    before_state: Optional[Dict[str, Any]]
    after_state: Optional[Dict[str, Any]]
    prev_hash: str
    record_hash: str
    chain_index: int
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


# ── Core Hash Functions ───────────────────────────────────────────────────────

def compute_hash(prev_hash: str, fields: Dict[str, Any]) -> str:
    """
    Compute HMAC-SHA256 of prev_hash + canonicalized fields.
    
    Args:
        prev_hash: Hash of the previous record in the chain
        fields: Dictionary of audit fields to hash
        
    Returns:
        Hexadecimal HMAC-SHA256 digest
    """
    # Canonicalize fields: sort keys, serialize to JSON
    canonical = json.dumps(fields, sort_keys=True, default=str, ensure_ascii=False)
    
    # Concatenate prev_hash + canonical fields
    payload = prev_hash + canonical
    
    # Compute HMAC-SHA256
    return hmac.new(
        AUDIT_HMAC_KEY.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


def get_prev_hash_and_index(conn: sqlite3.Connection) -> Tuple[str, int]:
    """
    Get the previous hash and chain index with row lock.
    
    Uses SELECT ... ORDER BY id DESC LIMIT 1 with row lock
    to ensure atomic chain extension.
    
    Args:
        conn: Database connection (must be in transaction)
        
    Returns:
        Tuple of (prev_hash, chain_index)
    """
    cursor = conn.execute("""
        SELECT record_hash, chain_index 
        FROM audit_logs 
        ORDER BY id DESC 
        LIMIT 1
    """)
    row = cursor.fetchone()
    
    if row is None:
        # First record in chain
        return GENESIS_HASH, 0
    else:
        return row[0], row[1] + 1


# ── Audit Logging with Hash Chain ─────────────────────────────────────────────

def log_audit_event(
    actor_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    outcome: str,
    before_state: Optional[Dict[str, Any]] = None,
    after_state: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> int:
    """
    Insert audit event with hash chain.
    
    This function:
    1. Gets the previous hash with row lock
    2. Computes the new record hash
    3. Inserts the record atomically
    
    Args:
        actor_id: ID of the actor performing the action
        action: Action type (e.g., 'buy', 'sell', 'transfer')
        resource_type: Type of resource (e.g., 'portfolio', 'position')
        resource_id: ID of the resource
        outcome: Result of the action (e.g., 'success', 'failed')
        before_state: State before the action (for audit trail)
        after_state: State after the action (for audit trail)
        ip_address: Client IP address
        user_agent: Client user agent
        conn: Optional external connection for transaction sharing
        
    Returns:
        ID of the inserted audit record
    """
    from app.db.database import _lock
    
    now_str = datetime.now().isoformat()
    external_conn = conn is not None
    
    if conn is None:
        conn = sqlite3.connect(str(AUDIT_DB_PATH))
        conn.row_factory = sqlite3.Row
    
    manage_transaction = not external_conn
    
    try:
        # Begin transaction with row lock
        if manage_transaction:
            conn.execute("BEGIN IMMEDIATE TRANSACTION")
        
        # Get previous hash and chain index
        prev_hash, chain_index = get_prev_hash_and_index(conn)
        
        # Build fields for hashing
        fields = {
            "timestamp": now_str,
            "actor_id": actor_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "outcome": outcome,
            "before_state": before_state,
            "after_state": after_state,
        }
        
        # Compute record hash
        record_hash = compute_hash(prev_hash, fields)
        
        # Insert audit record
        cursor = conn.execute("""
            INSERT INTO audit_logs (
                timestamp, agent_id, action, resource, details,
                ip_address, user_agent, prev_hash, record_hash, chain_index
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            now_str,
            actor_id,
            action,
            f"{resource_type}:{resource_id}",
            json.dumps({
                "resource_type": resource_type,
                "resource_id": resource_id,
                "outcome": outcome,
                "before_state": before_state,
                "after_state": after_state,
            }, default=str, ensure_ascii=False),
            ip_address,
            user_agent,
            prev_hash,
            record_hash,
            chain_index,
        ))
        
        record_id = cursor.lastrowid
        
        if manage_transaction:
            conn.commit()
        
        logger.info(f"[AuditChain] Logged event: id={record_id}, action={action}, chain_index={chain_index}")
        
        return record_id
        
    except Exception as e:
        if manage_transaction:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.error(f"[AuditChain] Failed to log audit event: {e}")
        raise
    finally:
        if not external_conn:
            conn.close()


# ── Chain Verification ────────────────────────────────────────────────────────

def verify_chain(from_id: Optional[int] = None, to_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Verify hash chain integrity.
    
    Checks:
    1. Each record's prev_hash matches the previous record's record_hash
    2. Each record's record_hash can be recomputed from its fields
    3. Chain index is sequential
    
    Args:
        from_id: Start ID for verification (None = from beginning)
        to_id: End ID for verification (None = to end)
        
    Returns:
        Dictionary with verification results:
        - valid: bool - Whether the chain is valid
        - checked_records: int - Number of records checked
        - first_invalid_id: Optional[int] - ID of first invalid record (if any)
        - error_type: Optional[str] - Type of error (if any)
    """
    conn = sqlite3.connect(str(AUDIT_DB_PATH))
    conn.row_factory = sqlite3.Row
    
    try:
        # Build query
        query = """
            SELECT id, timestamp, agent_id, action, resource, details,
                   ip_address, user_agent, prev_hash, record_hash, chain_index
            FROM audit_logs
            WHERE 1=1
        """
        params = []
        
        if from_id is not None:
            query += " AND id >= ?"
            params.append(from_id)
        if to_id is not None:
            query += " AND id <= ?"
            params.append(to_id)
        
        query += " ORDER BY id ASC"
        
        rows = conn.execute(query, params).fetchall()
        
        if not rows:
            return {
                "valid": True,
                "checked_records": 0,
                "first_invalid_id": None,
                "error_type": None,
                "message": "No records to verify"
            }
        
        # Verify chain - check ALL records with hash fields
        pre_chain_count = 0  # Count of records with empty hash fields
        chain_records = []  # Records with hash chain fields
        
        # Separate pre-chain and chain records
        for i, row in enumerate(rows):
            if not row["prev_hash"] and not row["record_hash"]:
                pre_chain_count += 1
            else:
                chain_records.append((i, row))
        
        if not chain_records:
            return {
                "valid": True,
                "checked_records": 0,
                "pre_chain_records": pre_chain_count,
                "first_invalid_id": None,
                "error_type": None,
                "message": "No hash chain records found (all pre-chain)"
            }
        
        # Build a map of record_hash by id for quick lookup
        record_hash_by_id = {rows[i]["id"]: rows[i]["record_hash"] for i, _ in chain_records if rows[i]["record_hash"]}
        
        # Verify each chain record
        for idx, (orig_idx, row) in enumerate(chain_records):
            # For records with non-empty prev_hash, verify it's valid
            if row["prev_hash"]:
                if row["chain_index"] == 0:
                    # Genesis record: prev_hash must be GENESIS_HASH
                    if row["prev_hash"] != GENESIS_HASH:
                        return {
                            "valid": False,
                            "checked_records": idx,
                            "pre_chain_records": pre_chain_count,
                            "first_invalid_id": row["id"],
                            "error_type": "genesis_hash_invalid",
                            "message": f"Record {row['id']}: chain_index=0 but prev_hash is not GENESIS_HASH"
                        }
                else:
                    # Non-genesis record: prev_hash must equal previous record's record_hash
                    # Find the previous record (by chain_index - 1)
                    prev_record = None
                    for prev_idx, prev_row in chain_records:
                        if prev_row["chain_index"] == row["chain_index"] - 1:
                            # Check if this is the immediate predecessor
                            if prev_row["record_hash"]:
                                prev_record = prev_row
                                break
                    
                    if prev_record is None:
                        return {
                            "valid": False,
                            "checked_records": idx,
                            "pre_chain_records": pre_chain_count,
                            "first_invalid_id": row["id"],
                            "error_type": "prev_hash_invalid",
                            "message": f"Record {row['id']}: no valid predecessor found for chain_index={row['chain_index']}"
                        }
                    
                    if row["prev_hash"] != prev_record["record_hash"]:
                        return {
                            "valid": False,
                            "checked_records": idx,
                            "pre_chain_records": pre_chain_count,
                            "first_invalid_id": row["id"],
                            "error_type": "prev_hash_mismatch",
                            "message": f"Record {row['id']}: prev_hash does not match predecessor's record_hash"
                        }
            
            # For records with non-empty prev_hash but empty record_hash, that's also invalid
            if row["prev_hash"] and not row["record_hash"]:
                return {
                    "valid": False,
                    "checked_records": idx,
                    "pre_chain_records": pre_chain_count,
                    "first_invalid_id": row["id"],
                    "error_type": "record_hash_missing",
                    "message": f"Record {row['id']}: has prev_hash but no record_hash"
                }
            
            # Verify the record_hash can be recomputed
            if row["record_hash"]:
                try:
                    details = json.loads(row["details"]) if row["details"] else {}
                except json.JSONDecodeError:
                    return {
                        "valid": False,
                        "checked_records": idx,
                        "pre_chain_records": pre_chain_count,
                        "first_invalid_id": row["id"],
                        "error_type": "invalid_json",
                        "message": f"Record {row['id']}: failed to parse details JSON"
                    }
                
                fields = {
                    "timestamp": row["timestamp"],
                    "actor_id": row["agent_id"],
                    "action": row["action"],
                    "resource_type": details.get("resource_type", ""),
                    "resource_id": details.get("resource_id", ""),
                    "outcome": details.get("outcome", ""),
                    "before_state": details.get("before_state"),
                    "after_state": details.get("after_state"),
                }
                
                computed_hash = compute_hash(row["prev_hash"] or GENESIS_HASH, fields)
                if computed_hash != row["record_hash"]:
                    return {
                        "valid": False,
                        "checked_records": idx,
                        "pre_chain_records": pre_chain_count,
                        "first_invalid_id": row["id"],
                        "error_type": "hash_mismatch",
                        "message": f"Record {row['id']}: computed hash does not match stored hash"
                    }
        
        verified_count = len(chain_records)
        return {
            "valid": True,
            "checked_records": verified_count,
            "pre_chain_records": pre_chain_count,
            "first_invalid_id": None,
            "error_type": None,
            "message": f"Chain integrity verified successfully ({verified_count} records, {pre_chain_count} pre-chain skipped)"
        }
        
    except Exception as e:
        logger.error(f"[AuditChain] Verification failed: {e}")
        return {
            "valid": False,
            "checked_records": 0,
            "first_invalid_id": None,
            "error_type": "exception",
            "message": str(e)
        }
    finally:
        conn.close()


def get_chain_stats() -> Dict[str, Any]:
    """
    Get statistics about the audit chain.
    
    Returns:
        Dictionary with chain statistics
    """
    conn = sqlite3.connect(str(AUDIT_DB_PATH))
    conn.row_factory = sqlite3.Row
    
    try:
        # Total records
        total = conn.execute("SELECT COUNT(*) as cnt FROM audit_logs").fetchone()["cnt"]
        
        # Chain index range
        index_range = conn.execute("""
            SELECT MIN(chain_index) as min_idx, MAX(chain_index) as max_idx
            FROM audit_logs
        """).fetchone()
        
        # First and last record
        first = conn.execute("""
            SELECT id, timestamp, prev_hash, record_hash, chain_index
            FROM audit_logs
            ORDER BY id ASC
            LIMIT 1
        """).fetchone()
        
        last = conn.execute("""
            SELECT id, timestamp, prev_hash, record_hash, chain_index
            FROM audit_logs
            ORDER BY id DESC
            LIMIT 1
        """).fetchone()
        
        return {
            "total_records": total,
            "chain_index_min": index_range["min_idx"] if index_range else None,
            "chain_index_max": index_range["max_idx"] if index_range else None,
            "first_record": dict(first) if first else None,
            "last_record": dict(last) if last else None,
            "genesis_hash": GENESIS_HASH,
            "retention_days": SEC_RETENTION_DAYS,
        }
    finally:
        conn.close()


# ── Convenience Functions for Trading Operations ──────────────────────────────

def log_buy(
    portfolio_id: int,
    symbol: str,
    shares: int,
    price: float,
    actor_id: str = "system",
    order_id: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> int:
    """
    Log a buy transaction with hash chain.
    
    Args:
        portfolio_id: Portfolio ID
        symbol: Stock symbol
        shares: Number of shares
        price: Buy price
        actor_id: Actor performing the buy
        order_id: Optional order ID
        ip_address: Client IP address
        
    Returns:
        Audit record ID
    """
    return log_audit_event(
        actor_id=actor_id,
        action="buy",
        resource_type="position_lot",
        resource_id=f"{portfolio_id}:{symbol}",
        outcome="success",
        before_state=None,
        after_state={
            "portfolio_id": portfolio_id,
            "symbol": symbol,
            "shares": shares,
            "price": price,
            "order_id": order_id,
        },
        ip_address=ip_address,
    )


def log_sell(
    portfolio_id: int,
    symbol: str,
    shares: int,
    price: float,
    realized_pnl: float,
    actor_id: str = "system",
    order_id: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> int:
    """
    Log a sell transaction with hash chain.
    
    Args:
        portfolio_id: Portfolio ID
        symbol: Stock symbol
        shares: Number of shares sold
        price: Sell price
        realized_pnl: Realized profit/loss
        actor_id: Actor performing the sell
        order_id: Optional order ID
        ip_address: Client IP address
        
    Returns:
        Audit record ID
    """
    return log_audit_event(
        actor_id=actor_id,
        action="sell",
        resource_type="position_lot",
        resource_id=f"{portfolio_id}:{symbol}",
        outcome="success",
        before_state=None,
        after_state={
            "portfolio_id": portfolio_id,
            "symbol": symbol,
            "shares": shares,
            "price": price,
            "realized_pnl": realized_pnl,
            "order_id": order_id,
        },
        ip_address=ip_address,
    )


def log_cash_operation(
    portfolio_id: int,
    operation: str,
    amount: float,
    balance_after: float,
    actor_id: str = "system",
    ip_address: Optional[str] = None,
) -> int:
    """
    Log a cash operation with hash chain.
    
    Args:
        portfolio_id: Portfolio ID
        operation: Operation type (deposit, withdraw, transfer_in, transfer_out)
        amount: Amount of cash
        balance_after: Balance after operation
        actor_id: Actor performing the operation
        ip_address: Client IP address
        
    Returns:
        Audit record ID
    """
    return log_audit_event(
        actor_id=actor_id,
        action=operation,
        resource_type="cash",
        resource_id=str(portfolio_id),
        outcome="success",
        before_state=None,
        after_state={
            "portfolio_id": portfolio_id,
            "amount": amount,
            "balance_after": balance_after,
        },
        ip_address=ip_address,
    )


# ── Module Test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 80)
    print("Audit Chain Service Test")
    print("=" * 80)
    
    # Test hash computation
    print("\n1. Test hash computation:")
    test_fields = {
        "timestamp": "2024-01-01T00:00:00",
        "actor_id": "test_user",
        "action": "buy",
        "resource_type": "position",
        "resource_id": "1:600519",
        "outcome": "success",
    }
    hash1 = compute_hash(GENESIS_HASH, test_fields)
    print(f"   Hash: {hash1}")
    print(f"   Length: {len(hash1)}")
    
    # Test chain verification
    print("\n2. Test chain verification:")
    result = verify_chain()
    print(f"   Valid: {result['valid']}")
    print(f"   Checked records: {result['checked_records']}")
    
    # Test chain stats
    print("\n3. Test chain stats:")
    stats = get_chain_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    print("\n" + "=" * 80)
    print("Audit chain test completed!")
