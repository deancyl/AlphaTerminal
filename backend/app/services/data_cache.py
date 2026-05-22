"""
DataCache - Task 15: 高性能数据缓存层

功能特性:
- TTL 过期机制
- LRU 驱逐策略
- 内存限制保护
- 线程安全操作
- 缓存命中率统计
- 10 个 Debug 诊断周期

设计原则:
- 简单高效: 使用 Python dict 存储，避免过度设计
- 内存安全: 严格限制内存使用，防止 OOM
- 可观测性: 完整的统计和 Debug 日志
"""

import logging
import sys
import threading
import time
import json
import random
import sqlite3
import asyncio
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, Optional, Callable, Awaitable

from app.db.db_writer import enqueue, T_CACHE_PERSIST

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 分层 TTL 策略配置
# ═══════════════════════════════════════════════════════════════

KLINE_TTL_CONFIG = {
    # 分钟级K线（盘中变化快）
    "1min": 60,  # 1分钟
    "5min": 180,  # 3分钟
    "15min": 300,  # 5分钟
    "30min": 300,  # 5分钟
    "60min": 600,  # 10分钟
    # 日级及以上（变化慢）
    "daily": 900,  # 15分钟（盘中）/ 3600（盘后）
    "weekly": 3600,  # 1小时
    "monthly": 7200,  # 2小时
}


def get_kline_ttl(period: str, is_trading_hours: bool = True) -> int:
    """
    获取K线数据的推荐TTL

    Args:
        period: K线周期 (1min, 5min, daily, etc.)
        is_trading_hours: 是否在交易时段

    Returns:
        TTL 秒数
    """
    base_ttl = KLINE_TTL_CONFIG.get(period, 300)

    # 日K线：交易时段较短TTL，盘后延长
    if period == "daily" and not is_trading_hours:
        return 3600  # 1小时

    return base_ttl


@dataclass
class CacheEntry:
    """缓存条目数据结构"""

    key: str
    value: Any
    created_at: float
    expires_at: float
    size_bytes: int = 0
    hit_count: int = 0

    def is_expired(self) -> bool:
        """检查是否过期"""
        return time.time() > self.expires_at


class DataCache:
    """
    高性能数据缓存

    特性:
    - TTL 过期自动清理
    - LRU 驱逐策略
    - 内存使用限制
    - 线程安全
    - 统计信息追踪
    """

    def __init__(self, max_size_mb: int = 100, default_ttl: int = 300):
        """
        初始化缓存

        Args:
            max_size_mb: 最大内存使用量 (MB)
            default_ttl: 默认过期时间 (秒)
        """
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.default_ttl = default_ttl

        # 使用 OrderedDict 实现 LRU
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()

        # Request coalescing locks (per-key) - prevents cache avalanche
        self._key_locks: Dict[str, threading.Lock] = {}
        self._key_locks_lock = threading.Lock()  # protects _key_locks dict

        # In-flight requests tracking (for async get_or_set)
        self._inflight: Dict[str, Any] = {}  # key -> future/result placeholder
        self._inflight_lock = threading.Lock()

        # Request coalescing with Events (prevents race conditions)
        self._pending_events: Dict[str, threading.Event] = {}
        self._pending_results: Dict[str, Any] = {}
        self._pending_errors: Dict[str, Exception] = {}
        self._pending_lock = threading.Lock()

        # Async request coalescing (for get_or_set_async)
        self._async_pending_events: Dict[str, asyncio.Event] = {}
        self._async_pending_results: Dict[str, Any] = {}
        self._async_pending_errors: Dict[str, Exception] = {}
        self._async_pending_lock = asyncio.Lock()

        # 统计信息
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "expired_removals": 0,
            "total_requests": 0,
            "coalesced_requests": 0,  # requests that waited for in-flight
        }

        # Debug 周期计数器
        self._debug_cycle = 0

        # Debug Cycle 1: 缓存初始化
        self._debug_cycle_1_init()

        logger.info(
            f"[DataCache] 初始化完成: max_size={max_size_mb}MB, default_ttl={default_ttl}s"
        )

    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，不存在或过期返回 None
        """
        with self._lock:
            self._stats["total_requests"] += 1

            # Debug Cycle 3: Cache get (hit)
            # Debug Cycle 4: Cache get (miss)
            return self._get_internal(key)

    def get_with_stale(
        self, key: str, fresh_ttl: int = 60, stale_ttl: int = 600
    ) -> tuple:
        """
        获取缓存值，支持 stale-while-revalidate 模式

        Args:
            key: 缓存键
            fresh_ttl: 数据新鲜阈值（秒），小于此值为新鲜数据
            stale_ttl: 数据过期阈值（秒），小于此值为过期数据

        Returns:
            tuple: (data, is_stale)
            - (data, False): 数据新鲜（age < fresh_ttl）
            - (data, True): 数据过期但可用（fresh_ttl <= age < stale_ttl）
            - (None, False): 数据不存在或完全过期（age >= stale_ttl）

        Example:
            >>> data, is_stale = cache.get_with_stale("forex:spot", fresh_ttl=60, stale_ttl=600)
            >>> if data:
            >>>     if is_stale:
            >>>         # 数据过期但可用，触发后台刷新
            >>>         asyncio.create_task(refresh_data())
            >>>     return data
            >>> # 无数据，需要等待首次获取
        """
        with self._lock:
            self._stats["total_requests"] += 1

            entry = self._cache.get(key)

            if entry is None:
                # 完全不存在
                self._stats["misses"] += 1
                self._debug_cycle_4_get_miss(key)
                return None, False

            # 计算数据年龄
            age = time.time() - entry.created_at

            # 完全过期（超过 stale_ttl）
            if age >= stale_ttl:
                del self._cache[key]
                self._stats["misses"] += 1
                self._stats["expired_removals"] += 1
                logger.debug(f"[DataCache] 键完全过期删除: {key}, age={age:.0f}s")
                return None, False

            # 数据可用（新鲜或过期）
            # 移动到末尾（LRU）
            self._cache.move_to_end(key)
            entry.hit_count += 1
            self._stats["hits"] += 1

            is_stale = age >= fresh_ttl

            if is_stale:
                logger.debug(
                    f"[DataCache] 返回过期数据: {key}, age={age:.0f}s, fresh_ttl={fresh_ttl}s"
                )
            else:
                self._debug_cycle_3_get_hit(key, entry)

            return entry.value, is_stale

    def _get_internal(self, key: str) -> Optional[Any]:
        """内部获取方法（不加锁）"""
        entry = self._cache.get(key)

        if entry is None:
            # Miss
            self._stats["misses"] += 1
            self._debug_cycle_4_get_miss(key)
            return None

        # 检查过期
        if entry.is_expired():
            del self._cache[key]
            self._stats["misses"] += 1
            self._stats["expired_removals"] += 1
            logger.debug(f"[DataCache] 键过期删除: {key}")
            return None

        # Hit - 移动到末尾（LRU）
        self._cache.move_to_end(key)
        entry.hit_count += 1
        self._stats["hits"] += 1

        # Debug Cycle 3: Cache get (hit)
        self._debug_cycle_3_get_hit(key, entry)

        return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过过时间（秒），None 使用默认值

        Returns:
            是否成功
        """
        with self._lock:
            # 计算大小
            size_bytes = self._estimate_size(value)

            # 检查单个值是否超过限制
            if size_bytes > self.max_size_bytes * 0.5:
                logger.warning(
                    f"[DataCache] 值过大，拒绝缓存: {key} ({size_bytes} bytes)"
                )
                return False

            # 清理空间
            self._ensure_space(size_bytes)

            # 创建条目
            now = time.time()
            ttl = ttl if ttl is not None else self.default_ttl

            # TTL添加10%随机抖动，防止缓存雪崩
            # 对于正数TTL，确保抖动后至少为1秒
            # 对于0或负数TTL，保持原值（立即过期）
            if ttl > 0:
                jitter = random.uniform(0.9, 1.1)  # ±10%
                actual_ttl = max(1, int(ttl * jitter))
            else:
                actual_ttl = ttl

            entry = CacheEntry(
                key=key,
                value=value,
                created_at=now,
                expires_at=now + actual_ttl,
                size_bytes=size_bytes,
            )

            # 如果键已存在，先删除
            if key in self._cache:
                del self._cache[key]

            # 添加到缓存
            self._cache[key] = entry

            # Debug Cycle 2: Cache set
            self._debug_cycle_2_set(key, entry)

            return True

    def delete(self, key: str) -> bool:
        """
        删除缓存值

        Args:
            key: 缓存键

        Returns:
            是否成功删除
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._debug_cycle_5_delete(key)
                return True
            return False

    def get_or_set(
        self, key: str, fetch_fn: Callable[[], Any], ttl: Optional[int] = None
    ) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached

        is_leader = False
        event = None

        with self._pending_lock:
            if key in self._pending_events:
                event = self._pending_events[key]
                self._stats["coalesced_requests"] += 1
            else:
                event = threading.Event()
                self._pending_events[key] = event
                is_leader = True

        if not is_leader:
            if not event.wait(timeout=30):
                with self._pending_lock:
                    self._pending_events.pop(key, None)
                raise TimeoutError(f"Timeout waiting for fetch result: {key}")

            with self._pending_lock:
                error = self._pending_errors.get(key)
                if error is not None:
                    self._pending_events.pop(key, None)
                    self._pending_errors.pop(key, None)
                    raise error
                self._pending_events.pop(key, None)

            cached = self.get(key)
            if cached is not None:
                return cached
            raise RuntimeError(f"Fetch completed but cache is empty for key: {key}")

        try:
            value = fetch_fn()
            self.set(key, value, ttl)
            with self._pending_lock:
                self._pending_results[key] = value
                event.set()
            return value
        except Exception as e:
            with self._pending_lock:
                self._pending_errors[key] = e
                event.set()
            raise
        finally:
            with self._pending_lock:
                self._pending_events.pop(key, None)

    async def get_or_set_async(
        self,
        key: str,
        fetch_fn: Callable[[], Awaitable[Any]],
        ttl: Optional[int] = None,
    ) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached

        is_leader = False
        event = None

        async with self._async_pending_lock:
            if key in self._async_pending_events:
                event = self._async_pending_events[key]
                self._stats["coalesced_requests"] += 1
            else:
                event = asyncio.Event()
                self._async_pending_events[key] = event
                is_leader = True

        if not is_leader:
            try:
                await asyncio.wait_for(event.wait(), timeout=30)
            except asyncio.TimeoutError:
                async with self._async_pending_lock:
                    self._async_pending_events.pop(key, None)
                raise TimeoutError(f"Timeout waiting for async fetch result: {key}")

            async with self._async_pending_lock:
                error = self._async_pending_errors.get(key)
                if error is not None:
                    self._async_pending_events.pop(key, None)
                    self._async_pending_errors.pop(key, None)
                    raise error
                self._async_pending_events.pop(key, None)

            cached = self.get(key)
            if cached is not None:
                return cached
            raise RuntimeError(f"Fetch completed but cache is empty for key: {key}")

        try:
            value = await fetch_fn()
            self.set(key, value, ttl)
            with self._pending_lock:
                event.set()
            return value
        except Exception as e:
            with self._pending_lock:
                self._pending_errors[key] = e
                event.set()
            raise
        finally:
            with self._pending_lock:
                self._pending_events.pop(key, None)
                self._pending_errors.pop(key, None)

    async def get_or_set_async(
        self,
        key: str,
        fetch_fn: Callable[[], Awaitable[Any]],
        ttl: Optional[int] = None,
    ) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached

        is_leader = False
        event = None

        async with self._async_pending_lock:
            if key in self._async_pending_events:
                event = self._async_pending_events[key]
                self._stats["coalesced_requests"] += 1
            else:
                event = asyncio.Event()
                self._async_pending_events[key] = event
                is_leader = True

        if not is_leader:
            try:
                await asyncio.wait_for(event.wait(), timeout=30)
            except asyncio.TimeoutError:
                async with self._async_pending_lock:
                    self._async_pending_events.pop(key, None)
                raise TimeoutError(f"Timeout waiting for async fetch result: {key}")

            async with self._async_pending_lock:
                error = self._async_pending_errors.get(key)
                if error is not None:
                    self._async_pending_events.pop(key, None)
                    self._async_pending_errors.pop(key, None)
                    raise error
                self._async_pending_events.pop(key, None)

            cached = self.get(key)
            if cached is not None:
                return cached
            raise RuntimeError(f"Fetch completed but cache is empty for key: {key}")

        try:
            value = await fetch_fn()
            self.set(key, value, ttl)
            with self._pending_lock:
                event.set()
            return value
        except Exception as e:
            with self._pending_lock:
                self._pending_errors[key] = e
                event.set()
            raise

    def clear(self):
        """清空缓存"""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            # Debug Cycle 9: Cache clear
            self._debug_cycle_9_clear(count)
            logger.info(f"[DataCache] 缓存已清空，删除 {count} 个条目")

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        with self._lock:
            total = self._stats["total_requests"]
            hits = self._stats["hits"]
            misses = self._stats["misses"]

            hit_rate = (hits / total * 100) if total > 0 else 0.0
            miss_rate = (misses / total * 100) if total > 0 else 0.0

            memory_usage = sum(e.size_bytes for e in self._cache.values())

            stats = {
                "hit_rate": round(hit_rate, 2),
                "miss_rate": round(miss_rate, 2),
                "total_requests": total,
                "hits": hits,
                "misses": misses,
                "memory_usage_bytes": memory_usage,
                "memory_usage_mb": round(memory_usage / 1024 / 1024, 2),
                "entry_count": len(self._cache),
                "evictions": self._stats["evictions"],
                "expired_removals": self._stats["expired_removals"],
                "coalesced_requests": self._stats["coalesced_requests"],
            }

            # Debug Cycle 8: Cache statistics
            self._debug_cycle_8_stats(stats)

            return stats

    def cleanup_expired(self) -> int:
        """
        清理过期条目

        Returns:
            清理的条目数量
        """
        with self._lock:
            now = time.time()
            expired_keys = [
                key for key, entry in self._cache.items() if entry.expires_at <= now
            ]

            for key in expired_keys:
                del self._cache[key]
                self._stats["expired_removals"] += 1

            # Debug Cycle 6: Cache cleanup (expired)
            self._debug_cycle_6_cleanup(expired_keys)

            if expired_keys:
                logger.info(f"[DataCache] 清理过期条目: {len(expired_keys)} 个")

            return len(expired_keys)

    def _ensure_space(self, required_bytes: int):
        """确保有足够空间（LRU 驱逐）"""
        current_usage = sum(e.size_bytes for e in self._cache.values())

        while current_usage + required_bytes > self.max_size_bytes and self._cache:
            # 移除最旧的条目（OrderedDict 的第一个）
            oldest_key, oldest_entry = self._cache.popitem(last=False)
            current_usage -= oldest_entry.size_bytes
            self._stats["evictions"] += 1

            # Debug Cycle 7: Memory management
            self._debug_cycle_7_memory_evict(oldest_key, oldest_entry)

            logger.debug(
                f"[DataCache] LRU 驱逐: {oldest_key} ({oldest_entry.size_bytes} bytes)"
            )

    def _estimate_size(self, value: Any) -> int:
        """估算对象大小（字节）"""
        try:
            return sys.getsizeof(value)
        except (TypeError, ValueError):
            # 保守估计
            return 1024

    # ==================== Debug Cycles ====================

    def _debug_cycle_1_init(self):
        """Debug Cycle 1: 缓存初始化"""
        self._debug_cycle += 1
        logger.debug(f"\n{'='*60}")
        logger.debug("[Debug Cycle 1] 缓存初始化")
        logger.debug(f"  - 最大内存: {self.max_size_bytes / 1024 / 1024:.2f} MB")
        logger.debug(f"  - 默认 TTL: {self.default_ttl} 秒")
        logger.debug("  - 线程安全: RLock")
        logger.debug("  - 存储结构: OrderedDict (LRU)")
        logger.debug(f"{'='*60}\n")

    def _debug_cycle_2_set(self, key: str, entry: CacheEntry):
        """Debug Cycle 2: Cache set 操作"""
        self._debug_cycle += 1
        logger.debug(f"\n{'='*60}")
        logger.debug("[Debug Cycle 2] Cache Set 操作")
        logger.debug(f"  - 键: {key}")
        logger.debug(f"  - 大小: {entry.size_bytes} bytes")
        logger.debug(f"  - TTL: {entry.expires_at - entry.created_at:.0f} 秒")
        logger.debug(f"  - 创建时间: {entry.created_at:.3f}")
        logger.debug(f"  - 过期时间: {entry.expires_at:.3f}")
        logger.debug(f"  - 当前条目数: {len(self._cache)}")
        logger.debug(f"{'='*60}\n")

    def _debug_cycle_3_get_hit(self, key: str, entry: CacheEntry):
        """Debug Cycle 3: Cache get (hit)"""
        self._debug_cycle += 1
        logger.debug(f"\n{'='*60}")
        logger.debug("[Debug Cycle 3] Cache Get - HIT")
        logger.debug(f"  - 键: {key}")
        logger.debug(f"  - 命中次数: {entry.hit_count}")
        logger.debug(f"  - 存活时间: {time.time() - entry.created_at:.2f} 秒")
        logger.debug(f"  - 剩余 TTL: {entry.expires_at - time.time():.2f} 秒")
        logger.debug(
            f"  - 总命中率: {self._stats['hits']}/{self._stats['total_requests']}"
        )
        logger.debug(f"{'='*60}\n")

    def _debug_cycle_4_get_miss(self, key: str):
        """Debug Cycle 4: Cache get (miss)"""
        self._debug_cycle += 1
        logger.debug(f"\n{'='*60}")
        logger.debug("[Debug Cycle 4] Cache Get - MISS")
        logger.debug(f"  - 键: {key}")
        logger.debug("  - 原因: 键不存在或已过期")
        logger.debug(f"  - 总未命中数: {self._stats['misses']}")
        logger.debug(f"  - 总请求数: {self._stats['total_requests']}")
        logger.debug(f"{'='*60}\n")

    def _debug_cycle_5_delete(self, key: str):
        """Debug Cycle 5: Cache delete 操作"""
        self._debug_cycle += 1
        logger.debug(f"\n{'='*60}")
        logger.debug("[Debug Cycle 5] Cache Delete 操作")
        logger.debug(f"  - 键: {key}")
        logger.debug("  - 删除结果: 成功")
        logger.debug(f"  - 剩余条目数: {len(self._cache)}")
        logger.debug(f"{'='*60}\n")

    def _debug_cycle_6_cleanup(self, expired_keys: list):
        """Debug Cycle 6: Cache cleanup (expired)"""
        self._debug_cycle += 1
        logger.debug(f"\n{'='*60}")
        logger.debug("[Debug Cycle 6] Cache Cleanup - 过期清理")
        logger.debug(f"  - 清理数量: {len(expired_keys)}")
        logger.debug(f"  - 清理的键: {expired_keys[:10]}")  # 只显示前10个
        logger.debug(f"  - 累计过期清理: {self._stats['expired_removals']}")
        logger.debug(f"  - 剩余条目数: {len(self._cache)}")
        logger.debug(f"{'='*60}\n")

    def _debug_cycle_7_memory_evict(self, key: str, entry: CacheEntry):
        """Debug Cycle 7: Memory management"""
        self._debug_cycle += 1
        memory_usage = sum(e.size_bytes for e in self._cache.values())
        logger.debug(f"\n{'='*60}")
        logger.debug("[Debug Cycle 7] Memory Management - LRU 驱逐")
        logger.debug(f"  - 驱逐键: {key}")
        logger.debug(f"  - 驱逐大小: {entry.size_bytes} bytes")
        logger.debug("  - 驱逐原因: 内存不足")
        logger.debug(f"  - 累计驱逐次数: {self._stats['evictions']}")
        logger.debug(f"  - 当前内存使用: {memory_usage / 1024 / 1024:.2f} MB")
        logger.debug(f"  - 内存限制: {self.max_size_bytes / 1024 / 1024:.2f} MB")
        logger.debug(f"{'='*60}\n")

    def _debug_cycle_8_stats(self, stats: dict):
        """Debug Cycle 8: Cache statistics"""
        self._debug_cycle += 1
        logger.debug(f"\n{'='*60}")
        logger.debug("[Debug Cycle 8] Cache Statistics")
        logger.debug(f"  - 命中率: {stats['hit_rate']}%")
        logger.debug(f"  - 未命中率: {stats['miss_rate']}%")
        logger.debug(f"  - 总请求数: {stats['total_requests']}")
        logger.debug(f"  - 命中数: {stats['hits']}")
        logger.debug(f"  - 未命中数: {stats['misses']}")
        logger.debug(f"  - 内存使用: {stats['memory_usage_mb']} MB")
        logger.debug(f"  - 条目数: {stats['entry_count']}")
        logger.debug(f"  - 驱逐次数: {stats['evictions']}")
        logger.debug(f"  - 过期清理: {stats['expired_removals']}")
        logger.debug(f"{'='*60}\n")

    def _debug_cycle_9_clear(self, count: int):
        """Debug Cycle 9: Cache clear"""
        self._debug_cycle += 1
        logger.debug(f"\n{'='*60}")
        logger.debug("[Debug Cycle 9] Cache Clear")
        logger.debug(f"  - 清空前条目数: {count}")
        logger.debug(f"  - 清空后条目数: {len(self._cache)}")
        logger.debug("  - 统计重置: 否（保留历史统计）")
        logger.debug(f"{'='*60}\n")

    def debug_cycle_10_performance_summary(self):
        """Debug Cycle 10: Performance summary"""
        self._debug_cycle += 1
        stats = self.get_stats()

        logger.info(f"\n{'='*60}")
        logger.info("[Debug Cycle 10] Performance Summary")
        logger.info(f"  - 总 Debug 周期: {self._debug_cycle}")
        logger.info(f"  - 命中率: {stats['hit_rate']}%")
        logger.info(
            f"  - 内存效率: {stats['memory_usage_mb']}/{self.max_size_bytes/1024/1024:.2f} MB"
        )
        logger.info(
            f"  - 平均条目大小: {stats['memory_usage_bytes']/max(stats['entry_count'],1):.0f} bytes"
        )
        logger.info(
            f"  - 驱逐率: {stats['evictions']/max(stats['total_requests'],1)*100:.2f}%"
        )
        logger.info(
            f"  - 过期率: {stats['expired_removals']/max(stats['total_requests'],1)*100:.2f}%"
        )
        logger.info(f"{'='*60}\n")

        return {"debug_cycles": self._debug_cycle, "performance": stats}

    # ═══════════════════════════════════════════════════════════════
    # SQLite 持久化支持（高可用缓存层）
    # ═══════════════════════════════════════════════════════════════

    def get_with_sqlite_fallback(self, key: str, source: str = "") -> Optional[Any]:
        """
        获取缓存值，支持 SQLite 降级

        流程：
        1. 先查内存缓存（快速路径）
        2. 内存未命中时查 SQLite（降级路径）
        3. SQLite 命中时提升到内存

        Args:
            key: 缓存键
            source: 数据源标识（如 'akshare', 'sina'）

        Returns:
            缓存值或 None
        """
        with self._lock:
            self._stats["total_requests"] += 1

            # 1. 内存快速路径
            result = self._get_internal(key)
            if result is not None:
                return result

        # 2. SQLite 降级路径（锁外执行，避免阻塞）
        sqlite_result = self._query_sqlite_cache(key)
        if sqlite_result is not None:
            value = sqlite_result["value"]
            ttl_remaining = int(sqlite_result["expires_at"] - time.time())

            if ttl_remaining > 0:
                # 3. 提升到内存缓存
                with self._lock:
                    self.set(key, value, ttl=ttl_remaining)
                    self._stats["hits"] += 1  # 计为命中（从 SQLite）

                logger.debug(
                    f"[DataCache] SQLite fallback hit: {key}, ttl_remaining={ttl_remaining}s"
                )
                return value

        return None

    def set_with_sqlite_persist(
        self, key: str, value: Any, ttl: Optional[int] = None, source: str = ""
    ):
        """
        设置缓存值，同时持久化到 SQLite

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒）
            source: 数据源标识
        """
        ttl = ttl if ttl is not None else self.default_ttl

        # 1. 写入内存缓存
        with self._lock:
            self.set(key, value, ttl)

        # 2. 异步写入 SQLite（通过 db_writer 队列）
        now = time.time()
        value_json = json.dumps(value) if not isinstance(value, str) else value
        enqueue(
            {
                "type": T_CACHE_PERSIST,
                "rows": [
                    {
                        "key": key,
                        "value": value_json,
                        "created_at": now,
                        "expires_at": now + ttl,
                        "size_bytes": len(value_json),
                        "source": source,
                    }
                ],
            }
        )

        logger.debug(f"[DataCache] Set + persist: {key}, ttl={ttl}s, source={source}")

    def _query_sqlite_cache(self, key: str) -> Optional[Dict]:
        """
        从 SQLite 查询缓存（内部方法）

        Args:
            key: 缓存键

        Returns:
            {'value': Any, 'expires_at': float} 或 None
        """
        import os

        db_path = os.path.join(
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            ),
            "database.db",
        )

        try:
            conn = sqlite3.connect(db_path, timeout=5)
            conn.row_factory = sqlite3.Row

            row = conn.execute(
                "SELECT value, expires_at FROM cache_persistence WHERE key = ?", (key,)
            ).fetchone()

            if row is None:
                conn.close()
                return None

            # 检查是否过期
            if time.time() > row["expires_at"]:
                conn.execute("DELETE FROM cache_persistence WHERE key = ?", (key,))
                conn.commit()
                conn.close()
                return None

            # 解析 JSON
            value = json.loads(row["value"])
            conn.close()

            return {"value": value, "expires_at": row["expires_at"]}

        except Exception as e:
            logger.warning(
                f"[DataCache] SQLite query failed: {key}, error={e}", exc_info=True
            )
            return None

    def restore_from_sqlite(self, limit: int = 100):
        """
        启动时从 SQLite 恢复缓存（预热）

        Args:
            limit: 最大恢复条目数
        """
        import os

        db_path = os.path.join(
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            ),
            "database.db",
        )

        try:
            conn = sqlite3.connect(db_path, timeout=10)
            conn.row_factory = sqlite3.Row

            now = time.time()
            rows = conn.execute(
                "SELECT key, value, expires_at FROM cache_persistence "
                "WHERE expires_at > ? ORDER BY expires_at DESC LIMIT ?",
                (now, limit),
            ).fetchall()

            restored = 0
            for row in rows:
                try:
                    value = json.loads(row["value"])
                    ttl_remaining = int(row["expires_at"] - now)

                    if ttl_remaining > 0:
                        with self._lock:
                            self.set(row["key"], value, ttl=ttl_remaining)
                        restored += 1
                except (json.JSONDecodeError, ValueError, TypeError, KeyError):
                    continue

            conn.close()
            logger.info(f"[DataCache] Restored {restored} entries from SQLite")

        except Exception as e:
            logger.warning(f"[DataCache] SQLite restore failed: {e}", exc_info=True)

    def cleanup_sqlite_expired(self) -> int:
        """
        清理 SQLite 中的过期缓存

        Returns:
            清理的条目数
        """
        import os

        db_path = os.path.join(
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            ),
            "database.db",
        )

        try:
            conn = sqlite3.connect(db_path, timeout=10)
            now = time.time()

            result = conn.execute(
                "DELETE FROM cache_persistence WHERE expires_at < ?", (now,)
            )
            deleted = result.rowcount
            conn.commit()
            conn.close()

            if deleted > 0:
                logger.info(f"[DataCache] SQLite cleanup: {deleted} expired entries")

            return deleted

        except Exception as e:
            logger.warning(f"[DataCache] SQLite cleanup failed: {e}", exc_info=True)
            return 0

    def warmup_cache(self, keys: list, fetch_fns: dict) -> int:
        """
        缓存预热：启动时预加载关键数据

        Args:
            keys: 需要预热的缓存键列表
            fetch_fns: 键到获取函数的映射 {key: callable}

        Returns:
            成功预热的条目数

        Example:
            >>> cache.warmup_cache(
            ...     keys=['kline:sh600519:daily', 'macro:overview'],
            ...     fetch_fns={
            ...         'kline:sh600519:daily': lambda: fetch_kline('sh600519', 'daily'),
            ...         'macro:overview': lambda: fetch_macro_overview()
            ...     }
            ... )
        """
        warmed = 0

        for key in keys:
            if key not in fetch_fns:
                logger.debug(f"[DataCache] Warmup skipped: {key} (no fetch function)")
                continue

            # 检查是否已缓存
            with self._lock:
                existing = self._get_internal(key)
                if existing is not None:
                    logger.debug(f"[DataCache] Warmup skipped: {key} (already cached)")
                    continue

            try:
                fetch_fn = fetch_fns[key]
                value = fetch_fn()

                if value is not None:
                    self.set(key, value)
                    warmed += 1
                    logger.info(f"[DataCache] Warmup success: {key}")
                else:
                    logger.debug(
                        f"[DataCache] Warmup skipped: {key} (fetch returned None)"
                    )

            except Exception as e:
                logger.warning(
                    f"[DataCache] Warmup failed for {key}: {e}", exc_info=True
                )

        logger.info(f"[DataCache] Warmup complete: {warmed}/{len(keys)} entries")
        return warmed

    async def warmup_cache_async(self, keys: list, fetch_fns: dict) -> int:
        """
        异步缓存预热：启动时预加载关键数据

        Args:
            keys: 需要预热的缓存键列表
            fetch_fns: 键到异步获取函数的映射 {key: async_callable}

        Returns:
            成功预热的条目数
        """
        warmed = 0

        for key in keys:
            if key not in fetch_fns:
                logger.debug(
                    f"[DataCache] Async warmup skipped: {key} (no fetch function)"
                )
                continue

            # 检查是否已缓存
            with self._lock:
                existing = self._get_internal(key)
                if existing is not None:
                    logger.debug(
                        f"[DataCache] Async warmup skipped: {key} (already cached)"
                    )
                    continue

            try:
                fetch_fn = fetch_fns[key]
                value = await fetch_fn()

                if value is not None:
                    self.set(key, value)
                    warmed += 1
                    logger.info(f"[DataCache] Async warmup success: {key}")
                else:
                    logger.debug(
                        f"[DataCache] Async warmup skipped: {key} (fetch returned None)"
                    )

            except Exception as e:
                logger.warning(
                    f"[DataCache] Async warmup failed for {key}: {e}", exc_info=True
                )

        logger.info(f"[DataCache] Async warmup complete: {warmed}/{len(keys)} entries")
        return warmed


# 全局缓存实例（单例模式）
_global_cache: Optional[DataCache] = None
_global_cache_lock = threading.Lock()


def get_cache() -> DataCache:
    """获取全局缓存实例"""
    global _global_cache
    if _global_cache is None:
        with _global_cache_lock:
            if _global_cache is None:
                _global_cache = DataCache()
    return _global_cache


# ═══════════════════════════════════════════════════════════════
# @smart_cache Decorator - Unified Multi-Level Caching
# ═══════════════════════════════════════════════════════════════

import functools
import inspect
from typing import Callable, Optional, Any, Dict

# TTL Configuration by data type (from audit requirements)
TTL_CONFIG = {
    # L1 (Memory) TTL - Fast tier for hot data
    "quotes_l1": 10,  # Real-time quotes: 10s
    "macro_l1": 300,  # Macro data: 5min
    "kline_l1": 300,  # K-line data: 5min
    "f9_l1": 300,  # F9 deep data: 5min
    "static_l1": 3600,  # Static data: 1h
    # L2 (SQLite) TTL - Persistent tier for warm data
    "quotes_l2": 3600,  # Quotes: 1h
    "macro_l2": 86400,  # Macro: 24h
    "kline_l2": 86400,  # K-line: 24h
    "f9_l2": 86400,  # F9: 24h
    "static_l2": 604800,  # Static: 7 days
}

# Decorator-level metrics tracking
_decorator_metrics: Dict[str, Dict[str, int]] = {}
_metrics_lock = threading.Lock()


def _get_decorator_metrics() -> Dict[str, Dict[str, int]]:
    """Get decorator-level cache metrics"""
    with _metrics_lock:
        return dict(_decorator_metrics)


def _record_metric(namespace: str, metric: str, value: int = 1):
    """Record a metric for a namespace"""
    with _metrics_lock:
        if namespace not in _decorator_metrics:
            _decorator_metrics[namespace] = {
                "hits": 0,
                "misses": 0,
                "l1_hits": 0,
                "l2_hits": 0,
                "evictions": 0,
                "stale_returns": 0,
                "circuit_breaker_fallbacks": 0,
            }
        _decorator_metrics[namespace][metric] += value


def smart_cache(
    key_template: str,
    level: int = 1,
    ttl: Optional[int] = None,
    ttl_type: Optional[str] = None,
    namespace: str = "",
    source: str = "",
    circuit_breaker: Optional[Any] = None,
    stale_ttl_multiplier: float = 10.0,
):
    """
    Unified multi-level caching decorator with circuit breaker integration.

    Features:
    - L1 (Memory): OrderedDict-based LRU with TTL, thread-safe, request coalescing
    - L2 (SQLite): Persistent cache with WAL mode, auto-promotion on hit
    - Key generation: Template-based with namespace prefix for isolation
    - Circuit breaker: Returns stale data when circuit is OPEN
    - Metrics tracking: Per-namespace hit/miss/eviction statistics

    Args:
        key_template: Cache key template with placeholders, e.g., "kline:{symbol}:{period}"
        level: Cache level (1=memory only, 2=memory+SQLite)
        ttl: Time-to-live in seconds (overrides ttl_type)
        ttl_type: TTL type from TTL_CONFIG (e.g., "quotes_l1", "macro_l2")
        namespace: Namespace prefix for key isolation (e.g., "macro", "forex")
        source: Data source identifier for debugging
        circuit_breaker: Optional CircuitBreaker instance for stale-while-revalidate
        stale_ttl_multiplier: Multiplier for stale TTL (default 10x of fresh TTL)

    Usage:
        # Basic usage
        @smart_cache("kline:{symbol}:{period}", level=2, ttl_type="kline_l1")
        def get_kline(symbol: str, period: str):
            return fetch_kline_data(symbol, period)

        # With namespace and circuit breaker
        @smart_cache(
            key_template="spot:{symbol}",
            level=2,
            ttl_type="quotes_l1",
            namespace="forex",
            circuit_breaker=forex_cb
        )
        async def get_forex_quote(symbol: str):
            return await fetch_forex_quote(symbol)

        # L1 only (memory cache)
        @smart_cache("quote:{symbol}", level=1, ttl=10, namespace="realtime")
        async def get_quote(symbol: str):
            return await fetch_quote(symbol)

    Flow:
        1. Check L1 cache (memory) - fast path
        2. If miss and level=2, check L2 cache (SQLite)
        3. If miss, call the function
        4. Store result in L1 (and L2 if level=2)
        5. If circuit breaker is OPEN, return stale data if available
    """

    def decorator(func: Callable) -> Callable:
        # Determine TTL
        actual_ttl = ttl
        if actual_ttl is None and ttl_type:
            actual_ttl = TTL_CONFIG.get(ttl_type, 300)
        if actual_ttl is None:
            actual_ttl = 300  # Default 5 minutes

        # Determine namespace
        actual_namespace = namespace or func.__module__.split(".")[-1]

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            cache = get_cache()

            # Build cache key from template
            cache_key = _build_cache_key(
                key_template, func, args, kwargs, actual_namespace
            )

            # Check circuit breaker state
            cb_is_open = False
            if circuit_breaker is not None:
                try:
                    cb_is_open = not circuit_breaker.is_available()
                except (AttributeError, RuntimeError):
                    cb_is_open = False

            # L1 check
            if level >= 1:
                result = cache.get(cache_key)
                if result is not None:
                    _record_metric(actual_namespace, "hits")
                    _record_metric(actual_namespace, "l1_hits")
                    logger.debug(f"[smart_cache] L1 hit: {cache_key}")
                    return result

            # L2 check (if level=2)
            if level >= 2:
                result = cache.get_with_sqlite_fallback(cache_key, source)
                if result is not None:
                    _record_metric(actual_namespace, "hits")
                    _record_metric(actual_namespace, "l2_hits")
                    logger.debug(f"[smart_cache] L2 hit: {cache_key}")
                    return result

            # If circuit breaker is open, try to return stale data
            if cb_is_open:
                stale_result = _get_stale_data(
                    cache, cache_key, actual_ttl * stale_ttl_multiplier
                )
                if stale_result is not None:
                    _record_metric(actual_namespace, "stale_returns")
                    _record_metric(actual_namespace, "circuit_breaker_fallbacks")
                    logger.warning(
                        f"[smart_cache] Circuit breaker OPEN, returning stale: {cache_key}"
                    )
                    return stale_result

            # Cache miss - call function
            _record_metric(actual_namespace, "misses")
            logger.debug(f"[smart_cache] Miss: {cache_key}, calling {func.__name__}")
            result = func(*args, **kwargs)

            # Store in cache
            if result is not None:
                cache.set(cache_key, result, ttl=actual_ttl)

                if level >= 2:
                    cache.set_with_sqlite_persist(
                        cache_key, result, ttl=actual_ttl, source=source
                    )

            return result

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            cache = get_cache()

            # Build cache key from template
            cache_key = _build_cache_key(
                key_template, func, args, kwargs, actual_namespace
            )

            # Check circuit breaker state
            cb_is_open = False
            if circuit_breaker is not None:
                try:
                    cb_is_open = not circuit_breaker.is_available()
                except (AttributeError, RuntimeError):
                    cb_is_open = False

            # L1 check
            if level >= 1:
                result = cache.get(cache_key)
                if result is not None:
                    _record_metric(actual_namespace, "hits")
                    _record_metric(actual_namespace, "l1_hits")
                    logger.debug(f"[smart_cache] L1 hit: {cache_key}")
                    return result

            # L2 check (if level=2)
            if level >= 2:
                result = cache.get_with_sqlite_fallback(cache_key, source)
                if result is not None:
                    _record_metric(actual_namespace, "hits")
                    _record_metric(actual_namespace, "l2_hits")
                    logger.debug(f"[smart_cache] L2 hit: {cache_key}")
                    return result

            # If circuit breaker is open, try to return stale data
            if cb_is_open:
                stale_result = _get_stale_data(
                    cache, cache_key, actual_ttl * stale_ttl_multiplier
                )
                if stale_result is not None:
                    _record_metric(actual_namespace, "stale_returns")
                    _record_metric(actual_namespace, "circuit_breaker_fallbacks")
                    logger.warning(
                        f"[smart_cache] Circuit breaker OPEN, returning stale: {cache_key}"
                    )
                    return stale_result
                # CB is open and no stale data - raise error
                from app.services.circuit_breaker import CircuitBreakerOpen

                cb_name = circuit_breaker.name if circuit_breaker else "unknown"
                cb_timeout = circuit_breaker.config.timeout if circuit_breaker else 30
                raise CircuitBreakerOpen(cb_name, cb_timeout)

            # Cache miss - use request coalescing for async
            _record_metric(actual_namespace, "misses")
            logger.debug(f"[smart_cache] Miss: {cache_key}, calling {func.__name__}")

            async def fetch_fn():
                return await func(*args, **kwargs)

            result = await cache.get_or_set_async(cache_key, fetch_fn, ttl=actual_ttl)

            # Store in L2 if level=2
            if result is not None and level >= 2:
                cache.set_with_sqlite_persist(
                    cache_key, result, ttl=actual_ttl, source=source
                )

            return result

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def _build_cache_key(
    template: str, func: Callable, args: tuple, kwargs: dict, namespace: str = ""
) -> str:
    """
    Build cache key from template and function arguments.

    Template format: "prefix:{arg1}:{arg2}"
    Named placeholders are replaced with argument values.

    Args:
        template: Key template with placeholders
        func: The decorated function
        args: Positional arguments
        kwargs: Keyword arguments
        namespace: Optional namespace prefix

    Returns:
        Fully resolved cache key
    """
    # Get function signature
    sig = inspect.signature(func)
    params = list(sig.parameters.keys())

    # Build argument dictionary
    arg_dict = {}
    for i, param in enumerate(params):
        if i < len(args):
            arg_dict[param] = args[i]

    # Add keyword arguments
    arg_dict.update(kwargs)

    # Replace placeholders in template
    key = template
    for param, value in arg_dict.items():
        placeholder = "{" + param + "}"
        if placeholder in key:
            key = key.replace(placeholder, str(value))

    # Add namespace prefix
    if namespace:
        key = f"{namespace}:{key}"

    return key


def _get_stale_data(cache: DataCache, key: str, stale_ttl: float) -> Optional[Any]:
    """
    Get stale data from cache when circuit breaker is open.

    Uses get_with_stale() to allow returning expired but usable data.

    Args:
        cache: DataCache instance
        key: Cache key
        stale_ttl: Maximum age for stale data (seconds)

    Returns:
        Stale data or None
    """
    try:
        data, is_stale = cache.get_with_stale(
            key, fresh_ttl=0, stale_ttl=int(stale_ttl)
        )
        return data
    except Exception as e:
        logger.debug(f"[smart_cache] Failed to get stale data for {key}: {e}")
        return None


# Convenience decorators for common use cases
def cache_quotes(func: Callable) -> Callable:
    """Cache real-time quotes (L1: 10s, L2: 1h)"""
    return smart_cache(
        key_template="quote:{symbol}",
        level=2,
        ttl_type="quotes_l1",
        namespace="quotes",
        source="quotes",
    )(func)


def cache_macro(func: Callable) -> Callable:
    """Cache macro data (L1: 5min, L2: 24h)"""
    return smart_cache(
        key_template="macro:{indicator}",
        level=2,
        ttl_type="macro_l1",
        namespace="macro",
        source="macro",
    )(func)


def cache_kline(func: Callable) -> Callable:
    """Cache K-line data (L1: 5min, L2: 24h)"""
    return smart_cache(
        key_template="kline:{symbol}:{period}",
        level=2,
        ttl_type="kline_l1",
        namespace="kline",
        source="kline",
    )(func)


def cache_f9(func: Callable) -> Callable:
    """Cache F9 deep data (L1: 5min, L2: 24h)"""
    return smart_cache(
        key_template="f9:{symbol}:{tab}",
        level=2,
        ttl_type="f9_l1",
        namespace="f9",
        source="f9",
    )(func)


def cache_static(func: Callable) -> Callable:
    """Cache static data (L1: 1h, L2: 7 days)"""
    return smart_cache(
        key_template="static:{type}:{id}",
        level=2,
        ttl_type="static_l1",
        namespace="static",
        source="static",
    )(func)


# Factory function for creating circuit-breaker-aware decorators
def create_cached_fetcher(
    namespace: str, ttl_type: str, circuit_breaker: Optional[Any] = None, level: int = 2
):
    """
    Factory function to create a cached fetcher with circuit breaker.

    Usage:
        forex_cb = CircuitBreaker("forex", failure_threshold=5, timeout=60)

        @create_cached_fetcher("forex", "quotes_l1", forex_cb)
        async def fetch_forex_quote(symbol: str):
            return await fetch_from_api(symbol)

    Args:
        namespace: Cache namespace
        ttl_type: TTL type from TTL_CONFIG
        circuit_breaker: Optional CircuitBreaker instance
        level: Cache level (1 or 2)

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        # Infer key template from function signature
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())

        # Build key template from first parameter (usually the identifier)
        if params:
            key_template = f"{{{params[0]}}}"
        else:
            key_template = "data"

        return smart_cache(
            key_template=key_template,
            level=level,
            ttl_type=ttl_type,
            namespace=namespace,
            circuit_breaker=circuit_breaker,
        )(func)

    return decorator
