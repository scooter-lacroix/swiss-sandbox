"""
Unit tests for error handling and recovery system.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime

from ..types import TaskStatus, ErrorInfo
from ..planner.models import Task, Subtask
from .engine import ExecutionEngine, SandboxCommandExecutor, ErrorRecoveryManager
from .models import RetryContext, ErrorRecoveryStrategy, AttemptInfo


class TestErrorRecoveryManager(unittest.TestCase):
    """Test cases for ErrorRecoveryManager."""
    
    def setUp(self):
        """Set up test environment."""
        self.recovery_manager = ErrorRecoveryManager()
    
    def test_default_strategies_initialized(self):
        """Test that default recovery strategies are initialized."""
        permission_strategies = self.recovery_manager.get_strategies_for_error("PermissionError")
        self.assertGreater(len(permission_strategies), 0)
        
        timeout_strategies = self.recovery_manager.get_strategies_for_error("TimeoutError")
        self.assertGreater(len(timeout_strategies), 0)
    
    def test_register_custom_strategy(self):
        """Test registering a custom recovery strategy."""
        custom_strategy = ErrorRecoveryStrategy(
            error_type="CustomError",
            description="Custom error recovery",
            suggested_actions=["Custom action 1", "Custom action 2"],
            success_probability=0.8
        )
        
        self.recovery_manager.register_strategy(custom_strategy)
        
        strategies = self.recovery_manager.get_strategies_for_error("CustomError")
        self.assertEqual(len(strategies), 1)
        self.assertEqual(strategies[0].description, "Custom error recovery")
    
    def test_analyze_permission_error_context(self):
        """Test error context analysis for permission errors."""
        error_info = ErrorInfo(
            error_type="PermissionError",
            message="Permission denied: '/test/file.txt'",
            context={"file_path": "/test/file.txt"}
        )
        
        environment_state = {
            "workspace_path": "/test",
            "workspace_writable": False
        }
        
        context = self.recovery_manager.analyze_error_context(error_info, environment_state)
        
        self.assertIn("error_analysis", context)
        self.assertIn("recovery_suggestions", context)
        self.assertTrue(any("permission" in suggestion.lower() 
                          for suggestion in context["recovery_suggestions"]))
    
    def test_analyze_command_error_context(self):
        """Test error context analysis for command errors."""
        error_info = ErrorInfo(
            error_type="CommandError",
            message="Command 'nonexistent_cmd' not found",
            context={"command": "nonexistent_cmd"}
        )
        
        environment_state = {"workspace_path": "/test"}
        
        context = self.recovery_manager.analyze_error_context(error_info, environment_state)
        
        self.assertIn("recovery_suggestions", context)
        self.assertTrue(any("PATH" in suggestion or "install" in suggestion.lower()
                          for suggestion in context["recovery_suggestions"]))
    
    def test_analyze_timeout_error_context(self):
        """Test error context analysis for timeout errors."""
        error_info = ErrorInfo(
            error_type="TimeoutError",
            message="Operation timed out after 30 seconds",
            context={"timeout": 30}
        )
        
        environment_state = {"workspace_path": "/test"}
        
        context = self.recovery_manager.analyze_error_context(error_info, environment_state)
        
        self.assertIn("recovery_suggestions", context)
        self.assertTrue(any("timeout" in suggestion.lower() or "resource" in suggestion.lower()
                          for suggestion in context["recovery_suggestions"]))


class TestRetryContext(unittest.TestCase):
    """Test cases for RetryContext."""
    
    def setUp(self):
        """Set up test environment."""
        self.task = Task(
            id="test_task",
            description="Test task",
            status=TaskStatus.NOT_STARTED
        )
        
        self.error_info = ErrorInfo(
            error_type="TestError",
            message="Test error message"
        )
        
        self.retry_context = RetryContext(
            original_task=self.task,
            error_info=self.error_info
        )
    
    def test_can_retry_initial(self):
        """Test that retry is initially possible."""
        self.assertTrue(self.retry_context.can_retry)
    
    def test_can_retry_after_max_attempts(self):
        """Test that retry is not possible after max attempts."""
        # Add max attempts
        for i in range(self.retry_context.max_retries):
            attempt = AttemptInfo(
                attempt_number=i + 1,
                timestamp=datetime.now(),
                duration=1.0,
                success=False
            )
            self.retry_context.previous_attempts.append(attempt)
        
        self.assertFalse(self.retry_context.can_retry)
    
    def test_next_delay_calculation(self):
        """Test exponential backoff delay calculation."""
        # Initial delay
        initial_delay = self.retry_context.next_delay
        self.assertEqual(initial_delay, self.retry_context.base_delay)
        
        # Add an attempt and check delay increases
        attempt = AttemptInfo(
            attempt_number=1,
            timestamp=datetime.now(),
            duration=1.0,
            success=False
        )
        self.retry_context.previous_attempts.append(attempt)
        
        second_delay = self.retry_context.next_delay
        expected_delay = self.retry_context.base_delay * self.retry_context.backoff_multiplier
        self.assertEqual(second_delay, expected_delay)
    
    def test_add_recovery_strategy(self):
        """Test adding recovery strategies."""
        strategy = ErrorRecoveryStrategy(
            error_type="TestError",
            description="Test recovery strategy",
            success_probability=0.7
        )
        
        self.retry_context.add_recovery_strategy(strategy)
        
        self.assertEqual(len(self.retry_context.recovery_strategies), 1)
        self.assertEqual(self.retry_context.recovery_strategies[0].description, 
                        "Test recovery strategy")
    
    def test_get_best_recovery_strategy(self):
        """Test getting the best recovery strategy."""
        strategy1 = ErrorRecoveryStrategy(
            error_type="TestError",
            description="Low probability strategy",
            success_probability=0.3
        )
        
        strategy2 = ErrorRecoveryStrategy(
            error_type="TestError",
            description="High probability strategy",
            success_probability=0.8
        )
        
        self.retry_context.add_recovery_strategy(strategy1)
        self.retry_context.add_recovery_strategy(strategy2)
        
        best_strategy = self.retry_context.get_best_recovery_strategy()
        self.assertEqual(best_strategy.description, "High probability strategy")


class TestExecutionEngineErrorHandling(unittest.TestCase):
    """Test cases for ExecutionEngine error handling."""
    
    def setUp(self):
        """Set up test environment."""
        self.engine = ExecutionEngine()
        self.temp_dir = tempfile.mkdtemp()
        self.sandbox_executor = SandboxCommandExecutor(self.temp_dir)
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_handle_error_comprehensive_context(self):
        """Test that error handling captures comprehensive context."""
        task = Task(
            id="error_task",
            description="Task that will error",
            status=TaskStatus.NOT_STARTED
        )
        
        # Create some file changes and command history
        self.sandbox_executor.create_file("test.txt", "content")
        self.sandbox_executor.execute_command("echo 'test'")
        
        error = ValueError("Test error for comprehensive context")
        retry_context = self.engine.handle_error(task, error, self.sandbox_executor)
        
        # Check error info
        self.assertEqual(retry_context.error_info.error_type, "ValueError")
        self.assertEqual(retry_context.error_info.message, "Test error for comprehensive context")
        self.assertIsNotNone(retry_context.error_info.stack_trace)
        
        # Check context includes task and workspace information
        context = retry_context.error_info.context
        self.assertEqual(context["task_id"], "error_task")
        self.assertIn("workspace_path", context)
        self.assertIn("file_changes_count", context)
        self.assertIn("commands_executed_count", context)
        
        # Check environment state
        env_state = retry_context.environment_state
        self.assertIn("workspace_path", env_state)
        self.assertIn("workspace_exists", env_state)
        self.assertIn("workspace_writable", env_state)
        self.assertIn("recent_file_changes", env_state)
        self.assertIn("recent_commands", env_state)
        
        # Check recovery strategies were assigned
        self.assertGreater(len(retry_context.recovery_strategies), 0)
    
    def test_retry_task_with_backoff(self):
        """Test task retry with exponential backoff."""
        task = Task(
            id="retry_task",
            description="Task to retry with backoff",
            status=TaskStatus.NOT_STARTED
        )
        
        error_info = ErrorInfo(
            error_type="TestError",
            message="Test error for retry"
        )
        
        retry_context = RetryContext(
            original_task=task,
            error_info=error_info,
            base_delay=0.1,  # Small delay for testing
            backoff_multiplier=2.0
        )
        
        # Mock time.sleep to avoid actual delays in tests
        with patch('time.sleep') as mock_sleep:
            result = self.engine.retry_task(retry_context, self.sandbox_executor)
            
            # Should have called sleep with base delay
            mock_sleep.assert_called_once_with(0.1)
        
        # Check attempt was recorded
        self.assertEqual(len(retry_context.previous_attempts), 1)
        self.assertEqual(retry_context.previous_attempts[0].attempt_number, 1)
    
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
        retry_context.previous_attempts = [
            AttemptInfo(1, datetime.now(), 1.0, False),
            AttemptInfo(2, datetime.now(), 1.0, False)
        ]
        
        result = self.engine.retry_task(retry_context, self.sandbox_executor)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error_info.error_type, "MaxRetriesExceeded")
        self.assertIn("Maximum number of retries", result.error_info.message)
    
    def test_permission_error_recovery(self):
        """Test recovery from permission errors."""
        task = Task(
            id="permission_task",
            description="Task with permission error",
            status=TaskStatus.NOT_STARTED
        )
        
        # Create a file and make it read-only to simulate permission error
        test_file = Path(self.temp_dir) / "readonly.txt"
        test_file.write_text("content")
        test_file.chmod(0o444)  # Read-only
        
        error = PermissionError("Permission denied")
        retry_context = self.engine.handle_error(task, error, self.sandbox_executor)
        
        # Test that permission recovery is applied
        self.engine._recover_from_permission_error(retry_context, self.sandbox_executor)
        
        # Check that workspace permissions were fixed
        workspace_stat = os.stat(str(self.sandbox_executor.workspace_path))
        self.assertTrue(workspace_stat.st_mode & 0o200)  # Write permission
    
    def test_error_recovery_strategies_applied(self):
        """Test that recovery strategies are applied during retry."""
        task = Task(
            id="strategy_task",
            description="Task with recovery strategy",
            status=TaskStatus.NOT_STARTED
        )
        
        # Create a custom recovery strategy
        recovery_called = False
        
        def custom_recovery(retry_context, sandbox_executor):
            nonlocal recovery_called
            recovery_called = True
        
        strategy = ErrorRecoveryStrategy(
            error_type="TestError",
            description="Custom recovery",
            recovery_function=custom_recovery,
            success_probability=0.9
        )
        
        error_info = ErrorInfo(
            error_type="TestError",
            message="Test error with recovery"
        )
        
        retry_context = RetryContext(
            original_task=task,
            error_info=error_info
        )
        retry_context.add_recovery_strategy(strategy)
        
        # Mock time.sleep to avoid delays
        with patch('time.sleep'):
            self.engine.retry_task(retry_context, self.sandbox_executor)
        
        # Check that recovery function was called
        self.assertTrue(recovery_called)
    
    def test_comprehensive_error_scenarios(self):
        """Test various error scenarios and their handling."""
        scenarios = [
            {
                "error": FileNotFoundError("File not found"),
                "expected_type": "FileNotFoundError"
            },
            {
                "error": TimeoutError("Operation timed out"),
                "expected_type": "TimeoutError"
            },
            {
                "error": ValueError("Invalid value"),
                "expected_type": "ValueError"
            },
            {
                "error": RuntimeError("Runtime error"),
                "expected_type": "RuntimeError"
            }
        ]
        
        for scenario in scenarios:
            with self.subTest(error_type=scenario["expected_type"]):
                task = Task(
                    id=f"task_{scenario['expected_type']}",
                    description=f"Task with {scenario['expected_type']}",
                    status=TaskStatus.NOT_STARTED
                )
                
                retry_context = self.engine.handle_error(
                    task, scenario["error"], self.sandbox_executor
                )
                
                self.assertEqual(retry_context.error_info.error_type, scenario["expected_type"])
                self.assertIsNotNone(retry_context.error_info.stack_trace)
                self.assertGreater(len(retry_context.suggested_approaches), 0)
    
    def test_retry_context_environment_state_capture(self):
        """Test that retry context captures detailed environment state."""
        task = Task(
            id="env_task",
            description="Task for environment state test",
            status=TaskStatus.NOT_STARTED
        )
        
        # Create some environment state
        self.sandbox_executor.create_file("file1.txt", "content1")
        self.sandbox_executor.modify_file("file1.txt", "modified content")
        self.sandbox_executor.execute_command("echo 'command1'")
        self.sandbox_executor.execute_command("echo 'command2'")
        
        error = RuntimeError("Test runtime error")
        retry_context = self.engine.handle_error(task, error, self.sandbox_executor)
        
        env_state = retry_context.environment_state
        
        # Check workspace information
        self.assertIn("workspace_path", env_state)
        self.assertIn("workspace_exists", env_state)
        self.assertIn("workspace_writable", env_state)
        
        # Check recent changes and commands are captured
        self.assertIn("recent_file_changes", env_state)
        self.assertIn("recent_commands", env_state)
        
        # Verify the captured data
        self.assertGreater(len(env_state["recent_file_changes"]), 0)
        self.assertGreater(len(env_state["recent_commands"]), 0)


if __name__ == '__main__':
    unittest.main()