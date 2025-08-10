"""
Tests for the resource management system.
"""

import pytest
import tempfile
import shutil
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from .resource_manager import ResourceManager, ResourceLimits, ResourceUsage, CleanupTask
from .cache_manager import CacheManager


class TestResourceLimits:
    """Test resource limits configuration."""
    
    def test_default_limits(self):
        """Test default resource limits."""
        limits = ResourceLimits()
        
        assert limits.max_memory_mb == 1024
        assert limits.max_disk_mb == 5120
        assert limits.max_cpu_percent == 80.0
        assert limits.max_open_files == 1000
        assert limits.max_processes == 50
    
    def test_custom_limits(self):
        """Test custom resource limits."""
        limits = ResourceLimits(
            max_memory_mb=2048,
            max_disk_mb=10240,
            max_cpu_percent=90.0
        )
        
        assert limits.max_memory_mb == 2048
        assert limits.max_disk_mb == 10240
        assert limits.max_cpu_percent == 90.0


class TestResourceUsage:
    """Test resource usage tracking."""
    
    def test_within_limits(self):
        """Test checking if usage is within limits."""
        limits = ResourceLimits(
            max_memory_mb=1000,
            max_disk_mb=2000,
            max_cpu_percent=80.0
        )
        
        # Usage within limits
        usage = ResourceUsage(
            memory_mb=500,
            disk_mb=1000,
            cpu_percent=50.0
        )
        
        assert usage.is_within_limits(limits) is True
    
    def test_exceeds_limits(self):
        """Test detecting when usage exceeds limits."""
        limits = ResourceLimits(
            max_memory_mb=1000,
            max_disk_mb=2000,
            max_cpu_percent=80.0
        )
        
        # Usage exceeding limits
        usage = ResourceUsage(
            memory_mb=1500,  # Exceeds memory limit
            disk_mb=1000,
            cpu_percent=90.0  # Exceeds CPU limit
        )
        
        assert usage.is_within_limits(limits) is False
    
    def test_get_violations(self):
        """Test getting specific limit violations."""
        limits = ResourceLimits(
            max_memory_mb=1000,
            max_disk_mb=2000,
            max_cpu_percent=80.0
        )
        
        usage = ResourceUsage(
            memory_mb=1500,  # Exceeds memory limit
            disk_mb=2500,    # Exceeds disk limit
            cpu_percent=50.0  # Within CPU limit
        )
        
        violations = usage.get_violations(limits)
        
        assert len(violations) == 2
        assert any("Memory usage" in v for v in violations)
        assert any("Disk usage" in v for v in violations)
        assert not any("CPU usage" in v for v in violations)


class TestCleanupTask:
    """Test cleanup task functionality."""
    
    def test_cleanup_task_creation(self):
        """Test creating a cleanup task."""
        def dummy_cleanup():
            return 5
        
        task = CleanupTask(
            name="test_task",
            description="Test cleanup task",
            cleanup_function=dummy_cleanup,
            priority=3
        )
        
        assert task.name == "test_task"
        assert task.description == "Test cleanup task"
        assert task.priority == 3
        assert task.enabled is True
        assert task.last_run is None
    
    def test_should_run_logic(self):
        """Test cleanup task scheduling logic."""
        def dummy_cleanup():
            return 0
        
        task = CleanupTask(
            name="test_task",
            description="Test task",
            cleanup_function=dummy_cleanup,
            max_age_hours=1.0
        )
        
        # Should run initially
        assert task.should_run() is True
        
        # Should run when forced
        assert task.should_run(force=True) is True
        
        # Set last run to recent time
        task.last_run = datetime.now()
        
        # Should not run if recently executed
        assert task.should_run() is False
        
        # Should run if enough time has passed
        task.last_run = datetime.now() - timedelta(hours=2)
        assert task.should_run() is True
        
        # Should not run if disabled
        task.enabled = False
        assert task.should_run() is False


class TestResourceManager:
    """Test the resource manager."""
    
    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary cache directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def cache_manager(self, temp_cache_dir):
        """Create a cache manager instance."""
        return CacheManager(cache_dir=temp_cache_dir, max_memory_mb=10)
    
    @pytest.fixture
    def resource_manager(self, cache_manager):
        """Create a resource manager instance."""
        limits = ResourceLimits(
            max_memory_mb=100,
            max_disk_mb=200,
            max_cpu_percent=80.0
        )
        return ResourceManager(
            cache_manager=cache_manager,
            resource_limits=limits,
            monitoring_interval=1,  # Short interval for testing
            cleanup_interval=2
        )
    
    def test_resource_manager_initialization(self, resource_manager):
        """Test resource manager initialization."""
        assert resource_manager.cache_manager is not None
        assert resource_manager.resource_limits is not None
        assert len(resource_manager._cleanup_tasks) > 0
        
        # Check default cleanup tasks are present
        task_names = [task.name for task in resource_manager._cleanup_tasks]
        assert "expired_cache_entries" in task_names
        assert "old_sandbox_environments" in task_names
        assert "temporary_files" in task_names
    
    @patch('psutil.virtual_memory')
    @patch('psutil.cpu_percent')
    @patch('psutil.Process')
    @patch('psutil.pids')
    def test_get_current_resource_usage(self, mock_pids, mock_process, 
                                       mock_cpu_percent, mock_virtual_memory, 
                                       resource_manager):
        """Test getting current resource usage."""
        # Mock system resource calls
        mock_memory = Mock()
        mock_memory.used = 1024 * 1024 * 500  # 500MB
        mock_virtual_memory.return_value = mock_memory
        
        mock_cpu_percent.return_value = 45.0
        
        mock_proc = Mock()
        mock_proc.open_files.return_value = [Mock()] * 10  # 10 open files
        mock_process.return_value = mock_proc
        
        mock_pids.return_value = list(range(50))  # 50 processes
        
        usage = resource_manager.get_current_resource_usage()
        
        assert usage.memory_mb == 500.0
        assert usage.cpu_percent == 45.0
        assert usage.open_files == 10
        assert usage.processes == 50
        assert isinstance(usage.timestamp, datetime)
    
    def test_add_custom_cleanup_task(self, resource_manager):
        """Test adding custom cleanup tasks."""
        def custom_cleanup():
            return 3
        
        custom_task = CleanupTask(
            name="custom_task",
            description="Custom cleanup task",
            cleanup_function=custom_cleanup,
            priority=1
        )
        
        initial_count = len(resource_manager._cleanup_tasks)
        resource_manager.add_cleanup_task(custom_task)
        
        assert len(resource_manager._cleanup_tasks) == initial_count + 1
        
        # Verify task was added
        task_names = [task.name for task in resource_manager._cleanup_tasks]
        assert "custom_task" in task_names
    
    def test_remove_cleanup_task(self, resource_manager):
        """Test removing cleanup tasks."""
        initial_count = len(resource_manager._cleanup_tasks)
        
        # Remove an existing task
        result = resource_manager.remove_cleanup_task("expired_cache_entries")
        assert result is True
        assert len(resource_manager._cleanup_tasks) == initial_count - 1
        
        # Try to remove non-existent task
        result = resource_manager.remove_cleanup_task("non_existent_task")
        assert result is False
    
    def test_run_cleanup_tasks(self, resource_manager):
        """Test running cleanup tasks."""
        # Add a mock cleanup task
        cleanup_called = False
        
        def mock_cleanup():
            nonlocal cleanup_called
            cleanup_called = True
            return 5
        
        mock_task = CleanupTask(
            name="mock_task",
            description="Mock cleanup task",
            cleanup_function=mock_cleanup,
            priority=1
        )
        
        resource_manager.add_cleanup_task(mock_task)
        
        # Run cleanup tasks
        results = resource_manager.run_cleanup_tasks(force=True)
        
        assert cleanup_called is True
        assert "mock_task" in results
        assert results["mock_task"] == 5
    
    def test_cleanup_task_status(self, resource_manager):
        """Test getting cleanup task status."""
        status_list = resource_manager.get_cleanup_task_status()
        
        assert isinstance(status_list, list)
        assert len(status_list) > 0
        
        # Check status structure
        first_status = status_list[0]
        required_keys = ["name", "description", "priority", "enabled", 
                        "last_run", "total_cleanups", "should_run"]
        
        for key in required_keys:
            assert key in first_status
    
    def test_resource_statistics(self, resource_manager):
        """Test getting resource statistics."""
        # Add some mock usage data
        usage1 = ResourceUsage(memory_mb=100, disk_mb=200, cpu_percent=30)
        usage2 = ResourceUsage(memory_mb=150, disk_mb=250, cpu_percent=40)
        
        resource_manager._usage_history = [usage1, usage2]
        
        stats = resource_manager.get_resource_statistics()
        
        assert "current" in stats
        assert "memory" in stats
        assert "disk" in stats
        assert "cpu" in stats
        assert "limits" in stats
        
        # Check memory statistics
        assert stats["memory"]["avg"] == 125.0  # (100 + 150) / 2
        assert stats["memory"]["max"] == 150.0
        assert stats["memory"]["min"] == 100.0
    
    def test_resource_violation_callbacks(self, resource_manager):
        """Test resource violation callbacks."""
        callback_called = False
        callback_usage = None
        callback_violations = None
        
        def violation_callback(usage, violations):
            nonlocal callback_called, callback_usage, callback_violations
            callback_called = True
            callback_usage = usage
            callback_violations = violations
        
        resource_manager.add_resource_violation_callback(violation_callback)
        
        # Simulate resource violation
        usage = ResourceUsage(memory_mb=200, cpu_percent=90)  # Exceeds limits
        violations = ["Memory exceeded", "CPU exceeded"]
        
        resource_manager._handle_resource_violations(usage, violations)
        
        assert callback_called is True
        assert callback_usage == usage
        assert callback_violations == violations
    
    def test_cleanup_callbacks(self, resource_manager):
        """Test cleanup event callbacks."""
        callback_called = False
        callback_task_name = None
        callback_count = None
        
        def cleanup_callback(task_name, cleaned_count):
            nonlocal callback_called, callback_task_name, callback_count
            callback_called = True
            callback_task_name = task_name
            callback_count = cleaned_count
        
        resource_manager.add_cleanup_callback(cleanup_callback)
        
        # Add and run a mock cleanup task
        def mock_cleanup():
            return 10
        
        mock_task = CleanupTask(
            name="callback_test_task",
            description="Test task for callbacks",
            cleanup_function=mock_cleanup
        )
        
        resource_manager.add_cleanup_task(mock_task)
        resource_manager.run_cleanup_tasks(force=True)
        
        assert callback_called is True
        assert callback_task_name == "callback_test_task"
        assert callback_count == 10


class TestResourceManagerIntegration:
    """Integration tests for resource manager."""
    
    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary cache directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def cache_manager(self, temp_cache_dir):
        """Create a cache manager instance."""
        return CacheManager(cache_dir=temp_cache_dir, max_memory_mb=1)
    
    @pytest.fixture
    def resource_manager(self, cache_manager):
        """Create a resource manager instance."""
        return ResourceManager(
            cache_manager=cache_manager,
            monitoring_interval=0.1,  # Very short for testing
            cleanup_interval=0.2
        )
    
    def test_monitoring_thread_lifecycle(self, resource_manager):
        """Test starting and stopping monitoring threads."""
        # Initially not running
        assert resource_manager._monitoring_thread is None
        
        # Start monitoring
        resource_manager.start_monitoring()
        
        assert resource_manager._monitoring_thread is not None
        assert resource_manager._monitoring_thread.is_alive()
        assert resource_manager._cleanup_thread is not None
        assert resource_manager._cleanup_thread.is_alive()
        
        # Let it run briefly
        time.sleep(0.5)
        
        # Stop monitoring
        resource_manager.stop_monitoring()
        
        # Threads should be stopped
        time.sleep(0.1)  # Give threads time to stop
        assert not resource_manager._monitoring_thread.is_alive()
        assert not resource_manager._cleanup_thread.is_alive()
    
    def test_automatic_cleanup_execution(self, resource_manager):
        """Test that cleanup tasks are executed automatically."""
        cleanup_executed = threading.Event()
        
        def test_cleanup():
            cleanup_executed.set()
            return 1
        
        # Add a test cleanup task with short interval
        test_task = CleanupTask(
            name="auto_test_task",
            description="Automatic test task",
            cleanup_function=test_cleanup,
            max_age_hours=0.001  # Very short interval
        )
        
        resource_manager.add_cleanup_task(test_task)
        
        # Start monitoring
        resource_manager.start_monitoring()
        
        # Wait for cleanup to be executed
        assert cleanup_executed.wait(timeout=2.0), "Cleanup task was not executed automatically"
        
        # Stop monitoring
        resource_manager.stop_monitoring()
    
    def test_memory_efficient_log_storage(self, resource_manager):
        """Test that resource usage history is stored efficiently."""
        # Generate a lot of usage data
        for i in range(2000):  # More than max history size
            usage = ResourceUsage(
                memory_mb=100 + i,
                disk_mb=200 + i,
                cpu_percent=30 + (i % 50)
            )
            resource_manager._record_usage(usage)
        
        # History should be limited to max size
        assert len(resource_manager._usage_history) <= resource_manager._max_history_size
        
        # Should contain the most recent entries
        latest_usage = resource_manager._usage_history[-1]
        assert latest_usage.memory_mb >= 100 + 1999  # Should be from recent entries


class TestStressConditions:
    """Test resource manager under stress conditions."""
    
    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary cache directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def cache_manager(self, temp_cache_dir):
        """Create a cache manager instance."""
        return CacheManager(cache_dir=temp_cache_dir, max_memory_mb=1)
    
    def test_resource_manager_under_load(self, cache_manager):
        """Test resource manager behavior under high load."""
        # Create resource manager with very low limits
        limits = ResourceLimits(
            max_memory_mb=1,    # Very low memory limit
            max_disk_mb=10,     # Very low disk limit
            max_cpu_percent=10.0  # Very low CPU limit
        )
        
        resource_manager = ResourceManager(
            cache_manager=cache_manager,
            resource_limits=limits,
            monitoring_interval=0.1,
            cleanup_interval=0.1
        )
        
        # Add data to cache to trigger resource pressure
        for i in range(50):
            cache_manager.analysis_cache.set(f"stress_key_{i}", "x" * 1000)
        
        # Start monitoring
        resource_manager.start_monitoring()
        
        # Let it run under stress
        time.sleep(1.0)
        
        # Manually trigger a monitoring cycle to ensure data is recorded
        usage = resource_manager.get_current_resource_usage()
        resource_manager._record_usage(usage)
        
        # Should have recorded some usage data
        assert len(resource_manager._usage_history) > 0
        
        # Should have run some cleanup tasks
        task_status = resource_manager.get_cleanup_task_status()
        cleanup_runs = sum(task["total_cleanups"] for task in task_status)
        assert cleanup_runs > 0
        
        # Stop monitoring
        resource_manager.stop_monitoring()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])