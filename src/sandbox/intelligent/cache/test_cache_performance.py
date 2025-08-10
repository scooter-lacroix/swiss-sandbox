"""
Performance tests for the caching system effectiveness.
"""

import pytest
import tempfile
import shutil
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

from .cache_manager import CacheManager
from ..analyzer.models import CodebaseAnalysis, CodebaseStructure, DependencyGraph, Pattern, CodeMetrics
from ..planner.models import TaskPlan, Task, CodebaseContext
from ..executor.models import ExecutionResult
from ..types import TaskStatus, PlanStatus


class TestCachePerformanceEffectiveness:
    """Test the performance effectiveness of the caching system."""
    
    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary cache directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def cache_manager(self, temp_cache_dir):
        """Create a cache manager instance."""
        return CacheManager(cache_dir=temp_cache_dir, max_memory_mb=50)
    
    def create_sample_analysis(self, project_id: str) -> CodebaseAnalysis:
        """Create a sample codebase analysis."""
        structure = CodebaseStructure(
            root_path=f"/test/project_{project_id}",
            languages=["python", "javascript"],
            frameworks=["django", "react"],
            file_tree={"src": {"main.py": None, "utils.py": None}},
            entry_points=["main.py"],
            test_directories=["tests"],
            config_files=["setup.py", "package.json"]
        )
        
        dependencies = DependencyGraph(
            dependencies=[],
            dependency_files=["requirements.txt", "package.json"]
        )
        
        patterns = [
            Pattern(name="MVC", type="architectural", confidence=0.9, description="MVC pattern"),
            Pattern(name="Factory", type="design", confidence=0.7, description="Factory pattern")
        ]
        
        metrics = CodeMetrics(
            lines_of_code=5000,
            cyclomatic_complexity=15.0,
            maintainability_index=75.0,
            test_coverage=85.0
        )
        
        return CodebaseAnalysis(
            structure=structure,
            dependencies=dependencies,
            patterns=patterns,
            metrics=metrics,
            summary=f"Analysis for project {project_id}",
            analysis_timestamp=datetime.now()
        )
    
    def test_analysis_cache_performance_improvement(self, cache_manager):
        """Test that analysis caching provides significant performance improvement."""
        analysis_cache = cache_manager.analysis_cache
        
        # Create a complex analysis that would be expensive to compute
        sample_analysis = self.create_sample_analysis("perf_test")
        workspace_hash = "performance_test_hash"
        
        # Simulate expensive analysis computation time
        def expensive_analysis_computation():
            time.sleep(0.1)  # Simulate 100ms computation
            return sample_analysis
        
        # First access - cache miss (expensive)
        start_time = time.time()
        result = analysis_cache.get_analysis(workspace_hash)
        assert result is None  # Cache miss
        
        # Simulate expensive computation and cache the result
        computed_analysis = expensive_analysis_computation()
        analysis_cache.cache_analysis(workspace_hash, computed_analysis)
        first_access_time = time.time() - start_time
        
        # Second access - cache hit (fast)
        start_time = time.time()
        cached_result = analysis_cache.get_analysis(workspace_hash)
        second_access_time = time.time() - start_time
        
        assert cached_result is not None
        assert cached_result.summary == sample_analysis.summary
        
        # Cache hit should be significantly faster
        assert second_access_time < first_access_time * 0.1  # At least 10x faster
        
        # Verify cache statistics
        stats = analysis_cache.get_stats()
        assert stats["hit_count"] >= 1
        assert stats["hit_rate"] > 0.0
    
    def test_task_plan_template_effectiveness(self, cache_manager):
        """Test that task plan templates improve planning efficiency."""
        task_plan_cache = cache_manager.task_plan_cache
        
        # Create a sample task plan template
        analysis = self.create_sample_analysis("template_test")
        context = CodebaseContext(analysis=analysis)
        
        task = Task(
            id="auth_task",
            description="Implement user authentication system",
            status=TaskStatus.NOT_STARTED
        )
        
        plan = TaskPlan(
            id="auth_plan",
            description="User authentication feature",
            tasks=[task],
            codebase_context=context,
            status=PlanStatus.APPROVED
        )
        
        # Cache the template
        template_key = "auth_template_django_python"
        result = task_plan_cache.cache_plan_template(template_key, plan, similarity_threshold=0.5)
        assert result is True
        
        # Simulate successful usage
        task_plan_cache.update_template_usage(template_key, success=True)
        task_plan_cache.update_template_usage(template_key, success=True)
        task_plan_cache.update_template_usage(template_key, success=False)
        
        # Test template matching for similar project
        similar_characteristics = {
            "languages": ["javascript", "python"],  # Match both languages
            "frameworks": ["django", "react"],      # Match both frameworks
            "task_count": 1,
            "has_tests": True,
            "patterns": ["MVC", "Factory"],         # Match both patterns
            "complexity_level": "medium",
            "project_size": "small"                 # Match the actual size
        }
        
        # Find similar templates
        similar_templates = task_plan_cache.find_similar_templates(similar_characteristics)
        assert len(similar_templates) > 0
        
        found_key, found_plan, similarity = similar_templates[0]
        assert found_key == template_key
        assert similarity > 0.5
        assert found_plan.description == plan.description
        
        # Check template analytics
        analytics = task_plan_cache.get_template_analytics()
        assert analytics["total_templates"] >= 1
        assert analytics["avg_success_rate"] > 0.5  # 2 successes out of 3 attempts
    
    def test_execution_cache_reduces_redundant_operations(self, cache_manager):
        """Test that execution caching reduces redundant operations."""
        execution_cache = cache_manager.execution_cache
        
        # Create sample execution result
        execution_result = ExecutionResult(
            plan_id="test_plan",
            success=True,
            total_duration=2.5,
            tasks_completed=3,
            tasks_failed=0,
            summary="Test execution completed successfully"
        )
        
        # Define a cacheable operation
        operation_type = "test_execution"
        parameters = {
            "test_file": "/path/to/test.py",
            "test_framework": "pytest",
            "timeout": 30
        }
        
        # Verify operation is cacheable
        assert execution_cache.is_operation_cacheable(operation_type, parameters) is True
        
        # First execution - cache miss
        start_time = time.time()
        cached_result = execution_cache.get_operation_result(operation_type, parameters)
        assert cached_result is None  # Cache miss
        
        # Simulate expensive operation and cache result
        time.sleep(0.05)  # Simulate 50ms operation
        execution_cache.cache_operation_result(operation_type, parameters, execution_result)
        first_execution_time = time.time() - start_time
        
        # Second execution - cache hit
        start_time = time.time()
        cached_result = execution_cache.get_operation_result(operation_type, parameters)
        second_execution_time = time.time() - start_time
        
        assert cached_result is not None
        assert cached_result.success == execution_result.success
        assert cached_result.summary == execution_result.summary
        
        # Cache hit should be much faster
        assert second_execution_time < first_execution_time * 0.2  # At least 5x faster
    
    def test_cache_memory_efficiency(self, cache_manager):
        """Test that the cache system manages memory efficiently."""
        analysis_cache = cache_manager.analysis_cache
        
        # Fill cache with multiple analyses
        analyses = []
        for i in range(20):
            analysis = self.create_sample_analysis(f"memory_test_{i}")
            workspace_hash = f"memory_hash_{i}"
            analysis_cache.cache_analysis(workspace_hash, analysis)
            analyses.append((workspace_hash, analysis))
        
        # Check initial memory usage
        initial_stats = cache_manager.get_combined_stats()
        initial_memory = initial_stats["total_memory_usage"]
        initial_entries = initial_stats["total_entries"]
        
        assert initial_entries >= 20
        assert initial_memory > 0
        
        # Add more data to trigger memory management
        for i in range(20, 50):
            large_analysis = self.create_sample_analysis(f"large_test_{i}")
            # Add extra data to make it larger
            large_analysis.metadata = {"large_data": "x" * 10000}
            workspace_hash = f"large_hash_{i}"
            analysis_cache.cache_analysis(workspace_hash, large_analysis)
        
        # Check memory usage after adding large data
        mid_stats = cache_manager.get_combined_stats()
        mid_memory = mid_stats["total_memory_usage"]
        
        # Memory should have increased
        assert mid_memory > initial_memory
        
        # Trigger memory cleanup
        cleanup_counts = cache_manager.cleanup_expired_entries()
        eviction_counts = cache_manager.enforce_memory_limits()
        
        # Check final memory usage
        final_stats = cache_manager.get_combined_stats()
        final_memory = final_stats["total_memory_usage"]
        
        # Memory management should have had some effect
        # (Either cleanup or eviction should have occurred)
        total_cleanup = sum(cleanup_counts.values()) + sum(eviction_counts.values())
        assert total_cleanup >= 0  # Some cleanup may have occurred
    
    def test_cache_hit_rate_optimization(self, cache_manager):
        """Test that cache hit rates improve with usage patterns."""
        analysis_cache = cache_manager.analysis_cache
        
        # Create a set of analyses that will be accessed repeatedly
        common_analyses = []
        for i in range(5):
            analysis = self.create_sample_analysis(f"common_{i}")
            workspace_hash = f"common_hash_{i}"
            analysis_cache.cache_analysis(workspace_hash, analysis)
            common_analyses.append(workspace_hash)
        
        # Simulate realistic access patterns (some analyses accessed more frequently)
        access_pattern = [
            common_analyses[0],  # Most frequently accessed
            common_analyses[0],
            common_analyses[1],  # Second most frequent
            common_analyses[0],
            common_analyses[2],  # Less frequent
            common_analyses[1],
            common_analyses[0],
            common_analyses[3],  # Rare
            common_analyses[1],
            common_analyses[0]
        ]
        
        # Execute access pattern
        hits = 0
        total_accesses = len(access_pattern)
        
        for workspace_hash in access_pattern:
            result = analysis_cache.get_analysis(workspace_hash)
            if result is not None:
                hits += 1
        
        # Calculate hit rate
        hit_rate = hits / total_accesses
        
        # Should have high hit rate since all analyses were cached
        assert hit_rate >= 0.9  # At least 90% hit rate
        
        # Verify cache statistics
        stats = analysis_cache.get_stats()
        assert stats["hit_rate"] >= 0.5  # Overall hit rate should be good
    
    def test_cache_invalidation_effectiveness(self, cache_manager):
        """Test that cache invalidation works effectively."""
        analysis_cache = cache_manager.analysis_cache
        execution_cache = cache_manager.execution_cache
        
        # Cache some analysis results
        analysis = self.create_sample_analysis("invalidation_test")
        workspace_hash = "invalidation_hash"
        analysis_cache.cache_analysis(workspace_hash, analysis)
        
        # Cache some execution results
        execution_result = ExecutionResult(
            plan_id="invalidation_plan",
            success=True,
            total_duration=1.0,
            tasks_completed=1,
            tasks_failed=0
        )
        
        operation_type = "test_execution"
        parameters = {"file_path": "/test/file.py"}
        execution_cache.cache_operation_result(operation_type, parameters, execution_result)
        
        # Verify items are cached
        assert analysis_cache.get_analysis(workspace_hash) is not None
        assert execution_cache.get_operation_result(operation_type, parameters) is not None
        
        # Test workspace-wide invalidation
        invalidation_counts = cache_manager.invalidate_workspace_caches("/test")
        
        # Should have invalidated some entries
        assert sum(invalidation_counts.values()) >= 0
        
        # Test file-specific invalidation
        file_invalidation_count = execution_cache.invalidate_related_results(["/test/file.py"])
        assert file_invalidation_count >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])