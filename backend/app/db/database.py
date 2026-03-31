"""
SQLite 数据库管理 - Phase 3+
WAL 模式 + 批量写入缓冲
"""
import sqlite3
import threading
import logging
import time

logger = logging.getLogger(__name__)

_db_path = "cache/alphaterminal.db"
_lock   = threading.Lock()

def _get_conn():
    conn = sqlite3.connect(_db_path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-8192")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

def init_tables():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS market_data_realtime (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol     TEXT    NOT NULL,
            name      TEXT,
            price     REAL,
            change_pct REAL    DEFAULT 0,
            volume    REAL,
            market    TEXT    DEFAULT '',
            data_type TEXT    DEFAULT 'realtime',
            timestamp INTEGER NOT NULL,
            UNIQUE(symbol, data_type)
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_realtime_symbol_ts ON market_data_realtime(symbol, timestamp);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_buffer_symbol ON write_buffer(symbol);")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS market_data_daily (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol     TEXT    NOT NULL,
            date       TEXT    NOT NULL,
            open       REAL,
            high       REAL,
            low        REAL,
            close      REAL,
            volume     REAL,
            change_pct REAL,
            timestamp  INTEGER NOT NULL,
            data_type  TEXT    DEFAULT 'daily',
            UNIQUE(symbol, date)
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_symbol_date ON market_data_daily(symbol, date);")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS market_data_periodic (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol     TEXT    NOT NULL,
            date       TEXT    NOT NULL,
            period     TEXT    NOT NULL,
            open       REAL,
            high       REAL,
            low        REAL,
            close      REAL,
            volume     REAL,
            change_pct REAL,
            timestamp  INTEGER NOT NULL,
            UNIQUE(symbol, date, period)
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_periodic_sym_date ON market_data_periodic(symbol, date, period);")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS write_buffer (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol     TEXT    NOT NULL,
            name      TEXT,
            price     REAL,
            change_pct REAL    DEFAULT 0,
            volume    REAL,
            market    TEXT    DEFAULT '',
            data_type TEXT    DEFAULT 'realtime',
            timestamp INTEGER NOT NULL
        );
    """)
    conn.commit()
    logger.info("[DB] 表初始化完成")

def buffer_insert(rows: list[dict]):
    if not rows: return
    conn = _get_conn()
    for r in rows:
        conn.execute("""
            INSERT OR REPLACE INTO market_data_realtime
                (symbol, name, price, change_pct, volume, market, data_type, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (r["symbol"], r.get("name"), r.get("price"),
              r.get("change_pct", 0), r.get("volume", 0),
              r.get("market", ""), r.get("data_type", "realtime"), r["timestamp"]))
    conn.commit()

def buffer_insert_daily(rows: list[dict]):
    """
    将日K线数据批量写入 market_data_daily（UPSERT 语义）
    防御性探针：若 close==high 比例 >50% 则丢弃整批
    """
    if not rows:
        return
    total = len(rows)
    bad = sum(1 for r in rows if abs(float(r.get("close") or 0) - float(r.get("high") or 0)) < 0.01)
    if total >= 10 and bad / total > 0.5:
        logger.error(f"[DB BLOCK] close==high 污染率 {bad/total:.0%} > 50%，拒绝写入 {total} 条")
        return
    conn = _get_conn()
    for r in rows:
        o = float(r.get("open") or 0)
        c = float(r.get("close") or 0)
        h = float(r.get("high") or 0)
        l = float(r.get("low") or 0)
        if h < l:
            h, l = l, h
        h = max(h, o, c)
        l = min(l, o, c)
        conn.execute("""
            INSERT INTO market_data_daily
                (symbol, date, open, high, low, close, volume, change_pct, timestamp, data_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, date) DO UPDATE SET
                open=excluded.open, high=excluded.high, low=excluded.low,
                close=excluded.close, volume=excluded.volume,
                change_pct=excluded.change_pct, timestamp=excluded.timestamp;
        """, (r["symbol"], r.get("date"), o, h, l, c,
              r.get("volume", 0), r.get("change_pct", 0),
              r["timestamp"], r.get("data_type", "daily")))
    conn.commit()
    logger.info(f"[DB] 日K线写入 {len(rows)} 条")

def buffer_insert_periodic(rows: list[dict], period: str):
    if not rows: return
    conn = _get_conn()
    for r in rows:
        conn.execute("""
            INSERT INTO market_data_periodic
                (symbol, date, period, open, high, low, close, volume, change_pct, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, date, period) DO UPDATE SET
                open=excluded.open, high=excluded.high, low=excluded.low,
                close=excluded.close, volume=excluded.volume,
                change_pct=excluded.change_pct, timestamp=excluded.timestamp;
        """, (r["symbol"], r["date"], period,
              r["open"], r["high"], r["low"], r["close"],
              r["volume"], r["change_pct"], r["timestamp"]))
    conn.commit()
    logger.info(f"[DB] {period}写入 {len(rows)} 条")

def flush_buffer_to_realtime():
    conn = _get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO market_data_realtime
            (symbol, name, price, change_pct, volume, market, data_type, timestamp)
        SELECT symbol, name, price, change_pct, volume, market, data_type, timestamp
        FROM write_buffer;
    """)
    conn.execute("DELETE FROM write_buffer;")
    conn.commit()

def get_latest_prices(symbols: list[str]) -> list[dict]:
    if not symbols: return []
    conn = _get_conn()
    placeholders = ",".join("?" * len(symbols))
    rows = conn.execute(f"""
        SELECT symbol, name, price, change_pct, volume, market, timestamp, data_type
        FROM market_data_realtime
        WHERE symbol IN ({placeholders})
        ORDER BY timestamp DESC;
    """, symbols).fetchall()
    seen = set()
    result = []
    for r in rows:
        sym = r[0]
        if sym not in seen:
            seen.add(sym)
            result.append({
                "symbol": r[0], "name": r[1], "price": r[2],
                "change_pct": r[3], "volume": r[4],
                "market": r[5], "timestamp": r[6], "data_type": r[7],
            })
    return result

def get_price_history(symbol: str, limit: int = 100) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute("""
        SELECT symbol, name, price, change_pct, timestamp
        FROM market_data_realtime
        WHERE symbol = ?
        ORDER BY timestamp ASC
        LIMIT ?;
    """, (symbol, limit)).fetchall()
    return [
        {"symbol": r[0], "name": r[1], "price": r[2],
         "change_pct": r[3], "timestamp": r[4]}
        for r in rows
    ]

def get_daily_history(symbol: str, limit: int = 300) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute("""
        SELECT symbol, date, open, high, low, close, volume, change_pct, timestamp
        FROM market_data_daily
        WHERE symbol = ?
        ORDER BY timestamp DESC
        LIMIT ?;
    """, (symbol, limit)).fetchall()
    rows = list(reversed(rows))
    return [
        {"symbol": r[0], "date": r[1],
         "open": r[2], "high": r[3], "low": r[4], "close": r[5],
         "volume": r[6], "change_pct": r[7], "timestamp": r[8]}
        for r in rows
    ]

def get_periodic_history(symbol: str, period: str, limit: int = 200) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute("""
        SELECT symbol, date, period, open, high, low, close, volume, change_pct, timestamp
        FROM market_data_periodic
        WHERE symbol = ? AND period = ?
        ORDER BY timestamp DESC
        LIMIT ?;
    """, (symbol, period, limit)).fetchall()
    rows = list(reversed(rows))
    return [
        {"symbol": r[0], "date": r[1], "period": r[2],
         "open": r[3], "high": r[4], "low": r[5], "close": r[6],
         "volume": r[7], "change_pct": r[8], "timestamp": r[9]}
        for r in rows
    ]
