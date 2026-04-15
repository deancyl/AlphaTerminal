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
    # 检测网络挂载路径，禁用 WAL 模式（SSHFS/FUSE 不支持 mmap）
    if "/vol3/" in _db_path or "/tmp/" in _db_path or "/nas/" in _db_path:
        conn.execute("PRAGMA journal_mode=DELETE")
    else:
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
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL, date TEXT NOT NULL,
                open REAL NOT NULL, high REAL NOT NULL, low REAL NOT NULL,
                close REAL NOT NULL, volume INTEGER NOT NULL,
                amount REAL DEFAULT 0.0,
                turnover_rate REAL DEFAULT 0.0,
                amplitude REAL DEFAULT 0.0,
                timestamp INTEGER NOT NULL,
                data_type TEXT NOT NULL DEFAULT 'daily',
                UNIQUE(symbol, date)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS market_data_periodic (
                symbol TEXT, date TEXT, period TEXT, open REAL, high REAL, 
                low REAL, close REAL, volume REAL, change_pct REAL, 
                timestamp INTEGER, UNIQUE(symbol, date, period)
            )
        """)
        # ── P3: 多账户模拟组合 ──────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS portfolios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                type TEXT NOT NULL DEFAULT 'main',
                created_at TEXT NOT NULL,
                total_cost REAL NOT NULL DEFAULT 0.0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                shares INTEGER NOT NULL DEFAULT 0,
                avg_cost REAL NOT NULL DEFAULT 0.0,
                updated_at TEXT NOT NULL,
                UNIQUE(portfolio_id, symbol),
                FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                total_asset REAL NOT NULL DEFAULT 0.0,
                total_cost REAL NOT NULL DEFAULT 0.0,
                UNIQUE(portfolio_id, date),
                FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE
            )
        """)
        conn.commit()
        conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_sym ON market_data_daily(symbol)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_periodic_sym_p ON market_data_periodic(symbol, period)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pos_port ON positions(portfolio_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_snap_port ON portfolio_snapshots(portfolio_id)")
        conn.commit()
        conn.close()
        # ── 全市场个股缓存表 ──────────────────────────────────────
        init_all_stocks_table()
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
    """
    写入 market_data_daily
    表列: id, symbol, date, open, high, low, close, volume, amount, turnover_rate, amplitude, timestamp, data_type
    """
    if not data_list: return
    with _lock:
        conn = _get_conn()
        ok = fail = 0
        for i in data_list:
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO market_data_daily "
                    "(symbol, date, open, high, low, close, volume, amount, turnover_rate, amplitude, timestamp, data_type) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (str(i.get('symbol','')), str(i.get('date','')),
                     float(i.get('open',0)), float(i.get('high',0)), float(i.get('low',0)),
                     float(i.get('close',0)), int(i.get('volume',0)),
                     float(i.get('amount', 0.0)),
                     float(i.get('turnover_rate', 0.0)),
                     float(i.get('amplitude', 0.0)),
                     int(i.get('timestamp',0)), str(i.get('data_type','daily'))))
                ok += 1
            except Exception as e:
                # 记录具体失败信息，便于排查
                fail += 1
                logger.error(f"[DB] buffer_insert_daily failed: symbol={i.get('symbol')}, date={i.get('date')}, error={e}")
                continue
        conn.commit()
        conn.close()
        if fail:
            logger.warning(f"[DB] buffer_insert_daily: {ok} ok, {fail} failed")
        else:
            logger.debug(f"[DB] buffer_insert_daily: {ok} rows inserted")

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
        # 先批量处理，只记录成功的行键；失败的保留在 buffer 中下次重试
        processed_keys = []   # [(symbol, name), ...]
        error_count = 0
        for r in rows:
            try:
                d = json.loads(r["data"])
                conn.execute("""
                    INSERT OR REPLACE INTO market_data_realtime
                    (symbol, name, price, change_pct, volume, market, data_type, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (r["symbol"], r["name"], d.get("price",0), d.get("change_pct",0),
                      d.get("volume",0), d.get("market",""), d.get("data_type",""), d.get("timestamp",0)))
                processed_keys.append((r["symbol"], r["name"]))
            except Exception:
                error_count += 1
                continue
        # 只删除成功写入的记录；失败的留在 buffer，下次重试
        if processed_keys:
            placeholders = ",".join(["(?,?)"] * len(processed_keys))
            flat = [item for pair in processed_keys for item in pair]
            conn.execute(f"DELETE FROM write_buffer WHERE (symbol, name) IN (VALUES {placeholders})", flat)
        conn.commit()
        conn.close()
        if error_count:
            logger.warning(f"[DB] flush: {len(processed_keys)} ok, {error_count} failed（保留buffer）")

def get_latest_prices(symbols=None, data_type='realtime'):
    # WAL模式下读操作无需全局锁（SQLite支持并发读）
    conn = _get_conn()
    try:
        if symbols is not None and len(symbols) > 0:
            qs = ",".join(["?"] * len(symbols))
            rows = conn.execute(f"SELECT * FROM market_data_realtime WHERE symbol IN ({qs})", symbols).fetchall()
        else:
            rows = conn.execute("SELECT * FROM market_data_realtime WHERE data_type=?", (data_type,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_daily_history(symbol, limit=300, offset=0):
    # WAL模式下读操作无需全局锁
    conn = _get_conn()
    try:
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
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_daily_count(symbol):
    """返回某标的日K总数（用于 has_more 判断）"""
    # WAL模式下读操作无需全局锁
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM market_data_daily WHERE symbol=?",
            (symbol,)
        ).fetchone()
        return row["cnt"] if row else 0
    finally:
        conn.close()

def get_periodic_count(symbol, period):
    """返回某标的某周期K线总数"""
    # WAL模式下读操作无需全局锁
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM market_data_periodic WHERE symbol=? AND period=?",
            (symbol, period)
        ).fetchone()
        return row["cnt"] if row else 0
    finally:
        conn.close()

def get_periodic_history(symbol, period, limit=200, offset=0):
    """获取周期K线（周线/月线），支持分页"""
    # WAL模式下读操作无需全局锁
    conn = _get_conn()
    try:
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
        return [dict(r) for r in rows]
    finally:
        conn.close()

get_price_history = get_daily_history

# ═══════════════════════════════════════════════════════════════
# 全市场个股缓存 (all_stocks)
# ═══════════════════════════════════════════════════════════════

def init_all_stocks_table():
    """初始化全市场个股表"""
    with _lock:
        conn = _get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS market_all_stocks (
                symbol      TEXT PRIMARY KEY,
                code        TEXT,
                name        TEXT,
                price       REAL,
                change_pct  REAL,
                per         REAL,
                pb          REAL,
                mktcap      REAL,
                nmc         REAL,
                volume       REAL,
                amount       REAL,
                turnover     REAL,
                price_high   REAL,
                price_low    REAL,
                open_price   REAL,
                updated_at   REAL
            )
        """)
        conn.commit()
        conn.close()

def upsert_all_stocks(rows):
    """批量写入全市场个股数据"""
    if not rows:
        return
    with _lock:
        conn = _get_conn()
        conn.executemany("""
            INSERT OR REPLACE INTO market_all_stocks
            (symbol, code, name, price, change_pct, per, pb, mktcap, nmc, volume, amount, turnover, price_high, price_low, open_price, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                r['symbol'], r['code'], r['name'],
                float(r.get('trade') or 0),
                float(r.get('changepercent') or 0),
                float(r.get('per') or 0) if r.get('per') not in (None, '') else None,
                float(r.get('pb') or 0) if r.get('pb') not in (None, '') else None,
                float(r.get('mktcap') or 0),
                float(r.get('nmc') or 0),
                float(r.get('volume') or 0),
                float(r.get('amount') or 0),
                float(r.get('turnoverratio') or 0),
                float(r.get('high') or 0),
                float(r.get('low') or 0),
                float(r.get('open') or 0),
                __import__('time').time()
            )
            for r in rows
        ])
        conn.commit()
        conn.close()

def get_all_stocks(limit=5000, offset=0, search=None):
    """获取全市场个股列表，支持搜索"""
    with _lock:
        conn = _get_conn()
        if search:
            pattern = f"%{search}%"
            rows = conn.execute("""
                SELECT * FROM market_all_stocks
                WHERE (code LIKE ? OR name LIKE ?) AND price > 0
                ORDER BY code
                LIMIT ? OFFSET ?
            """, (pattern, pattern, limit, offset)).fetchall()
            total = conn.execute("""
                SELECT COUNT(*) AS cnt FROM market_all_stocks
                WHERE (code LIKE ? OR name LIKE ?) AND price > 0
            """, (pattern, pattern)).fetchone()['cnt']
        else:
            rows = conn.execute("""
                SELECT * FROM market_all_stocks WHERE price > 0
                ORDER BY code LIMIT ? OFFSET ?
            """, (limit, offset)).fetchall()
            total = conn.execute("SELECT COUNT(*) AS cnt FROM market_all_stocks WHERE price > 0").fetchone()['cnt']
        conn.close()
        rows_list = [dict(r) for r in rows]
        # 补充 change 字段（数据库只有 change_pct）
        for r in rows_list:
            price = float(r.get('price') or 0)
            change_pct = float(r.get('change_pct') or 0)
            if 'change' not in r or r.get('change') is None:
                r['change'] = round(price * change_pct / 100, 3)
        return total, rows_list


def get_all_stocks_lite():
    """轻量全量查询：只返回 StockScreener 需要的字段，无分页"""
    # WAL模式下读操作无需锁
    conn = _get_conn()
    try:
        rows = conn.execute("""
            SELECT code, name, price, change_pct, turnover, volume, amount, per, pb, mktcap
            FROM market_all_stocks WHERE price > 0 ORDER BY code
        """).fetchall()
        result = []
        for r in rows:
            price = float(r['price'] or 0)
            change_pct = float(r['change_pct'] or 0)
            prev = price / (1 + change_pct / 100) if change_pct != -100 else price
            change = round(price - prev, 3)
            result.append({
                "code": r['code'],
                "name": r['name'],
                "price": price,
                "change_pct": change_pct,
                "change": change,
                "turnover": float(r['turnover'] or 0),
                "volume": float(r['volume'] or 0),
                "amount": float(r['amount'] or 0),
                "pe": float(r['per'] or 0) if r['per'] else 0,  # PE
                "pb": float(r['pb'] or 0) if r['pb'] else 0,    # PB
                "mktcap": float(r['mktcap'] or 0) / 100000000,  # 市值(亿)
            })
        return result
    finally:
        conn.close()

def get_all_stocks_count():
    """返回全市场个股总数"""
    with _lock:
        conn = _get_conn()
        cnt = conn.execute("SELECT COUNT(*) as cnt FROM market_all_stocks WHERE price > 0").fetchone()['cnt']
        conn.close()
        return cnt
