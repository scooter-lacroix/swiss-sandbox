"""
Resource management and cleanup system for the intelligent sandbox.
"""

import os
import psutil
import shutil
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
import logging

from .cache_manager import CacheManager


@dataclass
class ResourceLimits:
    """Resource limits configuration."""
    max_memory_mb: int = 1024
    max_disk_mb: int = 5120  # 5GB
    max_cpu_percent: float = 80.0
    max_open_files: int = 1000
    max_processes: int = 50


@dataclass
class ResourceUsage:
    """Current resource usage statistics."""
    memory_mb: float = 0.0
    disk_mb: float = 0.0
    cpu_percent: float = 0.0
    open_files: int = 0
    processes: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def is_within_limits(self, limits: ResourceLimits) -> bool:
        """Check if current usage is within specified limits."""
        return (
            self.memory_mb <= limits.max_memory_mb and
            self.disk_mb <= limits.max_disk_mb and
            self.cpu_percent <= limits.max_cpu_percent and
            self.open_files <= limits.max_open_files and
            self.processes <= limits.max_processes
        )
    
    def get_violations(self, limits: ResourceLimits) -> List[str]:
        """Get list of resource limit violations."""
        violations = []
        
        if self.memory_mb > limits.max_memory_mb:
            violations.append(f"Memory usage ({self.memory_mb:.1f}MB) exceeds limit ({limits.max_memory_mb}MB)")
        
        if self.disk_mb > limits.max_disk_mb:
            violations.append(f"Disk usage ({self.disk_mb:.1f}MB) exceeds limit ({limits.max_disk_mb}MB)")
        
        if self.cpu_percent > limits.max_cpu_percent:
            violations.append(f"CPU usage ({self.cpu_percent:.1f}%) exceeds limit ({limits.max_cpu_percent}%)")
        
        if self.open_files > limits.max_open_files:
            violations.append(f"Open files ({self.open_files}) exceeds limit ({limits.max_open_files})")
        
        if self.processes > limits.max_processes:
            violations.append(f"Process count ({self.processes}) exceeds limit ({limits.max_processes})")
        
        return violations


@dataclass
class CleanupTask:
    """Represents a cleanup task to be executed."""
    name: str
    description: str
    cleanup_function: Callable[[], int]  # Returns number of items cleaned
    priority: int = 5  # 1 = highest priority, 10 = lowest
    max_age_hours: float = 24.0
    enabled: bool = True
    last_run: Optional[datetime] = None
    total_cleanups: int = 0
    
    def should_run(self, force: bool = False) -> bool:
        """Check if this cleanup task should run."""
        if not self.enabled:
            return False
        
        if force:
            return True
        
        if self.last_run is None:
            return True
        
        # Run if it's been more than max_age_hours since last run
        time_since_last = datetime.now() - self.last_run
        return time_since_last.total_seconds() > (self.max_age_hours * 3600)


class ResourceManager:
    """Manages system resources and performs automatic cleanup."""
    
    def __init__(self, 
                 cache_manager: CacheManager,
                 resource_limits: Optional[ResourceLimits] = None,
                 monitoring_interval: int = 60,
                 cleanup_interval: int = 300):
        """
        Initialize the resource manager.
        
        Args:
            cache_manager: Cache manager instance
            resource_limits: Resource limits configuration
            monitoring_interval: Resource monitoring interval in seconds
            cleanup_interval: Cleanup task interval in seconds
        """
        self.cache_manager = cache_manager
        self.resource_limits = resource_limits or ResourceLimits()
        self.monitoring_interval = monitoring_interval
        self.cleanup_interval = cleanup_interval
        
        # Resource monitoring
        self._monitoring_thread: Optional[threading.Thread] = None
        self._cleanup_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()
        
        # Resource usage history
        self._usage_history: List[ResourceUsage] = []
        self._max_history_size = 1440  # 24 hours at 1-minute intervals
        
        # Cleanup tasks
        self._cleanup_tasks: List[CleanupTask] = []
        self._setup_default_cleanup_tasks()
        
        # Callbacks for resource events
        self._resource_violation_callbacks: List[Callable[[ResourceUsage, List[str]], None]] = []
        self._cleanup_callbacks: List[Callable[[str, int], None]] = []
        
        # Logger
        self.logger = logging.getLogger(__name__)
    
    def _setup_default_cleanup_tasks(self) -> None:
        """Set up default cleanup tasks."""
        self._cleanup_tasks = [
            CleanupTask(
                name="expired_cache_entries",
                description="Clean up expired cache entries",
                cleanup_function=self._cleanup_expired_cache_entries,
                priority=1,
                max_age_hours=1.0
            ),
            CleanupTask(
                name="old_sandbox_environments",
                description="Clean up old sandbox environments",
                cleanup_function=self._cleanup_old_sandbox_environments,
                priority=2,
                max_age_hours=6.0
            ),
            CleanupTask(
                name="large_log_files",
                description="Rotate and compress large log files",
                cleanup_function=self._cleanup_large_log_files,
                priority=3,
                max_age_hours=12.0
            ),
            CleanupTask(
                name="temporary_files",
                description="Clean up temporary files",
                cleanup_function=self._cleanup_temporary_files,
                priority=4,
                max_age_hours=2.0
            ),
            CleanupTask(
                name="memory_cache_optimization",
                description="Optimize memory cache usage",
                cleanup_function=self._optimize_memory_cache,
                priority=5,
                max_age_hours=0.5
            )
        ]
    
    def start_monitoring(self) -> None:
        """Start resource monitoring and cleanup threads."""
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            return
        
        self._stop_monitoring.clear()
        
        # Start monitoring thread
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            name="ResourceMonitor",
            daemon=True
        )
        self._monitoring_thread.start()
        
        # Start cleanup thread
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            name="ResourceCleanup",
            daemon=True
        )
        self._cleanup_thread.start()
        
        self.logger.info("Resource monitoring and cleanup started")
    
    def stop_monitoring(self) -> None:
        """Stop resource monitoring and cleanup threads."""
        self._stop_monitoring.set()
        
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=5.0)
        
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5.0)
        
        self.logger.info("Resource monitoring and cleanup stopped")
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while not self._stop_monitoring.wait(self.monitoring_interval):
            try:
                usage = self.get_current_resource_usage()
                self._record_usage(usage)
                
                # Check for resource violations
                if not usage.is_within_limits(self.resource_limits):
                    violations = usage.get_violations(self.resource_limits)
                    self._handle_resource_violations(usage, violations)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
    
    def _cleanup_loop(self) -> None:
        """Main cleanup loop."""
        while not self._stop_monitoring.wait(self.cleanup_interval):
            try:
                self.run_cleanup_tasks()
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")
    
    def get_current_resource_usage(self) -> ResourceUsage:
        """Get current system resource usage."""
        try:
            # Memory usage
            memory_info = psutil.virtual_memory()
            memory_mb = memory_info.used / (1024 * 1024)
            
            # Disk usage for cache directory
            cache_dir = Path(self.cache_manager.cache_dir)
            disk_usage = 0.0
            if cache_dir.exists():
                disk_usage = sum(
                    f.stat().st_size for f in cache_dir.rglob('*') if f.is_file()
                ) / (1024 * 1024)
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Process information
            current_process = psutil.Process()
            open_files = len(current_process.open_files())
            processes = len(psutil.pids())
            
            return ResourceUsage(
                memory_mb=memory_mb,
                disk_mb=disk_usage,
                cpu_percent=cpu_percent,
                open_files=open_files,
                processes=processes
            )
            
        except Exception as e:
            self.logger.error(f"Error getting resource usage: {e}")
            return ResourceUsage()
    
    def _record_usage(self, usage: ResourceUsage) -> None:
        """Record resource usage in history."""
        self._usage_history.append(usage)
        
        # Limit history size
        if len(self._usage_history) > self._max_history_size:
            self._usage_history = self._usage_history[-self._max_history_size:]
    
    def _handle_resource_violations(self, usage: ResourceUsage, violations: List[str]) -> None:
        """Handle resource limit violations."""
        self.logger.warning(f"Resource violations detected: {violations}")
        
        # Trigger immediate cleanup for high-priority tasks
        high_priority_tasks = [t for t in self._cleanup_tasks if t.priority <= 2]
        for task in high_priority_tasks:
            if task.enabled:
                try:
                    cleaned_count = task.cleanup_function()
                    task.last_run = datetime.now()
                    task.total_cleanups += 1
                    self.logger.info(f"Emergency cleanup '{task.name}': {cleaned_count} items cleaned")
                except Exception as e:
                    self.logger.error(f"Error in emergency cleanup '{task.name}': {e}")
        
        # Notify callbacks
        for callback in self._resource_violation_callbacks:
            try:
                callback(usage, violations)
            except Exception as e:
                self.logger.error(f"Error in resource violation callback: {e}")
    
    def run_cleanup_tasks(self, force: bool = False) -> Dict[str, int]:
        """Run cleanup tasks that are due."""
        cleanup_results = {}
        
        # Sort tasks by priority
        tasks_to_run = [t for t in self._cleanup_tasks if t.should_run(force)]
        tasks_to_run.sort(key=lambda t: t.priority)
        
        for task in tasks_to_run:
            try:
                start_time = time.time()
                cleaned_count = task.cleanup_function()
                duration = time.time() - start_time
                
                task.last_run = datetime.now()
                task.total_cleanups += 1
                cleanup_results[task.name] = cleaned_count
                
                self.logger.info(
                    f"Cleanup task '{task.name}' completed: "
                    f"{cleaned_count} items cleaned in {duration:.2f}s"
                )
                
                # Notify callbacks
                for callback in self._cleanup_callbacks:
                    try:
                        callback(task.name, cleaned_count)
                    except Exception as e:
                        self.logger.error(f"Error in cleanup callback: {e}")
                        
            except Exception as e:
                self.logger.error(f"Error running cleanup task '{task.name}': {e}")
                cleanup_results[task.name] = 0
        
        return cleanup_results
    
    def _cleanup_expired_cache_entries(self) -> int:
        """Clean up expired cache entries."""
        cleanup_counts = self.cache_manager.cleanup_expired_entries()
        return sum(cleanup_counts.values())
    
    def _cleanup_old_sandbox_environments(self) -> int:
        """Clean up old sandbox environments."""
        cleaned_count = 0
        
        # Look for sandbox directories that are older than 24 hours
        sandbox_dirs = [
            Path("artifacts"),
            Path("sessions"),
            Path("artifact_backups")
        ]
        
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        for base_dir in sandbox_dirs:
            if not base_dir.exists():
                continue
            
            for item in base_dir.iterdir():
                if item.is_dir():
                    try:
                        # Check if directory is old enough
                        stat = item.stat()
                        modified_time = datetime.fromtimestamp(stat.st_mtime)
                        
                        if modified_time < cutoff_time:
                            shutil.rmtree(item, ignore_errors=True)
                            cleaned_count += 1
                            self.logger.debug(f"Removed old sandbox directory: {item}")
                            
                    except Exception as e:
                        self.logger.error(f"Error cleaning up {item}: {e}")
        
        return cleaned_count
    
    def _cleanup_large_log_files(self) -> int:
        """Clean up and rotate large log files."""
        cleaned_count = 0
        max_log_size_mb = 100
        
        # Find log files
        log_patterns = ["*.log", "*.out", "*.err"]
        log_dirs = [Path("."), Path("logs"), Path("artifacts")]
        
        for log_dir in log_dirs:
            if not log_dir.exists():
                continue
            
            for pattern in log_patterns:
                for log_file in log_dir.glob(pattern):
                    try:
                        if log_file.is_file():
                            size_mb = log_file.stat().st_size / (1024 * 1024)
                            
                            if size_mb > max_log_size_mb:
                                # Rotate the log file
                                backup_name = f"{log_file}.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                                log_file.rename(backup_name)
                                
                                # Create new empty log file
                                log_file.touch()
                                
                                cleaned_count += 1
                                self.logger.debug(f"Rotated large log file: {log_file}")
                                
                    except Exception as e:
                        self.logger.error(f"Error rotating log file {log_file}: {e}")
        
        return cleaned_count
    
    def _cleanup_temporary_files(self) -> int:
        """Clean up temporary files."""
        cleaned_count = 0
        
        # Clean up Python cache files
        for cache_dir in Path(".").rglob("__pycache__"):
            try:
                shutil.rmtree(cache_dir, ignore_errors=True)
                cleaned_count += 1
            except Exception:
                pass
        
        # Clean up .pyc files
        for pyc_file in Path(".").rglob("*.pyc"):
            try:
                pyc_file.unlink()
                cleaned_count += 1
            except Exception:
                pass
        
        # Clean up temporary test files
        temp_patterns = ["*.tmp", "*.temp", ".pytest_cache"]
        for pattern in temp_patterns:
            for temp_item in Path(".").rglob(pattern):
                try:
                    if temp_item.is_file():
                        temp_item.unlink()
                        cleaned_count += 1
                    elif temp_item.is_dir():
                        shutil.rmtree(temp_item, ignore_errors=True)
                        cleaned_count += 1
                except Exception:
                    pass
        
        return cleaned_count
    
    def _optimize_memory_cache(self) -> int:
        """Optimize memory cache usage."""
        eviction_counts = self.cache_manager.enforce_memory_limits()
        return sum(eviction_counts.values())
    
    def add_cleanup_task(self, task: CleanupTask) -> None:
        """Add a custom cleanup task."""
        self._cleanup_tasks.append(task)
        self.logger.info(f"Added cleanup task: {task.name}")
    
    def remove_cleanup_task(self, task_name: str) -> bool:
        """Remove a cleanup task by name."""
        for i, task in enumerate(self._cleanup_tasks):
            if task.name == task_name:
                del self._cleanup_tasks[i]
                self.logger.info(f"Removed cleanup task: {task_name}")
                return True
        return False
    
    def get_cleanup_task_status(self) -> List[Dict[str, Any]]:
        """Get status of all cleanup tasks."""
        return [
            {
                "name": task.name,
                "description": task.description,
                "priority": task.priority,
                "enabled": task.enabled,
                "last_run": task.last_run.isoformat() if task.last_run else None,
                "total_cleanups": task.total_cleanups,
                "should_run": task.should_run()
            }
            for task in self._cleanup_tasks
        ]
    
    def get_resource_usage_history(self, hours: int = 24) -> List[ResourceUsage]:
        """Get resource usage history for the specified number of hours."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            usage for usage in self._usage_history
            if usage.timestamp >= cutoff_time
        ]
    
    def get_resource_statistics(self) -> Dict[str, Any]:
        """Get resource usage statistics."""
        if not self._usage_history:
            return {"error": "No usage history available"}
        
        recent_usage = self._usage_history[-100:]  # Last 100 readings
        
        memory_values = [u.memory_mb for u in recent_usage]
        disk_values = [u.disk_mb for u in recent_usage]
        cpu_values = [u.cpu_percent for u in recent_usage]
        
        return {
            "current": self._usage_history[-1] if self._usage_history else None,
            "memory": {
                "avg": sum(memory_values) / len(memory_values),
                "max": max(memory_values),
                "min": min(memory_values)
            },
            "disk": {
                "avg": sum(disk_values) / len(disk_values),
                "max": max(disk_values),
                "min": min(disk_values)
            },
            "cpu": {
                "avg": sum(cpu_values) / len(cpu_values),
                "max": max(cpu_values),
                "min": min(cpu_values)
            },
            "limits": {
                "memory_mb": self.resource_limits.max_memory_mb,
                "disk_mb": self.resource_limits.max_disk_mb,
                "cpu_percent": self.resource_limits.max_cpu_percent
            }
        }
    
    def add_resource_violation_callback(self, callback: Callable[[ResourceUsage, List[str]], None]) -> None:
        """Add a callback for resource violations."""
        self._resource_violation_callbacks.append(callback)
    
    def add_cleanup_callback(self, callback: Callable[[str, int], None]) -> None:
        """Add a callback for cleanup events."""
        self._cleanup_callbacks.append(callback)