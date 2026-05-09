"""Agent Token Service for AlphaTerminal.

Comprehensive debug logging for 20 debug cycles.
"""

import hashlib
import logging
import os
import secrets
import sqlite3
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union

# Configure comprehensive logging
logger = logging.getLogger(__name__)

# Set DEBUG level for detailed logging during development
if os.getenv("TOKEN_DEBUG", "false").lower() == "true":
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s'
    )
    handler.setFormatter(formatter)
    if not logger.handlers:
        logger.addHandler(handler)

USE_DB_PERSISTENCE = True
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "cache", "tokens.db")


class TokenScope(Enum):
    READ = "R"  # Market data
    WRITE = "W"  # Modify strategies
    BACKTEST = "B"  # Backtest tasks
    NOTIFY = "N"  # Notifications
    TRADE = "T"  # Trading (default paper-only)


class Market(Enum):
    AStock = "ASTOCK"
    HKStock = "HKSTOCK"
    USStock = "USSTOCK"
    Crypto = "CRYPTO"
    Forex = "FOREX"
    Futures = "FUTURES"


@dataclass
class AgentToken:
    id: str
    name: str
    token_prefix: str
    token_hash: str
    scopes: List[TokenScope]
    markets: List[str] = field(default_factory=lambda: ["*"])
    instruments: List[str] = field(default_factory=lambda: ["*"])
    paper_only: bool = True
    rate_limit: int = 120
    expires_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_used_at: Optional[datetime] = None
    is_active: bool = True
    access_count: int = 0
    revoked_at: Optional[datetime] = None

    def has_scope(self, scope: TokenScope) -> bool:
        scope_value = scope.value if isinstance(scope, TokenScope) else scope
        for s in self.scopes:
            if isinstance(s, TokenScope):
                if s.value == scope_value:
                    return True
            elif s == scope_value:
                return True
        return False

    def can_access_market(self, market: Union[Market, str]) -> bool:
        market_str = market.value if isinstance(market, Market) else market
        if "*" in self.markets:
            return True
        return market_str in self.markets

    def can_access_instrument(self, instrument: str) -> bool:
        if "*" in self.instruments:
            return True
        return instrument in self.instruments

    def to_dict(self) -> dict:
        scopes_list = []
        for s in self.scopes:
            if isinstance(s, TokenScope):
                scopes_list.append(s.value)
            else:
                scopes_list.append(s)
        return {
            "id": self.id,
            "name": self.name,
            "token_prefix": self.token_prefix,
            "scopes": scopes_list,
            "markets": self.markets,
            "instruments": self.instruments,
            "paper_only": self.paper_only,
            "rate_limit": self.rate_limit,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat(),
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "is_active": self.is_active,
            "access_count": self.access_count,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
        }


def _generate_token() -> str:
    logger.debug(f"[TOKEN_GEN] Starting token generation")
    raw = secrets.token_hex(32)[:40]
    token = "AGT1_" + raw
    logger.debug(f"[TOKEN_GEN] Generated token prefix: {token[:12]}***")
    logger.info(f"[TOKEN_GEN] Token generated successfully, length={len(token)}")
    return token


def _hash_token(token: str) -> str:
    logger.debug(f"[TOKEN_HASH] Starting SHA256 hash for token prefix: {token[:12]}***")
    try:
        hash_result = hashlib.sha256(token.encode()).hexdigest()
        logger.debug(f"[TOKEN_HASH] Hash computed: {hash_result[:16]}***")
        logger.info(f"[TOKEN_HASH] Token hashed successfully")
        return hash_result
    except Exception as e:
        logger.error(f"[TOKEN_HASH] Failed to hash token: {e}\n{traceback.format_exc()}")
        raise


class AgentTokenService:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        logger.info("[TOKEN_SVC_INIT] Initializing AgentTokenService singleton")
        if hasattr(self, '_initialized') and self._initialized:
            logger.debug("[TOKEN_SVC_INIT] Already initialized, skipping")
            return

        logger.debug("[TOKEN_SVC_INIT] Creating token storage structures")
        self._tokens: Dict[str, AgentToken] = {}
        self._rate_cache: Dict[str, List[float]] = {}
        self._cleanup_lock = threading.Lock()
        self._initialized = True
        logger.debug(f"[TOKEN_SVC_INIT] Storage created: tokens={len(self._tokens)}, rate_cache={len(self._rate_cache)}")

        logger.debug(f"[TOKEN_SVC_INIT] DB persistence mode: {USE_DB_PERSISTENCE}")
        if USE_DB_PERSISTENCE:
            logger.info("[TOKEN_SVC_INIT] Loading tokens from persistent DB")
            self._load_tokens_from_db()
        else:
            logger.info("[TOKEN_SVC_INIT] Initializing local SQLite DB")
            self._init_db()
            self._load_tokens_from_db()
        
        logger.info(f"[TOKEN_SVC_INIT] Starting cleanup thread")
        self._start_cleanup_thread()
        logger.info(f"[TOKEN_SVC_INIT] AgentTokenService initialized successfully, total tokens: {len(self._tokens)}")

    @classmethod
    def get_instance(cls) -> "AgentTokenService":
        return cls()

    def _init_db(self):
        logger.info("[TOKEN_DB_INIT] Initializing local SQLite database")
        try:
            self._conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            logger.debug(f"[TOKEN_DB_INIT] Connected to DB at: {DB_PATH}")
            
            logger.debug("[TOKEN_DB_INIT] Creating tokens table")
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS tokens (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    token_prefix TEXT NOT NULL,
                    token_hash TEXT UNIQUE NOT NULL,
                    scopes TEXT NOT NULL,
                    markets TEXT DEFAULT '*',
                    instruments TEXT DEFAULT '*',
                    paper_only INTEGER DEFAULT 1,
                    rate_limit INTEGER DEFAULT 120,
                    expires_at TEXT,
                    created_at TEXT NOT NULL,
                    last_used_at TEXT,
                    is_active INTEGER DEFAULT 1,
                    access_count INTEGER DEFAULT 0
                )
            """)
            
            logger.debug("[TOKEN_DB_INIT] Creating audit_logs table")
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    endpoint TEXT DEFAULT "",
                    details TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            logger.debug("[TOKEN_DB_INIT] Creating indexes")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_token_id ON audit_logs(token_id)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_token_hash ON tokens(token_hash)")
            self._conn.commit()
            logger.info("[TOKEN_DB_INIT] Database initialized successfully")
        except Exception as e:
            logger.error(f"[TOKEN_DB_INIT] Failed to initialize DB: {e}\n{traceback.format_exc()}")
            raise

    def _load_tokens_from_db(self):
        logger.info("[TOKEN_LOAD] Loading tokens from database")
        loaded_count = 0
        error_count = 0
        
        if USE_DB_PERSISTENCE:
            logger.debug("[TOKEN_LOAD] Using persistent DB mode")
            from app.db.token_db import list_tokens
            try:
                tokens = list_tokens(include_inactive=True)
                logger.debug(f"[TOKEN_LOAD] Retrieved {len(tokens)} token records from DB")
                for t in tokens:
                    try:
                        token = AgentToken(
                            id=t["id"],
                            name=t["name"],
                            token_prefix=t["token_prefix"],
                            token_hash=t["token_hash"],
                            scopes=[TokenScope(s) for s in t["scopes"]],
                            markets=t["markets"],
                            instruments=t.get("instruments", ["*"]),
                            paper_only=t["paper_only"],
                            rate_limit=t["rate_limit"],
                            expires_at=datetime.fromisoformat(t["expires_at"]) if t.get("expires_at") else None,
                            created_at=datetime.fromisoformat(t["created_at"]),
                            last_used_at=datetime.fromisoformat(t["last_used_at"]) if t.get("last_used_at") else None,
                            is_active=t["is_active"],
                            access_count=t.get("access_count", 0),
                            revoked_at=datetime.fromisoformat(t["revoked_at"]) if t.get("revoked_at") else None,
                        )
                        self._tokens[token.token_hash] = token
                        self._rate_cache[token.token_hash] = []
                        loaded_count += 1
                        logger.debug(f"[TOKEN_LOAD] Loaded token: id={token.id}, name={token.name}, prefix={token.token_prefix}")
                    except Exception as e:
                        error_count += 1
                        logger.error(f"[TOKEN_LOAD] Failed to parse token record: {e}\n{traceback.format_exc()}")
                logger.info(f"[TOKEN_LOAD] Loaded {loaded_count} tokens from persistent DB, errors={error_count}")
            except Exception as e:
                logger.error(f"[TOKEN_LOAD] Failed to load tokens from DB: {e}\n{traceback.format_exc()}")
        else:
            logger.debug("[TOKEN_LOAD] Using local SQLite mode")
            try:
                rows = self._conn.execute("SELECT * FROM tokens").fetchall()
                logger.debug(f"[TOKEN_LOAD] Retrieved {len(rows)} token rows from SQLite")
                for row in rows:
                    try:
                        token = AgentToken(
                            id=row[0],
                            name=row[1],
                            token_prefix=row[2],
                            token_hash=row[3],
                            scopes=[TokenScope(s) for s in row[4].split(',')],
                            markets=row[5].split(',') if row[5] != '*' else ['*'],
                            instruments=row[6].split(',') if row[6] != '*' else ['*'],
                            paper_only=bool(row[7]),
                            rate_limit=row[8],
                            expires_at=datetime.fromisoformat(row[9]) if row[9] else None,
                            created_at=datetime.fromisoformat(row[10]),
                            last_used_at=datetime.fromisoformat(row[11]) if row[11] else None,
                            is_active=bool(row[12]),
                            access_count=row[13],
                        )
                        self._tokens[token.token_hash] = token
                        self._rate_cache[token.token_hash] = []
                        loaded_count += 1
                        logger.debug(f"[TOKEN_LOAD] Loaded token: id={token.id}, name={token.name}")
                    except Exception as e:
                        error_count += 1
                        logger.error(f"[TOKEN_LOAD] Failed to parse token row: {e}\n{traceback.format_exc()}")
                logger.info(f"[TOKEN_LOAD] Loaded {loaded_count} tokens from SQLite, errors={error_count}")
            except Exception as e:
                logger.error(f"[TOKEN_LOAD] Failed to load tokens from SQLite: {e}\n{traceback.format_exc()}")

    def _save_token(self, token: AgentToken):
        logger.info(f"[TOKEN_SAVE] Saving token: id={token.id}, name={token.name}")
        logger.debug(f"[TOKEN_SAVE] Token details: prefix={token.token_prefix}, scopes={[s.value for s in token.scopes]}, markets={token.markets}")
        
        if USE_DB_PERSISTENCE:
            logger.debug("[TOKEN_SAVE] Using persistent DB save")
            from app.db.token_db import create_token, update_token_usage
            try:
                create_token(
                    token_id=token.id,
                    name=token.name,
                    token_hash=token.token_hash,
                    token_prefix=token.token_prefix,
                    scopes=[s.value for s in token.scopes],
                    markets=token.markets,
                    instruments=token.instruments,
                    paper_only=token.paper_only,
                    rate_limit=token.rate_limit,
                    expires_at=token.expires_at,
                )
                logger.info(f"[TOKEN_SAVE] Token saved to persistent DB: id={token.id}")
            except ValueError as e:
                logger.debug(f"[TOKEN_SAVE] Token already exists (expected): {e}")
            except Exception as e:
                logger.error(f"[TOKEN_SAVE] Failed to save token to persistent DB: {e}\n{traceback.format_exc()}")
        else:
            logger.debug("[TOKEN_SAVE] Using SQLite save")
            try:
                self._conn.execute("""
                    INSERT OR REPLACE INTO tokens 
                    (id, name, token_prefix, token_hash, scopes, markets, instruments, paper_only, rate_limit, expires_at, created_at, last_used_at, is_active, access_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    token.id,
                    token.name,
                    token.token_prefix,
                    token.token_hash,
                    ','.join([s.value for s in token.scopes]),
                    ','.join(token.markets) if token.markets != ['*'] else '*',
                    ','.join(token.instruments) if token.instruments != ['*'] else '*',
                    int(token.paper_only),
                    token.rate_limit,
                    token.expires_at.isoformat() if token.expires_at else None,
                    token.created_at.isoformat(),
                    token.last_used_at.isoformat() if token.last_used_at else None,
                    int(token.is_active),
                    token.access_count,
                ))
                self._conn.commit()
                logger.info(f"[TOKEN_SAVE] Token saved to SQLite: id={token.id}")
            except Exception as e:
                logger.error(f"[TOKEN_SAVE] Failed to save token to SQLite: {e}\n{traceback.format_exc()}")

    def _start_cleanup_thread(self):
        logger.info("[TOKEN_CLEANUP] Starting cleanup thread")
        def cleanup_loop():
            logger.debug("[TOKEN_CLEANUP_THREAD] Cleanup thread started")
            while True:
                time.sleep(300)  # 5 minutes
                logger.debug("[TOKEN_CLEANUP_THREAD] Running scheduled cleanup")
                self._cleanup_expired()

        t = threading.Thread(target=cleanup_loop, daemon=True)
        t.start()
        logger.debug(f"[TOKEN_CLEANUP] Cleanup thread started: thread_id={t.ident}")

    def _cleanup_expired(self):
        logger.debug("[TOKEN_CLEANUP] Starting expired token cleanup")
        with self._cleanup_lock:
            now = datetime.now()
            logger.debug(f"[TOKEN_CLEANUP] Checking {len(self._tokens)} tokens for expiration")
            expired_ids = [
                tid for tid, token in self._tokens.items()
                if token.expires_at and token.expires_at <= now
            ]
            logger.debug(f"[TOKEN_CLEANUP] Found {len(expired_ids)} expired tokens")
            
            for tid in expired_ids:
                logger.info(f"[TOKEN_CLEANUP] Removing expired token: hash={tid[:16]}***")
                del self._tokens[tid]
                if USE_DB_PERSISTENCE:
                    from app.db.token_db import delete_expired_tokens
                    delete_expired_tokens()
                else:
                    try:
                        self._conn.execute("DELETE FROM tokens WHERE token_hash = ?", (tid,))
                        self._conn.commit()
                    except Exception as e:
                        logger.error(f"[TOKEN_CLEANUP] Failed to delete expired token: {e}\n{traceback.format_exc()}")
            
            logger.info(f"[TOKEN_CLEANUP] Cleanup complete, removed {len(expired_ids)} tokens")

    def create_token(
        self,
        name: str,
        scopes: List[TokenScope],
        markets: List[str] = None,
        instruments: List[str] = None,
        paper_only: bool = True,
        rate_limit: int = 120,
        expires_in_days: int = None,
    ) -> Tuple[str, AgentToken]:
        logger.info(f"[TOKEN_CREATE] Creating new token: name={name}")
        logger.debug(f"[TOKEN_CREATE] Parameters: scopes={[s.value for s in scopes]}, markets={markets}, instruments={instruments}, paper_only={paper_only}, rate_limit={rate_limit}, expires_in_days={expires_in_days}")
        
        try:
            raw_token = _generate_token()
            token_hash = _hash_token(raw_token)
            logger.debug(f"[TOKEN_CREATE] Generated token hash: {token_hash[:16]}***")

            expires_at = None
            if expires_in_days is not None:
                expires_at = datetime.now() + timedelta(days=expires_in_days)
                logger.debug(f"[TOKEN_CREATE] Token will expire at: {expires_at.isoformat()}")

            token = AgentToken(
                id=str(uuid.uuid4()),
                name=name,
                token_prefix=raw_token[:12],
                token_hash=token_hash,
                scopes=scopes,
                markets=markets or ["*"],
                instruments=instruments or ["*"],
                paper_only=paper_only,
                rate_limit=rate_limit,
                expires_at=expires_at,
            )
            logger.debug(f"[TOKEN_CREATE] Token object created: id={token.id}, prefix={token.token_prefix}")

            with self._lock:
                self._tokens[token_hash] = token
                self._rate_cache[token_hash] = []
                logger.debug(f"[TOKEN_CREATE] Token stored in memory, total tokens: {len(self._tokens)}")

            self._save_token(token)
            logger.info(f"[TOKEN_CREATE] Token created successfully: id={token.id}, name={name}")
            return raw_token, token
        except Exception as e:
            logger.error(f"[TOKEN_CREATE] Failed to create token: {e}\n{traceback.format_exc()}")
            raise

    def verify_token(self, raw_token: str) -> Optional[AgentToken]:
        logger.debug(f"[TOKEN_VERIFY] Starting token verification for prefix: {raw_token[:12] if raw_token else 'None'}***")
        
        if not raw_token:
            logger.warning("[TOKEN_VERIFY] Empty token provided")
            return None
        
        try:
            token_hash = _hash_token(raw_token)
            logger.debug(f"[TOKEN_VERIFY] Computed hash: {token_hash[:16]}***")

            with self._lock:
                token = self._tokens.get(token_hash)
                logger.debug(f"[TOKEN_VERIFY] Token lookup result: {'found' if token else 'not found'}")

                if not token:
                    logger.warning(f"[TOKEN_VERIFY] Token not found: hash={token_hash[:16]}***")
                    return None

                logger.debug(f"[TOKEN_VERIFY] Token found: id={token.id}, name={token.name}, is_active={token.is_active}")
                
                if not token.is_active:
                    logger.warning(f"[TOKEN_VERIFY] Token is inactive: id={token.id}")
                    return None

                if token.expires_at and token.expires_at <= datetime.now():
                    logger.warning(f"[TOKEN_VERIFY] Token expired: id={token.id}, expired_at={token.expires_at.isoformat()}")
                    return None

                now = time.time()
                window = 60.0
                logger.debug(f"[TOKEN_VERIFY] Checking rate limit: current_time={now}, window={window}s, limit={token.rate_limit}")

                if token.token_hash not in self._rate_cache:
                    self._rate_cache[token.token_hash] = []
                    logger.debug(f"[TOKEN_VERIFY] Initialized rate cache for token")

                timestamps = self._rate_cache[token.token_hash]
                logger.debug(f"[TOKEN_VERIFY] Current timestamps in window: {len(timestamps)}")
                
                timestamps = [ts for ts in timestamps if now - ts < window]
                self._rate_cache[token.token_hash] = timestamps
                logger.debug(f"[TOKEN_VERIFY] Timestamps after cleanup: {len(timestamps)}")

                if len(timestamps) >= token.rate_limit:
                    logger.warning(f"[TOKEN_VERIFY] Rate limit exceeded: id={token.id}, requests={len(timestamps)}, limit={token.rate_limit}")
                    return None

                timestamps.append(now)
                logger.debug(f"[TOKEN_VERIFY] Request allowed, new count: {len(timestamps)}")

                token.last_used_at = datetime.now()
                token.access_count += 1
                logger.debug(f"[TOKEN_VERIFY] Updated usage: last_used_at={token.last_used_at}, access_count={token.access_count}")
                
                if USE_DB_PERSISTENCE:
                    from app.db.token_db import update_token_usage
                    update_token_usage(token_hash)
                    logger.debug(f"[TOKEN_VERIFY] Updated usage in persistent DB")

                logger.info(f"[TOKEN_VERIFY] Token verified successfully: id={token.id}, name={token.name}")
                return token
        except Exception as e:
            logger.error(f"[TOKEN_VERIFY] Token verification failed: {e}\n{traceback.format_exc()}")
            return None

    def log_audit(self, token_id: str, action: str, endpoint: str = "", details: dict = None):
        logger.info(f"[TOKEN_AUDIT] Logging audit: token_id={token_id}, action={action}, endpoint={endpoint}")
        logger.debug(f"[TOKEN_AUDIT] Audit details: {details}")
        
        try:
            if USE_DB_PERSISTENCE:
                logger.debug("[TOKEN_AUDIT] Using persistent DB audit log")
                from app.db.audit_db import log_audit as db_log_audit
                db_log_audit(
                    agent_id=token_id,
                    action=action,
                    resource=endpoint,
                    details=details,
                )
                logger.info(f"[TOKEN_AUDIT] Audit logged to persistent DB: token_id={token_id}")
            else:
                logger.debug("[TOKEN_AUDIT] Using SQLite audit log")
                details_str = str(details) if details else None
                with self._lock:
                    self._conn.execute(
                        "INSERT INTO audit_logs (token_id, action, endpoint, details) VALUES (?, ?, ?, ?)",
                        (token_id, action, endpoint, details_str),
                    )
                    self._conn.commit()
                logger.info(f"[TOKEN_AUDIT] Audit logged to SQLite: token_id={token_id}")
        except Exception as e:
            logger.error(f"[TOKEN_AUDIT] Failed to log audit: {e}\n{traceback.format_exc()}")

    def revoke_token(self, token_id: str) -> bool:
        logger.info(f"[TOKEN_REVOKE] Attempting to revoke token: id={token_id}")
        
        try:
            with self._lock:
                for token in self._tokens.values():
                    if token.id == token_id:
                        logger.debug(f"[TOKEN_REVOKE] Found token: name={token.name}, prefix={token.token_prefix}")
                        token.is_active = False
                        token.revoked_at = datetime.now()
                        logger.debug(f"[TOKEN_REVOKE] Token marked as inactive, revoked_at={token.revoked_at}")
                        
                        if USE_DB_PERSISTENCE:
                            logger.debug("[TOKEN_REVOKE] Updating persistent DB")
                            from app.db.token_db import revoke_token as db_revoke
                            db_revoke(token_id)
                        else:
                            logger.debug("[TOKEN_REVOKE] Updating SQLite")
                            self._save_token(token)
                        
                        logger.info(f"[TOKEN_REVOKE] Token revoked successfully: id={token_id}")
                        return True
                
                logger.warning(f"[TOKEN_REVOKE] Token not found: id={token_id}")
                return False
        except Exception as e:
            logger.error(f"[TOKEN_REVOKE] Failed to revoke token: {e}\n{traceback.format_exc()}")
            return False

    def list_tokens(self, include_inactive: bool = False) -> List[AgentToken]:
        logger.debug(f"[TOKEN_LIST] Listing tokens: include_inactive={include_inactive}")
        
        with self._lock:
            if include_inactive:
                result = list(self._tokens.values())
                logger.debug(f"[TOKEN_LIST] Returning all tokens: count={len(result)}")
            else:
                result = [t for t in self._tokens.values() if t.is_active]
                logger.debug(f"[TOKEN_LIST] Returning active tokens: count={len(result)}, total={len(self._tokens)}")
            
            logger.info(f"[TOKEN_LIST] Listed {len(result)} tokens")
            return result

    def get_expiring_tokens(self, days: int = 7) -> List[AgentToken]:
        logger.info(f"[TOKEN_EXPIRING] Getting tokens expiring within {days} days")
        
        if USE_DB_PERSISTENCE:
            logger.debug("[TOKEN_EXPIRING] Using persistent DB query")
            from app.db.token_db import get_expiring_tokens as db_get_expiring
            tokens_data = db_get_expiring(days)
            result = [
                self._tokens.get(t["token_hash"])
                for t in tokens_data
                if t.get("token_hash") in self._tokens
            ]
            logger.info(f"[TOKEN_EXPIRING] Found {len(result)} expiring tokens from persistent DB")
            return result
        else:
            cutoff = datetime.now() + timedelta(days=days)
            logger.debug(f"[TOKEN_EXPIRING] Cutoff date: {cutoff.isoformat()}")
            with self._lock:
                result = [
                    t for t in self._tokens.values()
                    if t.expires_at and t.expires_at <= cutoff and t.is_active
                ]
                logger.info(f"[TOKEN_EXPIRING] Found {len(result)} expiring tokens from memory")
                return result

    def get_audit_logs(
        self,
        token_id: str = None,
        action: str = None,
        start_time: datetime = None,
        end_time: datetime = None,
        limit: int = 100,
    ) -> List[dict]:
        logger.info(f"[TOKEN_AUDIT_GET] Getting audit logs: token_id={token_id}, action={action}, limit={limit}")
        logger.debug(f"[TOKEN_AUDIT_GET] Time range: start={start_time}, end={end_time}")
        
        try:
            if USE_DB_PERSISTENCE:
                logger.debug("[TOKEN_AUDIT_GET] Using persistent DB query")
                from app.db.audit_db import get_audit_logs as db_get_audit
                logs = db_get_audit(
                    agent_id=token_id,
                    action=action,
                    start_time=start_time,
                    end_time=end_time,
                    limit=limit,
                )
                result = [
                    {
                        "id": log.get("id"),
                        "token_id": log.get("agent_id"),
                        "action": log.get("action"),
                        "endpoint": log.get("resource", ""),
                        "details": log.get("details"),
                        "timestamp": log.get("timestamp"),
                    }
                    for log in logs
                ]
                logger.info(f"[TOKEN_AUDIT_GET] Retrieved {len(result)} audit logs from persistent DB")
                return result
            else:
                logger.debug("[TOKEN_AUDIT_GET] Using SQLite query")
                query = "SELECT id, token_id, action, endpoint, details, timestamp FROM audit_logs WHERE 1=1"
                params = []

                if token_id:
                    query += " AND token_id = ?"
                    params.append(token_id)
                if action:
                    query += " AND action = ?"
                    params.append(action)
                if start_time:
                    query += " AND timestamp >= ?"
                    params.append(start_time.isoformat())
                if end_time:
                    query += " AND timestamp <= ?"
                    params.append(end_time.isoformat())

                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)
                
                logger.debug(f"[TOKEN_AUDIT_GET] Query: {query}, params: {params}")

                cursor = self._conn.execute(query, params)
                rows = cursor.fetchall()

                result = [
                    {
                        "id": row[0],
                        "token_id": row[1],
                        "action": row[2],
                        "endpoint": row[3],
                        "details": row[4],
                        "timestamp": row[5],
                    }
                    for row in rows
                ]
                logger.info(f"[TOKEN_AUDIT_GET] Retrieved {len(result)} audit logs from SQLite")
                return result
        except Exception as e:
            logger.error(f"[TOKEN_AUDIT_GET] Failed to get audit logs: {e}\n{traceback.format_exc()}")
            return []

    def check_scope(self, token: AgentToken, required_scope: TokenScope) -> bool:
        logger.debug(f"[TOKEN_SCOPE] Checking scope for token: id={token.id}, required={required_scope.value}")
        
        try:
            has_scope = token.has_scope(required_scope)
            logger.debug(f"[TOKEN_SCOPE] Token scopes: {[s.value for s in token.scopes]}, has_scope={has_scope}")
            
            if has_scope:
                logger.info(f"[TOKEN_SCOPE] Scope check passed: token={token.id}, scope={required_scope.value}")
            else:
                logger.warning(f"[TOKEN_SCOPE] Scope check failed: token={token.id}, required={required_scope.value}, available={[s.value for s in token.scopes]}")
            
            return has_scope
        except Exception as e:
            logger.error(f"[TOKEN_SCOPE] Scope check error: {e}\n{traceback.format_exc()}")
            return False

    def is_expired(self, token: AgentToken) -> bool:
        logger.debug(f"[TOKEN_EXPIRED] Checking expiration for token: id={token.id}")
        
        try:
            if not token.expires_at:
                logger.debug(f"[TOKEN_EXPIRED] Token has no expiration, not expired: id={token.id}")
                return False
            
            now = datetime.now()
            is_expired = token.expires_at <= now
            
            logger.debug(f"[TOKEN_EXPIRED] Token expires_at={token.expires_at.isoformat()}, now={now.isoformat()}, is_expired={is_expired}")
            
            if is_expired:
                logger.warning(f"[TOKEN_EXPIRED] Token is expired: id={token.id}, expired_at={token.expires_at.isoformat()}")
            else:
                logger.info(f"[TOKEN_EXPIRED] Token is valid: id={token.id}, expires_at={token.expires_at.isoformat()}")
            
            return is_expired
        except Exception as e:
            logger.error(f"[TOKEN_EXPIRED] Expiration check error: {e}\n{traceback.format_exc()}")
            return True

    def check_rate_limit(self, token: AgentToken) -> bool:
        logger.debug(f"[TOKEN_RATE] Checking rate limit for token: id={token.id}, limit={token.rate_limit}")
        
        try:
            now = time.time()
            window = 60.0
            
            if token.token_hash not in self._rate_cache:
                self._rate_cache[token.token_hash] = []
                logger.debug(f"[TOKEN_RATE] Initialized rate cache for token")
            
            timestamps = self._rate_cache.get(token.token_hash, [])
            timestamps = [ts for ts in timestamps if now - ts < window]
            
            current_count = len(timestamps)
            allowed = current_count < token.rate_limit
            
            logger.debug(f"[TOKEN_RATE] Current requests in window: {current_count}, limit: {token.rate_limit}, allowed: {allowed}")
            
            if allowed:
                logger.info(f"[TOKEN_RATE] Rate limit check passed: token={token.id}, requests={current_count}/{token.rate_limit}")
            else:
                logger.warning(f"[TOKEN_RATE] Rate limit exceeded: token={token.id}, requests={current_count}/{token.rate_limit}")
            
            return allowed
        except Exception as e:
            logger.error(f"[TOKEN_RATE] Rate limit check error: {e}\n{traceback.format_exc()}")
            return False


def get_token_service() -> AgentTokenService:
    logger.debug("[TOKEN_SVC_GET] Getting token service instance")
    return AgentTokenService.get_instance()
