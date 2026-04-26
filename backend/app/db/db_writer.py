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

def _get_conn():
    """创建数据库连接（每批次新建，复用连接池不值得）"""
    conn = sqlite3.connect(_db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    
    # WAL 模式检测：基于文件系统类型而非路径字符串
    # 网络文件系统（NFS/SMB/CIFS）不支持 WAL，需使用 DELETE 模式
    import os
    _db_dir = os.path.dirname(_db_path) or os.getcwd()
    
    # 检测是否为网络文件系统或特殊路径
    _use_delete_mode = False
    
    # 方法1：路径特征检测（快速判断已知网络存储路径）
    network_path_prefixes = ['/vol3/', '/nas/', '/mnt/nfs', '/mnt/smb', '/net/']
    if any(_db_path.startswith(p) for p in network_path_prefixes):
        _use_delete_mode = True
    
    # 方法2：尝试 stat 获取文件系统信息（更可靠）
    if not _use_delete_mode:
        try:
            # macOS/Linux: stat -f '%T' 或检查 st_dev 类型
            # 如果无法确定，尝试启用 WAL 并检查结果
            cur = conn.execute("PRAGMA journal_mode=WAL")
            result = cur.fetchone()
            if result and result[0] == "wal":
                # WAL 成功启用，验证 -wal 和 -shm 文件是否可创建
                wal_path = _db_path + "-wal"
                shm_path = _db_path + "-shm"
                # 尝试写入测试，确认 WAL 文件可正常创建
                conn.execute("CREATE TABLE IF NOT EXISTS _wal_test (id INTEGER)")
                conn.execute("INSERT INTO _wal_test VALUES (1)")
                conn.commit()
                conn.execute("DROP TABLE IF EXISTS _wal_test")
                conn.commit()
                # 如果以上操作成功，WAL 模式可用
            else:
                _use_delete_mode = True
        except (sqlite3.OperationalError, OSError, IOError) as e:
            # WAL 启用失败（可能是网络文件系统不支持）
            logger.warning(f"[DBWriter] WAL mode unavailable: {e}, using DELETE mode")
            _use_delete_mode = True
    
    if _use_delete_mode:
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
    """
    DBWriterThread 主体：死循环从队列取任务执行。
    退出条件：_shutdown_flag 被 set() 且队列完全清空。
    """
    conn = None
    try:
        conn = _get_conn()
        logger.info("[DBWriter] 🟢 started (queue maxsize=%s)", _write_queue.maxsize)
        while True:
            try:
                # block=True, timeout=1 — 每秒检查一次 shutdown_flag
                task = _write_queue.get(block=True, timeout=1.0)
            except queue.Empty:
                if _shutdown_flag.is_set():
                    # 队列已空，退出
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
    """
    将写入任务投入队列，立即返回（< 1ms）。
    task = {"type": T_DAILY|T_PERIODIC|T_REALTIME|T_ALLSTOCKS|T_BUFFER,
            "rows": [...], "period": "weekly" (optional)}
    """
    _write_queue.put(task)
    qsize = _write_queue.qsize()
    logger.debug(f"[DBQueue] enqueued {task.get('type')} ({len(task.get('rows', []))} rows), queue_size={qsize}")


def start_writer():
    """在 lifespan 启动时调用（main.py）"""
    global _writer_thread
    if _writer_thread is None or not _writer_thread.is_alive():
        _shutdown_flag.clear()
        _writer_thread = threading.Thread(target=db_writer_loop, name="DBWriter", daemon=True)
        _writer_thread.start()
        logger.info("[DBWriter] thread started")


def stop_writer():
    """
    在 lifespan 关闭时调用（main.py）：
    1. 通知 writer 停止（shutdown_flag）
    2. 等待最多 30s 让队列排空
    3. 强制终止（daemon 线程会被外层进程终止）
    """
    logger.info("[DBWriter] initiating graceful shutdown...")
    _shutdown_flag.set()

    if _writer_thread and _writer_thread.is_alive():
        remaining = _write_queue.qsize()
        if remaining > 0:
            logger.info(f"[DBWriter] waiting for {remaining} tasks to flush (max 30s)...")
        # 等待队列自然排空（最多 30s）
        _writer_thread.join(timeout=30)
        if _writer_thread.is_alive():
            logger.warning(f"[DBWriter] ⚠️  {remaining} tasks still in queue after 30s timeout")
        else:
            logger.info("[DBWriter] ✅ all tasks flushed, writer thread exited cleanly")
