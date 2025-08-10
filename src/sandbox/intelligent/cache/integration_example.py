"""
Integration example demonstrating the caching and resource management system.
"""

import time
from datetime import datetime
from pathlib import Path

from .cache_manager import CacheManager
from .resource_manager import ResourceManager, ResourceLimits, CleanupTask
from ..analyzer.models import CodebaseAnalysis, CodebaseStructure, DependencyGraph, Pattern, CodeMetrics
from ..planner.models import TaskPlan, Task, CodebaseContext
from ..executor.models import ExecutionResult
from ..types import TaskStatus, PlanStatus


def create_sample_analysis(project_name: str) -> CodebaseAnalysis:
    """Create a sample codebase analysis for demonstration."""
    structure = CodebaseStructure(
        root_path=f"/demo/projects/{project_name}",
        languages=["python", "javascript"],
        frameworks=["django", "react"],
        file_tree={
            "src": {
                "main.py": None,
                "utils.py": None,
                "components": {
                    "auth.py": None,
                    "api.py": None
                }
            },
            "tests": {
                "test_main.py": None,
                "test_utils.py": None
            }
        },
        entry_points=["src/main.py"],
        test_directories=["tests"],
        config_files=["setup.py", "package.json", "requirements.txt"]
    )
    
    dependencies = DependencyGraph(
        dependencies=[],
        dependency_files=["requirements.txt", "package.json"]
    )
    
    patterns = [
        Pattern(name="MVC", type="architectural", confidence=0.9, description="Model-View-Controller pattern"),
        Pattern(name="Factory", type="design", confidence=0.8, description="Factory pattern for object creation"),
        Pattern(name="Observer", type="design", confidence=0.7, description="Observer pattern for event handling")
    ]
    
    metrics = CodeMetrics(
        lines_of_code=5000,
        cyclomatic_complexity=12.5,
        maintainability_index=78.0,
        test_coverage=85.0,
        technical_debt_ratio=0.15,
        duplication_percentage=5.2
    )
    
    return CodebaseAnalysis(
        structure=structure,
        dependencies=dependencies,
        patterns=patterns,
        metrics=metrics,
        summary=f"Comprehensive analysis of {project_name} project",
        analysis_timestamp=datetime.now()
    )


def create_sample_task_plan(project_name: str, analysis: CodebaseAnalysis) -> TaskPlan:
    """Create a sample task plan for demonstration."""
    context = CodebaseContext(
        analysis=analysis,
        key_files=["src/main.py", "src/utils.py"],
        important_patterns=["MVC", "Factory"],
        constraints=["Maintain backward compatibility", "Follow PEP 8"],
        recommendations=["Add more unit tests", "Improve error handling"]
    )
    
    tasks = [
        Task(
            id="auth_implementation",
            description="Implement user authentication system",
            status=TaskStatus.NOT_STARTED,
            estimated_duration=120  # 2 hours
        ),
        Task(
            id="api_endpoints",
            description="Create REST API endpoints",
            status=TaskStatus.NOT_STARTED,
            dependencies=["auth_implementation"],
            estimated_duration=180  # 3 hours
        ),
        Task(
            id="frontend_integration",
            description="Integrate with React frontend",
            status=TaskStatus.NOT_STARTED,
            dependencies=["api_endpoints"],
            estimated_duration=240  # 4 hours
        )
    ]
    
    return TaskPlan(
        id=f"{project_name}_plan",
        description=f"Development plan for {project_name}",
        tasks=tasks,
        codebase_context=context,
        status=PlanStatus.APPROVED
    )


def demonstrate_caching_system():
    """Demonstrate the caching system functionality."""
    print("=== Caching System Demonstration ===\n")
    
    # Initialize cache manager
    cache_manager = CacheManager(cache_dir="demo_cache", max_memory_mb=100)
    
    print("1. Codebase Analysis Caching")
    print("-" * 30)
    
    # Create sample analyses
    projects = ["ecommerce_app", "blog_platform", "task_manager"]
    
    for project in projects:
        print(f"Analyzing project: {project}")
        
        # Simulate expensive analysis
        start_time = time.time()
        analysis = create_sample_analysis(project)
        analysis_time = time.time() - start_time
        
        # Cache the analysis
        workspace_hash = cache_manager.generate_cache_key(project, "v1.0")
        cache_manager.analysis_cache.cache_analysis(workspace_hash, analysis)
        
        print(f"  - Analysis completed in {analysis_time:.3f}s")
        print(f"  - Cached with hash: {workspace_hash[:12]}...")
    
    print(f"\nCached {len(projects)} analyses")
    
    # Demonstrate cache hits
    print("\n2. Cache Hit Performance")
    print("-" * 25)
    
    for project in projects:
        workspace_hash = cache_manager.generate_cache_key(project, "v1.0")
        
        # Cache hit - should be very fast
        start_time = time.time()
        cached_analysis = cache_manager.analysis_cache.get_analysis(workspace_hash)
        hit_time = time.time() - start_time
        
        print(f"  - {project}: Retrieved in {hit_time:.6f}s (cache hit)")
        assert cached_analysis is not None
        assert cached_analysis.structure.root_path.endswith(project)
    
    # Show cache statistics
    stats = cache_manager.get_combined_stats()
    print(f"\nCache Statistics:")
    print(f"  - Total entries: {stats['total_entries']}")
    print(f"  - Hit rate: {stats['hit_rate']:.2%}")
    print(f"  - Memory usage: {stats['total_memory_usage'] / 1024:.1f} KB")
    
    print("\n3. Task Plan Template Caching")
    print("-" * 32)
    
    # Create and cache task plan templates
    for project in projects:
        workspace_hash = cache_manager.generate_cache_key(project, "v1.0")
        analysis = cache_manager.analysis_cache.get_analysis(workspace_hash)
        
        plan = create_sample_task_plan(project, analysis)
        template_key = f"{project}_template"
        
        cache_manager.task_plan_cache.cache_plan_template(template_key, plan)
        print(f"  - Cached template: {template_key}")
    
    # Demonstrate template similarity matching
    print("\n4. Template Similarity Matching")
    print("-" * 33)
    
    search_characteristics = {
        "languages": ["python", "javascript"],
        "frameworks": ["django", "react"],
        "task_count": 3,
        "has_tests": True,
        "patterns": ["MVC", "Factory"],
        "complexity_level": "medium",
        "project_size": "medium"
    }
    
    similar_templates = cache_manager.task_plan_cache.find_similar_templates(
        search_characteristics, max_results=3
    )
    
    print(f"Found {len(similar_templates)} similar templates:")
    for template_key, plan, similarity in similar_templates:
        print(f"  - {template_key}: {similarity:.2%} similarity")
    
    print("\n5. Execution Result Caching")
    print("-" * 28)
    
    # Simulate cacheable operations
    operations = [
        ("test_execution", {"test_file": "test_auth.py", "framework": "pytest"}),
        ("build_operation", {"target": "production", "optimize": True}),
        ("lint_check", {"files": ["src/*.py"], "strict": True})
    ]
    
    for op_type, params in operations:
        # Create sample execution result
        result = ExecutionResult(
            plan_id=f"{op_type}_plan",
            success=True,
            total_duration=2.5,
            tasks_completed=1,
            tasks_failed=0,
            summary=f"{op_type} completed successfully"
        )
        
        # Cache the result
        cache_manager.execution_cache.cache_operation_result(op_type, params, result)
        print(f"  - Cached {op_type} result")
        
        # Verify cache hit
        cached_result = cache_manager.execution_cache.get_operation_result(op_type, params)
        assert cached_result is not None
        print(f"    ✓ Cache hit verified")
    
    # Final statistics
    final_stats = cache_manager.get_combined_stats()
    print(f"\nFinal Cache Statistics:")
    print(f"  - Total entries: {final_stats['total_entries']}")
    print(f"  - Hit rate: {final_stats['hit_rate']:.2%}")
    print(f"  - Memory usage: {final_stats['total_memory_usage'] / 1024:.1f} KB")
    
    return cache_manager


def demonstrate_resource_management(cache_manager: CacheManager):
    """Demonstrate the resource management system."""
    print("\n\n=== Resource Management Demonstration ===\n")
    
    # Set up resource limits for demonstration
    limits = ResourceLimits(
        max_memory_mb=50,    # Low limit for demonstration
        max_disk_mb=100,     # Low limit for demonstration
        max_cpu_percent=75.0,
        max_open_files=500,
        max_processes=25
    )
    
    # Initialize resource manager
    resource_manager = ResourceManager(
        cache_manager=cache_manager,
        resource_limits=limits,
        monitoring_interval=2,  # 2 seconds for demo
        cleanup_interval=5      # 5 seconds for demo
    )
    
    print("1. Resource Monitoring Setup")
    print("-" * 28)
    print(f"Resource Limits:")
    print(f"  - Memory: {limits.max_memory_mb} MB")
    print(f"  - Disk: {limits.max_disk_mb} MB")
    print(f"  - CPU: {limits.max_cpu_percent}%")
    
    # Get current resource usage
    current_usage = resource_manager.get_current_resource_usage()
    print(f"\nCurrent Usage:")
    print(f"  - Memory: {current_usage.memory_mb:.1f} MB")
    print(f"  - Disk: {current_usage.disk_mb:.1f} MB")
    print(f"  - CPU: {current_usage.cpu_percent:.1f}%")
    
    # Check if within limits
    within_limits = current_usage.is_within_limits(limits)
    print(f"  - Within limits: {'✓' if within_limits else '✗'}")
    
    if not within_limits:
        violations = current_usage.get_violations(limits)
        print(f"  - Violations: {len(violations)}")
        for violation in violations:
            print(f"    • {violation}")
    
    print("\n2. Cleanup Tasks")
    print("-" * 15)
    
    # Show available cleanup tasks
    cleanup_status = resource_manager.get_cleanup_task_status()
    print(f"Available cleanup tasks: {len(cleanup_status)}")
    
    for task_info in cleanup_status:
        print(f"  - {task_info['name']}: Priority {task_info['priority']}")
        print(f"    Description: {task_info['description']}")
        print(f"    Should run: {'✓' if task_info['should_run'] else '✗'}")
        print(f"    Total cleanups: {task_info['total_cleanups']}")
    
    print("\n3. Manual Cleanup Execution")
    print("-" * 28)
    
    # Run cleanup tasks manually
    cleanup_results = resource_manager.run_cleanup_tasks(force=True)
    
    total_cleaned = sum(cleanup_results.values())
    print(f"Cleanup completed: {total_cleaned} items cleaned")
    
    for task_name, count in cleanup_results.items():
        if count > 0:
            print(f"  - {task_name}: {count} items")
    
    print("\n4. Custom Cleanup Task")
    print("-" * 22)
    
    # Add a custom cleanup task
    demo_cleaned_count = 0
    
    def demo_cleanup():
        nonlocal demo_cleaned_count
        demo_cleaned_count += 10
        return 10
    
    custom_task = CleanupTask(
        name="demo_cleanup",
        description="Demonstration cleanup task",
        cleanup_function=demo_cleanup,
        priority=1,
        max_age_hours=0.001  # Very short for immediate execution
    )
    
    resource_manager.add_cleanup_task(custom_task)
    print("Added custom cleanup task: demo_cleanup")
    
    # Run the custom task
    custom_results = resource_manager.run_cleanup_tasks(force=True)
    print(f"Custom cleanup executed: {custom_results.get('demo_cleanup', 0)} items")
    
    print("\n5. Resource Statistics")
    print("-" * 20)
    
    # Add some usage history for statistics
    for i in range(5):
        usage = resource_manager.get_current_resource_usage()
        resource_manager._record_usage(usage)
        time.sleep(0.1)  # Small delay between readings
    
    stats = resource_manager.get_resource_statistics()
    
    if "error" not in stats:
        print("Resource usage statistics:")
        print(f"  Memory - Avg: {stats['memory']['avg']:.1f} MB, "
              f"Max: {stats['memory']['max']:.1f} MB")
        print(f"  Disk - Avg: {stats['disk']['avg']:.1f} MB, "
              f"Max: {stats['disk']['max']:.1f} MB")
        print(f"  CPU - Avg: {stats['cpu']['avg']:.1f}%, "
              f"Max: {stats['cpu']['max']:.1f}%")
    
    print("\n6. Cache Health Monitoring")
    print("-" * 25)
    
    cache_health = cache_manager.get_cache_health()
    print(f"Cache health status: {cache_health['status']}")
    print(f"Memory usage: {cache_health['memory_usage_percentage']:.1f}%")
    print(f"Hit rate: {cache_health['hit_rate']:.2%}")
    
    if cache_health['issues']:
        print("Issues detected:")
        for issue in cache_health['issues']:
            print(f"  - {issue}")
    else:
        print("No issues detected ✓")
    
    return resource_manager


def main():
    """Main demonstration function."""
    print("Intelligent Sandbox Caching and Resource Management Demo")
    print("=" * 60)
    
    try:
        # Demonstrate caching system
        cache_manager = demonstrate_caching_system()
        
        # Demonstrate resource management
        resource_manager = demonstrate_resource_management(cache_manager)
        
        print("\n\n=== Integration Summary ===")
        print("-" * 27)
        
        # Show final combined statistics
        combined_stats = cache_manager.get_combined_stats()
        print(f"Cache Performance:")
        print(f"  - Total entries: {combined_stats['total_entries']}")
        print(f"  - Hit rate: {combined_stats['hit_rate']:.2%}")
        print(f"  - Memory usage: {combined_stats['total_memory_usage'] / 1024:.1f} KB")
        
        cleanup_status = resource_manager.get_cleanup_task_status()
        total_cleanups = sum(task['total_cleanups'] for task in cleanup_status)
        print(f"\nResource Management:")
        print(f"  - Cleanup tasks: {len(cleanup_status)}")
        print(f"  - Total cleanups performed: {total_cleanups}")
        
        print(f"\n✓ Demonstration completed successfully!")
        
    except Exception as e:
        print(f"\n✗ Error during demonstration: {e}")
        raise
    
    finally:
        # Cleanup
        try:
            import shutil
            shutil.rmtree("demo_cache", ignore_errors=True)
            print("\nDemo cache directory cleaned up.")
        except Exception:
            pass


if __name__ == "__main__":
    main()