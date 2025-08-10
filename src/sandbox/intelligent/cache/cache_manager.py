"""
Central cache manager for coordinating different cache types.
"""

import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path

from .interfaces import CacheInterface
from .models import CacheStats
from .analysis_cache import AnalysisCache
from .task_plan_cache import TaskPlanCache
from .execution_cache import ExecutionCache


class CacheManager:
    """Central manager for all caching operations."""
    
    def __init__(self, cache_dir: str = None, max_memory_mb: int = 512):
        """
        Initialize the cache manager.
        
        Args:
            cache_dir: Directory for persistent cache storage
            max_memory_mb: Maximum memory usage for all caches combined
        """
        self.cache_dir = Path(cache_dir or os.path.expanduser("~/.sandbox_cache"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self._caches: Dict[str, CacheInterface] = {}
        
        # Initialize specific cache types
        self._analysis_cache = AnalysisCache(
            cache_dir=self.cache_dir / "analysis",
            max_entries=1000
        )
        self._task_plan_cache = TaskPlanCache(
            cache_dir=self.cache_dir / "task_plans",
            max_templates=500
        )
        self._execution_cache = ExecutionCache(
            cache_dir=self.cache_dir / "execution",
            max_entries=2000
        )
        
        self._caches = {
            "analysis": self._analysis_cache,
            "task_plans": self._task_plan_cache,
            "execution": self._execution_cache
        }
    
    @property
    def analysis_cache(self) -> AnalysisCache:
        """Get the analysis cache instance."""
        return self._analysis_cache
    
    @property
    def task_plan_cache(self) -> TaskPlanCache:
        """Get the task plan cache instance."""
        return self._task_plan_cache
    
    @property
    def execution_cache(self) -> ExecutionCache:
        """Get the execution cache instance."""
        return self._execution_cache
    
    def get_cache(self, cache_type: str) -> Optional[CacheInterface]:
        """
        Get a specific cache by type.
        
        Args:
            cache_type: Type of cache to retrieve
            
        Returns:
            Cache instance or None if not found
        """
        return self._caches.get(cache_type)
    
    def clear_all_caches(self) -> bool:
        """
        Clear all caches.
        
        Returns:
            True if all caches were cleared successfully
        """
        success = True
        for cache in self._caches.values():
            if not cache.clear():
                success = False
        return success
    
    def get_combined_stats(self) -> Dict[str, Any]:
        """
        Get combined statistics from all caches.
        
        Returns:
            Dictionary with combined cache statistics
        """
        combined_stats = {
            "total_memory_usage": 0,
            "total_entries": 0,
            "total_hits": 0,
            "total_misses": 0,
            "cache_types": {}
        }
        
        for cache_type, cache in self._caches.items():
            stats = cache.get_stats()
            combined_stats["cache_types"][cache_type] = stats
            
            # Aggregate totals
            combined_stats["total_memory_usage"] += stats.get("memory_usage_bytes", 0)
            combined_stats["total_entries"] += stats.get("total_entries", 0)
            combined_stats["total_hits"] += stats.get("hit_count", 0)
            combined_stats["total_misses"] += stats.get("miss_count", 0)
        
        # Calculate combined hit rate
        total_requests = combined_stats["total_hits"] + combined_stats["total_misses"]
        combined_stats["hit_rate"] = (
            combined_stats["total_hits"] / total_requests if total_requests > 0 else 0.0
        )
        
        return combined_stats
    
    def cleanup_expired_entries(self) -> Dict[str, int]:
        """
        Clean up expired entries from all caches.
        
        Returns:
            Dictionary with cleanup counts per cache type
        """
        cleanup_counts = {}
        
        for cache_type, cache in self._caches.items():
            if hasattr(cache, 'cleanup_expired'):
                cleanup_counts[cache_type] = cache.cleanup_expired()
            else:
                cleanup_counts[cache_type] = 0
                
        return cleanup_counts
    
    def enforce_memory_limits(self) -> Dict[str, int]:
        """
        Enforce memory limits by evicting least recently used entries.
        
        Returns:
            Dictionary with eviction counts per cache type
        """
        current_usage = self.get_combined_stats()["total_memory_usage"]
        
        if current_usage <= self.max_memory_bytes:
            return {cache_type: 0 for cache_type in self._caches.keys()}
        
        # Calculate how much memory to free (with 10% buffer)
        target_usage = int(self.max_memory_bytes * 0.9)
        memory_to_free = current_usage - target_usage
        
        eviction_counts = {}
        
        # Evict from caches in order of priority (execution -> analysis -> task_plans)
        priority_order = ["execution", "analysis", "task_plans"]
        
        for cache_type in priority_order:
            if memory_to_free <= 0:
                break
                
            cache = self._caches.get(cache_type)
            if cache and hasattr(cache, 'evict_lru_entries'):
                # Estimate entries to evict (rough calculation)
                cache_stats = cache.get_stats()
                avg_entry_size = (
                    cache_stats.get("memory_usage_bytes", 0) / 
                    max(cache_stats.get("total_entries", 1), 1)
                )
                
                if avg_entry_size > 0:
                    entries_to_evict = min(
                        int(memory_to_free / avg_entry_size),
                        cache_stats.get("total_entries", 0)
                    )
                    
                    evicted = cache.evict_lru_entries(entries_to_evict)
                    eviction_counts[cache_type] = evicted
                    memory_to_free -= evicted * avg_entry_size
                else:
                    eviction_counts[cache_type] = 0
            else:
                eviction_counts[cache_type] = 0
        
        return eviction_counts
    
    def generate_cache_key(self, *args, **kwargs) -> str:
        """
        Generate a consistent cache key from arguments.
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            SHA-256 hash of the arguments
        """
        # Create a deterministic representation
        key_data = {
            "args": args,
            "kwargs": sorted(kwargs.items())
        }
        
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.sha256(key_str.encode()).hexdigest()
    
    def invalidate_workspace_caches(self, workspace_path: str) -> Dict[str, int]:
        """
        Invalidate all caches related to a specific workspace.
        
        Args:
            workspace_path: Path to the workspace
            
        Returns:
            Dictionary with invalidation counts per cache type
        """
        workspace_hash = self.generate_cache_key(workspace_path)
        invalidation_counts = {}
        
        # Invalidate analysis cache
        if self._analysis_cache.invalidate_analysis(workspace_hash):
            invalidation_counts["analysis"] = 1
        else:
            invalidation_counts["analysis"] = 0
        
        # Invalidate execution cache for files in the workspace
        if hasattr(self._execution_cache, 'invalidate_workspace'):
            invalidation_counts["execution"] = self._execution_cache.invalidate_workspace(workspace_path)
        else:
            invalidation_counts["execution"] = 0
        
        # Task plan cache doesn't need workspace-specific invalidation
        invalidation_counts["task_plans"] = 0
        
        return invalidation_counts
    
    def get_cache_health(self) -> Dict[str, Any]:
        """
        Get overall cache system health metrics.
        
        Returns:
            Dictionary with health metrics
        """
        stats = self.get_combined_stats()
        
        health = {
            "status": "healthy",
            "memory_usage_percentage": (
                stats["total_memory_usage"] / self.max_memory_bytes * 100
                if self.max_memory_bytes > 0 else 0
            ),
            "hit_rate": stats["hit_rate"],
            "total_entries": stats["total_entries"],
            "issues": []
        }
        
        # Check for potential issues
        if health["memory_usage_percentage"] > 90:
            health["status"] = "warning"
            health["issues"].append("High memory usage")
        
        if health["hit_rate"] < 0.3:
            health["status"] = "warning"
            health["issues"].append("Low cache hit rate")
        
        if health["total_entries"] == 0:
            health["status"] = "info"
            health["issues"].append("No cached entries")
        
        return health
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive cache statistics including hit rates and performance metrics.
        
        Returns:
            Dictionary with detailed cache statistics
        """
        combined_stats = self.get_combined_stats()
        
        # Calculate additional metrics
        total_requests = combined_stats["total_hits"] + combined_stats["total_misses"]
        
        stats = {
            "hit_rate": combined_stats["hit_rate"],
            "total_requests": total_requests,
            "cache_size": combined_stats["total_entries"],
            "memory_usage_mb": combined_stats["total_memory_usage"] / (1024 * 1024),
            "memory_usage_percentage": (
                combined_stats["total_memory_usage"] / self.max_memory_bytes * 100
                if self.max_memory_bytes > 0 else 0
            ),
            "cache_types": {}
        }
        
        # Add per-cache-type statistics
        for cache_type, cache_stats in combined_stats["cache_types"].items():
            cache_requests = cache_stats.get("hit_count", 0) + cache_stats.get("miss_count", 0)
            cache_hit_rate = (
                cache_stats.get("hit_count", 0) / cache_requests 
                if cache_requests > 0 else 0.0
            )
            
            stats["cache_types"][cache_type] = {
                "hit_rate": cache_hit_rate,
                "requests": cache_requests,
                "entries": cache_stats.get("total_entries", 0),
                "memory_mb": cache_stats.get("memory_usage_bytes", 0) / (1024 * 1024)
            }
        
        return stats