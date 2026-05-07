"""Agent Token Service for AlphaTerminal."""

import hashlib
import secrets
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union

DB_PATH = "/tmp/alpha_terminal_tokens.db"


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

    def has_scope(self, scope: TokenScope) -> bool:
        return scope in self.scopes

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
        return {
            "id": self.id,
            "name": self.name,
            "token_prefix": self.token_prefix,
            "scopes": [s.value for s in self.scopes],
            "markets": self.markets,
            "instruments": self.instruments,
            "paper_only": self.paper_only,
            "rate_limit": self.rate_limit,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat(),
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "is_active": self.is_active,
            "access_count": self.access_count,
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

        self._init_db()
        self._start_cleanup_thread()

    @classmethod
    def get_instance(cls) -> "AgentTokenService":
        return cls()

    def _init_db(self):
        self._conn = sqlite3.connect(DB_PATH, check_same_thread=False)
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
        self._conn.commit()

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

            # Check rate limit atomically with token state
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

            return token

    def log_audit(self, token_id: str, action: str, endpoint: str = "", details: dict = None):
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
                    return True
            return False

    def list_tokens(self, include_inactive: bool = False) -> List[AgentToken]:
        with self._lock:
            if include_inactive:
                return list(self._tokens.values())
            return [t for t in self._tokens.values() if t.is_active]

    def get_expiring_tokens(self, days: int = 7) -> List[AgentToken]:
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
