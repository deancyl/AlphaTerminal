"""
SQLite 数据库管理 - Phase 3
WAL 模式 + 批量写入缓冲
"""
import sqlite3
import threading
import time
from typing import Optional

DB_PATH = "/vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal_Workspace/backend/cache/alphaterminal.db"

# 每个线程独立连接，SQLite 推荐做法
_thread_local = threading.local()

def _get_conn() -> sqlite3.Connection:
    if not hasattr(_thread_local, "conn"):
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA cache_size=-64000;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        _thread_local.conn = conn
    return _thread_local.conn


def init_tables():
    """建表（幂等，若表已存在则 ALTER 添加新列）"""
    conn = _get_conn()

    # market_data_realtime
    conn.execute("""
        CREATE TABLE IF NOT EXISTS market_data_realtime (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol       TEXT    NOT NULL,
            name         TEXT,
            market       TEXT    NOT NULL,
            price        REAL,
            change_pct   REAL,
            volume       REAL,
            timestamp    INTEGER NOT NULL,
            data_type    TEXT    DEFAULT 'index',
            created_at   INTEGER DEFAULT (unixepoch())
        );
    """)
    # 增量添加可能缺失的列（旧表升级）
    for col_sql in [
        "ALTER TABLE market_data_realtime ADD COLUMN name TEXT;",
        "ALTER TABLE market_data_realtime ADD COLUMN data_type TEXT DEFAULT 'index';",
        "ALTER TABLE market_data_realtime ADD COLUMN created_at INTEGER DEFAULT (unixepoch());",
    ]:
        try:
            conn.execute(col_sql)
        except Exception:
            pass

    # write_buffer
    conn.execute("""
        CREATE TABLE IF NOT EXISTS write_buffer (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol       TEXT    NOT NULL,
            name         TEXT,
            market       TEXT    NOT NULL,
            price        REAL,
            change_pct   REAL,
            volume       REAL,
            timestamp    INTEGER NOT NULL,
            data_type    TEXT    DEFAULT 'index',
            buffered_at  INTEGER DEFAULT (unixepoch())
        );
    """)
    for col_sql in [
        "ALTER TABLE write_buffer ADD COLUMN name TEXT;",
        "ALTER TABLE write_buffer ADD COLUMN data_type TEXT DEFAULT 'index';",
        "ALTER TABLE write_buffer ADD COLUMN buffered_at INTEGER DEFAULT (unixepoch());",
    ]:
        try:
            conn.execute(col_sql)
        except Exception:
            pass

    conn.execute("CREATE INDEX IF NOT EXISTS idx_realtime_symbol_ts ON market_data_realtime(symbol, timestamp);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_buffer_symbol ON write_buffer(symbol);")
    conn.commit()


def buffer_insert(rows: list[dict]):
    """
    将行情数据批量写入缓冲表（事务保护）
    rows: [{symbol, name, market, price, change_pct, volume, timestamp, data_type}, ...]
    """
    if not rows:
        return
    conn = _get_conn()
    now = int(time.time())
    conn.executemany(
        """INSERT INTO write_buffer
           (symbol, name, market, price, change_pct, volume, timestamp, data_type, buffered_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [(r["symbol"], r.get("name"), r["market"], r.get("price"),
          r.get("change_pct"), r.get("volume"), r["timestamp"],
          r.get("data_type", "index"), now)
         for r in rows]
    )
    conn.commit()


def flush_buffer_to_realtime() -> int:
    """
    将 write_buffer 批量刷入 market_data_realtime（事务保护）
    返回刷入行数
    """
    conn = _get_conn()
    cursor = conn.execute("SELECT COUNT(*) FROM write_buffer;")
    count = cursor.fetchone()[0]
    if count == 0:
        return 0

    conn.execute("""
        INSERT INTO market_data_realtime
            (symbol, name, market, price, change_pct, volume, timestamp, data_type, created_at)
        SELECT symbol, name, market, price, change_pct, volume, timestamp, data_type, buffered_at
        FROM write_buffer;
    """)
    conn.execute("DELETE FROM write_buffer;")
    conn.commit()
    return count


def get_latest_prices(symbols: list[str], data_type: str | None = None) -> list[dict]:
    """
    查询每只标的最新一条行情（按 symbol 分组取 timestamp 最大）
    若 data_type=None 则不限制类型
    """
    conn = _get_conn()
    placeholders = ",".join("?" * len(symbols))
    if data_type is not None:
        query = f"""
            SELECT symbol, name, market, price, change_pct, volume, timestamp, data_type
            FROM market_data_realtime
            WHERE symbol IN ({placeholders})
              AND data_type = ?
            GROUP BY symbol
            HAVING timestamp = MAX(timestamp);"""
        rows = conn.execute(query, (*symbols, data_type)).fetchall()
    else:
        query = f"""
            SELECT symbol, name, market, price, change_pct, volume, timestamp, data_type
            FROM market_data_realtime
            WHERE symbol IN ({placeholders})
            GROUP BY symbol
            HAVING timestamp = MAX(timestamp);"""
        rows = conn.execute(query, (*symbols,)).fetchall()
    return [
        {"symbol": r[0], "name": r[1], "market": r[2],
         "price": r[3], "change_pct": r[4], "volume": r[5],
         "timestamp": r[6], "data_type": r[7]}
        for r in rows
    ]


def get_price_history(symbol: str, limit: int = 100) -> list[dict]:
    """查询某标的历史行情（用于图表）"""
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
