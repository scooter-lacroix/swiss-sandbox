"""
Tests for dynamic task status management system.
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock

from ..types import TaskStatus, ErrorInfo
from .models import Task, TaskPlan, Subtask, CodebaseContext
from .status_manager import DynamicStatusManager, TaskProgress, StatusUpdate


class TestDynamicStatusManager:
    """Test cases for DynamicStatusManager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.manager = DynamicStatusManager()
        
        # Create a test plan with tasks and subtasks
        self.task1 = Task(
            id="task1",
            description="Implement feature A",
            estimated_duration=60
        )
        
        self.subtask1 = Subtask(
            id="subtask1",
            description="Design feature A",
            estimated_duration=30
        )
        
        self.subtask2 = Subtask(
            id="subtask2",
            description="Implement feature A core",
            dependencies=["subtask1"],
            estimated_duration=30
        )
        
        self.task1.subtasks = [self.subtask1, self.subtask2]
        
        self.task2 = Task(
            id="task2",
            description="Test feature A",
            dependencies=["task1"],
            estimated_duration=30
        )
        
        self.plan = TaskPlan(
            id="plan1",
            description="Feature A development",
            tasks=[self.task1, self.task2]
        )
    
    def test_register_plan(self):
        """Test plan registration and initialization."""
        self.manager.register_plan(self.plan)
        
        # Check that progress tracking is initialized
        assert "task1" in self.manager._task_progress
        assert "task2" in self.manager._task_progress
        assert "subtask1" in self.manager._task_progress
        assert "subtask2" in self.manager._task_progress
        
        # Check initial status
        progress1 = self.manager.get_task_progress("task1")
        assert progress1.status == TaskStatus.NOT_STARTED
        assert progress1.estimated_duration == 60
        assert progress1.progress_percentage == 0.0
    
    def test_update_task_status_basic(self):
        """Test basic task status updates."""
        self.manager.register_plan(self.plan)
        
        # Start task
        result = self.manager.update_task_status("task1", TaskStatus.IN_PROGRESS)
        assert result is True
        
        progress = self.manager.get_task_progress("task1")
        assert progress.status == TaskStatus.IN_PROGRESS
        assert progress.start_time is not None
        assert progress.progress_percentage == 5.0  # Started
        
        # Complete task
        result = self.manager.update_task_status("task1", TaskStatus.COMPLETED)
        assert result is True
        
        progress = self.manager.get_task_progress("task1")
        assert progress.status == TaskStatus.COMPLETED
        assert progress.end_time is not None
        assert progress.progress_percentage == 100.0
        assert progress.actual_duration is not None
    
    def test_update_task_status_with_progress(self):
        """Test status updates with progress percentage."""
        self.manager.register_plan(self.plan)
        
        # Start task
        self.manager.update_task_status("task1", TaskStatus.IN_PROGRESS)
        
        # Update progress
        result = self.manager.update_task_status(
            "task1", 
            TaskStatus.IN_PROGRESS, 
            progress_percentage=50.0
        )
        assert result is True
        
        progress = self.manager.get_task_progress("task1")
        assert progress.progress_percentage == 50.0
    
    def test_update_task_status_with_error(self):
        """Test status updates with error information."""
        self.manager.register_plan(self.plan)
        
        error_info = ErrorInfo(
            error_type="RuntimeError",
            message="Test error",
            stack_trace="Stack trace here"
        )
        
        result = self.manager.update_task_status(
            "task1", 
            TaskStatus.ERROR,
            error_info=error_info
        )
        assert result is True
        
        progress = self.manager.get_task_progress("task1")
        assert progress.status == TaskStatus.ERROR
        assert progress.error_info == error_info
        assert progress.end_time is not None
    
    def test_update_nonexistent_task(self):
        """Test updating status of nonexistent task."""
        self.manager.register_plan(self.plan)
        
        result = self.manager.update_task_status("nonexistent", TaskStatus.IN_PROGRESS)
        assert result is False
    
    def test_get_plan_progress(self):
        """Test getting overall plan progress."""
        self.manager.register_plan(self.plan)
        
        # Initially no progress
        progress = self.manager.get_plan_progress("plan1")
        assert progress['total_tasks'] == 2
        assert progress['completed_tasks'] == 0
        assert progress['completion_percentage'] == 0.0
        
        # Complete one task
        self.manager.update_task_status("task1", TaskStatus.COMPLETED)
        
        progress = self.manager.get_plan_progress("plan1")
        assert progress['completed_tasks'] == 1
        assert progress['completion_percentage'] == 50.0
    
    def test_get_plan_progress_nonexistent(self):
        """Test getting progress for nonexistent plan."""
        progress = self.manager.get_plan_progress("nonexistent")
        assert progress == {}
    
    def test_modify_task_description(self):
        """Test modifying task description."""
        self.manager.register_plan(self.plan)
        
        result = self.manager.modify_task(
            "task1", 
            new_description="Modified feature A implementation"
        )
        assert result is True
        assert self.task1.description == "Modified feature A implementation"
    
    def test_modify_task_duration(self):
        """Test modifying task estimated duration."""
        self.manager.register_plan(self.plan)
        
        result = self.manager.modify_task("task1", new_estimated_duration=90)
        assert result is True
        assert self.task1.estimated_duration == 90
        
        # Check that progress tracking is updated
        progress = self.manager.get_task_progress("task1")
        assert progress.estimated_duration == 90
    
    def test_modify_task_dependencies(self):
        """Test modifying task dependencies."""
        self.manager.register_plan(self.plan)
        
        # Add dependency
        result = self.manager.modify_task("task1", add_dependencies=["task0"])
        assert result is True
        assert "task0" in self.task1.dependencies
        
        # Remove dependency
        result = self.manager.modify_task("task2", remove_dependencies=["task1"])
        assert result is True
        assert "task1" not in self.task2.dependencies
    
    def test_modify_nonexistent_task(self):
        """Test modifying nonexistent task."""
        self.manager.register_plan(self.plan)
        
        result = self.manager.modify_task("nonexistent", new_description="Test")
        assert result is False
    
    def test_replan_from_task(self):
        """Test re-planning a task with new subtasks."""
        self.manager.register_plan(self.plan)
        
        new_subtasks = [
            {
                'id': 'new_subtask1',
                'description': 'New subtask 1',
                'estimated_duration': 20
            },
            {
                'id': 'new_subtask2',
                'description': 'New subtask 2',
                'dependencies': ['new_subtask1'],
                'estimated_duration': 25
            }
        ]
        
        result = self.manager.replan_from_task("task1", new_subtasks)
        assert result is True
        
        # Check that old subtasks are removed from tracking
        assert "subtask1" not in self.manager._task_progress
        assert "subtask2" not in self.manager._task_progress
        
        # Check that new subtasks are added
        assert "new_subtask1" in self.manager._task_progress
        assert "new_subtask2" in self.manager._task_progress
        
        # Check task object is updated
        assert len(self.task1.subtasks) == 2
        assert self.task1.subtasks[0].id == "new_subtask1"
        assert self.task1.subtasks[1].id == "new_subtask2"
    
    def test_get_status_history(self):
        """Test getting status update history."""
        self.manager.register_plan(self.plan)
        
        # Make several status updates
        self.manager.update_task_status("task1", TaskStatus.IN_PROGRESS, "Started")
        self.manager.update_task_status("task1", TaskStatus.IN_PROGRESS, "50% done", 50.0)
        self.manager.update_task_status("task1", TaskStatus.COMPLETED, "Finished")
        
        history = self.manager.get_status_history("task1")
        assert len(history) == 3
        
        assert history[0].old_status == TaskStatus.NOT_STARTED
        assert history[0].new_status == TaskStatus.IN_PROGRESS
        assert history[0].message == "Started"
        
        assert history[2].new_status == TaskStatus.COMPLETED
        assert history[2].message == "Finished"
    
    def test_status_listeners(self):
        """Test status update listeners."""
        self.manager.register_plan(self.plan)
        
        # Create mock listener
        listener = Mock()
        self.manager.add_status_listener(listener)
        
        # Update status
        self.manager.update_task_status("task1", TaskStatus.IN_PROGRESS)
        
        # Check listener was called
        listener.assert_called_once()
        update = listener.call_args[0][0]
        assert isinstance(update, StatusUpdate)
        assert update.task_id == "task1"
        assert update.new_status == TaskStatus.IN_PROGRESS
        
        # Remove listener
        self.manager.remove_status_listener(listener)
        listener.reset_mock()
        
        # Update status again
        self.manager.update_task_status("task1", TaskStatus.COMPLETED)
        
        # Listener should not be called
        listener.assert_not_called()
    
    def test_get_active_tasks(self):
        """Test getting active tasks."""
        self.manager.register_plan(self.plan)
        
        # Initially no active tasks
        active = self.manager.get_active_tasks()
        assert len(active) == 0
        
        # Start some tasks
        self.manager.update_task_status("task1", TaskStatus.IN_PROGRESS)
        self.manager.update_task_status("subtask1", TaskStatus.IN_PROGRESS)
        
        active = self.manager.get_active_tasks()
        assert len(active) == 2
        
        task_ids = [task.task_id for task in active]
        assert "task1" in task_ids
        assert "subtask1" in task_ids
        
        # Test filtering by plan
        active_plan = self.manager.get_active_tasks("plan1")
        assert len(active_plan) == 2
        
        active_other = self.manager.get_active_tasks("other_plan")
        assert len(active_other) == 0


class TestTaskProgress:
    """Test cases for TaskProgress model."""
    
    def test_elapsed_time_no_start(self):
        """Test elapsed time when task hasn't started."""
        progress = TaskProgress(task_id="test", status=TaskStatus.NOT_STARTED)
        assert progress.elapsed_time is None
    
    def test_elapsed_time_with_start(self):
        """Test elapsed time calculation."""
        start_time = datetime.now() - timedelta(minutes=30)
        progress = TaskProgress(
            task_id="test", 
            status=TaskStatus.IN_PROGRESS,
            start_time=start_time
        )
        
        elapsed = progress.elapsed_time
        assert elapsed is not None
        assert 29 <= elapsed <= 31  # Allow for small timing differences
    
    def test_elapsed_time_completed(self):
        """Test elapsed time for completed task."""
        start_time = datetime.now() - timedelta(minutes=45)
        end_time = datetime.now() - timedelta(minutes=15)
        
        progress = TaskProgress(
            task_id="test",
            status=TaskStatus.COMPLETED,
            start_time=start_time,
            end_time=end_time
        )
        
        elapsed = progress.elapsed_time
        assert elapsed == 30
    
    def test_remaining_time_no_estimate(self):
        """Test remaining time without duration estimate."""
        progress = TaskProgress(task_id="test", status=TaskStatus.IN_PROGRESS)
        assert progress.remaining_time is None
    
    def test_remaining_time_with_progress(self):
        """Test remaining time calculation with progress."""
        start_time = datetime.now() - timedelta(minutes=20)
        progress = TaskProgress(
            task_id="test",
            status=TaskStatus.IN_PROGRESS,
            start_time=start_time,
            estimated_duration=60,
            progress_percentage=25.0
        )
        
        remaining = progress.remaining_time
        assert remaining is not None
        assert 55 <= remaining <= 65  # Should be around 60 minutes remaining
    
    def test_remaining_time_no_progress(self):
        """Test remaining time without progress percentage."""
        start_time = datetime.now() - timedelta(minutes=20)
        progress = TaskProgress(
            task_id="test",
            status=TaskStatus.IN_PROGRESS,
            start_time=start_time,
            estimated_duration=60,
            progress_percentage=0.0
        )
        
        remaining = progress.remaining_time
        assert remaining == 40  # 60 - 20 elapsed


class TestStatusUpdate:
    """Test cases for StatusUpdate model."""
    
    def test_status_update_creation(self):
        """Test creating status update."""
        update = StatusUpdate(
            task_id="test",
            old_status=TaskStatus.NOT_STARTED,
            new_status=TaskStatus.IN_PROGRESS,
            message="Task started"
        )
        
        assert update.task_id == "test"
        assert update.old_status == TaskStatus.NOT_STARTED
        assert update.new_status == TaskStatus.IN_PROGRESS
        assert update.message == "Task started"
        assert isinstance(update.timestamp, datetime)


if __name__ == "__main__":
    pytest.main([__file__])