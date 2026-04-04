import sqlite3
import threading
import json
import logging
import os

logger = logging.getLogger(__name__)
# 使用工作区根目录的 database.db（包含示例数据）
# __file__ is /vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal/backend/app/db/database.py
# dirname(__file__) = /vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal/backend/app/db
# dirname(dirname(__file__)) = /vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal/backend/app
# dirname(dirname(dirname(__file__))) = /vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal/backend
# dirname(dirname(dirname(dirname(__file__)))) = /vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal
_db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'database.db')
_lock = threading.RLock()

def _get_conn():
    conn = sqlite3.connect(_db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    # 优先 WAL，目录无写权限时自动降级为 DELETE 模式
    try:
        cur = conn.execute("PRAGMA journal_mode=WAL")
        if cur.fetchone()[0] != "wal":
            conn.execute("PRAGMA journal_mode=DELETE")
    except sqlite3.OperationalError:
        conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

def init_tables():
    with _lock:
        conn = _get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS market_data_realtime (
                symbol TEXT PRIMARY KEY, name TEXT, price REAL, 
                change_pct REAL, volume REAL, market TEXT, 
                data_type TEXT, timestamp INTEGER
            )
        """)
        conn.execute("CREATE TABLE IF NOT EXISTS write_buffer (symbol TEXT, name TEXT, data TEXT)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS market_data_daily (
                symbol TEXT, date TEXT, open REAL, high REAL, low REAL, 
                close REAL, volume REAL, change_pct REAL, timestamp INTEGER,
                data_type TEXT DEFAULT 'daily', UNIQUE(symbol, date)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS market_data_periodic (
                symbol TEXT, date TEXT, period TEXT, open REAL, high REAL, 
                low REAL, close REAL, volume REAL, change_pct REAL, 
                timestamp INTEGER, UNIQUE(symbol, date, period)
            )
        """)
        conn.commit()
        conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_sym ON market_data_daily(symbol)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_periodic_sym_p ON market_data_periodic(symbol, period)")
        conn.commit()
        conn.close()
    print(f"✅ DB Ready: {_db_path}")

def buffer_insert(data_list):
    if not data_list: return
    with _lock:
        conn = _get_conn()
        for item in data_list:
            conn.execute("INSERT INTO write_buffer VALUES (?,?,?)", 
                        (item.get('symbol',''), item.get('name',''), json.dumps(item)))
        conn.commit(); conn.close()

def buffer_insert_daily(data_list):
    if not data_list: return
    with _lock:
        conn = _get_conn()
        for i in data_list:
            conn.execute("INSERT OR REPLACE INTO market_data_daily VALUES (?,?,?,?,?,?,?,?,?,?)",
                (i.get('symbol',''), i.get('date',''), i.get('open',0), i.get('high',0), i.get('low',0), 
                 i.get('close',0), i.get('volume',0), i.get('change_pct',0), i.get('timestamp',0), 'daily'))
        conn.commit(); conn.close()

def buffer_insert_periodic(data_list, period=None):
    if not data_list: return
    with _lock:
        conn = _get_conn()
        for i in data_list:
            p = period or i.get('period', 'weekly')
            conn.execute("INSERT OR REPLACE INTO market_data_periodic VALUES (?,?,?,?,?,?,?,?,?,?)",
                (i.get('symbol',''), i.get('date',''), p, i.get('open',0), i.get('high',0), i.get('low',0), 
                 i.get('close',0), i.get('volume',0), i.get('change_pct',0), i.get('timestamp',0)))
        conn.commit(); conn.close()

def flush_buffer_to_realtime():
    with _lock:
        conn = _get_conn()
        rows = conn.execute("SELECT * FROM write_buffer").fetchall()
        for r in rows:
            try:
                d = json.loads(r["data"])
                conn.execute("""
                    INSERT OR REPLACE INTO market_data_realtime 
                    (symbol, name, price, change_pct, volume, market, data_type, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (r["symbol"], r["name"], d.get("price",0), d.get("change_pct",0), 
                      d.get("volume",0), d.get("market",""), d.get("data_type",""), d.get("timestamp",0)))
            except Exception:
                continue
        conn.execute("DELETE FROM write_buffer")
        conn.commit(); conn.close()

def get_latest_prices(symbols=None, data_type='realtime'):
    with _lock:
        conn = _get_conn()
        # 极致防御：防止空列表导致 SQL 语法错误
        if symbols is not None and len(symbols) > 0:
            qs = ",".join(["?"] * len(symbols))
            rows = conn.execute(f"SELECT * FROM market_data_realtime WHERE symbol IN ({qs})", symbols).fetchall()
        else:
            rows = conn.execute("SELECT * FROM market_data_realtime WHERE data_type=?", (data_type,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

def get_daily_history(symbol, limit=300, offset=0):
    with _lock:
        conn = _get_conn()
        if offset > 0:
            rows = conn.execute(
                "SELECT * FROM market_data_daily WHERE symbol=? ORDER BY date DESC LIMIT ? OFFSET ?",
                (symbol, limit, offset)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM market_data_daily WHERE symbol=? ORDER BY date DESC LIMIT ?",
                (symbol, limit)
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

def get_daily_count(symbol):
    """返回某标的日K总数（用于 has_more 判断）"""
    with _lock:
        conn = _get_conn()
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM market_data_daily WHERE symbol=?",
            (symbol,)
        ).fetchone()
        conn.close()
        return row["cnt"] if row else 0

def get_periodic_history(symbol, period, limit=200, offset=0):
    with _lock:
        conn = _get_conn()
        if offset > 0:
            rows = conn.execute("""
                SELECT * FROM market_data_periodic WHERE symbol=? AND period=?
                ORDER BY date DESC LIMIT ? OFFSET ?
            """, (symbol, period, limit, offset)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM market_data_periodic WHERE symbol=? AND period=?
                ORDER BY date DESC LIMIT ?
            """, (symbol, period, limit)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

def get_periodic_count(symbol, period):
    """返回某标的某周期K线总数"""
    with _lock:
        conn = _get_conn()
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM market_data_periodic WHERE symbol=? AND period=?",
            (symbol, period)
        ).fetchone()
        conn.close()
        return row["cnt"] if row else 0

get_price_history = get_daily_history

def get_periodic_history(symbol, period, limit=200):
    with _lock:
        conn = _get_conn()
        rows = conn.execute("""
            SELECT * FROM market_data_periodic WHERE symbol=? AND period=? 
            ORDER BY date DESC LIMIT ?
        """, (symbol, period, limit)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
