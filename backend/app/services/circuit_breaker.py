"""
熔断器模式实现 - Circuit Breaker Pattern

用于数据源故障时的自动降级切换，防止级联故障。

状态转换:
  CLOSED → OPEN (失败次数超过阈值)
  OPEN → HALF_OPEN (冷却时间结束，尝试请求)
  HALF_OPEN → CLOSED (请求成功)
  HALF_OPEN → OPEN (请求失败)

v2 新增: 滑动窗口熔断器（SlidingWindowCircuitBreaker）
  - 在指定时间窗口内统计失败率，而非仅统计连续失败次数
  - 更精准地反映数据源的健康状态
"""
import time
import threading
from enum import Enum
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from collections import deque


class CircuitState(Enum):
    CLOSED = "closed"      # 正常，流量通过
    OPEN = "open"          # 熔断，流量拒绝
    HALF_OPEN = "half_open"  # 半开，只允许一个测试请求


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    failure_threshold: int = 5       # 失败次数阈值 (OPEN)
    success_threshold: int = 2       # 成功次数阈值 (CLOSED from HALF_OPEN)
    timeout: float = 30.0             # OPEN 状态持续时间 (秒)
    half_open_max_calls: int = 3     # HALF_OPEN 状态下允许的调用数（需 >= success_threshold）


@dataclass
class SlidingWindowConfig:
    """滑动窗口熔断器配置"""
    window_size: float = 60.0        # 时间窗口大小（秒）
    min_calls: int = 5               # 窗口内最小调用数（低于此值不触发熔断）
    failure_rate_threshold: float = 0.5  # 失败率阈值（50%）
    consecutive_failures: int = 5    # 连续失败次数阈值（快速熔断）
    timeout: float = 30.0            # OPEN 状态持续时间（秒）
    success_threshold: int = 2       # HALF_OPEN → CLOSED 成功次数阈值


@dataclass
class CircuitBreakerStats:
    """熔断器统计"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    state_change_times: list = field(default_factory=list)
    
    def record_success(self):
        self.total_calls += 1
        self.successful_calls += 1
        self.consecutive_successes += 1
        self.consecutive_failures = 0
        self.last_success_time = time.time()
    
    def record_failure(self):
        self.total_calls += 1
        self.failed_calls += 1
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        self.last_failure_time = time.time()


class CircuitBreaker:
    """
    熔断器实现。
    
    使用方式:
        cb = CircuitBreaker("sina", failure_threshold=5, timeout=30)
        
        with cb:
            # 在这里执行可能失败的操作
            result = await fetcher.get_quote(symbol)
    
    如果熔断器 OPEN，会抛出 CircuitBreakerOpen 异常。
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._state_lock = threading.RLock()
        self._opened_at: Optional[float] = None
        self._half_open_calls = 0
        self._stats = CircuitBreakerStats()
    
    @property
    def state(self) -> CircuitState:
        with self._state_lock:
            return self._get_state_unsafe()
    
    def _get_state_unsafe(self) -> CircuitState:
        """获取状态（必须在持有锁时调用）"""
        if self._state == CircuitState.OPEN:
            # 检查是否应该转换到 HALF_OPEN
            if self._opened_at and (time.time() - self._opened_at) >= self.config.timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                self._stats.consecutive_failures = 0
                self._record_state_change(CircuitState.HALF_OPEN)
        return self._state
    
    def _record_state_change(self, new_state: CircuitState):
        self._stats.state_change_times.append({
            "time": time.time(),
            "from": self._state.value,
            "to": new_state.value
        })
    
    def _can_execute(self) -> bool:
        """检查是否允许执行（在持有锁时调用）"""
        state = self._get_state_unsafe()
        
        if state == CircuitState.CLOSED:
            return True
        
        if state == CircuitState.OPEN:
            return False
        
        # HALF_OPEN: 只允许一个调用
        if self._half_open_calls < self.config.half_open_max_calls:
            self._half_open_calls += 1
            return True
        return False
    
    def record_success(self):
        """记录成功调用"""
        with self._state_lock:
            self._stats.record_success()
            
            if self._state == CircuitState.HALF_OPEN:
                if self._stats.consecutive_successes >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._stats.consecutive_successes = 0
                    self._stats.consecutive_failures = 0  # 修复: 进入 CLOSED 前必须重置失败计数
                    self._record_state_change(CircuitState.CLOSED)
    
    def record_failure(self):
        """记录失败调用"""
        with self._state_lock:
            self._stats.record_failure()
            
            if self._state == CircuitState.HALF_OPEN:
                # 测试请求失败，重新打开
                self._state = CircuitState.OPEN
                self._opened_at = time.time()
                self._record_state_change(CircuitState.OPEN)
            
            elif self._state == CircuitState.CLOSED:
                if self._stats.consecutive_failures >= self.config.failure_threshold:
                    self._state = CircuitState.OPEN
                    self._opened_at = time.time()
                    self._record_state_change(CircuitState.OPEN)
    
    def is_available(self) -> bool:
        """检查当前是否可用"""
        with self._state_lock:
            return self._can_execute()
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self._state_lock:
            return {
                "name": self.name,
                "state": self._get_state_unsafe().value,
                "total_calls": self._stats.total_calls,
                "successful_calls": self._stats.successful_calls,
                "failed_calls": self._stats.failed_calls,
                "consecutive_failures": self._stats.consecutive_failures,
                "consecutive_successes": self._stats.consecutive_successes,
                "last_failure_time": self._stats.last_failure_time,
                "last_success_time": self._stats.last_success_time,
                "opened_at": self._opened_at,
                "failure_threshold": self.config.failure_threshold,
                "timeout": self.config.timeout,
            }
    
    def reset(self):
        """重置熔断器"""
        with self._state_lock:
            self._state = CircuitState.CLOSED
            self._opened_at = None
            self._half_open_calls = 0
            self._stats = CircuitBreakerStats()
    
    def __enter__(self):
        """上下文管理器入口 - 支持 with 语句"""
        if not self.is_available():
            stats = self.get_stats()
            raise CircuitBreakerOpen(
                self.name,
                stats.get("timeout", 30)
            )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        if exc_type is not None and issubclass(exc_type, Exception):
            self.record_failure()
        else:
            self.record_success()
        return False  # 不吞没异常


class CircuitBreakerOpen(Exception):
    """熔断器打开异常"""
    def __init__(self, name: str, timeout: float):
        self.name = name
        self.timeout = timeout
        super().__init__(f"Circuit breaker '{name}' is OPEN. Try again in {timeout:.1f}s")


class CircuitContext:
    """熔断器上下文管理器"""
    
    def __init__(self, breaker: CircuitBreaker):
        self.breaker = breaker
    
    def __enter__(self):
        if not self.breaker.is_available():
            stats = self.breaker.get_stats()
            raise CircuitBreakerOpen(
                self.breaker.name,
                stats.get("timeout", 30)
            )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None and issubclass(exc_type, Exception):
            self.breaker.record_failure()
        else:
            self.breaker.record_success()
        return False  # 不吞没异常


class SlidingWindowCircuitBreaker:
    """
    滑动窗口熔断器 - 基于时间窗口内的失败率触发熔断。
    
    与传统熔断器的区别：
    - 传统：仅统计连续失败次数
    - 滑动窗口：统计时间窗口内的失败率，更精准反映数据源健康状态
    
    触发条件（满足任一）：
    1. 连续失败次数 >= consecutive_failures（快速熔断）
    2. 窗口内失败率 >= failure_rate_threshold 且调用数 >= min_calls
    
    使用方式：
        cb = SlidingWindowCircuitBreaker("sina", SlidingWindowConfig())
        
        with cb:
            result = await fetcher.get_quote(symbol)
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[SlidingWindowConfig] = None
    ):
        self.name = name
        self.config = config or SlidingWindowConfig()
        self._state = CircuitState.CLOSED
        self._state_lock = threading.RLock()
        self._opened_at: Optional[float] = None
        self._half_open_calls = 0
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._window: deque = deque()  # 存储 (timestamp, is_success) 元组
    
    @property
    def state(self) -> CircuitState:
        """获取当前熔断器状态"""
        with self._state_lock:
            # 检查是否应该从 OPEN 转换到 HALF_OPEN
            if self._state == CircuitState.OPEN:
                if self._opened_at and (time.time() - self._opened_at) >= self.config.timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    self._consecutive_failures = 0
            return self._state
    
    def _clean_window(self):
        """清理窗口外的过期记录"""
        now = time.time()
        cutoff = now - self.config.window_size
        while self._window and self._window[0][0] < cutoff:
            self._window.popleft()
    
    def _get_window_stats(self) -> Dict[str, int]:
        """获取窗口内统计"""
        self._clean_window()
        total = len(self._window)
        failures = sum(1 for _, is_success in self._window if not is_success)
        return {"total": total, "failures": failures, "successes": total - failures}
    
    def _should_open(self) -> bool:
        """判断是否应该熔断"""
        # 条件1: 连续失败快速熔断
        if self._consecutive_failures >= self.config.consecutive_failures:
            return True
        
        # 条件2: 窗口内失败率熔断
        stats = self._get_window_stats()
        if stats["total"] >= self.config.min_calls:
            failure_rate = stats["failures"] / stats["total"]
            if failure_rate >= self.config.failure_rate_threshold:
                return True
        
        return False
    
    def record_success(self):
        """记录成功调用"""
        with self._state_lock:
            now = time.time()
            self._window.append((now, True))
            self._consecutive_successes += 1
            self._consecutive_failures = 0
            
            if self._state == CircuitState.HALF_OPEN:
                if self._consecutive_successes >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._consecutive_successes = 0
                    self._consecutive_failures = 0
    
    def record_failure(self):
        """记录失败调用"""
        with self._state_lock:
            now = time.time()
            self._window.append((now, False))
            self._consecutive_failures += 1
            self._consecutive_successes = 0
            
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._opened_at = time.time()
            elif self._state == CircuitState.CLOSED:
                if self._should_open():
                    self._state = CircuitState.OPEN
                    self._opened_at = time.time()
    
    def is_available(self) -> bool:
        """检查当前是否可用"""
        with self._state_lock:
            if self._state == CircuitState.CLOSED:
                return True
            if self._state == CircuitState.OPEN:
                if self._opened_at and (time.time() - self._opened_at) >= self.config.timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    self._consecutive_failures = 0
                    return True
                return False
            # HALF_OPEN
            return True
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self._state_lock:
            window_stats = self._get_window_stats()
            failure_rate = 0.0
            if window_stats["total"] > 0:
                failure_rate = window_stats["failures"] / window_stats["total"]
            
            return {
                "name": self.name,
                "state": self._state.value,
                "window_size": self.config.window_size,
                "window_calls": window_stats["total"],
                "window_failures": window_stats["failures"],
                "failure_rate": round(failure_rate, 3),
                "consecutive_failures": self._consecutive_failures,
                "consecutive_successes": self._consecutive_successes,
                "opened_at": self._opened_at,
                "config": {
                    "window_size": self.config.window_size,
                    "min_calls": self.config.min_calls,
                    "failure_rate_threshold": self.config.failure_rate_threshold,
                    "consecutive_failures": self.config.consecutive_failures,
                    "timeout": self.config.timeout,
                }
            }
    
    def reset(self):
        """重置熔断器"""
        with self._state_lock:
            self._state = CircuitState.CLOSED
            self._opened_at = None
            self._half_open_calls = 0
            self._consecutive_failures = 0
            self._consecutive_successes = 0
            self._window.clear()
    
    def __enter__(self):
        if not self.is_available():
            raise CircuitBreakerOpen(self.name, self.config.timeout)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None and issubclass(exc_type, Exception):
            self.record_failure()
        else:
            self.record_success()
        return False


class SlidingWindowCircuitContext:
    """滑动窗口熔断器上下文管理器"""
    
    def __init__(self, breaker: SlidingWindowCircuitBreaker, source_name: str = ""):
        self.breaker = breaker
        self.source_name = source_name
    
    def __enter__(self):
        if not self.breaker.is_available():
            raise CircuitBreakerOpen(self.breaker.name, self.breaker.config.timeout)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None and issubclass(exc_type, Exception):
            self.breaker.record_failure()
        else:
            self.breaker.record_success()
        return False