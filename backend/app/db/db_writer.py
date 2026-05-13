"""
db_writer.py — 异步数据库写入队列（生产者-消费者模式）

背景：所有 buffer_insert* 操作原本持有 threading.RLock() 全局锁，
在 APScheduler 全量拉取时会独占锁 300ms+，阻塞所有读 API。

改造后：
- buffer_insert* → 生产者：将任务包 enqueue() 后立即返回（< 1ms）
- DBWriterThread → 单一消费者：在独立线程中串行执行所有写入
- 读操作（get_*）→ 保持无锁（WAL 模式本身支持并发读）
"""
import queue
import threading
import logging
import sqlite3
import os
import json
import time

logger = logging.getLogger(__name__)

# ── 全局队列（模块级单例）───────────────────────────────────────
_write_queue: queue.Queue = queue.Queue()
_shutdown_flag = threading.Event()
_writer_thread: threading.Thread | None = None

# ── 健康监控（Iteration 1-3 新增）───────────────────────────────────────
_last_heartbeat: float = 0.0
_items_processed: int = 0
_writer_start_time: float = 0.0
_heartbeat_lock = threading.Lock()

# ── 数据库路径（与 database.py 保持一致）───────────────────────
_db_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    'database.db'
)

# ── 任务类型常量 ────────────────────────────────────────────────
T_DAILY     = 'daily'       # market_data_daily
T_PERIODIC  = 'periodic'    # market_data_periodic
T_REALTIME  = 'realtime'    # flush write_buffer → market_data_realtime
T_ALLSTOCKS = 'all_stocks' # 全市场个股 upsert
T_BUFFER    = 'buffer'      # write_buffer INSERT


# ═══════════════════════════════════════════════════════════════
# 消费者：DBWriterThread
# ═══════════════════════════════════════════════════════════════

_WAL_MODE_CHECKED = False
_WAL_MODE_OK = True

def _get_conn():
    """创建数据库连接（每批次新建，复用连接池不值得）"""
    global _WAL_MODE_CHECKED, _WAL_MODE_OK
    conn = sqlite3.connect(_db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    
    # WAL 模式检测：仅在首次启动时执行，后续直接复用结果
    import os
    _db_dir = os.path.dirname(_db_path) or os.getcwd()
    
    if not _WAL_MODE_CHECKED:
        # 检测是否为网络文件系统或特殊路径
        _use_delete_mode = False
        network_path_prefixes = ['/vol3/', '/nas/', '/mnt/nfs', '/mnt/smb', '/net/']
        if any(_db_path.startswith(p) for p in network_path_prefixes):
            _use_delete_mode = True
        
        if not _use_delete_mode:
            try:
                cur = conn.execute("PRAGMA journal_mode=WAL")
                result = cur.fetchone()
                if result and result[0] == "wal":
                    _WAL_MODE_OK = True
                else:
                    _use_delete_mode = True
            except (sqlite3.OperationalError, OSError, IOError):
                _use_delete_mode = True
        
        if _use_delete_mode:
            conn.execute("PRAGMA journal_mode=DELETE")
            conn.commit()
            _WAL_MODE_OK = False
            logger.warning("[DBWriter] WAL mode unavailable, using DELETE mode")
        
        _WAL_MODE_CHECKED = True
    else:
        # 后续连接：直接使用已检测的模式
        if _WAL_MODE_OK:
            conn.execute("PRAGMA journal_mode=WAL")
        else:
            conn.execute("PRAGMA journal_mode=DELETE")
    
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def _write_daily(conn, rows):
    ok = fail = 0
    for i in rows:
        try:
            conn.execute(
                "INSERT OR REPLACE INTO market_data_daily "
                "(symbol, date, open, high, low, close, volume, amount, "
                "turnover_rate, amplitude, timestamp, data_type) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (str(i.get('symbol','')), str(i.get('date','')),
                 float(i.get('open',0)), float(i.get('high',0)),
                 float(i.get('low',0)), float(i.get('close',0)),
                 int(i.get('volume',0)), float(i.get('amount', 0.0)),
                 float(i.get('turnover_rate', 0.0)),
                 float(i.get('amplitude', 0.0)),
                 int(i.get('timestamp',0)),
                 str(i.get('data_type','daily')))
            )
            ok += 1
        except Exception as e:
            fail += 1
            logger.error(f"[DBWriter] daily insert failed: symbol={i.get('symbol')}, error={e}")
    conn.commit()
    return ok, fail


def _write_periodic(conn, rows, period):
    ok = 0
    for i in rows:
        try:
            p = period or i.get('period', 'weekly')
            conn.execute(
                "INSERT OR REPLACE INTO market_data_periodic "
                "(symbol, date, period, open, high, low, close, volume, change_pct, timestamp) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (i.get('symbol',''), i.get('date',''), p,
                 i.get('open',0), i.get('high',0), i.get('low',0),
                 i.get('close',0), i.get('volume',0),
                 i.get('change_pct',0), i.get('timestamp',0))
            )
            ok += 1
        except Exception as e:
            logger.error(f"[DBWriter] periodic insert failed: {e}")
    conn.commit()
    return ok, 0


def _flush_realtime(conn):
    rows = conn.execute("SELECT * FROM write_buffer").fetchall()
    processed_keys = []
    error_count = 0
    for r in rows:
        try:
            d = json.loads(r["data"])
            conn.execute("""
                INSERT OR REPLACE INTO market_data_realtime
                (symbol, name, price, change_pct, volume, market, data_type, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (r["symbol"], r["name"], d.get("price",0), d.get("change_pct",0),
                  d.get("volume",0), d.get("market",""), d.get("data_type",""),
                  d.get("timestamp",0)))
            processed_keys.append((r["symbol"], r["name"]))
        except Exception:
            error_count += 1
    if processed_keys:
        placeholders = ",".join(["(?,?)"] * len(processed_keys))
        flat = [item for pair in processed_keys for item in pair]
        conn.execute(f"DELETE FROM write_buffer WHERE (symbol, name) IN (VALUES {placeholders})", flat)
    conn.commit()
    return len(processed_keys), error_count


def _write_all_stocks(conn, rows):
    ok = 0
    for r in rows:
        try:
            conn.execute("""
                INSERT OR REPLACE INTO market_all_stocks
                (symbol, code, name, price, change_pct, per, pb, mktcap, nmc,
                 volume, amount, turnover, price_high, price_low, open_price, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
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
                time.time()
            ))
            ok += 1
        except Exception as e:
            logger.error(f"[DBWriter] all_stocks upsert failed: {e}")
    conn.commit()
    return ok, 0


def _write_buffer(conn, rows):
    ok = 0
    for item in rows:
        try:
            conn.execute("INSERT INTO write_buffer VALUES (?,?,?)",
                (item.get('symbol',''), item.get('name',''), json.dumps(item)))
            ok += 1
        except Exception as e:
            logger.error(f"[DBWriter] buffer insert failed: {e}")
    conn.commit()
    return ok, 0


def db_writer_loop():
    conn = None
    try:
        conn = _get_conn()
        logger.info("[DBWriter] 🟢 started (queue maxsize=%s)", _write_queue.maxsize)
        while True:
            try:
                task = _write_queue.get(block=True, timeout=1.0)
            except queue.Empty:
                if _shutdown_flag.is_set():
                    break
                continue

            task_type = task.get('type')
            rows      = task.get('rows', [])
            period    = task.get('period')
            count     = len(rows)
            t0        = time.monotonic()

            try:
                if task_type == T_DAILY:
                    ok, fail = _write_daily(conn, rows)
                    logger.info(f"[DBWriter] ✅ daily {ok} rows" + (f", {fail} failed" if fail else ""))

                elif task_type == T_PERIODIC:
                    ok, fail = _write_periodic(conn, rows, period)
                    logger.info(f"[DBWriter] ✅ periodic {ok} rows")

                elif task_type == T_REALTIME:
                    ok_cnt, err_cnt = _flush_realtime(conn)
                    logger.info(f"[DBWriter] ✅ realtime flush {ok_cnt} rows" + (f", {err_cnt} failed" if err_cnt else ""))

                elif task_type == T_ALLSTOCKS:
                    ok, fail = _write_all_stocks(conn, rows)
                    logger.info(f"[DBWriter] ✅ all_stocks {ok} rows")

                elif task_type == T_BUFFER:
                    ok, fail = _write_buffer(conn, rows)
                    logger.info(f"[DBWriter] ✅ buffer {ok} rows")

                else:
                    logger.warning(f"[DBWriter] unknown task type: {task_type}")

                elapsed = (time.monotonic() - t0) * 1000
                logger.debug(f"[DBWriter] completed in {elapsed:.1f}ms")

                with _heartbeat_lock:
                    global _last_heartbeat, _items_processed
                    _last_heartbeat = time.time()
                    _items_processed += 1

            except Exception as e:
                logger.error(f"[DBWriter] task execution error: {e}", exc_info=True)

            finally:
                _write_queue.task_done()

    except Exception as e:
        logger.error(f"[DBWriter] fatal error: {e}", exc_info=True)
    finally:
        if conn:
            try: conn.close()
            except Exception: pass
        logger.info("[DBWriter] 🔴 stopped")


# ═══════════════════════════════════════════════════════════════
# 生产者接口（供 database.py 调用）
# ═══════════════════════════════════════════════════════════════

def enqueue(task: dict):
    _write_queue.put(task)
    qsize = _write_queue.qsize()
    logger.debug(f"[DBQueue] enqueued {task.get('type')} ({len(task.get('rows', []))} rows), queue_size={qsize}")
    ensure_writer_running()


def ensure_writer_running():
    global _writer_thread
    if _writer_thread is None or not _writer_thread.is_alive():
        logger.warning("[DBQueue] writer thread not running, starting...")
        start_writer()


def is_writer_healthy() -> dict:
    with _heartbeat_lock:
        return {
            "is_alive": _writer_thread.is_alive() if _writer_thread else False,
            "queue_size": _write_queue.qsize(),
            "last_heartbeat": _last_heartbeat,
            "items_processed": _items_processed,
            "uptime": time.time() - _writer_start_time if _writer_start_time > 0 else 0,
        }


def start_writer():
    global _writer_thread, _writer_start_time
    if _writer_thread is None or not _writer_thread.is_alive():
        _shutdown_flag.clear()
        _writer_start_time = time.time()
        _writer_thread = threading.Thread(target=db_writer_loop, name="DBWriter", daemon=True)
        _writer_thread.start()
        logger.info("[DBWriter] thread started")


def stop_writer():
    logger.info("[DBWriter] initiating graceful shutdown...")
    _shutdown_flag.set()

    if _writer_thread and _writer_thread.is_alive():
        remaining = _write_queue.qsize()
        if remaining > 0:
            logger.info(f"[DBWriter] waiting for {remaining} tasks to flush (max 30s)...")
        _writer_thread.join(timeout=30)
        if _writer_thread.is_alive():
            logger.warning(f"[DBWriter] ⚠️  {remaining} tasks still in queue after 30s timeout")
        else:
            logger.info("[DBWriter] ✅ all tasks flushed, writer thread exited cleanly")
