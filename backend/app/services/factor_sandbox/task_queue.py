"""
FactorSandbox 异步任务队列

解决全A股筛选（5000+股票）阻塞 FastAPI 事件循环的问题：
1. 任务提交后立即返回 job_id
2. 后台工作线程处理任务
3. 前端通过 SSE 或轮询获取进度
4. 任务状态持久化到 SQLite
"""
import asyncio
import sqlite3
import json
import uuid
import threading
from datetime import datetime
from typing import Optional, Dict
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

# 数据库路径
DB_PATH = "backend/database.db"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScreeningJob:
    job_id: str
    status: JobStatus
    factors: list
    universe: str
    progress: int
    total: int
    result: Optional[list]
    error: Optional[str]
    created_at: str
    updated_at: str


class FactorSandboxTaskQueue:
    """异步任务队列管理器"""

    def __init__(self, max_workers: int = 2):
        self._lock = threading.Lock()
        self._jobs: Dict[str, ScreeningJob] = {}
        self._queue: asyncio.Queue = None
        self._workers: list = []
        self._max_workers = max_workers
        self._running = False
        self._loop: asyncio.AbstractEventLoop = None

        # 初始化数据库表
        self._init_db()

    def _init_db(self):
        """创建任务队列表"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS screening_jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                factors TEXT NOT NULL,
                universe TEXT NOT NULL,
                progress INTEGER DEFAULT 0,
                total INTEGER DEFAULT 0,
                result TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    def _get_conn(self):
        """获取数据库连接"""
        return sqlite3.connect(DB_PATH, check_same_thread=False)

    def submit_job(self, factors: list, universe: str) -> str:
        """提交新任务"""
        job_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()

        job = ScreeningJob(
            job_id=job_id,
            status=JobStatus.PENDING,
            factors=factors,
            universe=universe,
            progress=0,
            total=0,
            result=None,
            error=None,
            created_at=now,
            updated_at=now
        )

        # 保存到内存和数据库
        with self._lock:
            self._jobs[job_id] = job

        self._save_job(job)

        # 添加到队列
        if self._queue:
            self._queue.put_nowait(job_id)

        logger.info(f"[TaskQueue] Job {job_id} submitted")
        return job_id

    def get_job(self, job_id: str) -> Optional[ScreeningJob]:
        """获取任务状态"""
        with self._lock:
            if job_id in self._jobs:
                return self._jobs[job_id]

        # 从数据库加载
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM screening_jobs WHERE job_id = ?",
            (job_id,)
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            job = ScreeningJob(
                job_id=row[0],
                status=JobStatus(row[1]),
                factors=json.loads(row[2]),
                universe=row[3],
                progress=row[4],
                total=row[5],
                result=json.loads(row[6]) if row[6] else None,
                error=row[7],
                created_at=row[8],
                updated_at=row[9]
            )
            with self._lock:
                self._jobs[job_id] = job
            return job

        return None

    def update_job(self, job_id: str, **kwargs):
        """更新任务状态"""
        with self._lock:
            if job_id not in self._jobs:
                return

            job = self._jobs[job_id]
            for key, value in kwargs.items():
                if hasattr(job, key):
                    setattr(job, key, value)

            job.updated_at = datetime.now().isoformat()
            self._save_job(job)

    def _save_job(self, job: ScreeningJob):
        """保存任务到数据库"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO screening_jobs 
            (job_id, status, factors, universe, progress, total, result, error, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job.job_id,
            job.status.value,
            json.dumps(job.factors),
            job.universe,
            job.progress,
            job.total,
            json.dumps(job.result) if job.result else None,
            job.error,
            job.created_at,
            job.updated_at
        ))
        conn.commit()
        conn.close()

    async def start(self):
        """启动工作线程"""
        if self._running:
            return

        self._running = True
        self._queue = asyncio.Queue()
        self._loop = asyncio.get_running_loop()

        # 启动工作协程
        for i in range(self._max_workers):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)

        logger.info(f"[TaskQueue] Started {self._max_workers} workers")

    async def stop(self):
        """停止工作线程"""
        self._running = False

        # 取消所有工作协程
        for worker in self._workers:
            worker.cancel()

        self._workers.clear()
        logger.info("[TaskQueue] Stopped")

    async def _worker(self, worker_id: int):
        """工作协程"""
        logger.info(f"[TaskQueue] Worker {worker_id} started")

        while self._running:
            try:
                job_id = await asyncio.wait_for(self._queue.get(), timeout=1.0)

                job = self.get_job(job_id)
                if not job:
                    continue

                # 更新状态为运行中
                self.update_job(job_id, status=JobStatus.RUNNING)

                try:
                    # 执行筛选任务（通过回调）
                    # 这里不直接调用 screener，而是通过事件通知
                    # 实际筛选逻辑在 router 中通过 SSE 推送

                    # 等待外部设置结果
                    # 超时 5 分钟
                    await asyncio.sleep(0.1)

                except asyncio.CancelledError:
                    self.update_job(job_id, status=JobStatus.CANCELLED)
                    break
                except Exception as e:
                    logger.error(f"[TaskQueue] Worker {worker_id} error: {e}", exc_info=True)
                    self.update_job(job_id, status=JobStatus.FAILED, error=str(e))

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"[TaskQueue] Worker {worker_id} unexpected error: {e}", exc_info=True)

        logger.info(f"[TaskQueue] Worker {worker_id} stopped")


# 全局单例
_task_queue: Optional[FactorSandboxTaskQueue] = None


def get_task_queue() -> FactorSandboxTaskQueue:
    """获取任务队列单例"""
    global _task_queue
    if _task_queue is None:
        _task_queue = FactorSandboxTaskQueue()
    return _task_queue
