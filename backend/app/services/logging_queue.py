"""
日志队列服务 - 将日志重定向到 WebSocket 队列
"""
import asyncio
import logging
import time
from typing import Optional

# 全局日志队列
_log_queue: Optional[asyncio.Queue] = None

def get_log_queue() -> asyncio.Queue:
    """获取日志队列单例"""
    global _log_queue
    if _log_queue is None:
        _log_queue = asyncio.Queue(maxsize=100)
    return _log_queue


class WebSocketLogHandler(logging.Handler):
    """自定义日志 Handler，将日志推送到 WebSocket 队列"""
    
    def __init__(self):
        super().__init__()
        self.setLevel(logging.INFO)
        self.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
    
    def emit(self, record):
        """发送日志到队列"""
        try:
            log_msg = self.format(record)
            
            # 解析日志级别
            level = "INFO"
            if record.levelno >= logging.ERROR:
                level = "ERROR"
            elif record.levelno >= logging.WARNING:
                level = "WARNING"
            elif record.levelno >= logging.DEBUG:
                level = "DEBUG"
            
            # 构造消息
            msg = {
                "timestamp": int(record.created),
                "level": level,
                "message": log_msg[:300]
            }
            
            # 推送到队列（不阻塞）
            queue = get_log_queue()
            try:
                queue.put_nowait(msg)
            except asyncio.QueueFull:
                # 队列满时丢弃最旧的
                try:
                    queue.get_nowait()
                except:
                    pass
                queue.put_nowait(msg)
                
        except Exception:
            self.handleError(record)


def init_logging_queue():
    """初始化日志队列 - 将应用日志接入 WebSocket 流"""
    queue = get_log_queue()
    
    # 添加自定义 Handler
    handler = WebSocketLogHandler()
    
    # 添加到 root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
    
    return queue