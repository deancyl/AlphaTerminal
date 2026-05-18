"""
自适应熔断器

功能:
- 根据历史恢复时间动态调整timeout
- 渐进式恢复（先试探性恢复）
- 记录恢复历史用于分析
"""
import time
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque

from app.services.circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerConfig

logger = logging.getLogger(__name__)

@dataclass
class RecoveryRecord:
    """恢复记录"""
    timestamp: datetime
    success: bool
    recovery_time: float  # 秒

class AdaptiveCircuitBreaker(CircuitBreaker):
    """自适应熔断器"""
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        base_timeout: float = 30.0,
        min_timeout: float = 10.0,
        max_timeout: float = 120.0,
        recovery_history_size: int = 10
    ):
        config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            timeout=base_timeout
        )
        super().__init__(name, config)
        self.base_timeout = base_timeout
        self.min_timeout = min_timeout
        self.max_timeout = max_timeout
        
        self._recovery_history: deque = deque(maxlen=recovery_history_size)
        self._current_timeout = base_timeout
        self._consecutive_failures = 0
    
    def get_adaptive_timeout(self) -> float:
        """
        计算自适应timeout
        
        策略:
        - 如果最近恢复成功率高，缩短timeout
        - 如果连续失败，延长timeout
        """
        if len(self._recovery_history) < 3:
            return self.base_timeout
        
        # 计算最近恢复成功率
        recent = list(self._recovery_history)[-5:]
        success_rate = sum(1 for r in recent if r.success) / len(recent)
        
        # 根据成功率调整
        if success_rate >= 0.8:
            # 成功率高，缩短timeout
            self._current_timeout = max(
                self.min_timeout,
                self._current_timeout * 0.5
            )
        elif success_rate <= 0.3:
            # 成功率低，延长timeout
            self._current_timeout = min(
                self.max_timeout,
                self._current_timeout * 1.5
            )
        
        # 连续失败惩罚
        if self._consecutive_failures > 3:
            self._current_timeout = min(
                self.max_timeout,
                self._current_timeout * (1 + self._consecutive_failures * 0.1)
            )
        
        return self._current_timeout
    
    def record_recovery(self, success: bool, recovery_time: float):
        """记录恢复结果"""
        self._recovery_history.append(RecoveryRecord(
            timestamp=datetime.now(),
            success=success,
            recovery_time=recovery_time
        ))
        
        if success:
            self._consecutive_failures = 0
        else:
            self._consecutive_failures += 1
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "name": self.name,
            "state": self.state.value,
            "current_timeout": round(self._current_timeout, 2),
            "base_timeout": self.base_timeout,
            "consecutive_failures": self._consecutive_failures,
            "recovery_history_size": len(self._recovery_history),
        }

# 管理器
class AdaptiveBreakerManager:
    """自适应熔断器管理器"""
    
    def __init__(self):
        self._breakers: Dict[str, AdaptiveCircuitBreaker] = {}
    
    def get_breaker(self, name: str) -> AdaptiveCircuitBreaker:
        """获取或创建熔断器"""
        if name not in self._breakers:
            self._breakers[name] = AdaptiveCircuitBreaker(name)
        return self._breakers[name]
    
    def get_all_stats(self) -> Dict[str, Dict]:
        """获取所有熔断器状态"""
        return {name: breaker.get_stats() for name, breaker in self._breakers.items()}

# 全局实例
_manager: Optional[AdaptiveBreakerManager] = None

def get_adaptive_breaker_manager() -> AdaptiveBreakerManager:
    global _manager
    if _manager is None:
        _manager = AdaptiveBreakerManager()
    return _manager
