"""Agent Token Service for AlphaTerminal."""

import hashlib
import logging
import os
import secrets
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

USE_DB_PERSISTENCE = True


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
    return "AGT1_" + secrets.token_hex(32)[:40]


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


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
        if hasattr(self, '_initialized') and self._initialized:
            return

        self._tokens: Dict[str, AgentToken] = {}
        self._rate_cache: Dict[str, List[float]] = {}
        self._cleanup_lock = threading.Lock()
        self._initialized = True

        if USE_DB_PERSISTENCE:
            self._load_tokens_from_db()
        else:
            self._init_db()
            self._load_tokens_from_db()
        
        self._start_cleanup_thread()

    @classmethod
    def get_instance(cls) -> "AgentTokenService":
        return cls()

    def _init_db(self):
        self._conn = sqlite3.connect(DB_PATH, check_same_thread=False)
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
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_token_id ON audit_logs(token_id)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_token_hash ON tokens(token_hash)")
        self._conn.commit()

    def _load_tokens_from_db(self):
        if USE_DB_PERSISTENCE:
            from app.db.token_db import list_tokens
            try:
                tokens = list_tokens(include_inactive=True)
                for t in tokens:
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
            except Exception as e:
                logger.warning(f"Failed to load tokens from DB: {e}")
        else:
            try:
                rows = self._conn.execute("SELECT * FROM tokens").fetchall()
                for row in rows:
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
            except Exception as e:
                logger.warning(f"Failed to load tokens from DB: {e}")

    def _save_token(self, token: AgentToken):
        if USE_DB_PERSISTENCE:
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
            except ValueError:
                pass
        else:
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
            except Exception as e:
                logger.warning(f"Failed to save token: {e}")

    def _start_cleanup_thread(self):
        def cleanup_loop():
            while True:
                time.sleep(300)  # 5 minutes
                self._cleanup_expired()

        t = threading.Thread(target=cleanup_loop, daemon=True)
        t.start()

    def _cleanup_expired(self):
        with self._cleanup_lock:
            now = datetime.now()
            expired_ids = [
                tid for tid, token in self._tokens.items()
                if token.expires_at and token.expires_at <= now
            ]
            for tid in expired_ids:
                del self._tokens[tid]
                if USE_DB_PERSISTENCE:
                    from app.db.token_db import delete_expired_tokens
                    delete_expired_tokens()
                else:
                    try:
                        self._conn.execute("DELETE FROM tokens WHERE token_hash = ?", (tid,))
                        self._conn.commit()
                    except Exception:
                        pass

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
        raw_token = _generate_token()
        token_hash = _hash_token(raw_token)

        expires_at = None
        if expires_in_days is not None:
            expires_at = datetime.now() + timedelta(days=expires_in_days)

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

        with self._lock:
            self._tokens[token_hash] = token
            self._rate_cache[token_hash] = []

        self._save_token(token)
        return raw_token, token

    def verify_token(self, raw_token: str) -> Optional[AgentToken]:
        token_hash = _hash_token(raw_token)

        with self._lock:
            token = self._tokens.get(token_hash)

            if not token:
                return None

            if not token.is_active:
                return None

            if token.expires_at and token.expires_at <= datetime.now():
                return None

            now = time.time()
            window = 60.0

            if token.token_hash not in self._rate_cache:
                self._rate_cache[token.token_hash] = []

            timestamps = self._rate_cache[token.token_hash]
            timestamps = [ts for ts in timestamps if now - ts < window]
            self._rate_cache[token.token_hash] = timestamps

            if len(timestamps) >= token.rate_limit:
                return None

            timestamps.append(now)

            token.last_used_at = datetime.now()
            token.access_count += 1
            
            if USE_DB_PERSISTENCE:
                from app.db.token_db import update_token_usage
                update_token_usage(token_hash)

            return token

    def log_audit(self, token_id: str, action: str, endpoint: str = "", details: dict = None):
        if USE_DB_PERSISTENCE:
            from app.db.audit_db import log_audit as db_log_audit
            db_log_audit(
                agent_id=token_id,
                action=action,
                resource=endpoint,
                details=details,
            )
        else:
            details_str = str(details) if details else None
            with self._lock:
                self._conn.execute(
                    "INSERT INTO audit_logs (token_id, action, endpoint, details) VALUES (?, ?, ?, ?)",
                    (token_id, action, endpoint, details_str),
                )
                self._conn.commit()

    def revoke_token(self, token_id: str) -> bool:
        with self._lock:
            for token in self._tokens.values():
                if token.id == token_id:
                    token.is_active = False
                    token.revoked_at = datetime.now()
                    if USE_DB_PERSISTENCE:
                        from app.db.token_db import revoke_token as db_revoke
                        db_revoke(token_id)
                    else:
                        self._save_token(token)
                    return True
            return False

    def list_tokens(self, include_inactive: bool = False) -> List[AgentToken]:
        with self._lock:
            if include_inactive:
                return list(self._tokens.values())
            return [t for t in self._tokens.values() if t.is_active]

    def get_expiring_tokens(self, days: int = 7) -> List[AgentToken]:
        if USE_DB_PERSISTENCE:
            from app.db.token_db import get_expiring_tokens as db_get_expiring
            tokens_data = db_get_expiring(days)
            return [
                self._tokens.get(t["token_hash"])
                for t in tokens_data
                if t.get("token_hash") in self._tokens
            ]
        else:
            cutoff = datetime.now() + timedelta(days=days)
            with self._lock:
                return [
                    t for t in self._tokens.values()
                    if t.expires_at and t.expires_at <= cutoff and t.is_active
                ]

    def get_audit_logs(
        self,
        token_id: str = None,
        action: str = None,
        start_time: datetime = None,
        end_time: datetime = None,
        limit: int = 100,
    ) -> List[dict]:
        if USE_DB_PERSISTENCE:
            from app.db.audit_db import get_audit_logs as db_get_audit
            logs = db_get_audit(
                agent_id=token_id,
                action=action,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
            )
            return [
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
        else:
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

            cursor = self._conn.execute(query, params)
            rows = cursor.fetchall()

            return [
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


def get_token_service() -> AgentTokenService:
    return AgentTokenService.get_instance()
