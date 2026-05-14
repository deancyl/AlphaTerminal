import sqlite3
import threading
import json
import logging
import os
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)
# 使用工作区根目录的 database.db（包含示例数据）
_db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'database.db')
_lock = threading.RLock()

# ── 线程级连接池（SQLite连接非线程安全，每个线程复用自己的连接）────────────────
_thread_local = threading.local()
_WAL_MODE_CHECKED = False
_USE_WAL = True

def _get_thread_conn():
    """获取当前线程的连接（复用，不频繁创建/关闭）"""
    global _WAL_MODE_CHECKED, _USE_WAL
    
    if not hasattr(_thread_local, 'conn') or _thread_local.conn is None:
        conn = sqlite3.connect(_db_path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        
        # WAL模式检测（仅首次）
        if not _WAL_MODE_CHECKED:
            if "/vol3/" in _db_path or "/tmp/" in _db_path or "/nas/" in _db_path:
                _USE_WAL = False
            else:
                try:
                    cur = conn.execute("PRAGMA journal_mode=WAL")
                    if cur.fetchone()[0] != "wal":
                        _USE_WAL = False
                except sqlite3.OperationalError:
                    _USE_WAL = False
            _WAL_MODE_CHECKED = True
        
        if _USE_WAL:
            conn.execute("PRAGMA journal_mode=WAL")
        else:
            conn.execute("PRAGMA journal_mode=DELETE")
        
        conn.execute("PRAGMA busy_timeout=30000")
        _thread_local.conn = conn
        logger.debug(f"[DB] Created new connection for thread {threading.current_thread().name}")
    
    return _thread_local.conn

def _close_thread_conn():
    """关闭当前线程的连接（用于清理）"""
    if hasattr(_thread_local, 'conn') and _thread_local.conn:
        _thread_local.conn.close()
        _thread_local.conn = None

@contextmanager
def get_conn():
    """上下文管理器：获取线程级连接（复用，不频繁关闭）"""
    conn = _get_thread_conn()
    try:
        yield conn
    except Exception:
        # 发生异常时回滚事务
        try:
            conn.rollback()
        except Exception:
            pass
        raise

def _get_conn():
    """兼容旧代码：返回新连接（用于需要独立连接的场景）"""
    conn = sqlite3.connect(_db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    if _USE_WAL:
        conn.execute("PRAGMA journal_mode=WAL")
    else:
        conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

# 延迟导入，避免循环依赖
from app.db.db_writer import enqueue, T_DAILY, T_PERIODIC, T_REALTIME, T_ALLSTOCKS, T_BUFFER

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
        conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_sym_date ON market_data_daily(symbol, date DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_periodic_sym_period_date ON market_data_periodic(symbol, period, date DESC)")
        # ── Admin 系统配置持久化 ────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        # ── Phase 1: 子账户系统增强 ───────────────────────────────
        # portfolios 表结构增强（新增字段，兼容存量数据）
        for col, dtype, default in [
            ("parent_id",      "INTEGER", "DEFAULT NULL"),
            ("cash_balance",   "REAL",    "DEFAULT 0.0"),
            ("currency",       "TEXT",     "DEFAULT 'CNY'"),
            ("asset_class",    "TEXT",     "DEFAULT 'mixed'"),
            ("initial_capital","REAL",    "DEFAULT 0.0"),
            ("status",         "TEXT",     "DEFAULT 'active'"),
            ("strategy",      "TEXT",     "DEFAULT NULL"),
            ("benchmark",     "TEXT",     "DEFAULT NULL"),
            ("description",    "TEXT",     "DEFAULT NULL"),
        ]:
            try:
                conn.execute(f"ALTER TABLE portfolios ADD COLUMN {col} {dtype} {default}")
            except Exception:
                pass  # 列已存在时静默忽略
        conn.execute("CREATE INDEX IF NOT EXISTS idx_portfolios_parent ON portfolios(parent_id)")

        # transactions 资金流水表（审计基石）
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_id    INTEGER NOT NULL,
                type            TEXT NOT NULL,
                amount          REAL NOT NULL,
                balance_after   REAL NOT NULL,
                counterparty_id  INTEGER DEFAULT NULL,
                related_symbol  TEXT DEFAULT NULL,
                note            TEXT DEFAULT NULL,
                created_at      TEXT NOT NULL,
                operator        TEXT DEFAULT 'system'
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_txn_portfolio ON transactions(portfolio_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_txn_type     ON transactions(type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_txn_created  ON transactions(created_at)")

        # ── Phase 2: 持仓批次追踪（Lots）────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS position_lots (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_id    INTEGER NOT NULL,
                symbol          TEXT NOT NULL,
                shares          INTEGER NOT NULL,        -- 本批次剩余股数（动态递减）
                avg_cost        REAL NOT NULL,           -- 本批次买入均价
                buy_date        TEXT NOT NULL,           -- 买入日期（date）
                buy_order_id    TEXT DEFAULT NULL,       -- 来源订单号（可选）
                status          TEXT NOT NULL DEFAULT 'open',  -- 'open' | 'closed'
                closed_at       TEXT DEFAULT NULL,       -- 平仓日期
                realized_pnl    REAL DEFAULT 0.0,         -- 已实现盈亏（平仓时计算）
                created_at      TEXT NOT NULL,
                UNIQUE(portfolio_id, symbol, buy_order_id, buy_date)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_lots_port_sym ON position_lots(portfolio_id, symbol)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_lots_status  ON position_lots(status)")

        # ── Phase 3: 持仓聚合视图表（Read-optimized summary）────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS position_summary (
                portfolio_id INTEGER NOT NULL,
                symbol       TEXT NOT NULL,
                total_shares INTEGER NOT NULL DEFAULT 0,
                avg_cost     REAL    NOT NULL DEFAULT 0.0,
                market_value REAL    NOT NULL DEFAULT 0.0,
                unrealized_pnl REAL NOT NULL DEFAULT 0.0,
                updated_at   TEXT    NOT NULL,
                PRIMARY KEY (portfolio_id, symbol)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_psym_portfolio ON position_summary(portfolio_id)")

        # ── 高可用缓存持久化表（SQLite-backed cache）───────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cache_persistence (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                hit_count INTEGER DEFAULT 0,
                size_bytes INTEGER DEFAULT 0,
                source TEXT DEFAULT ''
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache_persistence(expires_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_source ON cache_persistence(source)")

        # ── 基金净值历史表─────────────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fund_nav_history (
                fund_code TEXT NOT NULL,
                nav_date TEXT NOT NULL,
                unit_nav REAL,
                acc_nav REAL,
                daily_growth REAL,
                source TEXT DEFAULT 'akshare',
                PRIMARY KEY (fund_code, nav_date)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fund_nav_code ON fund_nav_history(fund_code)")

        conn.commit()
        conn.close()
        # ── 全市场个股缓存表 ──────────────────────────────────────
        init_all_stocks_table()
        # ── Strategy/Token/Audit 持久化表 ──────────────────────────────
        init_persistence_tables()
    logger.info(f"DB Ready: {_db_path}")

def buffer_insert(data_list):
    """写入 write_buffer（生产者：立即入队，不持有锁）"""
    if not data_list: return
    enqueue({"type": T_BUFFER, "rows": data_list})

def buffer_insert_daily(data_list):
    """
    写入 market_data_daily（生产者：立即入队，不持有锁）
    表列: id, symbol, date, open, high, low, close, volume, amount, turnover_rate, amplitude, timestamp, data_type
    """
    if not data_list: return
    enqueue({"type": T_DAILY, "rows": data_list})

def buffer_insert_periodic(data_list, period=None):
    """写入 market_data_periodic（生产者：立即入队，不持有锁）"""
    if not data_list: return
    enqueue({"type": T_PERIODIC, "rows": data_list, "period": period})

def flush_buffer_to_realtime():
    """将 write_buffer 刷新到 market_data_realtime（生产者：立即入队，不持有锁）"""
    enqueue({"type": T_REALTIME, "rows": []})

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

def init_persistence_tables():
    """初始化策略/Token/审计日志持久化表"""
    from app.db.strategy_db import init_strategy_table
    from app.db.token_db import init_token_table
    from app.db.audit_db import init_audit_table
    
    init_strategy_table()
    init_token_table()
    init_audit_table()

def upsert_all_stocks(rows):
    """批量写入全市场个股数据（生产者：立即入队，不持有锁）"""
    if not rows:
        return
    enqueue({"type": T_ALLSTOCKS, "rows": rows})

def search_stocks(
    keyword=None,
    min_pct_chg=None, max_pct_chg=None,
    min_turnover=None, max_turnover=None,
    min_price=None, max_price=None,
    min_pe=None, max_pe=None,
    min_pb=None, max_pb=None,
    min_mktcap=None, max_mktcap=None,
    sort_by='change_pct', sort_dir='desc',
    page=1, page_size=50
):
    """
    全市场个股服务端过滤+排序+分页
    解决 StockScreener 前端全量拉取 + computed 阻塞浏览器的性能瓶颈
    """
    conn = _get_conn()
    try:
        conditions = ["price > 0"]
        args = []

        if keyword:
            pattern = f"%{keyword}%"
            conditions.append("(code LIKE ? OR name LIKE ?)")
            args.extend([pattern, pattern])

        if min_pct_chg is not None:
            conditions.append("change_pct >= ?")
            args.append(float(min_pct_chg))
        if max_pct_chg is not None:
            conditions.append("change_pct <= ?")
            args.append(float(max_pct_chg))

        if min_turnover is not None:
            conditions.append("turnover >= ?")
            args.append(float(min_turnover))
        if max_turnover is not None:
            conditions.append("turnover <= ?")
            args.append(float(max_turnover))

        if min_price is not None:
            conditions.append("price >= ?")
            args.append(float(min_price))
        if max_price is not None:
            conditions.append("price <= ?")
            args.append(float(max_price))

        if min_pe is not None:
            conditions.append("per >= ?")
            args.append(float(min_pe))
        if max_pe is not None:
            conditions.append("per <= ?")
            args.append(float(max_pe))

        if min_pb is not None:
            conditions.append("pb >= ?")
            args.append(float(min_pb))
        if max_pb is not None:
            conditions.append("pb <= ?")
            args.append(float(max_pb))

        if min_mktcap is not None:
            conditions.append("mktcap >= ?")
            args.append(float(min_mktcap) * 1e8)  # 亿 → 元
        if max_mktcap is not None:
            conditions.append("mktcap <= ?")
            args.append(float(max_mktcap) * 1e8)

        ORDER_FIELDS = {
            'code': 'code', 'name': 'name', 'price': 'price',
            'change_pct': 'change_pct', 'turnover': 'turnover',
            'volume': 'volume', 'amount': 'amount',
            'per': 'per', 'pb': 'pb', 'mktcap': 'mktcap',
        }
        if sort_by not in ORDER_FIELDS:
            raise ValueError(f"Invalid sort_by: '{sort_by}'. Must be one of: {list(ORDER_FIELDS.keys())}")
        order_col = ORDER_FIELDS[sort_by]
        if sort_dir.upper() not in ('ASC', 'DESC'):
            raise ValueError(f"Invalid sort_dir: '{sort_dir}'. Must be 'asc' or 'desc'")
        order_dir = sort_dir.upper()

        where_clause = " AND ".join(conditions)

        # 统计总数
        count_sql = f"SELECT COUNT(*) as cnt FROM market_all_stocks WHERE {where_clause}"
        total = conn.execute(count_sql, args).fetchone()['cnt']

        # 分页
        offset = max(0, (max(1, page) - 1) * min(200, max(1, page_size)))
        limit = min(200, max(1, page_size))

        query_sql = f"""
            SELECT code, name, price, change_pct, per, pb, mktcap, nmc,
                   turnover, volume, amount, price_high, price_low, open_price, updated_at
            FROM market_all_stocks
            WHERE {where_clause}
            ORDER BY {order_col} {order_dir}
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(query_sql, [*args, limit, offset]).fetchall()

        # 序列化（补充 computed 字段）
        result = []
        for r in rows:
            price = float(r['price'] or 0)
            change_pct = float(r['change_pct'] or 0)
            prev = price / (1 + change_pct / 100) if change_pct != -100 else price
            result.append({
                "code": r['code'],
                "name": r['name'],
                "price": price,
                "change_pct": change_pct,
                "change": round(price - prev, 3),
                "turnover": float(r['turnover'] or 0),
                "volume": float(r['volume'] or 0),
                "amount": float(r['amount'] or 0),
                "pe": float(r['per'] or 0) if r['per'] else 0,
                "pb": float(r['pb'] or 0) if r['pb'] else 0,
                "mktcap": round(float(r['mktcap'] or 0) / 1e8, 2),
                "price_high": float(r['price_high'] or 0),
                "price_low": float(r['price_low'] or 0),
                "open_price": float(r['open_price'] or 0),
            })

        return total, result, page, page_size

    finally:
        conn.close()

def get_all_stocks(limit=5000, offset=0, search=None):
    """获取全市场个股列表，支持搜索"""
    # WAL 模式支持并发读，不再需要应用层锁
    conn = _get_conn()
    try:
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
        # 数据处理放在 try 块内，确保连接有效
        rows_list = [dict(r) for r in rows]
        # 补充 change 字段（数据库只有 change_pct）
        for r in rows_list:
            price = float(r.get('price') or 0)
            change_pct = float(r.get('change_pct') or 0)
            if 'change' not in r or r.get('change') is None:
                r['change'] = round(price * change_pct / 100, 3)
        return total, rows_list
    finally:
        conn.close()


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
    # WAL 模式支持并发读
    conn = _get_conn()
    try:
        cnt = conn.execute("SELECT COUNT(*) as cnt FROM market_all_stocks WHERE price > 0").fetchone()['cnt']
        return cnt
    finally:
        conn.close()

# ═══════════════════════════════════════════════════════════════════════════
# Admin 系统配置持久化
# ═══════════════════════════════════════════════════════════════════════════

def get_admin_config(key: str, default=None):
    """读取 admin 配置项（JSON 字符串），不存在则返回 default"""
    with _lock:
        conn = _get_conn()
        try:
            row = conn.execute(
                "SELECT value FROM admin_config WHERE key = ?", (key,)
            ).fetchone()
            if row is None:
                return default
            try:
                import json as _json
                return _json.loads(row['value'])
            except Exception:
                return row['value']
        finally:
            conn.close()

def set_admin_config(key: str, value):
    """写入 admin 配置项（自动 JSON 序列化）"""
    import json as _json
    with _lock:
        conn = _get_conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO admin_config (key, value, updated_at) VALUES (?, ?, ?)",
                (key, _json.dumps(value), datetime.now().isoformat())
            )
            conn.commit()
        finally:
            conn.close()

def get_all_admin_configs():
    """读取所有 admin 配置项"""
    with _lock:
        conn = _get_conn()
        try:
            rows = conn.execute("SELECT key, value FROM admin_config").fetchall()
            import json as _json
            result = {}
            for r in rows:
                try:
                    result[r['key']] = _json.loads(r['value'])
                except Exception:
                    result[r['key']] = r['value']
            return result
        finally:
            conn.close()
