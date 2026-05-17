"""
Cache Metrics Collector for Prometheus Monitoring

Provides metrics for:
- Cache hit/miss/eviction rates
- Data source fetch latencies
- Data source request/error counts
"""

import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from threading import Lock
from collections import defaultdict


@dataclass
class CacheMetrics:
    """Thread-safe cache metrics collector."""
    
    # Cache statistics
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    
    # Latency tracking (in seconds)
    fetch_latencies: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))
    
    # Data source statistics
    source_requests: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    source_errors: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    # Thread safety
    _lock: Lock = field(default_factory=Lock, repr=False)
    
    def record_hit(self) -> None:
        """Record a cache hit."""
        with self._lock:
            self.hits += 1
    
    def record_miss(self) -> None:
        """Record a cache miss."""
        with self._lock:
            self.misses += 1
    
    def record_eviction(self) -> None:
        """Record a cache eviction."""
        with self._lock:
            self.evictions += 1
    
    def record_latency(self, source: str, latency_seconds: float) -> None:
        """
        Record fetch latency for a data source.
        
        Args:
            source: Data source identifier (e.g., 'akshare', 'sina', 'eastmoney')
            latency_seconds: Time taken to fetch data
        """
        with self._lock:
            # Keep only last 1000 samples per source to prevent memory growth
            if len(self.fetch_latencies[source]) >= 1000:
                self.fetch_latencies[source] = self.fetch_latencies[source][-999:]
            self.fetch_latencies[source].append(latency_seconds)
    
    def record_request(self, source: str) -> None:
        """Record a request to a data source."""
        with self._lock:
            self.source_requests[source] += 1
    
    def record_error(self, source: str) -> None:
        """Record an error from a data source."""
        with self._lock:
            self.source_errors[source] += 1
    
    def get_hit_rate(self) -> float:
        """Calculate cache hit rate (0.0 to 1.0)."""
        with self._lock:
            total = self.hits + self.misses
            return self.hits / total if total > 0 else 0.0
    
    def get_avg_latency(self, source: str) -> float:
        """Get average latency for a data source."""
        with self._lock:
            latencies = self.fetch_latencies.get(source, [])
            return sum(latencies) / len(latencies) if latencies else 0.0
    
    def get_p95_latency(self, source: str) -> float:
        """Get 95th percentile latency for a data source."""
        with self._lock:
            latencies = self.fetch_latencies.get(source, [])
            if not latencies:
                return 0.0
            sorted_latencies = sorted(latencies)
            idx = int(len(sorted_latencies) * 0.95)
            return sorted_latencies[min(idx, len(sorted_latencies) - 1)]
    
    def get_error_rate(self, source: str) -> float:
        """Get error rate for a data source (0.0 to 1.0)."""
        with self._lock:
            requests = self.source_requests.get(source, 0)
            errors = self.source_errors.get(source, 0)
            return errors / requests if requests > 0 else 0.0
    
    def to_prometheus(self) -> str:
        """
        Export metrics in Prometheus text format.
        
        Returns:
            Prometheus-formatted metrics string
        """
        with self._lock:
            total = self.hits + self.misses
            hit_rate = self.hits / total if total > 0 else 0.0
            
            lines = []
            
            lines.append("# HELP cache_hits_total Total number of cache hits")
            lines.append("# TYPE cache_hits_total counter")
            lines.append(f"cache_hits_total {self.hits}")
            
            lines.append("# HELP cache_misses_total Total number of cache misses")
            lines.append("# TYPE cache_misses_total counter")
            lines.append(f"cache_misses_total {self.misses}")
            
            lines.append("# HELP cache_evictions_total Total number of cache evictions")
            lines.append("# TYPE cache_evictions_total counter")
            lines.append(f"cache_evictions_total {self.evictions}")
            
            lines.append("# HELP cache_hit_rate Current cache hit rate (0-1)")
            lines.append("# TYPE cache_hit_rate gauge")
            lines.append(f"cache_hit_rate {hit_rate:.6f}")
            
            lines.append("")
            lines.append("# HELP datasource_requests_total Total requests per data source")
            lines.append("# TYPE datasource_requests_total counter")
            for source, count in self.source_requests.items():
                lines.append(f'datasource_requests_total{{source="{source}"}} {count}')
            
            lines.append("# HELP datasource_errors_total Total errors per data source")
            lines.append("# TYPE datasource_errors_total counter")
            for source, count in self.source_errors.items():
                lines.append(f'datasource_errors_total{{source="{source}"}} {count}')
            
            lines.append("# HELP datasource_error_rate Error rate per data source (0-1)")
            lines.append("# TYPE datasource_error_rate gauge")
            for source in self.source_requests.keys():
                requests = self.source_requests.get(source, 0)
                errors = self.source_errors.get(source, 0)
                error_rate = errors / requests if requests > 0 else 0.0
                lines.append(f'datasource_error_rate{{source="{source}"}} {error_rate:.6f}')
            
            lines.append("")
            lines.append("# HELP datasource_latency_avg_seconds Average fetch latency per data source")
            lines.append("# TYPE datasource_latency_avg_seconds gauge")
            for source in self.fetch_latencies.keys():
                latencies = self.fetch_latencies.get(source, [])
                avg = sum(latencies) / len(latencies) if latencies else 0.0
                lines.append(f'datasource_latency_avg_seconds{{source="{source}"}} {avg:.6f}')
            
            lines.append("# HELP datasource_latency_p95_seconds 95th percentile fetch latency per data source")
            lines.append("# TYPE datasource_latency_p95_seconds gauge")
            for source in self.fetch_latencies.keys():
                latencies = self.fetch_latencies.get(source, [])
                if not latencies:
                    p95 = 0.0
                else:
                    sorted_latencies = sorted(latencies)
                    idx = int(len(sorted_latencies) * 0.95)
                    p95 = sorted_latencies[min(idx, len(sorted_latencies) - 1)]
                lines.append(f'datasource_latency_p95_seconds{{source="{source}"}} {p95:.6f}')
            
            return "\n".join(lines) + "\n"


# Global singleton instance
_cache_metrics: Optional[CacheMetrics] = None
_metrics_lock = Lock()


def get_cache_metrics() -> CacheMetrics:
    """Get the global cache metrics instance."""
    global _cache_metrics
    with _metrics_lock:
        if _cache_metrics is None:
            _cache_metrics = CacheMetrics()
        return _cache_metrics


def record_cache_hit() -> None:
    """Convenience function to record a cache hit."""
    get_cache_metrics().record_hit()


def record_cache_miss() -> None:
    """Convenience function to record a cache miss."""
    get_cache_metrics().record_miss()


def record_cache_eviction() -> None:
    """Convenience function to record a cache eviction."""
    get_cache_metrics().record_eviction()


def record_fetch_latency(source: str, latency_seconds: float) -> None:
    """Convenience function to record fetch latency."""
    get_cache_metrics().record_latency(source, latency_seconds)


def record_source_request(source: str) -> None:
    """Convenience function to record a source request."""
    get_cache_metrics().record_request(source)


def record_source_error(source: str) -> None:
    """Convenience function to record a source error."""
    get_cache_metrics().record_error(source)


class LatencyContext:
    """Context manager for measuring fetch latency."""
    
    def __init__(self, source: str):
        self.source = source
        self.start_time: Optional[float] = None
    
    def __enter__(self):
        self.start_time = time.time()
        record_source_request(self.source)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            latency = time.time() - self.start_time
            record_fetch_latency(self.source, latency)
        
        if exc_type is not None:
            record_source_error(self.source)
        
        return False  # Don't suppress exceptions
