"""
SQLite 数据库管理 - Phase 3
WAL 模式 + 批量写入缓冲
"""
import logging
import sqlite3

logger = logging.getLogger(__name__)
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

    # Phase 7: 历史K线日线表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS market_data_daily (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol       TEXT    NOT NULL,
            date         TEXT    NOT NULL,
            open         REAL,
            high         REAL,
            low          REAL,
            close        REAL,
            volume       REAL,
            change_pct   REAL,
            timestamp    INTEGER NOT NULL,
            data_type    TEXT    DEFAULT 'daily',
            UNIQUE(symbol, date)
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_symbol_date ON market_data_daily(symbol, date);")
    # Phase 9: periodic 表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS market_data_periodic (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL, date TEXT NOT NULL, period TEXT NOT NULL,
            open REAL, high REAL, low REAL, close REAL,
            volume REAL, change_pct REAL, timestamp INTEGER NOT NULL,
            UNIQUE(symbol, date, period)
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_periodic_sym_date ON market_data_periodic(symbol, date, period);")
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



def buffer_insert_daily(rows: list[dict]):
    """
    将日K线数据批量写入 market_data_daily（UPSERT 语义）
    """
    if not rows:
        return
    # ── 防御性探针：若>50%的数据 close==high，说明数据源被污染，丢弃整批 ──
    if len(rows) >= 10:
        bad = sum(1 for r in rows if float(r.get("close") or 0) >= float(r.get("high") or 0) - 0.01 > 0
        bad_pct = bad / len(rows)
        if bad_pct > 0.5:
            import logging as _log
            _log.error(f"[DB BLOCK] close==high污染率{bad_pct:.0%} > 50%，数据被拒绝写入")
            return
    conn = _get_conn()
    for r in rows:
        o = r.get("open") or 0
        c = r.get("close") or 0
        h = r.get("high") or 0
        l = r.get("low") or 0
        # 防御性: 确保 high >= low
        if h < l:
            h, l = l, h
        # 确保 high >= open,close 且 low <= open,close
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
    """写入周K或月K数据"""
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


def get_periodic_history(symbol: str, period: str, limit: int = 200) -> list[dict]:
    """查询周K/月K历史"""
    conn = _get_conn()
    rows = conn.execute("""
        SELECT symbol, date, period, open, high, low, close, volume, change_pct, timestamp
        FROM market_data_periodic
        WHERE symbol = ? AND period = ?
        ORDER BY timestamp DESC LIMIT ?;
    """, (symbol, period, limit)).fetchall()
    rows = list(reversed(rows))
    return [
        {"symbol": r[0], "date": r[1], "period": r[2],
         "open": r[3], "high": r[4], "low": r[5], "close": r[6],
         "volume": r[7], "change_pct": r[8], "timestamp": r[9]}
        for r in rows
    ]



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


def get_daily_history(symbol: str, limit: int = 300) -> list[dict]:
    """
    Phase 7: 查询某标的历史日K线（从 market_data_daily）
    用于 ECharts K 线图表
    注意: DB存的是完整历史，API按 timestamp DESC 取最近 limit 条，
          返回前再 reverse() 成 ASC（图表要求 x轴从旧到新）。
    """
    conn = _get_conn()
    rows = conn.execute("""
        SELECT symbol, date, open, high, low, close, volume, change_pct, timestamp
        FROM market_data_daily
        WHERE symbol = ?
        ORDER BY timestamp DESC
        LIMIT ?;
    """, (symbol, limit)).fetchall()
    # reverse → ASC（最旧在前，最新在后，图表正确）
    rows = list(reversed(rows))
    return [
        {"symbol": r[0], "date": r[1],
         "open": r[2], "high": r[3], "low": r[4],
         "close": r[5], "volume": r[6],
         "change_pct": r[7], "timestamp": r[8]}
        for r in rows
    ]
