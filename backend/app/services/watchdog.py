"""
进程保活监控服务 (Watchdog Service)

功能：
1. 监控后端进程健康状态（HTTP 心跳检测）
2. 进程崩溃时自动重启（可配置开关）
3. 记录崩溃日志和重启历史
4. 提供 Admin API 控制开关

设计原则：
- 轻量级：不引入外部依赖（systemd/pm2）
- 可配置：通过 admin_config 表持久化开关状态
- 自包含：watchdog 作为独立线程运行，不阻塞主服务
"""
import asyncio
import logging
import os
import signal
import subprocess
import sys
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

import httpx

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# 配置常量
# ═══════════════════════════════════════════════════════════════

WATCHDOG_CONFIG_KEY = "watchdog_enabled"  # admin_config 表中的 key
HEALTH_CHECK_INTERVAL = 30  # 秒，健康检查间隔
RESTART_DELAY = 5  # 秒，重启前等待时间
MAX_RESTART_ATTEMPTS = 3  # 连续重启失败的最大次数
RESTART_COOLDOWN = 300  # 秒，超过此次数后进入冷却期

# 后端启动命令（相对于 backend 目录）
BACKEND_START_CMD = [sys.executable, "start_backend.py"]
BACKEND_HEALTH_URL = "http://localhost:8002/health"  # 健康检查端点
BACKEND_PID_FILE = "/tmp/alphaterminal_backend.pid"  # PID 文件路径


# ═══════════════════════════════════════════════════════════════
# Watchdog 状态管理
# ═══════════════════════════════════════════════════════════════

class WatchdogState:
    """Watchdog 运行时状态"""
    def __init__(self):
        self.enabled: bool = False  # 是否启用保活
        self.running: bool = False  # watchdog 线程是否运行中
        self.last_check: Optional[datetime] = None
        self.last_restart: Optional[datetime] = None
        self.restart_count: int = 0  # 连续重启计数
        self.total_restarts: int = 0  # 总计重启次数
        self.errors: List[Dict[str, Any]] = []  # 最近错误记录（保留最近10条）
        self._lock = threading.Lock()
    
    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "enabled": self.enabled,
                "running": self.running,
                "last_check": self.last_check.isoformat() if self.last_check else None,
                "last_restart": self.last_restart.isoformat() if self.last_restart else None,
                "restart_count": self.restart_count,
                "total_restarts": self.total_restarts,
                "recent_errors": self.errors[-5:],  # 最近5条
            }
    
    def record_error(self, error: str):
        with self._lock:
            self.errors.append({
                "time": datetime.now().isoformat(),
                "error": error,
            })
            # 只保留最近10条
            if len(self.errors) > 10:
                self.errors = self.errors[-10:]
    
    def record_restart(self):
        with self._lock:
            self.last_restart = datetime.now()
            self.restart_count += 1
            self.total_restarts += 1
    
    def reset_restart_count(self):
        with self._lock:
            self.restart_count = 0


# 全局状态实例
_watchdog_state = WatchdogState()
_watchdog_thread: Optional[threading.Thread] = None
_watchdog_stop_event = threading.Event()


def get_watchdog_state() -> Dict[str, Any]:
    """获取 watchdog 当前状态"""
    return _watchdog_state.to_dict()


# ═══════════════════════════════════════════════════════════════
# 配置持久化
# ═══════════════════════════════════════════════════════════════

def _get_db_conn():
    """获取数据库连接"""
    from app.db.database import _get_conn
    return _get_conn()


def load_watchdog_config() -> bool:
    """从数据库加载 watchdog 配置"""
    try:
        conn = _get_db_conn()
        cursor = conn.execute(
            "SELECT value FROM admin_config WHERE key = ?",
            (WATCHDOG_CONFIG_KEY,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return row[0].lower() == "true"
        
        # 默认关闭
        return False
    except Exception as e:
        logger.warning(f"[Watchdog] 加载配置失败: {e}")
        return False


def save_watchdog_config(enabled: bool) -> bool:
    """保存 watchdog 配置到数据库"""
    try:
        conn = _get_db_conn()
        conn.execute(
            """INSERT OR REPLACE INTO admin_config (key, value, updated_at) 
               VALUES (?, ?, ?)""",
            (WATCHDOG_CONFIG_KEY, str(enabled).lower(), datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        
        _watchdog_state.enabled = enabled
        logger.info(f"[Watchdog] 配置已保存: enabled={enabled}")
        return True
    except Exception as e:
        logger.error(f"[Watchdog] 保存配置失败: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# 健康检查与重启逻辑
# ═══════════════════════════════════════════════════════════════

def _check_backend_health() -> bool:
    """检查后端健康状态"""
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(BACKEND_HEALTH_URL)
            return response.status_code == 200
    except Exception as e:
        logger.debug(f"[Watchdog] 健康检查失败: {e}")
        return False


def _get_backend_pid() -> Optional[int]:
    """从 PID 文件读取后端进程 ID"""
    try:
        if os.path.exists(BACKEND_PID_FILE):
            with open(BACKEND_PID_FILE, 'r') as f:
                return int(f.read().strip())
    except Exception as e:
        logger.debug(f"[Watchdog] 读取 PID 文件失败: {e}")
    return None


def _is_process_running(pid: int) -> bool:
    """检查进程是否存活"""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _restart_backend() -> bool:
    """重启后端服务"""
    try:
        logger.warning("[Watchdog] 正在重启后端服务...")
        
        # 1. 尝试优雅终止旧进程
        old_pid = _get_backend_pid()
        if old_pid and _is_process_running(old_pid):
            try:
                os.kill(old_pid, signal.SIGTERM)
                # 等待最多 5 秒
                for _ in range(10):
                    time.sleep(0.5)
                    if not _is_process_running(old_pid):
                        break
                else:
                    # 强制终止
                    os.kill(old_pid, signal.SIGKILL)
                    time.sleep(1)
            except Exception as e:
                logger.warning(f"[Watchdog] 终止旧进程失败: {e}")
        
        # 2. 启动新进程
        backend_dir = Path(__file__).resolve().parent.parent.parent  # app/services/ → app/ → backend/
        proc = subprocess.Popen(
            BACKEND_START_CMD,
            cwd=backend_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # 脱离终端
        )
        
        # 3. 写入 PID 文件
        with open(BACKEND_PID_FILE, 'w') as f:
            f.write(str(proc.pid))
        
        logger.info(f"[Watchdog] 后端已重启，新 PID: {proc.pid}")
        return True
        
    except Exception as e:
        logger.error(f"[Watchdog] 重启后端失败: {e}")
        _watchdog_state.record_error(f"重启失败: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# Watchdog 主循环
# ═══════════════════════════════════════════════════════════════

def _watchdog_loop():
    """Watchdog 主循环（在独立线程中运行）"""
    logger.info("[Watchdog] 监控线程已启动")
    
    while not _watchdog_stop_event.is_set():
        try:
            # 检查是否启用
            if not _watchdog_state.enabled:
                time.sleep(HEALTH_CHECK_INTERVAL)
                continue
            
            _watchdog_state.last_check = datetime.now()
            
            # 健康检查
            if not _check_backend_health():
                logger.warning("[Watchdog] 后端健康检查失败")
                _watchdog_state.record_error("健康检查失败")
                
                # 检查连续重启次数
                if _watchdog_state.restart_count >= MAX_RESTART_ATTEMPTS:
                    logger.error(f"[Watchdog] 连续重启 {_watchdog_state.restart_count} 次仍未恢复，进入冷却期")
                    _watchdog_state.record_error(f"进入冷却期（连续{MAX_RESTART_ATTEMPTS}次重启失败）")
                    time.sleep(RESTART_COOLDOWN)
                    _watchdog_state.reset_restart_count()
                    continue
                
                # 执行重启
                time.sleep(RESTART_DELAY)
                if _restart_backend():
                    _watchdog_state.record_restart()
                    # 等待启动完成
                    time.sleep(5)
                    if _check_backend_health():
                        logger.info("[Watchdog] 后端重启成功，健康检查通过")
                        _watchdog_state.reset_restart_count()
                    else:
                        logger.warning("[Watchdog] 后端重启后健康检查仍失败")
                else:
                    _watchdog_state.record_restart()  # 记录失败的重启
            else:
                # 健康检查通过，重置连续失败计数
                if _watchdog_state.restart_count > 0:
                    _watchdog_state.reset_restart_count()
            
            # 等待下次检查
            time.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"[Watchdog] 监控循环异常: {e}")
            _watchdog_state.record_error(f"监控循环异常: {e}")
            time.sleep(HEALTH_CHECK_INTERVAL)
    
    logger.info("[Watchdog] 监控线程已停止")


# ═══════════════════════════════════════════════════════════════
# 对外接口
# ═══════════════════════════════════════════════════════════════

def start_watchdog():
    """启动 watchdog 线程"""
    global _watchdog_thread
    
    if _watchdog_thread and _watchdog_thread.is_alive():
        logger.info("[Watchdog] 已经在运行中")
        return
    
    # 加载配置
    _watchdog_state.enabled = load_watchdog_config()
    _watchdog_state.running = True
    _watchdog_stop_event.clear()
    
    # 启动线程
    _watchdog_thread = threading.Thread(target=_watchdog_loop, daemon=True)
    _watchdog_thread.start()
    
    logger.info(f"[Watchdog] 已启动，当前状态: enabled={_watchdog_state.enabled}")


def stop_watchdog():
    """停止 watchdog 线程"""
    global _watchdog_thread
    
    if not _watchdog_thread or not _watchdog_thread.is_alive():
        return
    
    _watchdog_state.running = False
    _watchdog_stop_event.set()
    _watchdog_thread.join(timeout=5)
    logger.info("[Watchdog] 已停止")


def toggle_watchdog(enabled: bool) -> bool:
    """切换 watchdog 开关状态"""
    # 保存配置
    if not save_watchdog_config(enabled):
        return False
    
    # 更新运行时状态
    _watchdog_state.enabled = enabled
    
    if enabled:
        logger.info("[Watchdog] 保活功能已启用")
    else:
        logger.info("[Watchdog] 保活功能已禁用")
    
    return True


# ═══════════════════════════════════════════════════════════════
# 初始化
# ═══════════════════════════════════════════════════════════════

def init_watchdog():
    """应用启动时初始化 watchdog"""
    start_watchdog()
