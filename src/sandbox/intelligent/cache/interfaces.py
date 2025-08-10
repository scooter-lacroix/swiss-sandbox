"""
Abstract interfaces for caching system components.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from ..analyzer.models import CodebaseAnalysis
from ..planner.models import TaskPlan
from ..executor.models import ExecutionResult


class CacheInterface(ABC):
    """Base interface for all cache implementations."""
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """
        Get a value from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set a value in the cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (None for default)
            
        Returns:
            True if successfully cached
        """
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """
        Delete a value from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if successfully deleted
        """
        pass
    
    @abstractmethod
    def clear(self) -> bool:
        """
        Clear all cached values.
        
        Returns:
            True if successfully cleared
        """
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """
        Check if a key exists in the cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists and is not expired
        """
        pass
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        pass


class AnalysisCacheInterface(CacheInterface):
    """Interface for codebase analysis result caching."""
    
    @abstractmethod
    def cache_analysis(self, workspace_hash: str, analysis: CodebaseAnalysis,
                      ttl: Optional[int] = None) -> bool:
        """
        Cache a codebase analysis result.
        
        Args:
            workspace_hash: Hash of the workspace content
            analysis: Analysis result to cache
            ttl: Time to live in seconds
            
        Returns:
            True if successfully cached
        """
        pass
    
    @abstractmethod
    def get_analysis(self, workspace_hash: str) -> Optional[CodebaseAnalysis]:
        """
        Get cached analysis result.
        
        Args:
            workspace_hash: Hash of the workspace content
            
        Returns:
            Cached analysis or None if not found/expired
        """
        pass
    
    @abstractmethod
    def invalidate_analysis(self, workspace_hash: str) -> bool:
        """
        Invalidate cached analysis for a workspace.
        
        Args:
            workspace_hash: Hash of the workspace content
            
        Returns:
            True if successfully invalidated
        """
        pass
    
    @abstractmethod
    def is_analysis_valid(self, workspace_hash: str, 
                         file_timestamps: Dict[str, datetime]) -> bool:
        """
        Check if cached analysis is still valid based on file timestamps.
        
        Args:
            workspace_hash: Hash of the workspace content
            file_timestamps: Dictionary of file paths to modification times
            
        Returns:
            True if cached analysis is still valid
        """
        pass


class TaskPlanCacheInterface(CacheInterface):
    """Interface for task plan template caching."""
    
    @abstractmethod
    def cache_plan_template(self, template_key: str, plan: TaskPlan,
                           similarity_threshold: float = 0.8) -> bool:
        """
        Cache a task plan as a template for similar projects.
        
        Args:
            template_key: Key identifying the template type
            plan: Task plan to use as template
            similarity_threshold: Minimum similarity for template matching
            
        Returns:
            True if successfully cached
        """
        pass
    
    @abstractmethod
    def find_similar_templates(self, project_characteristics: Dict[str, Any],
                              max_results: int = 5) -> List[Tuple[str, TaskPlan, float]]:
        """
        Find similar task plan templates.
        
        Args:
            project_characteristics: Characteristics of the current project
            max_results: Maximum number of templates to return
            
        Returns:
            List of (template_key, plan, similarity_score) tuples
        """
        pass
    
    @abstractmethod
    def get_plan_template(self, template_key: str) -> Optional[TaskPlan]:
        """
        Get a specific task plan template.
        
        Args:
            template_key: Template identifier
            
        Returns:
            Cached template or None if not found
        """
        pass
    
    @abstractmethod
    def update_template_usage(self, template_key: str, success: bool) -> bool:
        """
        Update template usage statistics.
        
        Args:
            template_key: Template identifier
            success: Whether the template was successfully used
            
        Returns:
            True if successfully updated
        """
        pass


class ExecutionCacheInterface(CacheInterface):
    """Interface for execution result caching."""
    
    @abstractmethod
    def cache_execution_result(self, operation_hash: str, result: ExecutionResult,
                              ttl: Optional[int] = None) -> bool:
        """
        Cache an execution result for repeated operations.
        
        Args:
            operation_hash: Hash of the operation parameters
            result: Execution result to cache
            ttl: Time to live in seconds
            
        Returns:
            True if successfully cached
        """
        pass
    
    @abstractmethod
    def get_execution_result(self, operation_hash: str) -> Optional[ExecutionResult]:
        """
        Get cached execution result.
        
        Args:
            operation_hash: Hash of the operation parameters
            
        Returns:
            Cached result or None if not found/expired
        """
        pass
    
    @abstractmethod
    def is_operation_cacheable(self, operation_type: str, 
                              parameters: Dict[str, Any]) -> bool:
        """
        Check if an operation is suitable for caching.
        
        Args:
            operation_type: Type of operation
            parameters: Operation parameters
            
        Returns:
            True if operation can be safely cached
        """
        pass
    
    @abstractmethod
    def invalidate_related_results(self, file_paths: List[str]) -> int:
        """
        Invalidate cached results that depend on specific files.
        
        Args:
            file_paths: List of file paths that have changed
            
        Returns:
            Number of invalidated cache entries
        """
        pass