"""
Performance optimization and caching system for the intelligent sandbox.
"""

from .interfaces import (
    CacheInterface,
    AnalysisCacheInterface,
    TaskPlanCacheInterface,
    ExecutionCacheInterface
)
from .cache_manager import CacheManager
from .analysis_cache import AnalysisCache
from .task_plan_cache import TaskPlanCache
from .execution_cache import ExecutionCache
from .resource_manager import ResourceManager, ResourceLimits, ResourceUsage, CleanupTask
from .models import CacheEntry, AnalysisCacheEntry, TaskPlanTemplate, ExecutionCacheEntry, CacheStats

__all__ = [
    'CacheInterface',
    'AnalysisCacheInterface', 
    'TaskPlanCacheInterface',
    'ExecutionCacheInterface',
    'CacheManager',
    'AnalysisCache',
    'TaskPlanCache',
    'ExecutionCache',
    'ResourceManager',
    'ResourceLimits',
    'ResourceUsage',
    'CleanupTask',
    'CacheEntry',
    'AnalysisCacheEntry',
    'TaskPlanTemplate',
    'ExecutionCacheEntry',
    'CacheStats'
]