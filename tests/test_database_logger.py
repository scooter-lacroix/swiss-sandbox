"""
Unit tests for the database action logger.
Tests database storage and retrieval functionality.
"""

import unittest
import tempfile
import os
import json
from datetime import datetime, timedelta

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sandbox.intelligent.logger.database import DatabaseActionLogger
from sandbox.intelligent.logger.models import LogQuery, LogSummary
from sandbox.intelligent.types import ActionType, FileChange, CommandInfo, ErrorInfo


class TestDatabaseActionLogger(unittest.TestCase):
    """Test cases for DatabaseActionLogger implementation."""
    
    def setUp(self):
        """Set up test fixtures with temporary database."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.logger = DatabaseActionLogger(self.temp_db.name)
        self.session_id = "test-session-123"
        self.task_id = "test-task-456"
        
    def tearDown(self):
        """Clean up temporary database."""
        try:
            os.unlink(self.temp_db.name)
        except OSError:
            pass
    
    def test_database_initialization(self):
        """Test that database is properly initialized with tables and indexes."""
        stats = self.logger.get_database_stats()
        
        # Verify all tables exist (they should have 0 rows initially)
        self.assertEqual(stats['actions_count'], 0)
        self.assertEqual(stats['file_changes_count'], 0)
        self.assertEqual(stats['command_info_count'], 0)
        self.assertEqual(stats['error_info_count'], 0)
        
        # Verify indexes are created
        self.assertGreater(stats['indexes_count'], 0)
    
    def test_log_action_database_storage(self):
        """Test that actions are properly stored in database."""
        action_id = self.logger.log_action(
            action_type=ActionType.TASK_START,
            description="Database test action",
            details={"test": "data", "number": 42},
            session_id=self.session_id,
            task_id=self.task_id
        )
        
        # Verify action was stored
        query = LogQuery(session_id=self.session_id)
        actions = self.logger.get_actions(query)
        
        self.assertEqual(len(actions), 1)
        action = actions[0]
        
        self.assertEqual(action.id, action_id)
        self.assertEqual(action.action_type, ActionType.TASK_START)
        self.assertEqual(action.description, "Database test action")
        self.assertEqual(action.details["test"], "data")
        self.assertEqual(action.details["number"], 42)
        self.assertEqual(action.session_id, self.session_id)
        self.assertEqual(action.task_id, self.task_id)
    
    def test_log_file_change_database_storage(self):
        """Test that file changes are properly stored with relationships."""
        file_path = "/test/database_file.py"
        before_content = "old content"
        after_content = "new content"
        
        action_id = self.logger.log_file_change(
            file_path=file_path,
            change_type="modify",
            before_content=before_content,
            after_content=after_content,
            session_id=self.session_id,
            task_id=self.task_id
        )
        
        # Verify action and file change were stored
        query = LogQuery(session_id=self.session_id)
        actions = self.logger.get_actions(query)
        
        self.assertEqual(len(actions), 1)
        action = actions[0]
        
        self.assertEqual(action.action_type, ActionType.FILE_MODIFY)
        self.assertEqual(len(action.file_changes), 1)
        
        file_change = action.file_changes[0]
        self.assertEqual(file_change.file_path, file_path)
        self.assertEqual(file_change.change_type, "modify")
        self.assertEqual(file_change.before_content, before_content)
        self.assertEqual(file_change.after_content, after_content)
    
    def test_log_command_database_storage(self):
        """Test that command executions are properly stored with relationships."""
        command = "python test_db.py"
        working_dir = "/test/workspace"
        output = "Database test passed"
        error_output = "Warning: test mode"
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
        
        # Verify action and command info were stored
        query = LogQuery(session_id=self.session_id)
        actions = self.logger.get_actions(query)
        
        self.assertEqual(len(actions), 1)
        action = actions[0]
        
        self.assertEqual(action.action_type, ActionType.COMMAND_EXECUTE)
        self.assertIsNotNone(action.command_info)
        
        cmd_info = action.command_info
        self.assertEqual(cmd_info.command, command)
        self.assertEqual(cmd_info.working_directory, working_dir)
        self.assertEqual(cmd_info.output, output)
        self.assertEqual(cmd_info.error_output, error_output)
        self.assertEqual(cmd_info.exit_code, exit_code)
        self.assertEqual(cmd_info.duration, duration)
    
    def test_log_error_database_storage(self):
        """Test that errors are properly stored with relationships."""
        error_type = "DatabaseError"
        message = "Connection failed"
        stack_trace = "Traceback: database connection error"
        context = {"host": "localhost", "port": 5432}
        
        action_id = self.logger.log_error(
            error_type=error_type,
            message=message,
            stack_trace=stack_trace,
            context=context,
            session_id=self.session_id,
            task_id=self.task_id
        )
        
        # Verify action and error info were stored
        query = LogQuery(session_id=self.session_id)
        actions = self.logger.get_actions(query)
        
        self.assertEqual(len(actions), 1)
        action = actions[0]
        
        self.assertEqual(action.action_type, ActionType.TASK_ERROR)
        self.assertIsNotNone(action.error_info)
        
        error_info = action.error_info
        self.assertEqual(error_info.error_type, error_type)
        self.assertEqual(error_info.message, message)
        self.assertEqual(error_info.stack_trace, stack_trace)
        self.assertEqual(error_info.context, context)
    
    def test_database_query_filtering(self):
        """Test database query filtering with various criteria."""
        # Insert test data
        sessions = ["session_1", "session_2", "session_3"]
        tasks = ["task_a", "task_b"]
        
        for i, session in enumerate(sessions):
            for j, task in enumerate(tasks):
                self.logger.log_action(
                    action_type=ActionType.TASK_START,
                    description=f"Action {i}-{j}",
                    session_id=session,
                    task_id=task
                )
        
        # Test session filtering
        query = LogQuery(session_id="session_2")
        actions = self.logger.get_actions(query)
        self.assertEqual(len(actions), 2)  # 2 tasks per session
        for action in actions:
            self.assertEqual(action.session_id, "session_2")
        
        # Test task filtering
        query = LogQuery(task_id="task_a")
        actions = self.logger.get_actions(query)
        self.assertEqual(len(actions), 3)  # 3 sessions per task
        for action in actions:
            self.assertEqual(action.task_id, "task_a")
        
        # Test combined filtering
        query = LogQuery(session_id="session_1", task_id="task_b")
        actions = self.logger.get_actions(query)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].session_id, "session_1")
        self.assertEqual(actions[0].task_id, "task_b")
    
    def test_database_pagination(self):
        """Test database query pagination with limit and offset."""
        # Insert test data
        num_actions = 20
        for i in range(num_actions):
            self.logger.log_action(
                action_type=ActionType.TASK_START,
                description=f"Pagination test {i}",
                session_id="pagination_test"
            )
        
        # Test limit
        query = LogQuery(session_id="pagination_test", limit=5)
        actions = self.logger.get_actions(query)
        self.assertEqual(len(actions), 5)
        
        # Test offset
        query = LogQuery(session_id="pagination_test", offset=10, limit=5)
        actions = self.logger.get_actions(query)
        self.assertEqual(len(actions), 5)
        
        # Test that results are ordered by timestamp
        query = LogQuery(session_id="pagination_test")
        all_actions = self.logger.get_actions(query)
        timestamps = [a.timestamp for a in all_actions]
        self.assertEqual(timestamps, sorted(timestamps))
    
    def test_database_summary_aggregation(self):
        """Test database summary generation with proper aggregation."""
        session_id = "summary_test"
        
        # Insert diverse test data
        self.logger.log_action(ActionType.TASK_START, "Start", session_id=session_id)
        self.logger.log_file_change("/file1.py", "create", session_id=session_id)
        self.logger.log_file_change("/file2.py", "modify", session_id=session_id)
        self.logger.log_command("ls", "/", "output", "", 0, 0.1, session_id=session_id)
        self.logger.log_command("pwd", "/", "output", "", 0, 0.1, session_id=session_id)
        self.logger.log_error("TestError", "Test error", session_id=session_id)
        self.logger.log_action(ActionType.TASK_COMPLETE, "Complete", session_id=session_id)
        
        # Generate summary
        summary = self.logger.get_log_summary(session_id=session_id)
        
        # Verify aggregated statistics
        self.assertEqual(summary.total_actions, 7)
        self.assertEqual(summary.files_modified, 2)
        self.assertEqual(summary.commands_executed, 2)
        self.assertEqual(summary.errors_encountered, 1)
        
        # Verify action type counts
        expected_counts = {
            ActionType.TASK_START: 1,
            ActionType.FILE_CREATE: 1,
            ActionType.FILE_MODIFY: 1,
            ActionType.COMMAND_EXECUTE: 2,
            ActionType.TASK_ERROR: 1,
            ActionType.TASK_COMPLETE: 1
        }
        
        for action_type, expected_count in expected_counts.items():
            self.assertEqual(summary.actions_by_type[action_type], expected_count)
    
    def test_database_export_formats(self):
        """Test database export functionality in different formats."""
        # Insert test data
        self.logger.log_action(ActionType.TASK_START, "Export test", session_id="export_test")
        self.logger.log_file_change("/test.py", "create", after_content="test", session_id="export_test")
        self.logger.log_command("echo test", "/", "test", "", 0, 0.1, session_id="export_test")
        self.logger.log_error("TestError", "Test error", session_id="export_test")
        
        query = LogQuery(session_id="export_test")
        
        # Test JSON export
        json_export = self.logger.export_logs(query, format="json")
        self.assertIsInstance(json_export, str)
        
        # Verify JSON structure
        actions_data = json.loads(json_export)
        self.assertIsInstance(actions_data, list)
        self.assertEqual(len(actions_data), 4)
        
        # Test CSV export
        csv_export = self.logger.export_logs(query, format="csv")
        self.assertIsInstance(csv_export, str)
        
        # Verify CSV structure
        lines = csv_export.strip().split('\n')
        self.assertGreater(len(lines), 4)  # Header + data rows
        
        # Test unsupported format
        with self.assertRaises(ValueError):
            self.logger.export_logs(query, format="xml")
    
    def test_database_cleanup_operations(self):
        """Test database cleanup operations."""
        # Insert test data
        sessions = ["cleanup_1", "cleanup_2", "cleanup_3"]
        for session in sessions:
            for i in range(5):
                self.logger.log_action(
                    ActionType.TASK_START,
                    f"Cleanup test {i}",
                    session_id=session
                )
        
        # Test session-based cleanup
        initial_count = self.logger.get_database_stats()['actions_count']
        self.assertEqual(initial_count, 15)  # 3 sessions * 5 actions
        
        cleared_count = self.logger.clear_logs(session_id="cleanup_2")
        self.assertEqual(cleared_count, 5)
        
        final_count = self.logger.get_database_stats()['actions_count']
        self.assertEqual(final_count, 10)  # 15 - 5
        
        # Verify correct session was cleared
        query = LogQuery(session_id="cleanup_2")
        remaining_actions = self.logger.get_actions(query)
        self.assertEqual(len(remaining_actions), 0)
        
        # Verify other sessions remain
        query = LogQuery(session_id="cleanup_1")
        remaining_actions = self.logger.get_actions(query)
        self.assertEqual(len(remaining_actions), 5)
    
    def test_database_persistence(self):
        """Test that data persists across logger instances."""
        # Insert data with first logger instance
        action_id = self.logger.log_action(
            ActionType.TASK_START,
            "Persistence test",
            session_id="persistence_test"
        )
        
        # Create new logger instance with same database
        new_logger = DatabaseActionLogger(self.temp_db.name)
        
        # Verify data persists
        query = LogQuery(session_id="persistence_test")
        actions = new_logger.get_actions(query)
        
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].id, action_id)
        self.assertEqual(actions[0].description, "Persistence test")
    
    def test_database_transaction_integrity(self):
        """Test that database operations maintain transaction integrity."""
        # This test ensures that related data is properly stored together
        action_id = self.logger.log_file_change(
            file_path="/transaction_test.py",
            change_type="create",
            after_content="test content",
            session_id="transaction_test"
        )
        
        # Verify both action and file_change records exist
        stats = self.logger.get_database_stats()
        self.assertEqual(stats['actions_count'], 1)
        self.assertEqual(stats['file_changes_count'], 1)
        
        # Verify they are properly linked
        query = LogQuery(session_id="transaction_test")
        actions = self.logger.get_actions(query)
        
        self.assertEqual(len(actions), 1)
        action = actions[0]
        self.assertEqual(len(action.file_changes), 1)
        self.assertEqual(action.file_changes[0].file_path, "/transaction_test.py")


if __name__ == '__main__':
    unittest.main()