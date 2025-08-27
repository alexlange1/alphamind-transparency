#!/usr/bin/env python3
"""
Professional metrics collection and reporting
Inspired by successful Bittensor subnet patterns
"""

import time
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import json


@dataclass
class MetricPoint:
    """Individual metric measurement"""
    name: str
    value: float
    timestamp: float
    tags: Dict[str, str]


@dataclass
class PerformanceStats:
    """Performance statistics for operations"""
    count: int
    total_time: float
    min_time: float
    max_time: float
    avg_time: float
    success_rate: float
    
    @classmethod
    def from_measurements(cls, times: List[float], successes: List[bool]) -> 'PerformanceStats':
        """Create stats from raw measurements"""
        if not times:
            return cls(0, 0.0, 0.0, 0.0, 0.0, 0.0)
        
        count = len(times)
        total_time = sum(times)
        min_time = min(times)
        max_time = max(times)
        avg_time = total_time / count
        success_rate = sum(successes) / len(successes) if successes else 0.0
        
        return cls(count, total_time, min_time, max_time, avg_time, success_rate)


class MetricsCollector:
    """
    Thread-safe metrics collection system
    Provides comprehensive monitoring for subnet operations
    """
    
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self._lock = threading.Lock()
        
        # Core metrics
        self.counters: Dict[str, int] = defaultdict(int)
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self.timers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        
        # Performance tracking
        self.operation_times: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self.operation_successes: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        
        # System health
        self.health_checks: Dict[str, Dict] = {}
        self.last_activity = time.time()
    
    def increment_counter(self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None):
        """Increment a counter metric"""
        with self._lock:
            full_name = self._build_metric_name(name, tags)
            self.counters[full_name] += value
            self.last_activity = time.time()
    
    def set_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Set a gauge metric"""
        with self._lock:
            full_name = self._build_metric_name(name, tags)
            self.gauges[full_name] = value
            self.last_activity = time.time()
    
    def record_histogram(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Record a histogram value"""
        with self._lock:
            full_name = self._build_metric_name(name, tags)
            self.histograms[full_name].append(value)
            self.last_activity = time.time()
    
    def record_timer(self, name: str, duration: float, tags: Optional[Dict[str, str]] = None):
        """Record a timer duration"""
        with self._lock:
            full_name = self._build_metric_name(name, tags)
            self.timers[full_name].append(duration)
            self.last_activity = time.time()
    
    def record_operation(self, name: str, duration: float, success: bool, tags: Optional[Dict[str, str]] = None):
        """Record operation performance"""
        with self._lock:
            full_name = self._build_metric_name(name, tags)
            self.operation_times[full_name].append(duration)
            self.operation_successes[full_name].append(success)
            self.last_activity = time.time()
    
    def update_health_check(self, component: str, status: str, details: Optional[Dict] = None):
        """Update component health status"""
        with self._lock:
            self.health_checks[component] = {
                'status': status,
                'timestamp': time.time(),
                'details': details or {}
            }
    
    def get_counter(self, name: str, tags: Optional[Dict[str, str]] = None) -> int:
        """Get counter value"""
        with self._lock:
            full_name = self._build_metric_name(name, tags)
            return self.counters.get(full_name, 0)
    
    def get_gauge(self, name: str, tags: Optional[Dict[str, str]] = None) -> Optional[float]:
        """Get gauge value"""
        with self._lock:
            full_name = self._build_metric_name(name, tags)
            return self.gauges.get(full_name)
    
    def get_histogram_stats(self, name: str, tags: Optional[Dict[str, str]] = None) -> Optional[Dict]:
        """Get histogram statistics"""
        with self._lock:
            full_name = self._build_metric_name(name, tags)
            values = list(self.histograms.get(full_name, []))
            
            if not values:
                return None
            
            return {
                'count': len(values),
                'min': min(values),
                'max': max(values),
                'avg': sum(values) / len(values),
                'p50': self._percentile(values, 0.5),
                'p95': self._percentile(values, 0.95),
                'p99': self._percentile(values, 0.99)
            }
    
    def get_timer_stats(self, name: str, tags: Optional[Dict[str, str]] = None) -> Optional[Dict]:
        """Get timer statistics"""
        with self._lock:
            full_name = self._build_metric_name(name, tags)
            values = list(self.timers.get(full_name, []))
            
            if not values:
                return None
            
            return {
                'count': len(values),
                'min_ms': min(values) * 1000,
                'max_ms': max(values) * 1000,
                'avg_ms': (sum(values) / len(values)) * 1000,
                'p50_ms': self._percentile(values, 0.5) * 1000,
                'p95_ms': self._percentile(values, 0.95) * 1000,
                'p99_ms': self._percentile(values, 0.99) * 1000
            }
    
    def get_operation_stats(self, name: str, tags: Optional[Dict[str, str]] = None) -> Optional[PerformanceStats]:
        """Get operation performance statistics"""
        with self._lock:
            full_name = self._build_metric_name(name, tags)
            times = list(self.operation_times.get(full_name, []))
            successes = list(self.operation_successes.get(full_name, []))
            
            if not times:
                return None
            
            return PerformanceStats.from_measurements(times, successes)
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall system health status"""
        with self._lock:
            overall_status = "healthy"
            failed_components = []
            
            for component, health in self.health_checks.items():
                if health['status'] != 'healthy':
                    overall_status = "degraded"
                    failed_components.append(component)
            
            return {
                'overall_status': overall_status,
                'failed_components': failed_components,
                'components': dict(self.health_checks),
                'last_activity': self.last_activity,
                'uptime_seconds': time.time() - self.last_activity
            }
    
    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary"""
        with self._lock:
            summary = {
                'timestamp': time.time(),
                'counters': dict(self.counters),
                'gauges': dict(self.gauges),
                'health': self.get_health_status()
            }
            
            # Add histogram summaries
            histogram_stats = {}
            for name in self.histograms:
                stats = self.get_histogram_stats(name.split('|')[0], self._parse_tags(name))
                if stats:
                    histogram_stats[name] = stats
            summary['histograms'] = histogram_stats
            
            # Add timer summaries
            timer_stats = {}
            for name in self.timers:
                stats = self.get_timer_stats(name.split('|')[0], self._parse_tags(name))
                if stats:
                    timer_stats[name] = stats
            summary['timers'] = timer_stats
            
            # Add operation summaries
            operation_stats = {}
            for name in self.operation_times:
                stats = self.get_operation_stats(name.split('|')[0], self._parse_tags(name))
                if stats:
                    operation_stats[name] = asdict(stats)
            summary['operations'] = operation_stats
            
            return summary
    
    def export_json(self) -> str:
        """Export all metrics as JSON"""
        return json.dumps(self.get_summary(), indent=2)
    
    def _build_metric_name(self, name: str, tags: Optional[Dict[str, str]]) -> str:
        """Build full metric name with tags"""
        if not tags:
            return name
        
        tag_string = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}|{tag_string}"
    
    def _parse_tags(self, full_name: str) -> Optional[Dict[str, str]]:
        """Parse tags from full metric name"""
        if '|' not in full_name:
            return None
        
        _, tag_string = full_name.split('|', 1)
        tags = {}
        
        for tag_pair in tag_string.split(','):
            if '=' in tag_pair:
                key, value = tag_pair.split('=', 1)
                tags[key] = value
        
        return tags
    
    def _percentile(self, values: List[float], percentile: float) -> float:
        """Calculate percentile from values"""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int(percentile * (len(sorted_values) - 1))
        return sorted_values[index]


class TimerContext:
    """Context manager for timing operations"""
    
    def __init__(self, metrics: MetricsCollector, name: str, tags: Optional[Dict[str, str]] = None):
        self.metrics = metrics
        self.name = name
        self.tags = tags
        self.start_time = None
        self.success = True
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            self.success = exc_type is None
            
            self.metrics.record_timer(self.name, duration, self.tags)
            self.metrics.record_operation(self.name, duration, self.success, self.tags)
    
    def mark_failed(self):
        """Mark operation as failed"""
        self.success = False


# Global metrics instance
_global_metrics = MetricsCollector()


def get_metrics() -> MetricsCollector:
    """Get global metrics instance"""
    return _global_metrics


def timer(name: str, tags: Optional[Dict[str, str]] = None) -> TimerContext:
    """Create a timer context manager"""
    return TimerContext(_global_metrics, name, tags)
