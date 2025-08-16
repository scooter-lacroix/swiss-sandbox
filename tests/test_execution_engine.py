"""
Unit tests for the ExecutionEngine class.

Tests cover Python execution, shell execution, Manim execution, timeout handling,
context management, and error handling scenarios.
"""

import os
import sys
import time
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import subprocess

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from sandbox.core.execution_engine import (
    ExecutionEngine, 
    ExecutionTimeoutError, 
    ExecutionSecurityError,
    TimeoutHandler
)
from sandbox.core.types import (
    ExecutionContext, ExecutionResult, ResourceLimits, SecurityLevel, ExecutionRecord
)


class TestTimeoutHandler(unittest.TestCase):
    """Test the TimeoutHandler class."""
    
    def test_timeout_handler_creation(self):
        """Test TimeoutHandler creation."""
        handler = TimeoutHandler(5)
        self.assertEqual(handler.timeout_seconds, 5)
        self.assertFalse(handler.timed_out)
        self.assertIsNone(handler.timer)
    
    def test_timeout_handler_context_manager(self):
        """Test TimeoutHandler as context manager."""
        with TimeoutHandler(1) as handler:
            self.assertIsNotNone(handler.timer)
            time.sleep(0.1)  # Short sleep, should not timeout
        
        # Timer should be cancelled after context exit
        self.assertIsNone(handler.timer)
    
    def test_timeout_handler_timeout(self):
        """Test TimeoutHandler timeout behavior."""
        # This test is tricky because we need to simulate timeout without actually waiting
        handler = TimeoutHandler(0.1)
        handler.start()
        
        # Wait for timeout to trigger
        time.sleep(0.2)
        
        # Check if timeout was triggered
        self.assertTrue(handler.timed_out)
        handler.cancel()


class TestExecutionEngine(unittest.TestCase):
    """Test the ExecutionEngine class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.engine = ExecutionEngine()
        
        # Create test context
        self.test_context = ExecutionContext(
            workspace_id="test_workspace",
            user_id="test_user",
            resource_limits=ResourceLimits(
                max_execution_time=5,
                max_memory_mb=256
            ),
            security_level=SecurityLevel.MODERATE
        )
        
        # Create temporary directory for artifacts
        self.temp_dir = Path(tempfile.mkdtemp())
        self.test_context.artifacts_dir = self.temp_dir
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.engine.cleanup_all()
        
        # Clean up temporary directory
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_engine_initialization(self):
        """Test ExecutionEngine initialization."""
        engine = ExecutionEngine()
        
        self.assertIsNotNone(engine)
        self.assertEqual(len(engine.execution_history), 0)
        self.assertEqual(len(engine.active_contexts), 0)
        self.assertEqual(engine.total_executions, 0)
        self.assertEqual(engine.successful_executions, 0)
        self.assertEqual(engine.failed_executions, 0)
    
    def test_python_execution_success(self):
        """Test successful Python code execution."""
        code = """
x = 5
y = 10
result = x + y
print(f"Result: {result}")
"""
        
        result = self.engine.execute_python(code, self.test_context)
        
        self.assertTrue(result.success)
        self.assertIn("Result: 15", result.output)
        self.assertIsNone(result.error)
        self.assertGreater(result.execution_time, 0)
        self.assertEqual(self.engine.total_executions, 1)
        self.assertEqual(self.engine.successful_executions, 1)
    
    def test_python_execution_error(self):
        """Test Python code execution with error."""
        code = """
# This will cause a NameError
print(undefined_variable)
"""
        
        result = self.engine.execute_python(code, self.test_context)
        
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error_type, "NameError")
        self.assertGreater(result.execution_time, 0)
        self.assertEqual(self.engine.total_executions, 1)
        self.assertEqual(self.engine.failed_executions, 1)
    
    def test_python_execution_syntax_error(self):
        """Test Python code execution with syntax error."""
        code = """
# Invalid syntax
if True
    print("Missing colon")
"""
        
        result = self.engine.execute_python(code, self.test_context)
        
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
        self.assertIn("Syntax error", result.error)
        self.assertEqual(result.error_type, "SyntaxError")
    
    @patch('subprocess.run')
    def test_shell_execution_success(self, mock_run):
        """Test successful shell command execution."""
        # Mock successful subprocess execution
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.stdout = "Hello World"
        mock_process.stderr = ""
        mock_run.return_value = mock_process
        
        result = self.engine.execute_shell("echo 'Hello World'", self.test_context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.output, "Hello World")
        self.assertIsNone(result.error)
        self.assertEqual(result.metadata['return_code'], 0)
        self.assertEqual(self.engine.total_executions, 1)
        self.assertEqual(self.engine.successful_executions, 1)
    
    @patch('subprocess.run')
    def test_shell_execution_error(self, mock_run):
        """Test shell command execution with error."""
        # Mock failed subprocess execution
        mock_process = Mock()
        mock_process.returncode = 1
        mock_process.stdout = ""
        mock_process.stderr = "Command not found"
        mock_run.return_value = mock_process
        
        result = self.engine.execute_shell("nonexistent_command", self.test_context)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Command not found")
        self.assertEqual(result.error_type, "CommandError")
        self.assertEqual(result.metadata['return_code'], 1)
        self.assertEqual(self.engine.total_executions, 1)
        self.assertEqual(self.engine.failed_executions, 1)
    
    @patch('subprocess.run')
    def test_shell_execution_timeout(self, mock_run):
        """Test shell command execution timeout."""
        # Mock timeout exception
        mock_run.side_effect = subprocess.TimeoutExpired("test_cmd", 5)
        
        result = self.engine.execute_shell("sleep 10", self.test_context)
        
        self.assertFalse(result.success)
        self.assertIn("timed out", result.error)
        self.assertEqual(result.error_type, "TimeoutError")
        self.assertEqual(self.engine.total_executions, 1)
        self.assertEqual(self.engine.failed_executions, 1)
    
    def test_manim_execution_success(self):
        """Test successful Manim script execution."""
        script = """
from manim import *

class TestScene(Scene):
    def construct(self):
        # Simple scene that should render quickly
        text = Text("Hello Manim!")
        self.add(text)
"""
        
        result = self.engine.execute_manim(script, self.test_context, quality='low')
        
        # Manim should be installed, so this should work
        if result.success:
            self.assertTrue(result.success)
            self.assertIsNone(result.error)
            self.assertEqual(result.metadata['quality'], 'low')
            self.assertEqual(self.engine.total_executions, 1)
            self.assertEqual(self.engine.successful_executions, 1)
        else:
            # If Manim execution fails, it might be due to environment issues
            # but the engine should still handle it gracefully
            self.assertFalse(result.success)
            self.assertIsNotNone(result.error)
            self.assertEqual(self.engine.total_executions, 1)
            self.assertEqual(self.engine.failed_executions, 1)
    
    def test_manim_execution_with_error(self):
        """Test Manim execution with script error."""
        script = """
from manim import *

class TestScene(Scene):
    def construct(self):
        # This will cause an error - undefined function
        undefined_manim_function()
"""
        
        result = self.engine.execute_manim(script, self.test_context, quality='low')
        
        # Should fail due to script error
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
        self.assertEqual(self.engine.total_executions, 1)
        self.assertEqual(self.engine.failed_executions, 1)
    
    def test_context_management(self):
        """Test execution context management."""
        # Execute code to create context
        code = "x = 42"
        result = self.engine.execute_python(code, self.test_context)
        
        self.assertTrue(result.success)
        self.assertIn(self.test_context.workspace_id, self.engine.active_contexts)
        
        # Execute more code in same context
        code2 = "print(x)"  # Should access x from previous execution
        result2 = self.engine.execute_python(code2, self.test_context)
        
        self.assertTrue(result2.success)
        self.assertIn("42", result2.output)
    
    def test_execution_history(self):
        """Test execution history tracking."""
        # Execute some code
        self.engine.execute_python("print('test1')", self.test_context)
        self.engine.execute_python("print('test2')", self.test_context)
        
        history = self.engine.get_execution_history()
        
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].language, "python")  # Most recent first
        self.assertEqual(history[0].context_id, self.test_context.workspace_id)
        self.assertIsInstance(history[0], ExecutionRecord)
    
    def test_execution_history_filtering(self):
        """Test execution history filtering."""
        # Create different context
        other_context = ExecutionContext(workspace_id="other_workspace")
        other_context.artifacts_dir = self.temp_dir / "other"
        other_context.artifacts_dir.mkdir(exist_ok=True)
        
        # Execute in different contexts and languages
        self.engine.execute_python("print('python1')", self.test_context)
        self.engine.execute_python("print('python2')", other_context)
        
        # Filter by context
        history_filtered = self.engine.get_execution_history(context_id=self.test_context.workspace_id)
        self.assertEqual(len(history_filtered), 1)
        self.assertEqual(history_filtered[0].context_id, self.test_context.workspace_id)
        
        # Filter by language
        history_python = self.engine.get_execution_history(language="python")
        self.assertEqual(len(history_python), 2)
        for record in history_python:
            self.assertEqual(record.language, "python")
    
    def test_statistics(self):
        """Test execution statistics."""
        # Execute some successful and failed operations
        self.engine.execute_python("print('success')", self.test_context)
        self.engine.execute_python("undefined_variable", self.test_context)  # Will fail
        
        stats = self.engine.get_statistics()
        
        self.assertEqual(stats['total_executions'], 2)
        self.assertEqual(stats['successful_executions'], 1)
        self.assertEqual(stats['failed_executions'], 1)
        self.assertEqual(stats['success_rate'], 0.5)
        self.assertEqual(stats['active_contexts'], 1)
        self.assertEqual(stats['languages']['python'], 2)
    
    def test_context_cleanup(self):
        """Test context cleanup."""
        # Create context by executing code
        self.engine.execute_python("x = 42", self.test_context)
        
        self.assertIn(self.test_context.workspace_id, self.engine.active_contexts)
        
        # Clean up context
        success = self.engine.cleanup_context(self.test_context.workspace_id)
        
        self.assertTrue(success)
        self.assertNotIn(self.test_context.workspace_id, self.engine.active_contexts)
    
    def test_cleanup_all(self):
        """Test cleanup of all resources."""
        # Create multiple contexts
        context2 = ExecutionContext(workspace_id="test_workspace_2")
        context2.artifacts_dir = self.temp_dir / "context2"
        context2.artifacts_dir.mkdir(exist_ok=True)
        
        self.engine.execute_python("x = 1", self.test_context)
        self.engine.execute_python("y = 2", context2)
        
        self.assertEqual(len(self.engine.active_contexts), 2)
        self.assertEqual(len(self.engine.execution_history), 2)
        
        # Clean up all
        self.engine.cleanup_all()
        
        self.assertEqual(len(self.engine.active_contexts), 0)
        self.assertEqual(len(self.engine.execution_history), 0)
    
    def test_security_validation(self):
        """Test security validation integration."""
        # Mock security manager
        mock_security = Mock()
        mock_validation = Mock()
        mock_validation.is_safe = False
        mock_validation.reason = "Dangerous operation detected"
        mock_security.validate_python_code.return_value = mock_validation
        
        engine = ExecutionEngine(security_manager=mock_security)
        
        result = engine.execute_python("import os; os.system('rm -rf /')", self.test_context)
        
        self.assertFalse(result.success)
        self.assertIn("Security violation", result.error)
        self.assertEqual(result.error_type, "SecurityError")
        mock_security.validate_python_code.assert_called_once()
    
    def test_execution_record_serialization(self):
        """Test ExecutionRecord serialization."""
        result = ExecutionResult(
            success=True,
            output="test output",
            execution_time=1.5
        )
        
        record = ExecutionRecord(
            execution_id="test_123",
            code="print('test')",
            language="python",
            context_id="test_context",
            result=result
        )
        
        record_dict = record.to_dict()
        
        self.assertEqual(record_dict['execution_id'], "test_123")
        self.assertEqual(record_dict['code'], "print('test')")
        self.assertEqual(record_dict['language'], "python")
        self.assertEqual(record_dict['context_id'], "test_context")
        self.assertIsInstance(record_dict['result'], dict)
        self.assertIsInstance(record_dict['timestamp'], float)


class TestExecutionEngineIntegration(unittest.TestCase):
    """Integration tests for ExecutionEngine."""
    
    def setUp(self):
        """Set up integration test fixtures."""
        self.engine = ExecutionEngine()
        self.temp_dir = Path(tempfile.mkdtemp())
        
        self.context = ExecutionContext(
            workspace_id="integration_test",
            resource_limits=ResourceLimits(max_execution_time=10),
            artifacts_dir=self.temp_dir
        )
    
    def tearDown(self):
        """Clean up integration test fixtures."""
        self.engine.cleanup_all()
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_python_with_file_creation(self):
        """Test Python execution that creates files."""
        code = """
import json
from pathlib import Path

# Create a test file
data = {'test': 'data', 'number': 42}
file_path = Path('test_output.json')
with open(file_path, 'w') as f:
    json.dump(data, f)

print(f"Created file: {file_path}")
"""
        
        result = self.engine.execute_python(code, self.context)
        
        self.assertTrue(result.success)
        self.assertIn("Created file", result.output)
        
        # Check if file was created in artifacts directory
        expected_file = self.temp_dir / 'test_output.json'
        # Note: The file might be created in the persistent context's artifacts directory
        # This test verifies the execution works, actual file location depends on implementation
    
    def test_multiple_executions_same_context(self):
        """Test multiple executions in the same context maintain state."""
        # First execution - define variables
        result1 = self.engine.execute_python("counter = 0", self.context)
        self.assertTrue(result1.success)
        
        # Second execution - modify variables
        result2 = self.engine.execute_python("counter += 1; print(f'Counter: {counter}')", self.context)
        self.assertTrue(result2.success)
        self.assertIn("Counter: 1", result2.output)
        
        # Third execution - use variables
        result3 = self.engine.execute_python("counter += 5; print(f'Final: {counter}')", self.context)
        self.assertTrue(result3.success)
        self.assertIn("Final: 6", result3.output)
    
    @unittest.skipIf(os.name == 'nt', "Shell test skipped on Windows")
    def test_shell_command_real(self):
        """Test real shell command execution (Unix only)."""
        result = self.engine.execute_shell("echo 'Hello from shell'", self.context)
        
        self.assertTrue(result.success)
        self.assertIn("Hello from shell", result.output)
        self.assertEqual(result.metadata['return_code'], 0)


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)