"""
Error Logger — 集中式错误日志服务

功能：
1. 统一捕获异常并写入 Python logging
2. 推送错误到 WebSocket 日志队列（/admin/logs/stream 消费）
3. 结构化错误信息（level + message + traceback + context）

所有路由层的 `except Exception: pass` 必须替换为本模块的 `log_error()` 调用。
"""
import asyncio
import logging
import traceback
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# WebSocket 日志队列（供 /admin/logs/stream 消费）
_log_queue: Optional[asyncio.Queue] = None


def init_log_queue(queue: asyncio.Queue):
    """初始化日志队列（由 admin.py 在启动时调用）"""
    global _log_queue
    _log_queue = queue


def push_log(level: str, message: str, context: Optional[Dict[str, Any]] = None):
    """
    推送一条日志到 WebSocket 队列 + Python logging。

    Args:
        level: ERROR | WARNING | INFO | DEBUG
        message: 日志消息
        context: 额外上下文（路由名、函数名、symbol 等）
    """
    import time

    log_entry = {
        "timestamp": int(time.time() * 1000),
        "level": level.upper(),
        "message": message,
    }
    if context:
        log_entry["context"] = context

    # 推送到 WebSocket 队列（非阻塞）
    if _log_queue is not None:
        try:
            _log_queue.put_nowait(log_entry)
        except asyncio.QueueFull:
            pass  # 队列满时丢弃，不影响主流程

    # 同时写入 Python logging
    log_func = getattr(logger, level.lower(), logger.info)
    log_func(f"[ErrorLogger] {message}")


def log_error(
    exception: Exception,
    module: str,
    function: str,
    context: Optional[Dict[str, Any]] = None,
    message: Optional[str] = None,
):
    """
    统一错误记录：logging + WebSocket 推送 + traceback。

    Args:
        exception: 捕获的异常对象
        module: 模块名（如 'market', 'portfolio'）
        function: 函数名
        context: 额外上下文（symbol, portfolio_id 等）
        message: 自定义错误消息（默认使用 str(exception)）
    """
    tb = traceback.format_exc().strip()
    msg = message or f"{module}.{function}: {type(exception).__name__}: {exception}"

    # Python logging（带 traceback）
    logger.error(f"[{module}.{function}] {msg}\n{tb}")

    # WebSocket 推送（简洁版，不含完整 traceback）
    push_context = {
        "module": module,
        "function": function,
        "exception_type": type(exception).__name__,
    }
    if context:
        push_context.update(context)
    push_log("ERROR", msg, context=push_context)


def log_warning(
    message: str,
    module: str,
    function: str,
    context: Optional[Dict[str, Any]] = None,
):
    """统一警告记录（无异常对象，仅消息）"""
    logger.warning(f"[{module}.{function}] {message}")
    push_context = {"module": module, "function": function}
    if context:
        push_context.update(context)
    push_log("WARNING", message, context=push_context)
