"""
后台任务管理器 - 用于长时间运行的后台任务（如 VACUUM）
支持进度追踪和 WebSocket 广播
"""

import logging
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """任务状态枚举"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BackgroundTask:
    """后台任务数据类"""

    task_id: str
    task_type: str
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0  # 0-100
    message: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }


class BackgroundTaskManager:
    """
    后台任务管理器

    功能:
    - 创建和管理后台任务
    - 追踪任务进度
    - 支持 WebSocket 广播进度更新
    - 任务状态查询
    """

    _instance: Optional["BackgroundTaskManager"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._tasks: Dict[str, BackgroundTask] = {}
        self._ws_broadcast: Optional[Callable] = None
        self._cleanup_interval = 3600
        self._last_cleanup = time.time()

    def __new__(cls) -> "BackgroundTaskManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def create_task(self, task_type: str) -> str:
        """
        创建新任务

        Args:
            task_type: 任务类型（如 'vacuum', 'backup' 等）

        Returns:
            任务 ID
        """
        task_id = f"{task_type}_{int(time.time())}_{secrets.token_hex(4)}"
        task = BackgroundTask(
            task_id=task_id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            message="任务已创建，等待执行",
        )
        self._tasks[task_id] = task
        logger.info(f"[BackgroundTask] Created task: {task_id}")
        return task_id

    def get_task(self, task_id: str) -> Optional[BackgroundTask]:
        """获取任务状态"""
        return self._tasks.get(task_id)

    def start_task(self, task_id: str) -> bool:
        """标记任务开始执行"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        task.message = "任务正在执行"
        self._broadcast_update(task)
        logger.info(f"[BackgroundTask] Started task: {task_id}")
        return True

    def update_progress(self, task_id: str, progress: int, message: str = "") -> bool:
        """
        更新任务进度

        Args:
            task_id: 任务 ID
            progress: 进度百分比 (0-100)
            message: 进度消息

        Returns:
            是否更新成功
        """
        task = self._tasks.get(task_id)
        if not task:
            return False

        task.progress = max(0, min(100, progress))
        if message:
            task.message = message

        self._broadcast_update(task)
        logger.debug(
            f"[BackgroundTask] Progress update: {task_id} - {progress}% - {message}"
        )
        return True

    def complete_task(
        self, task_id: str, result: Optional[Dict[str, Any]] = None
    ) -> bool:
        """标记任务完成"""
        task = self._tasks.get(task_id)
        if not task:
            return False

        task.status = TaskStatus.COMPLETED
        task.progress = 100
        task.result = result
        task.completed_at = datetime.now()
        task.message = "任务完成"

        self._broadcast_update(task)
        logger.info(f"[BackgroundTask] Completed task: {task_id}")
        return True

    def fail_task(self, task_id: str, error: str) -> bool:
        """标记任务失败"""
        task = self._tasks.get(task_id)
        if not task:
            return False

        task.status = TaskStatus.FAILED
        task.error = error
        task.completed_at = datetime.now()
        task.message = f"任务失败: {error}"

        self._broadcast_update(task)
        logger.error(f"[BackgroundTask] Failed task: {task_id} - {error}")
        return True

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self._tasks.get(task_id)
        if not task:
            return False

        if task.status == TaskStatus.RUNNING:
            logger.warning(f"[BackgroundTask] Cannot cancel running task: {task_id}")
            return False

        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now()
        task.message = "任务已取消"

        self._broadcast_update(task)
        logger.info(f"[BackgroundTask] Cancelled task: {task_id}")
        return True

    def set_ws_broadcast(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        设置 WebSocket 广播回调

        Args:
            callback: 回调函数，接收任务更新字典
        """
        self._ws_broadcast = callback
        logger.info("[BackgroundTask] WebSocket broadcast callback set")

    def _broadcast_update(self, task: BackgroundTask) -> None:
        """广播任务更新"""
        if self._ws_broadcast:
            try:
                self._ws_broadcast({"type": "task_update", "data": task.to_dict()})
            except Exception as e:
                logger.error(f"[BackgroundTask] Broadcast failed: {e}", exc_info=True)

    def cleanup_completed_tasks(self, max_age_hours: int = 24) -> int:
        """
        清理已完成的旧任务

        Args:
            max_age_hours: 最大保留时间（小时）

        Returns:
            清理的任务数量
        """
        now = datetime.now()
        cutoff = now.timestamp() - (max_age_hours * 3600)

        to_remove = []
        for task_id, task in self._tasks.items():
            if task.status in (
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
            ):
                if task.completed_at and task.completed_at.timestamp() < cutoff:
                    to_remove.append(task_id)

        for task_id in to_remove:
            del self._tasks[task_id]

        if to_remove:
            logger.info(f"[BackgroundTask] Cleaned up {len(to_remove)} old tasks")

        return len(to_remove)

    def get_all_tasks(self, task_type: Optional[str] = None) -> list[BackgroundTask]:
        """
        获取所有任务

        Args:
            task_type: 可选，筛选特定类型的任务

        Returns:
            任务列表
        """
        tasks = list(self._tasks.values())
        if task_type:
            tasks = [t for t in tasks if t.task_type == task_type]
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)


# 全局单例
_task_manager: Optional[BackgroundTaskManager] = None


def get_task_manager() -> BackgroundTaskManager:
    """获取全局任务管理器实例"""
    global _task_manager
    if _task_manager is None:
        _task_manager = BackgroundTaskManager()
    return _task_manager
