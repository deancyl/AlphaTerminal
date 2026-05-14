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
import sqlite3
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from app.db.db_writer import enqueue, T_CACHE_PERSIST

logger = logging.getLogger(__name__)


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
        
        # 统计信息
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "expired_removals": 0,
            "total_requests": 0,
        }
        
        # Debug 周期计数器
        self._debug_cycle = 0
        
        # Debug Cycle 1: 缓存初始化
        self._debug_cycle_1_init()
        
        logger.info(f"[DataCache] 初始化完成: max_size={max_size_mb}MB, default_ttl={default_ttl}s")
    
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
            ttl: 过期时间（秒），None 使用默认值
            
        Returns:
            是否成功
        """
        with self._lock:
            # 计算大小
            size_bytes = self._estimate_size(value)
            
            # 检查单个值是否超过限制
            if size_bytes > self.max_size_bytes * 0.5:
                logger.warning(f"[DataCache] 值过大，拒绝缓存: {key} ({size_bytes} bytes)")
                return False
            
            # 清理空间
            self._ensure_space(size_bytes)
            
            # 创建条目
            now = time.time()
            ttl = ttl if ttl is not None else self.default_ttl
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=now,
                expires_at=now + ttl,
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
                # Debug Cycle 5: Cache delete
                self._debug_cycle_5_delete(key)
                return True
            return False
    
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
                key for key, entry in self._cache.items()
                if entry.expires_at <= now
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
            
            logger.debug(f"[DataCache] LRU 驱逐: {oldest_key} ({oldest_entry.size_bytes} bytes)")
    
    def _estimate_size(self, value: Any) -> int:
        """估算对象大小（字节）"""
        try:
            return sys.getsizeof(value)
        except Exception:
            # 保守估计
            return 1024
    
    # ==================== Debug Cycles ====================
    
    def _debug_cycle_1_init(self):
        """Debug Cycle 1: 缓存初始化"""
        self._debug_cycle += 1
        logger.debug(f"\n{'='*60}")
        logger.debug(f"[Debug Cycle 1] 缓存初始化")
        logger.debug(f"  - 最大内存: {self.max_size_bytes / 1024 / 1024:.2f} MB")
        logger.debug(f"  - 默认 TTL: {self.default_ttl} 秒")
        logger.debug(f"  - 线程安全: RLock")
        logger.debug(f"  - 存储结构: OrderedDict (LRU)")
        logger.debug(f"{'='*60}\n")
    
    def _debug_cycle_2_set(self, key: str, entry: CacheEntry):
        """Debug Cycle 2: Cache set 操作"""
        self._debug_cycle += 1
        logger.debug(f"\n{'='*60}")
        logger.debug(f"[Debug Cycle 2] Cache Set 操作")
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
        logger.debug(f"[Debug Cycle 3] Cache Get - HIT")
        logger.debug(f"  - 键: {key}")
        logger.debug(f"  - 命中次数: {entry.hit_count}")
        logger.debug(f"  - 存活时间: {time.time() - entry.created_at:.2f} 秒")
        logger.debug(f"  - 剩余 TTL: {entry.expires_at - time.time():.2f} 秒")
        logger.debug(f"  - 总命中率: {self._stats['hits']}/{self._stats['total_requests']}")
        logger.debug(f"{'='*60}\n")
    
    def _debug_cycle_4_get_miss(self, key: str):
        """Debug Cycle 4: Cache get (miss)"""
        self._debug_cycle += 1
        logger.debug(f"\n{'='*60}")
        logger.debug(f"[Debug Cycle 4] Cache Get - MISS")
        logger.debug(f"  - 键: {key}")
        logger.debug(f"  - 原因: 键不存在或已过期")
        logger.debug(f"  - 总未命中数: {self._stats['misses']}")
        logger.debug(f"  - 总请求数: {self._stats['total_requests']}")
        logger.debug(f"{'='*60}\n")
    
    def _debug_cycle_5_delete(self, key: str):
        """Debug Cycle 5: Cache delete 操作"""
        self._debug_cycle += 1
        logger.debug(f"\n{'='*60}")
        logger.debug(f"[Debug Cycle 5] Cache Delete 操作")
        logger.debug(f"  - 键: {key}")
        logger.debug(f"  - 删除结果: 成功")
        logger.debug(f"  - 剩余条目数: {len(self._cache)}")
        logger.debug(f"{'='*60}\n")
    
    def _debug_cycle_6_cleanup(self, expired_keys: list):
        """Debug Cycle 6: Cache cleanup (expired)"""
        self._debug_cycle += 1
        logger.debug(f"\n{'='*60}")
        logger.debug(f"[Debug Cycle 6] Cache Cleanup - 过期清理")
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
        logger.debug(f"[Debug Cycle 7] Memory Management - LRU 驱逐")
        logger.debug(f"  - 驱逐键: {key}")
        logger.debug(f"  - 驱逐大小: {entry.size_bytes} bytes")
        logger.debug(f"  - 驱逐原因: 内存不足")
        logger.debug(f"  - 累计驱逐次数: {self._stats['evictions']}")
        logger.debug(f"  - 当前内存使用: {memory_usage / 1024 / 1024:.2f} MB")
        logger.debug(f"  - 内存限制: {self.max_size_bytes / 1024 / 1024:.2f} MB")
        logger.debug(f"{'='*60}\n")
    
    def _debug_cycle_8_stats(self, stats: dict):
        """Debug Cycle 8: Cache statistics"""
        self._debug_cycle += 1
        logger.debug(f"\n{'='*60}")
        logger.debug(f"[Debug Cycle 8] Cache Statistics")
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
        logger.debug(f"[Debug Cycle 9] Cache Clear")
        logger.debug(f"  - 清空前条目数: {count}")
        logger.debug(f"  - 清空后条目数: {len(self._cache)}")
        logger.debug(f"  - 统计重置: 否（保留历史统计）")
        logger.debug(f"{'='*60}\n")
    
    def debug_cycle_10_performance_summary(self):
        """Debug Cycle 10: Performance summary"""
        self._debug_cycle += 1
        stats = self.get_stats()
        
        logger.info(f"\n{'='*60}")
        logger.info(f"[Debug Cycle 10] Performance Summary")
        logger.info(f"  - 总 Debug 周期: {self._debug_cycle}")
        logger.info(f"  - 命中率: {stats['hit_rate']}%")
        logger.info(f"  - 内存效率: {stats['memory_usage_mb']}/{self.max_size_bytes/1024/1024:.2f} MB")
        logger.info(f"  - 平均条目大小: {stats['memory_usage_bytes']/max(stats['entry_count'],1):.0f} bytes")
        logger.info(f"  - 驱逐率: {stats['evictions']/max(stats['total_requests'],1)*100:.2f}%")
        logger.info(f"  - 过期率: {stats['expired_removals']/max(stats['total_requests'],1)*100:.2f}%")
        logger.info(f"{'='*60}\n")
        
        return {
            "debug_cycles": self._debug_cycle,
            "performance": stats
        }

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
            value = sqlite_result['value']
            ttl_remaining = int(sqlite_result['expires_at'] - time.time())
            
            if ttl_remaining > 0:
                # 3. 提升到内存缓存
                with self._lock:
                    self.set(key, value, ttl=ttl_remaining)
                    self._stats["hits"] += 1  # 计为命中（从 SQLite）
                
                logger.debug(f"[DataCache] SQLite fallback hit: {key}, ttl_remaining={ttl_remaining}s")
                return value
        
        return None

    def set_with_sqlite_persist(self, key: str, value: Any, ttl: int = None, source: str = ""):
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
        enqueue({
            "type": T_CACHE_PERSIST,
            "rows": [{
                "key": key,
                "value": value_json,
                "created_at": now,
                "expires_at": now + ttl,
                "size_bytes": len(value_json),
                "source": source
            }]
        })
        
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
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            'database.db'
        )
        
        try:
            conn = sqlite3.connect(db_path, timeout=5)
            conn.row_factory = sqlite3.Row
            
            row = conn.execute(
                "SELECT value, expires_at FROM cache_persistence WHERE key = ?",
                (key,)
            ).fetchone()
            
            if row is None:
                conn.close()
                return None
            
            # 检查是否过期
            if time.time() > row['expires_at']:
                conn.execute("DELETE FROM cache_persistence WHERE key = ?", (key,))
                conn.commit()
                conn.close()
                return None
            
            # 解析 JSON
            value = json.loads(row['value'])
            conn.close()
            
            return {'value': value, 'expires_at': row['expires_at']}
            
        except Exception as e:
            logger.warning(f"[DataCache] SQLite query failed: {key}, error={e}")
            return None

    def restore_from_sqlite(self, limit: int = 100):
        """
        启动时从 SQLite 恢复缓存（预热）
        
        Args:
            limit: 最大恢复条目数
        """
        import os
        db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            'database.db'
        )
        
        try:
            conn = sqlite3.connect(db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            
            now = time.time()
            rows = conn.execute(
                "SELECT key, value, expires_at FROM cache_persistence "
                "WHERE expires_at > ? ORDER BY expires_at DESC LIMIT ?",
                (now, limit)
            ).fetchall()
            
            restored = 0
            for row in rows:
                try:
                    value = json.loads(row['value'])
                    ttl_remaining = int(row['expires_at'] - now)
                    
                    if ttl_remaining > 0:
                        with self._lock:
                            self.set(row['key'], value, ttl=ttl_remaining)
                        restored += 1
                except Exception:
                    continue
            
            conn.close()
            logger.info(f"[DataCache] Restored {restored} entries from SQLite")
            
        except Exception as e:
            logger.warning(f"[DataCache] SQLite restore failed: {e}")

    def cleanup_sqlite_expired(self) -> int:
        """
        清理 SQLite 中的过期缓存
        
        Returns:
            清理的条目数
        """
        import os
        db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            'database.db'
        )
        
        try:
            conn = sqlite3.connect(db_path, timeout=10)
            now = time.time()
            
            result = conn.execute(
                "DELETE FROM cache_persistence WHERE expires_at < ?",
                (now,)
            )
            deleted = result.rowcount
            conn.commit()
            conn.close()
            
            if deleted > 0:
                logger.info(f"[DataCache] SQLite cleanup: {deleted} expired entries")
            
            return deleted
            
        except Exception as e:
            logger.warning(f"[DataCache] SQLite cleanup failed: {e}")
            return 0


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
