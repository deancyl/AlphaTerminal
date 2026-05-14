"""
Agent Token Database Service - Comprehensive debug logging for 20 debug cycles.

This module provides a unified database layer for agent token management with:
- SQLite database schema for agent_tokens and agent_audit_logs tables
- CRUD operations with comprehensive debug logging
- Database indexes for performance optimization
- Thread-safe operations with proper connection management

Tables:
- agent_tokens: Persistent token storage with all token attributes
- agent_audit_logs: Audit trail for all token operations

Author: AlphaTerminal Team
Version: 0.6.12
"""

import json
import logging
import os
import sqlite3
import threading
import traceback
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

# Configure comprehensive logging
logger = logging.getLogger(__name__)

# Debug mode flag - set via environment variable for 20 debug cycles
DEBUG_MODE = os.getenv("AGENT_DB_DEBUG", "false").lower() == "true"

if DEBUG_MODE:
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

# Database configuration
DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "cache",
    "agent_tokens.db"
)

# Thread-local storage for connections
_thread_local = threading.local()
_lock = threading.RLock()

# WAL mode configuration
_WAL_MODE_CHECKED = False
_USE_WAL = True


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class AgentToken:
    """Agent token data class with all attributes."""
    id: str
    name: str
    token_hash: str
    token_prefix: str
    scopes: List[str]
    markets: List[str] = field(default_factory=lambda: ["*"])
    instruments: List[str] = field(default_factory=lambda: ["*"])
    paper_only: bool = True
    rate_limit: int = 120
    rate_limit_window_start: Optional[str] = None
    request_count: int = 0
    expires_at: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_used_at: Optional[str] = None
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentToken":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class AuditLog:
    """Audit log entry data class."""
    id: Optional[int] = None
    token_id: str = ""
    action: str = ""
    resource: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    ip_address: str = ""
    user_agent: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


# ============================================================================
# Database Connection Management
# ============================================================================

def _ensure_db_directory():
    """Ensure database directory exists."""
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        logger.info(f"[AGENT_DB] Creating database directory: {db_dir}")
        os.makedirs(db_dir, exist_ok=True)
        logger.debug(f"[AGENT_DB] Database directory created successfully")


def _get_thread_conn() -> sqlite3.Connection:
    """
    Get thread-local database connection.
    
    Creates a new connection per thread for thread safety.
    Uses WAL mode for better concurrency.
    """
    global _WAL_MODE_CHECKED, _USE_WAL
    
    logger.debug(f"[AGENT_DB_CONN] Getting connection for thread: {threading.current_thread().name}")
    
    if not hasattr(_thread_local, 'conn') or _thread_local.conn is None:
        logger.info(f"[AGENT_DB_CONN] Creating new connection for thread: {threading.current_thread().name}")
        
        _ensure_db_directory()
        
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        
        logger.debug(f"[AGENT_DB_CONN] Connected to database: {DB_PATH}")
        
        # WAL mode detection (only once)
        if not _WAL_MODE_CHECKED:
            logger.debug("[AGENT_DB_CONN] Checking WAL mode compatibility")
            if "/vol3/" in DB_PATH or "/tmp/" in DB_PATH or "/nas/" in DB_PATH:
                _USE_WAL = False
                logger.debug("[AGENT_DB_CONN] Network path detected, disabling WAL mode")
            else:
                try:
                    cur = conn.execute("PRAGMA journal_mode=WAL")
                    result = cur.fetchone()[0]
                    if result != "wal":
                        _USE_WAL = False
                        logger.debug(f"[AGENT_DB_CONN] WAL mode not available, got: {result}")
                    else:
                        logger.debug("[AGENT_DB_CONN] WAL mode enabled successfully")
                except sqlite3.OperationalError as e:
                    _USE_WAL = False
                    logger.debug(f"[AGENT_DB_CONN] WAL mode check failed: {e}")
            _WAL_MODE_CHECKED = True
        
        # Set journal mode
        if _USE_WAL:
            conn.execute("PRAGMA journal_mode=WAL")
            logger.debug("[AGENT_DB_CONN] Set journal mode to WAL")
        else:
            conn.execute("PRAGMA journal_mode=DELETE")
            logger.debug("[AGENT_DB_CONN] Set journal mode to DELETE")
        
        # Set busy timeout
        conn.execute("PRAGMA busy_timeout=30000")
        logger.debug("[AGENT_DB_CONN] Set busy timeout to 30000ms")
        
        _thread_local.conn = conn
        logger.info(f"[AGENT_DB_CONN] Connection created successfully for thread: {threading.current_thread().name}")
    
    return _thread_local.conn


def _close_thread_conn():
    """Close thread-local connection."""
    logger.debug(f"[AGENT_DB_CONN_CLOSE] Closing connection for thread: {threading.current_thread().name}")
    
    if hasattr(_thread_local, 'conn') and _thread_local.conn:
        try:
            _thread_local.conn.close()
            logger.info(f"[AGENT_DB_CONN_CLOSE] Connection closed for thread: {threading.current_thread().name}")
        except Exception as e:
            logger.error(f"[AGENT_DB_CONN_CLOSE] Failed to close connection: {e}\n{traceback.format_exc()}")
        finally:
            _thread_local.conn = None


@contextmanager
def get_conn():
    """Context manager for database connection."""
    logger.debug("[AGENT_DB_CTX] Entering connection context")
    conn = _get_thread_conn()
    try:
        yield conn
        logger.debug("[AGENT_DB_CTX] Connection context completed successfully")
    except Exception as e:
        logger.error(f"[AGENT_DB_CTX] Exception in connection context: {e}\n{traceback.format_exc()}")
        try:
            conn.rollback()
            logger.debug("[AGENT_DB_CTX] Transaction rolled back")
        except Exception:
            pass
        raise


# ============================================================================
# AgentDB Class
# ============================================================================

class AgentDB:
    """
    Agent Token Database Manager.
    
    Provides comprehensive CRUD operations for agent tokens with:
    - Thread-safe operations
    - Comprehensive debug logging
    - Performance-optimized indexes
    - Audit trail support
    """
    
    _instance = None
    _init_lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern for database manager."""
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    logger.info("[AGENT_DB_NEW] Creating new AgentDB instance")
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize database manager."""
        if hasattr(self, '_initialized') and self._initialized:
            logger.debug("[AGENT_DB_INIT] Already initialized, skipping")
            return
        
        logger.info("[AGENT_DB_INIT] Initializing AgentDB")
        logger.debug(f"[AGENT_DB_INIT] Database path: {DB_PATH}")
        logger.debug(f"[AGENT_DB_INIT] Debug mode: {DEBUG_MODE}")
        logger.debug(f"[AGENT_DB_INIT] WAL mode: {_USE_WAL}")
        
        self._initialized = True
        self.init_db()
        
        logger.info("[AGENT_DB_INIT] AgentDB initialized successfully")
    
    @classmethod
    def get_instance(cls) -> "AgentDB":
        """Get singleton instance."""
        logger.debug("[AGENT_DB_GET] Getting AgentDB instance")
        return cls()
    
    def init_db(self) -> bool:
        """
        Initialize database tables and indexes.
        
        Creates:
        - agent_tokens table with all required columns
        - agent_audit_logs table for audit trail
        - Performance indexes on key columns
        
        Returns:
            True if initialization successful, False otherwise
        """
        logger.info("[AGENT_DB_INIT_DB] Starting database initialization")
        
        with _lock:
            conn = _get_thread_conn()
            
            try:
                # Create agent_tokens table
                logger.debug("[AGENT_DB_INIT_DB] Creating agent_tokens table")
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
                        rate_limit_window_start TEXT,
                        request_count INTEGER DEFAULT 0,
                        expires_at TEXT,
                        created_at TEXT NOT NULL,
                        last_used_at TEXT,
                        is_active INTEGER DEFAULT 1
                    )
                """)
                logger.debug("[AGENT_DB_INIT_DB] agent_tokens table created")
                
                # Create agent_audit_logs table
                logger.debug("[AGENT_DB_INIT_DB] Creating agent_audit_logs table")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS agent_audit_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        token_id TEXT NOT NULL,
                        action TEXT NOT NULL,
                        resource TEXT,
                        details TEXT,
                        ip_address TEXT,
                        user_agent TEXT,
                        timestamp TEXT NOT NULL
                    )
                """)
                logger.debug("[AGENT_DB_INIT_DB] agent_audit_logs table created")
                
                # Create indexes for agent_tokens
                logger.debug("[AGENT_DB_INIT_DB] Creating indexes for agent_tokens")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_token_hash ON agent_tokens(token_hash)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_token_id ON agent_tokens(id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_token_expires ON agent_tokens(expires_at)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_token_active ON agent_tokens(is_active)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_token_name ON agent_tokens(name)")
                logger.debug("[AGENT_DB_INIT_DB] agent_tokens indexes created")
                
                # Create indexes for agent_audit_logs
                logger.debug("[AGENT_DB_INIT_DB] Creating indexes for agent_audit_logs")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_token_id ON agent_audit_logs(token_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON agent_audit_logs(action)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON agent_audit_logs(timestamp)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_resource ON agent_audit_logs(resource)")
                logger.debug("[AGENT_DB_INIT_DB] agent_audit_logs indexes created")
                
                conn.commit()
                logger.info("[AGENT_DB_INIT_DB] Database initialization completed successfully")
                return True
                
            except Exception as e:
                logger.error(f"[AGENT_DB_INIT_DB] Database initialization failed: {e}\n{traceback.format_exc()}")
                return False
    
    def save_token(self, token: AgentToken) -> bool:
        """
        Save a new token to the database.
        
        Args:
            token: AgentToken object to save
            
        Returns:
            True if saved successfully, False otherwise
        """
        logger.info(f"[AGENT_DB_SAVE] Saving token: id={token.id}, name={token.name}")
        logger.debug(f"[AGENT_DB_SAVE] Token details: hash={token.token_hash[:16]}***, prefix={token.token_prefix}")
        logger.debug(f"[AGENT_DB_SAVE] Token attributes: scopes={token.scopes}, markets={token.markets}, paper_only={token.paper_only}")
        
        with _lock:
            conn = _get_thread_conn()
            
            try:
                # Serialize list fields
                scopes_str = ",".join(token.scopes) if token.scopes else ""
                markets_str = ",".join(token.markets) if token.markets and token.markets != ["*"] else "*"
                instruments_str = ",".join(token.instruments) if token.instruments and token.instruments != ["*"] else "*"
                
                logger.debug(f"[AGENT_DB_SAVE] Serialized fields: scopes='{scopes_str}', markets='{markets_str}', instruments='{instruments_str}'")
                
                # SQL query with parameters
                sql = """
                    INSERT INTO agent_tokens
                    (id, name, token_hash, token_prefix, scopes, markets, instruments, 
                     paper_only, rate_limit, rate_limit_window_start, request_count, 
                     expires_at, created_at, last_used_at, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                params = (
                    token.id,
                    token.name,
                    token.token_hash,
                    token.token_prefix,
                    scopes_str,
                    markets_str,
                    instruments_str,
                    int(token.paper_only),
                    token.rate_limit,
                    token.rate_limit_window_start,
                    token.request_count,
                    token.expires_at,
                    token.created_at,
                    token.last_used_at,
                    int(token.is_active),
                )
                
                logger.debug(f"[AGENT_DB_SAVE] Executing SQL: {sql.strip()}")
                logger.debug(f"[AGENT_DB_SAVE] Parameters: {params}")
                
                conn.execute(sql, params)
                conn.commit()
                
                logger.info(f"[AGENT_DB_SAVE] Token saved successfully: id={token.id}")
                return True
                
            except sqlite3.IntegrityError as e:
                logger.error(f"[AGENT_DB_SAVE] Integrity error (duplicate token): {e}\n{traceback.format_exc()}")
                return False
            except Exception as e:
                logger.error(f"[AGENT_DB_SAVE] Failed to save token: {e}\n{traceback.format_exc()}")
                return False
    
    def get_token_by_hash(self, token_hash: str) -> Optional[AgentToken]:
        """
        Get token by hash.
        
        Args:
            token_hash: Token hash to search for
            
        Returns:
            AgentToken if found, None otherwise
        """
        logger.info(f"[AGENT_DB_GET_HASH] Getting token by hash: {token_hash[:16]}***")
        logger.debug(f"[AGENT_DB_GET_HASH] Full hash: {token_hash}")
        
        conn = _get_thread_conn()
        
        try:
            sql = "SELECT * FROM agent_tokens WHERE token_hash = ?"
            logger.debug(f"[AGENT_DB_GET_HASH] Executing SQL: {sql}")
            logger.debug(f"[AGENT_DB_GET_HASH] Parameter: {token_hash[:16]}***")
            
            row = conn.execute(sql, (token_hash,)).fetchone()
            
            if row is None:
                logger.warning(f"[AGENT_DB_GET_HASH] Token not found: {token_hash[:16]}***")
                return None
            
            logger.debug(f"[AGENT_DB_GET_HASH] Token found: id={row['id']}, name={row['name']}")
            token = self._row_to_token(row)
            logger.info(f"[AGENT_DB_GET_HASH] Retrieved token successfully: id={token.id}")
            return token
            
        except Exception as e:
            logger.error(f"[AGENT_DB_GET_HASH] Failed to get token: {e}\n{traceback.format_exc()}")
            return None
    
    def get_token_by_id(self, token_id: str) -> Optional[AgentToken]:
        """
        Get token by ID.
        
        Args:
            token_id: Token ID to search for
            
        Returns:
            AgentToken if found, None otherwise
        """
        logger.info(f"[AGENT_DB_GET_ID] Getting token by ID: {token_id}")
        
        conn = _get_thread_conn()
        
        try:
            sql = "SELECT * FROM agent_tokens WHERE id = ?"
            logger.debug(f"[AGENT_DB_GET_ID] Executing SQL: {sql}")
            logger.debug(f"[AGENT_DB_GET_ID] Parameter: {token_id}")
            
            row = conn.execute(sql, (token_id,)).fetchone()
            
            if row is None:
                logger.warning(f"[AGENT_DB_GET_ID] Token not found: {token_id}")
                return None
            
            logger.debug(f"[AGENT_DB_GET_ID] Token found: name={row['name']}, prefix={row['token_prefix']}")
            token = self._row_to_token(row)
            logger.info(f"[AGENT_DB_GET_ID] Retrieved token successfully: id={token.id}")
            return token
            
        except Exception as e:
            logger.error(f"[AGENT_DB_GET_ID] Failed to get token: {e}\n{traceback.format_exc()}")
            return None
    
    def list_tokens(self, active_only: bool = True) -> List[AgentToken]:
        """
        List all tokens.
        
        Args:
            active_only: If True, only return active tokens
            
        Returns:
            List of AgentToken objects
        """
        logger.info(f"[AGENT_DB_LIST] Listing tokens: active_only={active_only}")
        
        conn = _get_thread_conn()
        
        try:
            if active_only:
                sql = "SELECT * FROM agent_tokens WHERE is_active = 1 ORDER BY created_at DESC"
                logger.debug(f"[AGENT_DB_LIST] Executing SQL: {sql}")
            else:
                sql = "SELECT * FROM agent_tokens ORDER BY created_at DESC"
                logger.debug(f"[AGENT_DB_LIST] Executing SQL: {sql}")
            
            rows = conn.execute(sql).fetchall()
            logger.debug(f"[AGENT_DB_LIST] Found {len(rows)} tokens")
            
            tokens = []
            for row in rows:
                try:
                    token = self._row_to_token(row)
                    tokens.append(token)
                    logger.debug(f"[AGENT_DB_LIST] Parsed token: id={token.id}, name={token.name}")
                except Exception as e:
                    logger.error(f"[AGENT_DB_LIST] Failed to parse token row: {e}\n{traceback.format_exc()}")
            
            logger.info(f"[AGENT_DB_LIST] Listed {len(tokens)} tokens successfully")
            return tokens
            
        except Exception as e:
            logger.error(f"[AGENT_DB_LIST] Failed to list tokens: {e}\n{traceback.format_exc()}")
            return []
    
    def update_token(self, token: AgentToken) -> bool:
        """
        Update an existing token.
        
        Args:
            token: AgentToken object with updated values
            
        Returns:
            True if updated successfully, False otherwise
        """
        logger.info(f"[AGENT_DB_UPDATE] Updating token: id={token.id}, name={token.name}")
        logger.debug(f"[AGENT_DB_UPDATE] Token details: is_active={token.is_active}, last_used_at={token.last_used_at}")
        
        with _lock:
            conn = _get_thread_conn()
            
            try:
                # Serialize list fields
                scopes_str = ",".join(token.scopes) if token.scopes else ""
                markets_str = ",".join(token.markets) if token.markets and token.markets != ["*"] else "*"
                instruments_str = ",".join(token.instruments) if token.instruments and token.instruments != ["*"] else "*"
                
                sql = """
                    UPDATE agent_tokens SET
                        name = ?, scopes = ?, markets = ?, instruments = ?,
                        paper_only = ?, rate_limit = ?, rate_limit_window_start = ?,
                        request_count = ?, expires_at = ?, last_used_at = ?, is_active = ?
                    WHERE id = ?
                """
                params = (
                    token.name,
                    scopes_str,
                    markets_str,
                    instruments_str,
                    int(token.paper_only),
                    token.rate_limit,
                    token.rate_limit_window_start,
                    token.request_count,
                    token.expires_at,
                    token.last_used_at,
                    int(token.is_active),
                    token.id,
                )
                
                logger.debug(f"[AGENT_DB_UPDATE] Executing SQL: {sql.strip()}")
                logger.debug(f"[AGENT_DB_UPDATE] Parameters: {params}")
                
                cursor = conn.execute(sql, params)
                conn.commit()
                
                updated = cursor.rowcount > 0
                if updated:
                    logger.info(f"[AGENT_DB_UPDATE] Token updated successfully: id={token.id}")
                else:
                    logger.warning(f"[AGENT_DB_UPDATE] Token not found for update: id={token.id}")
                
                return updated
                
            except Exception as e:
                logger.error(f"[AGENT_DB_UPDATE] Failed to update token: {e}\n{traceback.format_exc()}")
                return False
    
    def revoke_token(self, token_id: str) -> bool:
        """
        Revoke a token (soft delete).
        
        Args:
            token_id: Token ID to revoke
            
        Returns:
            True if revoked successfully, False otherwise
        """
        logger.info(f"[AGENT_DB_REVOKE] Revoking token: id={token_id}")
        
        with _lock:
            conn = _get_thread_conn()
            
            try:
                now = datetime.now().isoformat()
                
                sql = "UPDATE agent_tokens SET is_active = 0, last_used_at = ? WHERE id = ?"
                logger.debug(f"[AGENT_DB_REVOKE] Executing SQL: {sql}")
                logger.debug(f"[AGENT_DB_REVOKE] Parameters: last_used_at={now}, id={token_id}")
                
                cursor = conn.execute(sql, (now, token_id))
                conn.commit()
                
                revoked = cursor.rowcount > 0
                if revoked:
                    logger.info(f"[AGENT_DB_REVOKE] Token revoked successfully: id={token_id}")
                else:
                    logger.warning(f"[AGENT_DB_REVOKE] Token not found for revocation: id={token_id}")
                
                return revoked
                
            except Exception as e:
                logger.error(f"[AGENT_DB_REVOKE] Failed to revoke token: {e}\n{traceback.format_exc()}")
                return False
    
    def log_audit(
        self,
        token_id: str,
        action: str,
        resource: str = "",
        details: Optional[Dict[str, Any]] = None,
        ip_address: str = "",
        user_agent: str = ""
    ) -> bool:
        """
        Log an audit event.
        
        Args:
            token_id: Token ID performing the action
            action: Action type (e.g., 'create', 'verify', 'revoke')
            resource: Resource being accessed
            details: Additional details as dict
            ip_address: Client IP address
            user_agent: Client user agent
            
        Returns:
            True if logged successfully, False otherwise
        """
        logger.info(f"[AGENT_DB_AUDIT] Logging audit: token_id={token_id}, action={action}")
        logger.debug(f"[AGENT_DB_AUDIT] Audit details: resource={resource}, ip={ip_address}")
        logger.debug(f"[AGENT_DB_AUDIT] Details: {details}")
        
        with _lock:
            conn = _get_thread_conn()
            
            try:
                now = datetime.now().isoformat()
                details_str = json.dumps(details, ensure_ascii=False) if details else None
                
                sql = """
                    INSERT INTO agent_audit_logs
                    (token_id, action, resource, details, ip_address, user_agent, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """
                params = (token_id, action, resource, details_str, ip_address, user_agent, now)
                
                logger.debug(f"[AGENT_DB_AUDIT] Executing SQL: {sql.strip()}")
                logger.debug(f"[AGENT_DB_AUDIT] Parameters: {params}")
                
                conn.execute(sql, params)
                conn.commit()
                
                logger.info(f"[AGENT_DB_AUDIT] Audit logged successfully: token_id={token_id}, action={action}")
                return True
                
            except Exception as e:
                logger.error(f"[AGENT_DB_AUDIT] Failed to log audit: {e}\n{traceback.format_exc()}")
                return False
    
    def get_audit_logs(
        self,
        token_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditLog]:
        """
        Get audit logs with optional filters.
        
        Args:
            token_id: Filter by token ID
            action: Filter by action type
            limit: Maximum number of results
            offset: Offset for pagination
            
        Returns:
            List of AuditLog objects
        """
        logger.info(f"[AGENT_DB_AUDIT_GET] Getting audit logs: token_id={token_id}, action={action}, limit={limit}")
        
        conn = _get_thread_conn()
        
        try:
            conditions = []
            params = []
            
            if token_id:
                conditions.append("token_id = ?")
                params.append(token_id)
                logger.debug(f"[AGENT_DB_AUDIT_GET] Filter: token_id={token_id}")
            
            if action:
                conditions.append("action = ?")
                params.append(action)
                logger.debug(f"[AGENT_DB_AUDIT_GET] Filter: action={action}")
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            sql = f"""
                SELECT * FROM agent_audit_logs
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])
            
            logger.debug(f"[AGENT_DB_AUDIT_GET] Executing SQL: {sql.strip()}")
            logger.debug(f"[AGENT_DB_AUDIT_GET] Parameters: {params}")
            
            rows = conn.execute(sql, params).fetchall()
            logger.debug(f"[AGENT_DB_AUDIT_GET] Found {len(rows)} audit logs")
            
            logs = []
            for row in rows:
                try:
                    log = self._row_to_audit_log(row)
                    logs.append(log)
                    logger.debug(f"[AGENT_DB_AUDIT_GET] Parsed audit log: id={log.id}, action={log.action}")
                except Exception as e:
                    logger.error(f"[AGENT_DB_AUDIT_GET] Failed to parse audit log row: {e}\n{traceback.format_exc()}")
            
            logger.info(f"[AGENT_DB_AUDIT_GET] Retrieved {len(logs)} audit logs successfully")
            return logs
            
        except Exception as e:
            logger.error(f"[AGENT_DB_AUDIT_GET] Failed to get audit logs: {e}\n{traceback.format_exc()}")
            return []
    
    def delete_expired_tokens(self) -> int:
        """
        Delete expired tokens from database.
        
        Returns:
            Number of tokens deleted
        """
        logger.info("[AGENT_DB_CLEANUP] Deleting expired tokens")
        
        with _lock:
            conn = _get_thread_conn()
            
            try:
                now = datetime.now().isoformat()
                
                sql = "DELETE FROM agent_tokens WHERE expires_at IS NOT NULL AND expires_at <= ?"
                logger.debug(f"[AGENT_DB_CLEANUP] Executing SQL: {sql}")
                logger.debug(f"[AGENT_DB_CLEANUP] Parameter: {now}")
                
                cursor = conn.execute(sql, (now,))
                conn.commit()
                
                deleted = cursor.rowcount
                logger.info(f"[AGENT_DB_CLEANUP] Deleted {deleted} expired tokens")
                return deleted
                
            except Exception as e:
                logger.error(f"[AGENT_DB_CLEANUP] Failed to delete expired tokens: {e}\n{traceback.format_exc()}")
                return 0
    
    def get_token_count(self, active_only: bool = True) -> int:
        """
        Get total token count.
        
        Args:
            active_only: If True, only count active tokens
            
        Returns:
            Number of tokens
        """
        logger.debug(f"[AGENT_DB_COUNT] Getting token count: active_only={active_only}")
        
        conn = _get_thread_conn()
        
        try:
            if active_only:
                sql = "SELECT COUNT(*) as cnt FROM agent_tokens WHERE is_active = 1"
            else:
                sql = "SELECT COUNT(*) as cnt FROM agent_tokens"
            
            row = conn.execute(sql).fetchone()
            count = row["cnt"] if row else 0
            
            logger.debug(f"[AGENT_DB_COUNT] Token count: {count}")
            return count
            
        except Exception as e:
            logger.error(f"[AGENT_DB_COUNT] Failed to get token count: {e}\n{traceback.format_exc()}")
            return 0
    
    def _row_to_token(self, row: sqlite3.Row) -> AgentToken:
        """Convert database row to AgentToken object."""
        logger.debug(f"[AGENT_DB_PARSE] Parsing token row: id={row['id']}")
        
        # Parse list fields
        scopes = row["scopes"].split(",") if row["scopes"] else []
        markets = row["markets"].split(",") if row["markets"] and row["markets"] != "*" else ["*"]
        instruments = row["instruments"].split(",") if row["instruments"] and row["instruments"] != "*" else ["*"]
        
        logger.debug(f"[AGENT_DB_PARSE] Parsed fields: scopes={scopes}, markets={markets}, instruments={instruments}")
        
        return AgentToken(
            id=row["id"],
            name=row["name"],
            token_hash=row["token_hash"],
            token_prefix=row["token_prefix"],
            scopes=scopes,
            markets=markets,
            instruments=instruments,
            paper_only=bool(row["paper_only"]),
            rate_limit=row["rate_limit"],
            rate_limit_window_start=row["rate_limit_window_start"],
            request_count=row["request_count"],
            expires_at=row["expires_at"],
            created_at=row["created_at"],
            last_used_at=row["last_used_at"],
            is_active=bool(row["is_active"]),
        )
    
    def _row_to_audit_log(self, row: sqlite3.Row) -> AuditLog:
        """Convert database row to AuditLog object."""
        logger.debug(f"[AGENT_DB_PARSE] Parsing audit log row: id={row['id']}")
        
        # Parse details JSON
        details = {}
        if row["details"]:
            try:
                details = json.loads(row["details"])
                logger.debug(f"[AGENT_DB_PARSE] Parsed details: {details}")
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"[AGENT_DB_PARSE] Failed to parse details JSON: {e}")
                details = {}
        
        return AuditLog(
            id=row["id"],
            token_id=row["token_id"],
            action=row["action"],
            resource=row["resource"] or "",
            details=details,
            ip_address=row["ip_address"] or "",
            user_agent=row["user_agent"] or "",
            timestamp=row["timestamp"],
        )


# ============================================================================
# Module-level convenience functions
# ============================================================================

def get_agent_db() -> AgentDB:
    """Get AgentDB singleton instance."""
    logger.debug("[AGENT_DB_MODULE] Getting AgentDB instance")
    return AgentDB.get_instance()


def init_agent_db():
    """Initialize agent database (called from database.py init_tables)."""
    logger.info("[AGENT_DB_MODULE] Initializing agent database from module")
    db = get_agent_db()
    logger.info("[AGENT_DB_MODULE] Agent database initialized")


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "AgentDB",
    "AgentToken",
    "AuditLog",
    "get_agent_db",
    "init_agent_db",
]
