"""
Async Job Queue System for AlphaTerminal
管理长时间运行的任务（回测、参数优化等）
"""

import json
import logging
import os
import queue
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import queue

logger = logging.getLogger(__name__)

DB_PATH = "/tmp/alpha_terminal_jobs.db"


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    job_id: str
    job_type: str
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    result: Optional[Dict] = None
    error: Optional[str] = None
    params: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
            "params": self.params,
        }


class JobQueue:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        self._jobs: Dict[str, Job] = {}
        self._job_queue = queue.Queue()
        self._workers: List[threading.Thread] = []
        self._worker_count = 4
        self._conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self._init_db()
        self._start_workers()
        self._initialized = True

    def _init_db(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                job_type TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                progress REAL DEFAULT 0,
                result TEXT,
                error TEXT,
                params TEXT
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
        self._conn.commit()

    def _start_workers(self):
        for i in range(self._worker_count):
            t = threading.Thread(target=self._worker_loop, daemon=True, name=f"JobWorker-{i}")
            t.start()
            self._workers.append(t)

    def _worker_loop(self):
        while True:
            try:
                job_id = self._job_queue.get(timeout=1)
                self._execute_job(job_id)
            except queue.Empty:
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"Worker error: {e}")

    def _execute_job(self, job_id: str):
        job = self._jobs.get(job_id)
        if not job:
            return

        job.status = JobStatus.RUNNING
        job.started_at = datetime.now()
        self._save_job(job)
        self._update_job(job_id, status=JobStatus.RUNNING.value, started_at=job.started_at.isoformat())

        try:
            if job.job_type == "backtest":
                result = self._run_backtest_job(job)
            elif job.job_type == "optimize":
                result = self._run_optimize_job(job)
            elif job.job_type == "experiment":
                result = self._run_experiment_job(job)
            else:
                result = {"error": f"Unknown job type: {job.job_type}"}

            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now()
            job.result = result
            job.progress = 1.0
            self._save_job(job)
            self._update_job(job_id, status=JobStatus.COMPLETED.value, completed_at=job.completed_at.isoformat(), result=json.dumps(result), progress=1.0)

        except Exception as e:
            job.status = JobStatus.FAILED
            job.completed_at = datetime.now()
            job.error = str(e)
            logger.error(f"Job {job_id} failed: {e}")
            self._update_job(job_id, status=JobStatus.FAILED.value, completed_at=job.completed_at.isoformat(), error=str(e))

    def _run_backtest_job(self, job: Job) -> Dict:
        params = job.params
        from app.services.strategy import create_indicator_strategy, detect_regime
        from app.services.strategy.performance import analyze_backtest_result
        import pandas as pd

        code = params.get("code", "")
        symbol = params.get("symbol", "")
        start_date = params.get("start_date", "")
        end_date = params.get("end_date", "")
        initial_capital = params.get("initial_capital", 100000.0)

        strategy = create_indicator_strategy(code)
        df = self._get_history_data(symbol, start_date, end_date)
        if df is None:
            raise ValueError(f"No data for {symbol}")

        signals = strategy.to_signal_df(df)
        signal_values = signals["signal"]

        equity = [1.0]
        position = 0
        for i in range(1, len(df)):
            sig = signal_values.iloc[i] if hasattr(signal_values, 'iloc') else signal_values[i]
            if position == 0 and sig == 1:
                position = 1
            elif position > 0 and sig == -1:
                position = 0
            ret = (df.iloc[i]["close"] / df.iloc[i-1]["close"] - 1) if position else 0
            equity.append(equity[-1] * (1 + ret))

        equity_series = pd.Series(equity, index=df.index)
        perf = analyze_backtest_result(equity_series, [])
        regime = detect_regime(df)

        return {
            **perf,
            "regime": regime.regime.value if regime else None,
            "trades_count": len([s for s in signal_values if s != 0]) // 2,
        }

    def _run_optimize_job(self, job: Job) -> Dict:
        params = job.params
        from app.services.strategy import create_indicator_strategy, quick_optimize, OptimizationMethod

        code = params.get("code", "")
        symbol = params.get("symbol", "")
        param_grid = params.get("param_grid", {})

        strategy = create_indicator_strategy(code)
        df = self._get_history_data(symbol, params.get("start_date", ""), params.get("end_date", ""))
        if df is None:
            raise ValueError(f"No data for {symbol}")

        report = quick_optimize(
            strategy_code=code,
            data=df,
            parameter_space=param_grid,
            metric=params.get("metric", "sharpe_ratio"),
        )

        return {
            "total_variants": report.total_variants,
            "best_score": report.best_score,
            "best_params": report.best_params,
        }

    def _run_experiment_job(self, job: Job) -> Dict:
        return {"status": "experiment job placeholder"}

    def _get_history_data(self, symbol: str, start_date: str, end_date: str):
        try:
            db_symbol = symbol.replace("sh", "").replace("sz", "")
            conn = sqlite3.connect(os.environ.get('ALPHATERM_DB', '/vol3/1000/docker/opencode/workspace/AlphaTerminal/database.db'))
            rows = conn.execute("""
                SELECT date, open, high, low, close, volume
                FROM market_data_daily
                WHERE symbol = ? AND date >= ? AND date <= ?
                ORDER BY date ASC
            """, (db_symbol, start_date, end_date)).fetchall()
            conn.close()
            if not rows:
                return None
            import pandas as pd
            dates = [r[0] for r in rows]
            data = {
                "open": [float(r[1]) for r in rows],
                "high": [float(r[2]) for r in rows],
                "low": [float(r[3]) for r in rows],
                "close": [float(r[4]) for r in rows],
                "volume": [float(r[5]) for r in rows],
            }
            df = pd.DataFrame(data, index=pd.to_datetime(dates))
            return df
        except Exception as e:
            logger.warning(f"Failed to get history: {e}")
            return None

    def _save_job(self, job: Job):
        self._jobs[job.job_id] = job

    def _update_job(self, job_id: str, **kwargs):
        updates = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [job_id]
        self._conn.execute(f"UPDATE jobs SET {updates} WHERE job_id = ?", values)
        self._conn.commit()

    def submit_job(self, job_type: str, params: Dict) -> str:
        job_id = str(uuid.uuid4())
        job = Job(
            job_id=job_id,
            job_type=job_type,
            status=JobStatus.PENDING,
            created_at=datetime.now(),
            params=params,
        )
        self._jobs[job_id] = job
        self._job_queue.put(job_id)
        self._save_job(job)
        return job_id

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def get_job_status(self, job_id: str) -> Dict:
        job = self._jobs.get(job_id)
        if not job:
            return {"job_id": job_id, "status": "not_found"}
        return job.to_dict()

    def cancel_job(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job:
            return False
        if job.status == JobStatus.PENDING:
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now()
            self._update_job(job_id, status=JobStatus.CANCELLED.value, completed_at=job.completed_at.isoformat())
            return True
        return False


def get_job_queue() -> JobQueue:
    return JobQueue()
