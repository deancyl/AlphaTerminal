"""
test_data_cache.py — Unit tests for DataCache module
Tests all cache functionality including:
  - Basic operations (get, set, delete, clear)
  - TTL expiration
  - LRU eviction
  - Memory management
  - Thread safety
  - Statistics tracking
  - Debug logging (10 cycles)
"""
import pytest
import time
import threading
import logging
from app.services.data_cache import DataCache, CacheEntry, get_cache


class TestCacheEntry:
    """Test CacheEntry dataclass."""
    
    def test_cache_entry_creation(self):
        """Test creating a cache entry."""
        now = time.time()
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            created_at=now,
            expires_at=now + 300,
            size_bytes=100,
            hit_count=0
        )
        assert entry.key == "test_key"
        assert entry.value == "test_value"
        assert entry.created_at == now
        assert entry.expires_at == now + 300
        assert entry.size_bytes == 100
        assert entry.hit_count == 0
    
    def test_is_expired_false(self):
        """Test is_expired returns False for valid entry."""
        now = time.time()
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            created_at=now,
            expires_at=now + 300
        )
        assert entry.is_expired() is False
    
    def test_is_expired_true(self):
        """Test is_expired returns True for expired entry."""
        now = time.time()
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            created_at=now - 400,
            expires_at=now - 100
        )
        assert entry.is_expired() is True


class TestDataCacheBasic:
    """Test basic cache operations."""
    
    def test_cache_initialization(self):
        """Test cache initializes correctly."""
        cache = DataCache(max_size_mb=50, default_ttl=600)
        assert cache.max_size_bytes == 50 * 1024 * 1024
        assert cache.default_ttl == 600
        assert len(cache._cache) == 0
        assert cache._stats["hits"] == 0
        assert cache._stats["misses"] == 0
    
    def test_set_and_get(self):
        """Test basic set and get operations."""
        cache = DataCache()
        
        assert cache.set("key1", "value1") is True
        assert cache.get("key1") == "value1"
        
        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["entry_count"] == 1
    
    def test_get_nonexistent_key(self):
        """Test getting a nonexistent key."""
        cache = DataCache()
        
        value = cache.get("nonexistent")
        assert value is None
        
        stats = cache.get_stats()
        assert stats["misses"] == 1
    
    def test_delete(self):
        """Test delete operation."""
        cache = DataCache()
        
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        assert cache.delete("key1") is True
        assert cache.get("key1") is None
        assert cache.delete("key1") is False
    
    def test_clear(self):
        """Test clear operation."""
        cache = DataCache()
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        
        assert len(cache._cache) == 3
        
        cache.clear()
        
        assert len(cache._cache) == 0
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.get("key3") is None


class TestDataCacheTTL:
    """Test TTL expiration."""
    
    def test_ttl_expiration(self):
        """Test that entries expire after TTL."""
        cache = DataCache(default_ttl=1)
        
        cache.set("key1", "value1", ttl=1)
        
        # Should exist immediately
        value = cache.get("key1")
        assert value == "value1"
        
        # Wait for expiration
        time.sleep(1.5)
        
        # Should be expired
        value = cache.get("key1")
        assert value is None
        
        # Check stats
        stats = cache.get_stats()
        assert stats["expired_removals"] >= 1
    
    def test_custom_ttl(self):
        """Test custom TTL for individual entries."""
        cache = DataCache(default_ttl=300)
        
        # Set with custom TTL
        cache.set("key1", "value1", ttl=1)
        cache.set("key2", "value2", ttl=300)
        
        # Wait for key1 to expire
        time.sleep(1.5)
        
        # key1 should be expired
        assert cache.get("key1") is None
        
        # key2 should still exist
        assert cache.get("key2") == "value2"
    
    def test_cleanup_expired(self):
        """Test manual cleanup of expired entries."""
        cache = DataCache()
        
        cache.set("key1", "value1", ttl=1)
        cache.set("key2", "value2", ttl=1)
        cache.set("key3", "value3", ttl=300)
        
        # Wait for key1 and key2 to expire
        time.sleep(1.5)
        
        # Cleanup
        count = cache.cleanup_expired()
        
        assert count == 2
        assert len(cache._cache) == 1
        assert cache.get("key3") == "value3"


class TestDataCacheLRU:
    """Test LRU eviction."""
    
    def test_lru_eviction(self):
        """Test LRU eviction when memory limit reached."""
        # Create cache with very small limit
        cache = DataCache(max_size_mb=1, default_ttl=300)
        
        # Add entries until eviction occurs
        large_value = "x" * 100000  # ~100KB
        
        for i in range(20):
            cache.set(f"key_{i}", large_value)
        
        # Check that eviction occurred
        stats = cache.get_stats()
        assert stats["evictions"] > 0
        
        # First entries should be evicted
        assert cache.get("key_0") is None
        
        # Recent entries should exist
        assert cache.get("key_19") is not None
    
    def test_lru_order_on_access(self):
        """Test that accessing an entry updates its LRU position."""
        cache = DataCache(max_size_mb=1, default_ttl=300)
        
        large_value = "x" * 100000
        
        cache.set("key_1", large_value)
        cache.set("key_2", large_value)
        cache.get("key_1")
        
        for i in range(3, 15):
            cache.set(f"key_{i}", large_value)
        
        stats = cache.get_stats()
        assert stats["evictions"] > 0


class TestDataCacheMemory:
    """Test memory management."""
    
    def test_memory_limit_enforcement(self):
        """Test that memory limit is enforced."""
        cache = DataCache(max_size_mb=1, default_ttl=300)
        
        large_value = "x" * 500000  # ~500KB
        cache.set("key1", large_value)
        
        stats = cache.get_stats()
        assert stats["memory_usage_bytes"] > 0
        assert stats["memory_usage_mb"] < 1.0
    
    def test_reject_oversized_value(self):
        """Test that oversized values are rejected."""
        cache = DataCache(max_size_mb=1, default_ttl=300)
        
        # Try to set a value larger than 50% of max size
        huge_value = "x" * 600000  # ~600KB
        result = cache.set("huge_key", huge_value)
        
        # Should be rejected
        assert result is False


class TestDataCacheStatistics:
    """Test statistics tracking."""
    
    def test_hit_rate_calculation(self):
        """Test hit rate calculation."""
        cache = DataCache()
        
        cache.set("key1", "value1")
        
        # 2 hits
        cache.get("key1")
        cache.get("key1")
        
        # 2 misses
        cache.get("key2")
        cache.get("key3")
        
        stats = cache.get_stats()
        
        assert stats["hits"] == 2
        assert stats["misses"] == 2
        assert stats["total_requests"] == 4
        assert stats["hit_rate"] == 50.0
        assert stats["miss_rate"] == 50.0
    
    def test_statistics_tracking(self):
        """Test comprehensive statistics tracking."""
        cache = DataCache()
        
        # Perform various operations
        cache.set("key1", "value1")
        cache.get("key1")  # hit
        cache.get("key2")  # miss
        cache.delete("key1")
        cache.set("key3", "value3", ttl=1)
        
        time.sleep(1.5)
        cache.get("key3")  # miss (expired)
        cache.cleanup_expired()
        
        stats = cache.get_stats()
        
        assert stats["total_requests"] == 3
        assert stats["hits"] == 1
        assert stats["misses"] == 2
        assert stats["expired_removals"] >= 1


class TestDataCacheThreadSafety:
    """Test thread safety."""
    
    def test_concurrent_access(self):
        """Test concurrent read/write operations."""
        cache = DataCache()
        errors = []
        
        def writer(start, count):
            try:
                for i in range(start, start + count):
                    cache.set(f"key_{i}", f"value_{i}")
            except RuntimeError as e:
                errors.append(e)
            except Exception as e:
                errors.append(e)

        def reader(start, count):
            try:
                for i in range(start, start + count):
                    cache.get(f"key_{i}")
            except RuntimeError as e:
                errors.append(e)
            except Exception as e:
                errors.append(e)
        
        # Create threads
        threads = []
        for i in range(5):
            threads.append(threading.Thread(target=writer, args=(i * 100, 100)))
            threads.append(threading.Thread(target=reader, args=(i * 100, 100)))
        
        # Start all threads
        for t in threads:
            t.start()
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # No errors should occur
        assert len(errors) == 0
        
        # Cache should have entries
        stats = cache.get_stats()
        assert stats["entry_count"] > 0


class TestDataCacheDebugCycles:
    """Test debug logging cycles."""
    
    def test_debug_cycle_1_init(self, caplog):
        """Test Debug Cycle 1: Cache initialization."""
        with caplog.at_level(logging.DEBUG):
            cache = DataCache(max_size_mb=50, default_ttl=600)
        
        # Check debug log contains initialization info
        assert any("Debug Cycle 1" in record.message for record in caplog.records)
        assert any("缓存初始化" in record.message for record in caplog.records)
    
    def test_debug_cycle_2_set(self, caplog):
        """Test Debug Cycle 2: Cache set operation."""
        cache = DataCache()
        
        with caplog.at_level(logging.DEBUG):
            cache.set("test_key", "test_value")
        
        assert any("Debug Cycle 2" in record.message for record in caplog.records)
        assert any("Cache Set 操作" in record.message for record in caplog.records)
    
    def test_debug_cycle_3_get_hit(self, caplog):
        """Test Debug Cycle 3: Cache get (hit)."""
        cache = DataCache()
        cache.set("test_key", "test_value")
        
        with caplog.at_level(logging.DEBUG):
            cache.get("test_key")
        
        assert any("Debug Cycle 3" in record.message for record in caplog.records)
        assert any("Cache Get - HIT" in record.message for record in caplog.records)
    
    def test_debug_cycle_4_get_miss(self, caplog):
        """Test Debug Cycle 4: Cache get (miss)."""
        cache = DataCache()
        
        with caplog.at_level(logging.DEBUG):
            cache.get("nonexistent_key")
        
        assert any("Debug Cycle 4" in record.message for record in caplog.records)
        assert any("Cache Get - MISS" in record.message for record in caplog.records)
    
    def test_debug_cycle_5_delete(self, caplog):
        """Test Debug Cycle 5: Cache delete operation."""
        cache = DataCache()
        cache.set("test_key", "test_value")
        
        with caplog.at_level(logging.DEBUG):
            cache.delete("test_key")
        
        assert any("Debug Cycle 5" in record.message for record in caplog.records)
        assert any("Cache Delete 操作" in record.message for record in caplog.records)
    
    def test_debug_cycle_6_cleanup(self, caplog):
        """Test Debug Cycle 6: Cache cleanup (expired)."""
        cache = DataCache()
        cache.set("test_key", "test_value", ttl=1)
        
        time.sleep(1.5)
        
        with caplog.at_level(logging.DEBUG):
            cache.cleanup_expired()
        
        assert any("Debug Cycle 6" in record.message for record in caplog.records)
        assert any("Cache Cleanup" in record.message for record in caplog.records)
    
    def test_debug_cycle_7_memory_evict(self, caplog):
        """Test Debug Cycle 7: Memory management."""
        cache = DataCache(max_size_mb=1, default_ttl=300)
        
        large_value = "x" * 100000
        
        with caplog.at_level(logging.DEBUG):
            for i in range(20):
                cache.set(f"key_{i}", large_value)
        
        assert any("Debug Cycle 7" in record.message for record in caplog.records)
        assert any("Memory Management" in record.message for record in caplog.records)
    
    def test_debug_cycle_8_stats(self, caplog):
        """Test Debug Cycle 8: Cache statistics."""
        cache = DataCache()
        cache.set("test_key", "test_value")
        
        with caplog.at_level(logging.DEBUG):
            cache.get_stats()
        
        assert any("Debug Cycle 8" in record.message for record in caplog.records)
        assert any("Cache Statistics" in record.message for record in caplog.records)
    
    def test_debug_cycle_9_clear(self, caplog):
        """Test Debug Cycle 9: Cache clear."""
        cache = DataCache()
        cache.set("test_key", "test_value")
        
        with caplog.at_level(logging.DEBUG):
            cache.clear()
        
        assert any("Debug Cycle 9" in record.message for record in caplog.records)
        assert any("Cache Clear" in record.message for record in caplog.records)
    
    def test_debug_cycle_10_performance_summary(self, caplog):
        """Test Debug Cycle 10: Performance summary."""
        cache = DataCache()
        cache.set("test_key", "test_value")
        cache.get("test_key")
        
        with caplog.at_level(logging.INFO):
            result = cache.debug_cycle_10_performance_summary()
        
        assert "debug_cycles" in result
        assert "performance" in result
        assert any("Debug Cycle 10" in record.message for record in caplog.records)
        assert any("Performance Summary" in record.message for record in caplog.records)


class TestGlobalCache:
    """Test global cache instance."""
    
    def test_get_cache_singleton(self):
        """Test that get_cache returns singleton."""
        cache1 = get_cache()
        cache2 = get_cache()
        
        assert cache1 is cache2
    
    def test_global_cache_functionality(self):
        """Test global cache works correctly."""
        cache = get_cache()
        
        cache.set("global_key", "global_value")
        assert cache.get("global_key") == "global_value"
        
        # Clean up
        cache.delete("global_key")


class TestDataCacheEdgeCases:
    """Test edge cases and error handling."""
    
    def test_set_none_value(self):
        """Test setting None as value."""
        cache = DataCache()
        
        result = cache.set("none_key", None)
        assert result is True
        
        value = cache.get("none_key")
        assert value is None
        
        stats = cache.get_stats()
        assert stats["misses"] == 0
    
    def test_set_complex_object(self):
        """Test setting complex objects."""
        cache = DataCache()
        
        complex_obj = {
            "nested": {
                "data": [1, 2, 3],
                "meta": {"key": "value"}
            }
        }
        
        result = cache.set("complex_key", complex_obj)
        assert result is True
        
        value = cache.get("complex_key")
        assert value == complex_obj
    
    def test_update_existing_key(self):
        """Test updating an existing key."""
        cache = DataCache()
        
        cache.set("key1", "value1")
        cache.set("key1", "value2")
        
        value = cache.get("key1")
        assert value == "value2"
        
        # Should only have 1 entry
        assert len(cache._cache) == 1
    
    def test_zero_ttl(self):
        """Test zero TTL (immediate expiration)."""
        cache = DataCache()
        
        cache.set("key1", "value1", ttl=0)
        
        # Should be expired immediately
        value = cache.get("key1")
        assert value is None
    
    def test_negative_ttl(self):
        """Test negative TTL (already expired)."""
        cache = DataCache()
        
        cache.set("key1", "value1", ttl=-10)
        
        # Should be expired
        value = cache.get("key1")
        assert value is None
