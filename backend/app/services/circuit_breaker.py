"""
熔断器模式实现 - Circuit Breaker Pattern

用于数据源故障时的自动降级切换，防止级联故障。

状态转换:
  CLOSED → OPEN (失败次数超过阈值)
  OPEN → HALF_OPEN (冷却时间结束，尝试请求)
  HALF_OPEN → CLOSED (请求成功)
  HALF_OPEN → OPEN (请求失败)
"""
import time
import threading
from enum import Enum
from typing import Dict, Optional
from dataclasses import dataclass, field


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
    half_open_max_calls: int = 1     # HALF_OPEN 状态下允许的调用数


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