"""
Unit tests for the execution engine.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime

from ..types import TaskStatus, ErrorInfo
from ..planner.models import Task, TaskPlan, Subtask, CodebaseContext
from ..analyzer.models import CodebaseAnalysis, CodebaseStructure, DependencyGraph, CodeMetrics
from .engine import ExecutionEngine, SandboxCommandExecutor
from .models import SandboxExecutor, RetryContext


class TestSandboxCommandExecutor(unittest.TestCase):
    """Test cases for SandboxCommandExecutor."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.executor = SandboxCommandExecutor(self.temp_dir)
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_execute_command_success(self):
        """Test successful command execution."""
        result = self.executor.execute_command("echo 'Hello World'")
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Hello World", result.output)
        self.assertEqual(result.error_output, "")
        self.assertGreater(result.duration, 0)
        
        # Check command was recorded
        commands = self.executor.get_commands_executed()
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0].command, "echo 'Hello World'")
    
    def test_execute_command_failure(self):
        """Test command execution failure."""
        result = self.executor.execute_command("nonexistent_command_xyz")
        
        self.assertNotEqual(result.exit_code, 0)
        self.assertNotEqual(result.error_output, "")
    
    def test_execute_command_timeout(self):
        """Test command timeout handling."""
        result = self.executor.execute_command("sleep 10", timeout=1)
        
        self.assertEqual(result.exit_code, -1)
        self.assertIn("timed out", result.error_output.lower())
    
    def test_create_file(self):
        """Test file creation."""
        content = "Hello, World!"
        success = self.executor.create_file("test.txt", content)
        
        self.assertTrue(success)
        
        # Verify file was created
        file_path = Path(self.temp_dir) / "test.txt"
        self.assertTrue(file_path.exists())
        self.assertEqual(file_path.read_text(), content)
        
        # Check file change was recorded
        changes = self.executor.get_file_changes()
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].change_type, "create")
        self.assertEqual(changes[0].after_content, content)
    
    def test_create_file_with_subdirectory(self):
        """Test file creation in subdirectory."""
        content = "Test content"
        success = self.executor.create_file("subdir/test.txt", content)
        
        self.assertTrue(success)
        
        # Verify file and directory were created
        file_path = Path(self.temp_dir) / "subdir" / "test.txt"
        self.assertTrue(file_path.exists())
        self.assertEqual(file_path.read_text(), content)
    
    def test_modify_file(self):
        """Test file modification."""
        # Create initial file
        initial_content = "Initial content"
        file_path = Path(self.temp_dir) / "test.txt"
        file_path.write_text(initial_content)
        
        # Modify the file
        new_content = "Modified content"
        success = self.executor.modify_file("test.txt", new_content)
        
        self.assertTrue(success)
        self.assertEqual(file_path.read_text(), new_content)
        
        # Check file change was recorded
        changes = self.executor.get_file_changes()
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].change_type, "modify")
        self.assertEqual(changes[0].before_content, initial_content)
        self.assertEqual(changes[0].after_content, new_content)
    
    def test_delete_file(self):
        """Test file deletion."""
        # Create initial file
        content = "Content to delete"
        file_path = Path(self.temp_dir) / "test.txt"
        file_path.write_text(content)
        
        # Delete the file
        success = self.executor.delete_file("test.txt")
        
        self.assertTrue(success)
        self.assertFalse(file_path.exists())
        
        # Check file change was recorded
        changes = self.executor.get_file_changes()
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].change_type, "delete")
        self.assertEqual(changes[0].before_content, content)
        self.assertIsNone(changes[0].after_content)
    
    def test_install_package_pip(self):
        """Test package installation with pip."""
        # Mock the execute_command method to avoid actual installation
        with patch.object(self.executor, 'execute_command') as mock_execute:
            mock_execute.return_value = Mock(exit_code=0)
            
            success = self.executor.install_package("requests", "pip")
            
            self.assertTrue(success)
            mock_execute.assert_called_once_with("pip install requests")
    
    def test_install_package_npm(self):
        """Test package installation with npm."""
        with patch.object(self.executor, 'execute_command') as mock_execute:
            mock_execute.return_value = Mock(exit_code=0)
            
            success = self.executor.install_package("lodash", "npm")
            
            self.assertTrue(success)
            mock_execute.assert_called_once_with("npm install lodash")
    
    def test_install_package_auto_detection(self):
        """Test automatic package manager detection."""
        # Create package.json to trigger npm detection
        package_json = Path(self.temp_dir) / "package.json"
        package_json.write_text('{"name": "test"}')
        
        with patch.object(self.executor, 'execute_command') as mock_execute:
            mock_execute.return_value = Mock(exit_code=0)
            
            success = self.executor.install_package("lodash", "auto")
            
            self.assertTrue(success)
            mock_execute.assert_called_once_with("npm install lodash")
    
    def test_isolation_path_validation(self):
        """Test that paths outside workspace are rejected when isolation is enabled."""
        # Test file creation outside workspace
        success = self.executor.create_file("../outside.txt", "content")
        self.assertFalse(success)  # Should fail, not raise exception
        
        with self.assertRaises(PermissionError):
            self.executor.execute_command("echo test", working_dir="/tmp")
    
    def test_isolation_disabled(self):
        """Test that isolation can be disabled."""
        executor = SandboxCommandExecutor(self.temp_dir, isolation_enabled=False)
        
        # This should not raise an exception when isolation is disabled
        try:
            executor.create_file("../outside.txt", "content")
        except PermissionError:
            self.fail("PermissionError raised when isolation is disabled")


class TestExecutionEngine(unittest.TestCase):
    """Test cases for ExecutionEngine."""
    
    def setUp(self):
        """Set up test environment."""
        self.engine = ExecutionEngine()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_execute_simple_task(self):
        """Test execution of a simple task."""
        task = Task(
            id="test_task_1",
            description="Create a test file",
            status=TaskStatus.NOT_STARTED
        )
        
        sandbox_executor = SandboxCommandExecutor(self.temp_dir)
        result = self.engine.execute_task(task, sandbox_executor)
        
        self.assertTrue(result.success)
        self.assertEqual(result.task_id, "test_task_1")
        self.assertGreater(result.duration, 0)
    
    def test_execute_task_with_subtasks(self):
        """Test execution of a task with subtasks."""
        subtask1 = Subtask(
            id="subtask_1",
            description="Create file subtask",
            status=TaskStatus.NOT_STARTED
        )
        
        subtask2 = Subtask(
            id="subtask_2",
            description="Run command subtask",
            status=TaskStatus.NOT_STARTED
        )
        
        task = Task(
            id="test_task_2",
            description="Task with subtasks",
            status=TaskStatus.NOT_STARTED,
            subtasks=[subtask1, subtask2]
        )
        
        sandbox_executor = SandboxCommandExecutor(self.temp_dir)
        result = self.engine.execute_task(task, sandbox_executor)
        
        self.assertTrue(result.success)
        self.assertEqual(subtask1.status, TaskStatus.COMPLETED)
        self.assertEqual(subtask2.status, TaskStatus.COMPLETED)
    
    def test_execute_plan_sequential(self):
        """Test execution of a task plan with sequential tasks."""
        # Create a simple codebase structure
        structure = CodebaseStructure(
            root_path=self.temp_dir,
            languages=["python"],
            frameworks=[]
        )
        
        dependencies = DependencyGraph()
        metrics = CodeMetrics()
        
        analysis = CodebaseAnalysis(
            structure=structure,
            dependencies=dependencies,
            patterns=[],
            metrics=metrics,
            summary="Test analysis",
            analysis_timestamp=datetime.now()
        )
        
        context = CodebaseContext(analysis=analysis)
        
        task1 = Task(
            id="task_1",
            description="First task",
            status=TaskStatus.NOT_STARTED
        )
        
        task2 = Task(
            id="task_2",
            description="Second task",
            status=TaskStatus.NOT_STARTED,
            dependencies=["task_1"]
        )
        
        plan = TaskPlan(
            id="test_plan",
            description="Test plan",
            tasks=[task1, task2],
            codebase_context=context
        )
        
        result = self.engine.execute_plan(plan)
        
        # Debug output
        if not result.success:
            print(f"Plan execution failed: {result.summary}")
            for task_result in result.task_results:
                if not task_result.success:
                    print(f"Task {task_result.task_id} failed: {task_result.error_info}")
        
        self.assertTrue(result.success)
        self.assertEqual(result.tasks_completed, 2)
        self.assertEqual(result.tasks_failed, 0)
        self.assertEqual(task1.status, TaskStatus.COMPLETED)
        self.assertEqual(task2.status, TaskStatus.COMPLETED)
    
    def test_execute_plan_with_dependency_failure(self):
        """Test execution stops when a dependency fails."""
        structure = CodebaseStructure(
            root_path=self.temp_dir,
            languages=["python"],
            frameworks=[]
        )
        
        dependencies = DependencyGraph()
        metrics = CodeMetrics()
        
        analysis = CodebaseAnalysis(
            structure=structure,
            dependencies=dependencies,
            patterns=[],
            metrics=metrics,
            summary="Test analysis",
            analysis_timestamp=datetime.now()
        )
        
        context = CodebaseContext(analysis=analysis)
        
        # Create a task that will fail
        failing_task = Task(
            id="failing_task",
            description="This task will fail",
            status=TaskStatus.NOT_STARTED
        )
        
        dependent_task = Task(
            id="dependent_task",
            description="This depends on failing task",
            status=TaskStatus.NOT_STARTED,
            dependencies=["failing_task"]
        )
        
        plan = TaskPlan(
            id="test_plan_fail",
            description="Test plan with failure",
            tasks=[failing_task, dependent_task],
            codebase_context=context
        )
        
        # Mock the execute_task method to make the first task fail
        original_execute_task = self.engine.execute_task
        
        def mock_execute_task(task, sandbox_executor):
            if task.id == "failing_task":
                from .models import TaskResult
                return TaskResult(
                    task_id=task.id,
                    success=False,
                    duration=0.1,
                    error_info=ErrorInfo(
                        error_type="TestError",
                        message="Simulated failure"
                    )
                )
            return original_execute_task(task, sandbox_executor)
        
        self.engine.execute_task = mock_execute_task
        
        result = self.engine.execute_plan(plan)
        
        self.assertFalse(result.success)
        self.assertEqual(result.tasks_completed, 0)
        self.assertEqual(result.tasks_failed, 1)
        self.assertEqual(failing_task.status, TaskStatus.ERROR)
        self.assertEqual(dependent_task.status, TaskStatus.NOT_STARTED)
    
    def test_handle_error(self):
        """Test error handling functionality."""
        task = Task(
            id="error_task",
            description="Task that will error",
            status=TaskStatus.NOT_STARTED
        )
        
        error = ValueError("Test error")
        sandbox_executor = SandboxCommandExecutor(self.temp_dir)
        
        retry_context = self.engine.handle_error(task, error, sandbox_executor)
        
        self.assertEqual(retry_context.original_task, task)
        self.assertEqual(retry_context.error_info.error_type, "ValueError")
        self.assertEqual(retry_context.error_info.message, "Test error")
        self.assertTrue(retry_context.can_retry)
        self.assertGreater(len(retry_context.suggested_approaches), 0)
    
    def test_retry_task(self):
        """Test task retry functionality."""
        task = Task(
            id="retry_task",
            description="Task to retry",
            status=TaskStatus.NOT_STARTED
        )
        
        error_info = ErrorInfo(
            error_type="TestError",
            message="Test error for retry"
        )
        
        retry_context = RetryContext(
            original_task=task,
            error_info=error_info
        )
        
        sandbox_executor = SandboxCommandExecutor(self.temp_dir)
        result = self.engine.retry_task(retry_context, sandbox_executor)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.task_id, task.id)
        self.assertEqual(len(retry_context.previous_attempts), 1)
    
    def test_retry_task_max_retries_exceeded(self):
        """Test retry behavior when max retries are exceeded."""
        task = Task(
            id="max_retry_task",
            description="Task that exceeds max retries",
            status=TaskStatus.NOT_STARTED
        )
        
        error_info = ErrorInfo(
            error_type="TestError",
            message="Test error"
        )
        
        retry_context = RetryContext(
            original_task=task,
            error_info=error_info,
            max_retries=2
        )
        
        # Add attempts to exceed max retries
        from .models import AttemptInfo
        retry_context.previous_attempts = [
            AttemptInfo(1, datetime.now(), 1.0, False),
            AttemptInfo(2, datetime.now(), 1.0, False)
        ]
        
        sandbox_executor = SandboxCommandExecutor(self.temp_dir)
        result = self.engine.retry_task(retry_context, sandbox_executor)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error_info.error_type, "MaxRetriesExceeded")
    
    def test_validate_environment(self):
        """Test environment validation."""
        sandbox_executor = SandboxExecutor(workspace_path=self.temp_dir)
        
        is_valid = self.engine.validate_environment(sandbox_executor)
        
        # Should be valid for existing directory
        self.assertTrue(is_valid)
    
    def test_execution_history(self):
        """Test that execution history is maintained."""
        initial_history_length = len(self.engine.get_execution_history())
        
        # Execute a simple plan
        task = Task(
            id="history_task",
            description="Task for history test",
            status=TaskStatus.NOT_STARTED
        )
        
        structure = CodebaseStructure(
            root_path=self.temp_dir,
            languages=["python"],
            frameworks=[]
        )
        
        dependencies = DependencyGraph()
        metrics = CodeMetrics()
        
        analysis = CodebaseAnalysis(
            structure=structure,
            dependencies=dependencies,
            patterns=[],
            metrics=metrics,
            summary="Test analysis",
            analysis_timestamp=datetime.now()
        )
        
        context = CodebaseContext(analysis=analysis)
        
        plan = TaskPlan(
            id="history_plan",
            description="Plan for history test",
            tasks=[task],
            codebase_context=context
        )
        
        self.engine.execute_plan(plan)
        
        # Check that history was updated
        history = self.engine.get_execution_history()
        self.assertEqual(len(history), initial_history_length + 1)
        self.assertEqual(history[-1].plan_id, "history_plan")


if __name__ == '__main__':
    unittest.main()