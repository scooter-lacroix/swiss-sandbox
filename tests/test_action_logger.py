"""
Unit tests for the action logging framework.
Tests logging accuracy and completeness for all action types.
"""

import unittest
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sandbox.intelligent.logger.logger import ActionLogger
from sandbox.intelligent.logger.models import LogQuery, LogSummary
from sandbox.intelligent.types import ActionType, FileChange, CommandInfo, ErrorInfo


class TestActionLogger(unittest.TestCase):
    """Test cases for ActionLogger implementation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.logger = ActionLogger()
        self.session_id = "test-session-123"
        self.task_id = "test-task-456"
    
    def test_log_action_basic(self):
        """Test basic action logging functionality."""
        # Test logging a basic action
        action_id = self.logger.log_action(
            action_type=ActionType.TASK_START,
            description="Starting test task",
            details={"test": "data"},
            session_id=self.session_id,
            task_id=self.task_id
        )
        
        # Verify action was logged
        self.assertIsNotNone(action_id)
        self.assertIn(action_id, self.logger._actions_by_id)
        
        # Verify action properties
        action = self.logger._actions_by_id[action_id]
        self.assertEqual(action.action_type, ActionType.TASK_START)
        self.assertEqual(action.description, "Starting test task")
        self.assertEqual(action.details["test"], "data")
        self.assertEqual(action.session_id, self.session_id)
        self.assertEqual(action.task_id, self.task_id)
        self.assertIsInstance(action.timestamp, datetime)
    
    def test_log_action_with_timestamp_tracking(self):
        """Test that actions are logged with accurate timestamps."""
        start_time = datetime.now()
        
        action_id = self.logger.log_action(
            action_type=ActionType.TASK_START,
            description="Test timestamp tracking"
        )
        
        end_time = datetime.now()
        action = self.logger._actions_by_id[action_id]
        
        # Verify timestamp is within expected range
        self.assertGreaterEqual(action.timestamp, start_time)
        self.assertLessEqual(action.timestamp, end_time)
    
    def test_log_file_change_create(self):
        """Test logging file creation with before/after state capture."""
        file_path = "/test/path/new_file.py"
        after_content = "print('Hello, World!')"
        
        action_id = self.logger.log_file_change(
            file_path=file_path,
            change_type="create",
            before_content=None,
            after_content=after_content,
            session_id=self.session_id,
            task_id=self.task_id
        )
        
        # Verify action was logged correctly
        action = self.logger._actions_by_id[action_id]
        self.assertEqual(action.action_type, ActionType.FILE_CREATE)
        self.assertEqual(action.description, f"Create file: {file_path}")
        self.assertEqual(len(action.file_changes), 1)
        
        # Verify file change details
        file_change = action.file_changes[0]
        self.assertEqual(file_change.file_path, file_path)
        self.assertEqual(file_change.change_type, "create")
        self.assertIsNone(file_change.before_content)
        self.assertEqual(file_change.after_content, after_content)
        self.assertIsInstance(file_change.timestamp, datetime)
    
    def test_log_file_change_modify(self):
        """Test logging file modification with before/after state capture."""
        file_path = "/test/path/existing_file.py"
        before_content = "print('Hello')"
        after_content = "print('Hello, World!')"
        
        action_id = self.logger.log_file_change(
            file_path=file_path,
            change_type="modify",
            before_content=before_content,
            after_content=after_content,
            session_id=self.session_id
        )
        
        # Verify action was logged correctly
        action = self.logger._actions_by_id[action_id]
        self.assertEqual(action.action_type, ActionType.FILE_MODIFY)
        self.assertEqual(action.description, f"Modify file: {file_path}")
        
        # Verify file change details
        file_change = action.file_changes[0]
        self.assertEqual(file_change.before_content, before_content)
        self.assertEqual(file_change.after_content, after_content)
    
    def test_log_file_change_delete(self):
        """Test logging file deletion."""
        file_path = "/test/path/deleted_file.py"
        before_content = "print('Goodbye')"
        
        action_id = self.logger.log_file_change(
            file_path=file_path,
            change_type="delete",
            before_content=before_content,
            after_content=None,
            session_id=self.session_id
        )
        
        # Verify action was logged correctly
        action = self.logger._actions_by_id[action_id]
        self.assertEqual(action.action_type, ActionType.FILE_DELETE)
        self.assertEqual(action.description, f"Delete file: {file_path}")
        
        # Verify file change details
        file_change = action.file_changes[0]
        self.assertEqual(file_change.before_content, before_content)
        self.assertIsNone(file_change.after_content)
    
    def test_log_command_execution(self):
        """Test logging command execution with output and exit codes."""
        command = "python test.py"
        working_dir = "/test/workspace"
        output = "Test passed successfully"
        error_output = ""
        exit_code = 0
        duration = 1.5
        
        action_id = self.logger.log_command(
            command=command,
            working_directory=working_dir,
            output=output,
            error_output=error_output,
            exit_code=exit_code,
            duration=duration,
            session_id=self.session_id,
            task_id=self.task_id
        )
        
        # Verify action was logged correctly
        action = self.logger._actions_by_id[action_id]
        self.assertEqual(action.action_type, ActionType.COMMAND_EXECUTE)
        self.assertEqual(action.description, f"Execute command: {command}")
        self.assertIsNotNone(action.command_info)
        
        # Verify command info details
        cmd_info = action.command_info
        self.assertEqual(cmd_info.command, command)
        self.assertEqual(cmd_info.working_directory, working_dir)
        self.assertEqual(cmd_info.output, output)
        self.assertEqual(cmd_info.error_output, error_output)
        self.assertEqual(cmd_info.exit_code, exit_code)
        self.assertEqual(cmd_info.duration, duration)
        self.assertIsInstance(cmd_info.timestamp, datetime)
    
    def test_log_command_with_error(self):
        """Test logging command execution with error output."""
        command = "python broken_test.py"
        error_output = "SyntaxError: invalid syntax"
        exit_code = 1
        
        action_id = self.logger.log_command(
            command=command,
            working_directory="/test",
            output="",
            error_output=error_output,
            exit_code=exit_code,
            duration=0.1,
            session_id=self.session_id
        )
        
        action = self.logger._actions_by_id[action_id]
        self.assertEqual(action.command_info.error_output, error_output)
        self.assertEqual(action.command_info.exit_code, exit_code)
    
    def test_log_error_with_full_context(self):
        """Test logging errors with full context and stack traces."""
        error_type = "ValueError"
        message = "Invalid input parameter"
        stack_trace = "Traceback (most recent call last):\n  File test.py, line 10"
        context = {"function": "test_function", "line": 10}
        
        action_id = self.logger.log_error(
            error_type=error_type,
            message=message,
            stack_trace=stack_trace,
            context=context,
            session_id=self.session_id,
            task_id=self.task_id
        )
        
        # Verify error was logged correctly
        action = self.logger._actions_by_id[action_id]
        self.assertEqual(action.action_type, ActionType.TASK_ERROR)
        self.assertEqual(action.description, f"Error: {message}")
        self.assertIsNotNone(action.error_info)
        
        # Verify error info details
        error_info = action.error_info
        self.assertEqual(error_info.error_type, error_type)
        self.assertEqual(error_info.message, message)
        self.assertEqual(error_info.stack_trace, stack_trace)
        self.assertEqual(error_info.context, context)
        self.assertIsInstance(error_info.timestamp, datetime)
    
    def test_get_actions_with_query_filters(self):
        """Test retrieving actions with various query filters."""
        # Log multiple actions with different properties
        session1 = "session-1"
        session2 = "session-2"
        task1 = "task-1"
        task2 = "task-2"
        
        # Actions for session 1
        self.logger.log_action(ActionType.TASK_START, "Start task 1", session_id=session1, task_id=task1)
        self.logger.log_file_change("/file1.py", "create", session_id=session1, task_id=task1)
        self.logger.log_command("ls", "/", "output", "", 0, 0.1, session_id=session1, task_id=task1)
        
        # Actions for session 2
        self.logger.log_action(ActionType.TASK_START, "Start task 2", session_id=session2, task_id=task2)
        self.logger.log_error("Error", "Test error", session_id=session2, task_id=task2)
        
        # Test filtering by session_id
        query = LogQuery(session_id=session1)
        actions = self.logger.get_actions(query)
        self.assertEqual(len(actions), 3)
        for action in actions:
            self.assertEqual(action.session_id, session1)
        
        # Test filtering by task_id
        query = LogQuery(task_id=task2)
        actions = self.logger.get_actions(query)
        self.assertEqual(len(actions), 2)
        for action in actions:
            self.assertEqual(action.task_id, task2)
        
        # Test filtering by action types
        query = LogQuery(action_types=[ActionType.FILE_CREATE, ActionType.COMMAND_EXECUTE])
        actions = self.logger.get_actions(query)
        self.assertEqual(len(actions), 2)
        action_types = [a.action_type for a in actions]
        self.assertIn(ActionType.FILE_CREATE, action_types)
        self.assertIn(ActionType.COMMAND_EXECUTE, action_types)
    
    def test_get_actions_with_time_range(self):
        """Test retrieving actions within a specific time range."""
        start_time = datetime.now()
        
        # Log an action
        action_id1 = self.logger.log_action(ActionType.TASK_START, "Early action")
        
        # Wait a bit and log another action
        import time
        time.sleep(0.01)
        middle_time = datetime.now()
        time.sleep(0.01)
        
        action_id2 = self.logger.log_action(ActionType.TASK_COMPLETE, "Late action")
        end_time = datetime.now()
        
        # Test filtering by start time
        query = LogQuery(start_time=middle_time)
        actions = self.logger.get_actions(query)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].id, action_id2)
        
        # Test filtering by end time
        query = LogQuery(end_time=middle_time)
        actions = self.logger.get_actions(query)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].id, action_id1)
        
        # Test filtering by time range
        query = LogQuery(start_time=start_time, end_time=end_time)
        actions = self.logger.get_actions(query)
        self.assertEqual(len(actions), 2)
    
    def test_get_actions_with_limit_and_offset(self):
        """Test pagination with limit and offset."""
        # Log multiple actions
        for i in range(10):
            self.logger.log_action(ActionType.TASK_START, f"Action {i}")
        
        # Test limit
        query = LogQuery(limit=5)
        actions = self.logger.get_actions(query)
        self.assertEqual(len(actions), 5)
        
        # Test offset
        query = LogQuery(offset=3, limit=3)
        actions = self.logger.get_actions(query)
        self.assertEqual(len(actions), 3)
        
        # Verify actions are sorted by timestamp
        timestamps = [a.timestamp for a in actions]
        self.assertEqual(timestamps, sorted(timestamps))
    
    def test_get_execution_history(self):
        """Test retrieving complete execution history for a session."""
        session_id = "test-session"
        
        # Log various actions for the session
        self.logger.log_action(ActionType.WORKSPACE_CREATE, "Create workspace", session_id=session_id)
        self.logger.log_action(ActionType.TASK_START, "Start task", session_id=session_id)
        self.logger.log_file_change("/file.py", "create", session_id=session_id)
        self.logger.log_command("python file.py", "/", "output", "", 0, 1.0, session_id=session_id)
        self.logger.log_action(ActionType.TASK_COMPLETE, "Complete task", session_id=session_id)
        
        # Log actions for different session (should not be included)
        self.logger.log_action(ActionType.TASK_START, "Other session", session_id="other-session")
        
        # Get execution history
        history = self.logger.get_execution_history(session_id)
        
        # Verify all actions for the session are included
        self.assertEqual(len(history), 5)
        for action in history:
            self.assertEqual(action.session_id, session_id)
        
        # Verify actions are sorted by timestamp
        timestamps = [a.timestamp for a in history]
        self.assertEqual(timestamps, sorted(timestamps))
    
    def test_get_log_summary(self):
        """Test generating log summaries with statistics."""
        session_id = "summary-test-session"
        
        # Log various types of actions
        self.logger.log_action(ActionType.TASK_START, "Start", session_id=session_id)
        self.logger.log_file_change("/file1.py", "create", session_id=session_id)
        self.logger.log_file_change("/file2.py", "modify", session_id=session_id)
        self.logger.log_command("ls", "/", "output", "", 0, 0.1, session_id=session_id)
        self.logger.log_command("pwd", "/", "output", "", 0, 0.1, session_id=session_id)
        self.logger.log_error("Error", "Test error", session_id=session_id)
        self.logger.log_action(ActionType.TASK_COMPLETE, "Complete", session_id=session_id)
        
        # Get summary
        summary = self.logger.get_log_summary(session_id=session_id)
        
        # Verify summary statistics
        self.assertEqual(summary.total_actions, 7)
        self.assertEqual(summary.files_modified, 2)  # 2 file changes
        self.assertEqual(summary.commands_executed, 2)  # 2 commands
        self.assertEqual(summary.errors_encountered, 1)  # 1 error
        
        # Verify action type counts
        self.assertEqual(summary.actions_by_type[ActionType.TASK_START], 1)
        self.assertEqual(summary.actions_by_type[ActionType.FILE_CREATE], 1)
        self.assertEqual(summary.actions_by_type[ActionType.FILE_MODIFY], 1)
        self.assertEqual(summary.actions_by_type[ActionType.COMMAND_EXECUTE], 2)
        self.assertEqual(summary.actions_by_type[ActionType.TASK_ERROR], 1)
        self.assertEqual(summary.actions_by_type[ActionType.TASK_COMPLETE], 1)
        
        # Verify time range is set
        self.assertIsNotNone(summary.time_range)
        self.assertIsInstance(summary.time_range[0], datetime)
        self.assertIsInstance(summary.time_range[1], datetime)
    
    def test_export_logs_json_format(self):
        """Test exporting logs in JSON format."""
        # Log some test actions
        self.logger.log_action(ActionType.TASK_START, "Test action", session_id="test")
        self.logger.log_file_change("/test.py", "create", after_content="test", session_id="test")
        self.logger.log_command("echo test", "/", "test", "", 0, 0.1, session_id="test")
        self.logger.log_error("TestError", "Test error message", session_id="test")
        
        # Export logs
        query = LogQuery(session_id="test")
        exported_data = self.logger.export_logs(query, format="json")
        
        # Verify export format
        self.assertIsInstance(exported_data, str)
        
        # Parse JSON and verify structure
        actions_data = json.loads(exported_data)
        self.assertIsInstance(actions_data, list)
        self.assertEqual(len(actions_data), 4)
        
        # Verify action structure
        action = actions_data[0]
        required_fields = ["id", "timestamp", "action_type", "description", "session_id"]
        for field in required_fields:
            self.assertIn(field, action)
        
        # Verify file change action has file_changes
        file_action = next(a for a in actions_data if a["action_type"] == "file_create")
        self.assertIn("file_changes", file_action)
        self.assertEqual(len(file_action["file_changes"]), 1)
        
        # Verify command action has command_info
        cmd_action = next(a for a in actions_data if a["action_type"] == "command_execute")
        self.assertIn("command_info", cmd_action)
        
        # Verify error action has error_info
        error_action = next(a for a in actions_data if a["action_type"] == "task_error")
        self.assertIn("error_info", error_action)
    
    def test_export_logs_unsupported_format(self):
        """Test that unsupported export formats raise appropriate errors."""
        query = LogQuery()
        
        with self.assertRaises(ValueError) as context:
            self.logger.export_logs(query, format="xml")
        
        self.assertIn("Unsupported export format", str(context.exception))
    
    def test_clear_logs_by_session(self):
        """Test clearing logs for a specific session."""
        session1 = "session-1"
        session2 = "session-2"
        
        # Log actions for both sessions
        self.logger.log_action(ActionType.TASK_START, "Session 1 action", session_id=session1)
        self.logger.log_action(ActionType.TASK_START, "Session 2 action", session_id=session2)
        self.logger.log_action(ActionType.TASK_COMPLETE, "Another session 1 action", session_id=session1)
        
        # Verify initial state
        self.assertEqual(len(self.logger._actions), 3)
        
        # Clear logs for session 1
        cleared_count = self.logger.clear_logs(session_id=session1)
        
        # Verify results
        self.assertEqual(cleared_count, 2)
        self.assertEqual(len(self.logger._actions), 1)
        
        # Verify remaining action is from session 2
        remaining_action = self.logger._actions[0]
        self.assertEqual(remaining_action.session_id, session2)
    
    def test_clear_logs_by_date(self):
        """Test clearing logs before a specific date."""
        # Log an action
        old_action_id = self.logger.log_action(ActionType.TASK_START, "Old action")
        
        # Get the timestamp and add a small delay
        import time
        time.sleep(0.01)
        cutoff_time = datetime.now()
        time.sleep(0.01)
        
        # Log another action
        new_action_id = self.logger.log_action(ActionType.TASK_COMPLETE, "New action")
        
        # Clear logs before cutoff time
        cleared_count = self.logger.clear_logs(before_date=cutoff_time.isoformat())
        
        # Verify results
        self.assertEqual(cleared_count, 1)
        self.assertEqual(len(self.logger._actions), 1)
        
        # Verify remaining action is the new one
        remaining_action = self.logger._actions[0]
        self.assertEqual(remaining_action.id, new_action_id)
    
    def test_logging_accuracy_and_completeness(self):
        """Test comprehensive logging accuracy and completeness."""
        # This test verifies that all logged information is accurate and complete
        
        # Test file change logging completeness
        file_path = "/complete/test/file.py"
        before_content = "original content"
        after_content = "modified content"
        
        action_id = self.logger.log_file_change(
            file_path=file_path,
            change_type="modify",
            before_content=before_content,
            after_content=after_content,
            session_id=self.session_id,
            task_id=self.task_id
        )
        
        action = self.logger._actions_by_id[action_id]
        
        # Verify all required information is captured
        self.assertIsNotNone(action.id)
        self.assertIsNotNone(action.timestamp)
        self.assertEqual(action.action_type, ActionType.FILE_MODIFY)
        self.assertIsNotNone(action.description)
        self.assertEqual(action.session_id, self.session_id)
        self.assertEqual(action.task_id, self.task_id)
        
        # Verify file change details are complete
        file_change = action.file_changes[0]
        self.assertEqual(file_change.file_path, file_path)
        self.assertEqual(file_change.change_type, "modify")
        self.assertEqual(file_change.before_content, before_content)
        self.assertEqual(file_change.after_content, after_content)
        self.assertIsNotNone(file_change.timestamp)
        
        # Test command logging completeness
        command = "python -m pytest tests/"
        working_dir = "/test/workspace"
        output = "All tests passed"
        error_output = "Warning: deprecated feature"
        exit_code = 0
        duration = 2.5
        
        cmd_action_id = self.logger.log_command(
            command=command,
            working_directory=working_dir,
            output=output,
            error_output=error_output,
            exit_code=exit_code,
            duration=duration,
            session_id=self.session_id,
            task_id=self.task_id
        )
        
        cmd_action = self.logger._actions_by_id[cmd_action_id]
        cmd_info = cmd_action.command_info
        
        # Verify all command information is captured
        self.assertEqual(cmd_info.command, command)
        self.assertEqual(cmd_info.working_directory, working_dir)
        self.assertEqual(cmd_info.output, output)
        self.assertEqual(cmd_info.error_output, error_output)
        self.assertEqual(cmd_info.exit_code, exit_code)
        self.assertEqual(cmd_info.duration, duration)
        self.assertIsNotNone(cmd_info.timestamp)
        
        # Test error logging completeness
        error_type = "RuntimeError"
        message = "Critical system error"
        stack_trace = "Full stack trace here..."
        context = {"module": "test_module", "function": "test_function", "variables": {"x": 42}}
        
        error_action_id = self.logger.log_error(
            error_type=error_type,
            message=message,
            stack_trace=stack_trace,
            context=context,
            session_id=self.session_id,
            task_id=self.task_id
        )
        
        error_action = self.logger._actions_by_id[error_action_id]
        error_info = error_action.error_info
        
        # Verify all error information is captured
        self.assertEqual(error_info.error_type, error_type)
        self.assertEqual(error_info.message, message)
        self.assertEqual(error_info.stack_trace, stack_trace)
        self.assertEqual(error_info.context, context)
        self.assertIsNotNone(error_info.timestamp)


if __name__ == '__main__':
    unittest.main()