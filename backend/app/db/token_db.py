"""
Token Database Service - Agent Token CRUD operations with SQLite persistence

Tables:
- agent_tokens: id, name, token_hash, token_prefix, scopes, markets, instruments, paper_only, rate_limit, expires_at, created_at, last_used_at, is_active, access_count, revoked_at
"""

import json
import logging
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

from app.db.database import _get_conn, _lock


def init_token_table():
    """Initialize agent_tokens table (called from database.py init_tables)"""
    with _lock:
        conn = _get_conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_tokens (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    token_hash TEXT UNIQUE NOT NULL,
                    token_prefix TEXT NOT NULL,
                    scopes TEXT NOT NULL,
                    markets TEXT DEFAULT '*',
                    instruments TEXT DEFAULT '*',
                    paper_only INTEGER DEFAULT 1,
                    rate_limit INTEGER DEFAULT 120,
                    expires_at TEXT,
                    created_at TEXT NOT NULL,
                    last_used_at TEXT,
                    is_active INTEGER DEFAULT 1,
                    access_count INTEGER DEFAULT 0,
                    revoked_at TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_token_hash ON agent_tokens(token_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_token_name ON agent_tokens(name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_token_active ON agent_tokens(is_active)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_token_expires ON agent_tokens(expires_at)")
            conn.commit()
        finally:
            conn.close()


def create_token(
    token_id: str,
    name: str,
    token_hash: str,
    token_prefix: str,
    scopes: List[str],
    markets: List[str] = None,
    instruments: List[str] = None,
    paper_only: bool = True,
    rate_limit: int = 120,
    expires_at: Optional[datetime] = None,
) -> Dict:
    """
    Create a new agent token
    
    Returns:
        Created token dict
    """
    now = datetime.now().isoformat()
    scopes_str = ",".join(scopes)
    markets_str = ",".join(markets) if markets and markets != ["*"] else "*"
    instruments_str = ",".join(instruments) if instruments and instruments != ["*"] else "*"
    
    with _lock:
        conn = _get_conn()
        try:
            conn.execute("""
                INSERT INTO agent_tokens
                (id, name, token_hash, token_prefix, scopes, markets, instruments, paper_only, rate_limit, expires_at, created_at, is_active, access_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                token_id,
                name,
                token_hash,
                token_prefix,
                scopes_str,
                markets_str,
                instruments_str,
                int(paper_only),
                rate_limit,
                expires_at.isoformat() if expires_at else None,
                now,
                1,
                0,
            ))
            conn.commit()
            
            return {
                "id": token_id,
                "name": name,
                "token_hash": token_hash,
                "token_prefix": token_prefix,
                "scopes": scopes,
                "markets": markets or ["*"],
                "instruments": instruments or ["*"],
                "paper_only": paper_only,
                "rate_limit": rate_limit,
                "expires_at": expires_at.isoformat() if expires_at else None,
                "created_at": now,
                "last_used_at": None,
                "is_active": True,
                "access_count": 0,
                "revoked_at": None,
            }
        except sqlite3.IntegrityError:
            logger.error(f"[TokenDB] Create failed - duplicate token_hash", exc_info=True)
            raise ValueError("Token with this hash already exists")
        except Exception as e:
            logger.error(f"[TokenDB] Create failed: {e}", exc_info=True)
            raise
        finally:
            conn.close()


def get_token_by_hash(token_hash: str) -> Optional[Dict]:
    """Get token by hash (for verification)"""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM agent_tokens WHERE token_hash = ?",
            (token_hash,)
        ).fetchone()
        
        if row is None:
            return None
        
        return _row_to_dict(row)
    except Exception as e:
        logger.error(f"[TokenDB] Get by hash failed: {e}", exc_info=True)
        return None
    finally:
        conn.close()


def get_token_by_id(token_id: str) -> Optional[Dict]:
    """Get token by ID"""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM agent_tokens WHERE id = ?",
            (token_id,)
        ).fetchone()
        
        if row is None:
            return None
        
        return _row_to_dict(row)
    except Exception as e:
        logger.error(f"[TokenDB] Get by id failed: {e}", exc_info=True)
        return None
    finally:
        conn.close()


def list_tokens(include_inactive: bool = False) -> List[Dict]:
    """List all tokens"""
    conn = _get_conn()
    try:
        if include_inactive:
            rows = conn.execute("SELECT * FROM agent_tokens ORDER BY created_at DESC").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM agent_tokens WHERE is_active = 1 ORDER BY created_at DESC"
            ).fetchall()
        
        return [_row_to_dict(row) for row in rows]
    except Exception as e:
        logger.error(f"[TokenDB] List failed: {e}", exc_info=True)
        return []
    finally:
        conn.close()


def update_token_usage(token_hash: str) -> bool:
    """Update token last_used_at and access_count"""
    with _lock:
        conn = _get_conn()
        try:
            now = datetime.now().isoformat()
            cursor = conn.execute("""
                UPDATE agent_tokens 
                SET last_used_at = ?, access_count = access_count + 1
                WHERE token_hash = ?
            """, (now, token_hash))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"[TokenDB] Update usage failed: {e}", exc_info=True)
            return False
        finally:
            conn.close()


def revoke_token(token_id: str) -> bool:
    """Revoke a token (soft delete)"""
    with _lock:
        conn = _get_conn()
        try:
            now = datetime.now().isoformat()
            cursor = conn.execute("""
                UPDATE agent_tokens 
                SET is_active = 0, revoked_at = ?
                WHERE id = ?
            """, (now, token_id))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"[TokenDB] Revoke failed: {e}", exc_info=True)
            return False
        finally:
            conn.close()


def delete_expired_tokens() -> int:
    """Delete expired tokens (cleanup job)"""
    with _lock:
        conn = _get_conn()
        try:
            now = datetime.now().isoformat()
            cursor = conn.execute(
                "DELETE FROM agent_tokens WHERE expires_at IS NOT NULL AND expires_at <= ?",
                (now,)
            )
            conn.commit()
            deleted = cursor.rowcount
            if deleted > 0:
                logger.info(f"[TokenDB] Deleted {deleted} expired tokens")
            return deleted
        except Exception as e:
            logger.error(f"[TokenDB] Delete expired failed: {e}", exc_info=True)
            return 0
        finally:
            conn.close()


def get_expiring_tokens(days: int = 7) -> List[Dict]:
    """Get tokens expiring within N days"""
    conn = _get_conn()
    try:
        cutoff = datetime.now()
        from datetime import timedelta
        cutoff_str = (cutoff + timedelta(days=days)).isoformat()
        
        rows = conn.execute("""
            SELECT * FROM agent_tokens 
            WHERE is_active = 1 
            AND expires_at IS NOT NULL 
            AND expires_at <= ?
            ORDER BY expires_at ASC
        """, (cutoff_str,)).fetchall()
        
        return [_row_to_dict(row) for row in rows]
    except Exception as e:
        logger.error(f"[TokenDB] Get expiring failed: {e}", exc_info=True)
        return []
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> Dict:
    """Convert sqlite3.Row to dict with list parsing"""
    result = dict(row)
    
    result["scopes"] = result["scopes"].split(",") if result.get("scopes") else []
    
    if result.get("markets") and result["markets"] != "*":
        result["markets"] = result["markets"].split(",")
    else:
        result["markets"] = ["*"]
    
    if result.get("instruments") and result["instruments"] != "*":
        result["instruments"] = result["instruments"].split(",")
    else:
        result["instruments"] = ["*"]
    
    result["paper_only"] = bool(result.get("paper_only", 1))
    result["is_active"] = bool(result.get("is_active", 1))
    
    return result
