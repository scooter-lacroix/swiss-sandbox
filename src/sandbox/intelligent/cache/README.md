# Intelligent Sandbox Caching and Resource Management System

This module provides a comprehensive caching and resource management system for the intelligent sandbox, designed to optimize performance and manage system resources efficiently.

## Overview

The system consists of two main components:

1. **Caching System**: Provides intelligent caching for analysis results, task plan templates, and execution results
2. **Resource Management**: Monitors system resources and performs automatic cleanup to maintain optimal performance

## Features

### Caching System

- **Analysis Cache**: Caches codebase analysis results with file timestamp validation
- **Task Plan Cache**: Stores task plan templates with similarity matching for reuse
- **Execution Cache**: Caches execution results for repeated operations
- **Memory Management**: Automatic memory limit enforcement with LRU eviction
- **Persistence**: Disk-based storage with automatic loading and saving

### Resource Management

- **Resource Monitoring**: Real-time monitoring of memory, disk, CPU, and process usage
- **Automatic Cleanup**: Scheduled cleanup tasks for expired cache entries, temporary files, and old environments
- **Custom Cleanup Tasks**: Support for adding custom cleanup operations
- **Resource Limits**: Configurable limits with violation detection and handling
- **Statistics**: Comprehensive resource usage statistics and health monitoring

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Cache Manager                            │
├─────────────────┬─────────────────┬─────────────────────────┤
│  Analysis Cache │ Task Plan Cache │    Execution Cache      │
├─────────────────┼─────────────────┼─────────────────────────┤
│ • Codebase      │ • Plan Templates│ • Operation Results     │
│   Analysis      │ • Similarity    │ • File Dependencies     │
│ • File Tracking │   Matching      │ • Invalidation          │
│ • TTL Support   │ • Usage Stats   │ • Cacheability Check    │
└─────────────────┴─────────────────┴─────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                 Resource Manager                            │
├─────────────────┬─────────────────┬─────────────────────────┤
│   Monitoring    │  Cleanup Tasks  │    Statistics           │
├─────────────────┼─────────────────┼─────────────────────────┤
│ • Memory Usage  │ • Expired Cache │ • Usage History         │
│ • Disk Usage    │ • Temp Files    │ • Health Monitoring     │
│ • CPU Usage     │ • Old Sandboxes │ • Violation Detection   │
│ • Process Count │ • Custom Tasks  │ • Callback Support      │
└─────────────────┴─────────────────┴─────────────────────────┘
```

## Usage Examples

### Basic Cache Usage

```python
from .cache_manager import CacheManager
from .resource_manager import ResourceManager, ResourceLimits

# Initialize cache manager
cache_manager = CacheManager(cache_dir="~/.sandbox_cache", max_memory_mb=512)

# Cache analysis results
analysis = perform_codebase_analysis(workspace)
workspace_hash = cache_manager.generate_cache_key(workspace_path)
cache_manager.analysis_cache.cache_analysis(workspace_hash, analysis)

# Retrieve cached analysis
cached_analysis = cache_manager.analysis_cache.get_analysis(workspace_hash)
```

### Resource Management

```python
# Set up resource limits
limits = ResourceLimits(
    max_memory_mb=1024,
    max_disk_mb=5120,
    max_cpu_percent=80.0
)

# Initialize resource manager
resource_manager = ResourceManager(
    cache_manager=cache_manager,
    resource_limits=limits
)

# Start monitoring
resource_manager.start_monitoring()

# Get current resource usage
usage = resource_manager.get_current_resource_usage()
print(f"Memory: {usage.memory_mb:.1f} MB")
print(f"CPU: {usage.cpu_percent:.1f}%")

# Run cleanup tasks
cleanup_results = resource_manager.run_cleanup_tasks()
```

### Custom Cleanup Tasks

```python
from .resource_manager import CleanupTask

def custom_cleanup():
    # Your cleanup logic here
    cleaned_count = cleanup_old_files()
    return cleaned_count

custom_task = CleanupTask(
    name="custom_cleanup",
    description="Clean up application-specific files",
    cleanup_function=custom_cleanup,
    priority=2,
    max_age_hours=6.0
)

resource_manager.add_cleanup_task(custom_task)
```

## Performance Benefits

### Caching Effectiveness

- **Analysis Cache**: Reduces expensive codebase analysis from seconds to microseconds
- **Task Plan Templates**: Enables reuse of successful task plans across similar projects
- **Execution Cache**: Eliminates redundant operations like repeated test runs

### Resource Optimization

- **Memory Management**: Prevents memory exhaustion through automatic cleanup
- **Disk Cleanup**: Maintains disk space by removing temporary and expired files
- **Process Monitoring**: Tracks resource usage to prevent system overload

## Configuration

### Cache Configuration

```python
cache_manager = CacheManager(
    cache_dir="/path/to/cache",
    max_memory_mb=512  # Maximum memory usage for all caches
)

# Configure individual caches
analysis_cache = AnalysisCache(
    cache_dir="/path/to/analysis_cache",
    max_entries=1000,
    default_ttl=3600  # 1 hour
)
```

### Resource Limits

```python
limits = ResourceLimits(
    max_memory_mb=1024,      # Maximum memory usage
    max_disk_mb=5120,        # Maximum disk usage (5GB)
    max_cpu_percent=80.0,    # Maximum CPU usage
    max_open_files=1000,     # Maximum open files
    max_processes=50         # Maximum processes
)
```

## Testing

The system includes comprehensive tests covering:

- **Unit Tests**: Individual component functionality
- **Integration Tests**: Component interaction and workflows
- **Performance Tests**: Cache effectiveness and resource management
- **Stress Tests**: Behavior under high load conditions

Run tests with:

```bash
# Run all cache tests
python -m pytest src/sandbox/intelligent/cache/ -v

# Run specific test categories
python -m pytest src/sandbox/intelligent/cache/test_cache_system.py -v
python -m pytest src/sandbox/intelligent/cache/test_resource_manager.py -v
python -m pytest src/sandbox/intelligent/cache/test_cache_performance.py -v
```

## Monitoring and Debugging

### Cache Statistics

```python
# Get combined statistics
stats = cache_manager.get_combined_stats()
print(f"Hit rate: {stats['hit_rate']:.2%}")
print(f"Total entries: {stats['total_entries']}")
print(f"Memory usage: {stats['total_memory_usage']} bytes")

# Get cache health
health = cache_manager.get_cache_health()
print(f"Status: {health['status']}")
print(f"Issues: {health['issues']}")
```

### Resource Monitoring

```python
# Get resource statistics
stats = resource_manager.get_resource_statistics()
print(f"Memory avg: {stats['memory']['avg']:.1f} MB")
print(f"CPU max: {stats['cpu']['max']:.1f}%")

# Get cleanup task status
cleanup_status = resource_manager.get_cleanup_task_status()
for task in cleanup_status:
    print(f"{task['name']}: {task['total_cleanups']} cleanups")
```

## Best Practices

1. **Cache Key Generation**: Use consistent, deterministic cache keys
2. **TTL Configuration**: Set appropriate TTL values based on data volatility
3. **Resource Limits**: Configure limits based on system capabilities
4. **Cleanup Scheduling**: Balance cleanup frequency with performance impact
5. **Monitoring**: Regularly check cache hit rates and resource usage

## Integration

The caching and resource management system integrates seamlessly with other intelligent sandbox components:

- **Analyzer**: Automatic caching of analysis results
- **Planner**: Template-based task plan generation
- **Executor**: Caching of execution results
- **Logger**: Resource usage logging and monitoring

## Troubleshooting

### Common Issues

1. **Low Cache Hit Rate**: Check cache key consistency and TTL settings
2. **High Memory Usage**: Reduce max_memory_mb or increase cleanup frequency
3. **Disk Space Issues**: Enable disk cleanup tasks and reduce cache retention
4. **Performance Degradation**: Monitor resource usage and adjust limits

### Debug Logging

Enable debug logging to troubleshoot issues:

```python
import logging
logging.getLogger('src.sandbox.intelligent.cache').setLevel(logging.DEBUG)
```

## Future Enhancements

- **Distributed Caching**: Support for multi-node cache sharing
- **Advanced Similarity**: Machine learning-based template matching
- **Predictive Cleanup**: AI-driven cleanup scheduling
- **Cloud Integration**: Support for cloud-based cache storage