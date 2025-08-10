"""
Integration tests for execution history tracking and summary generation.
Tests end-to-end history tracking with verified outcomes.
"""

import unittest
import tempfile
import os
import json
from datetime import datetime, timedelta

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sandbox.intelligent.logger.database import DatabaseActionLogger
from sandbox.intelligent.logger.history import ExecutionHistoryTracker, OutcomeStatus, VerifiedOutcome
from sandbox.intelligent.types import ActionType, TaskStatus


class TestExecutionHistoryIntegration(unittest.TestCase):
    """Integration test cases for execution history tracking."""
    
    def setUp(self):
        """Set up test fixtures with database logger and history tracker."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.logger = DatabaseActionLogger(self.temp_db.name)
        self.history_tracker = ExecutionHistoryTracker(self.logger)
        self.session_id = "integration-test-session"
        
    def tearDown(self):
        """Clean up temporary database."""
        try:
            os.unlink(self.temp_db.name)
        except OSError:
            pass
    
    def test_end_to_end_task_execution_tracking(self):
        """Test complete task execution tracking from start to finish."""
        task_id = "test-task-001"
        
        # Simulate a complete task execution
        # 1. Task start
        self.logger.log_action(
            ActionType.TASK_START,
            "Starting file processing task",
            session_id=self.session_id,
            task_id=task_id
        )
        
        # 2. File creation
        self.logger.log_file_change(
            file_path="/workspace/data_processor.py",
            change_type="create",
            after_content="def process_data():\n    return 'processed'",
            session_id=self.session_id,
            task_id=task_id
        )
        
        # 3. Command execution (successful)
        self.logger.log_command(
            command="python data_processor.py",
            working_directory="/workspace",
            output="Data processed successfully",
            error_output="",
            exit_code=0,
            duration=1.5,
            session_id=self.session_id,
            task_id=task_id
        )
        
        # 4. File modification
        self.logger.log_file_change(
            file_path="/workspace/output.txt",
            change_type="modify",
            before_content="old data",
            after_content="processed data",
            session_id=self.session_id,
            task_id=task_id
        )
        
        # 5. Task completion
        self.logger.log_action(
            ActionType.TASK_COMPLETE,
            "File processing task completed successfully",
            session_id=self.session_id,
            task_id=task_id
        )
        
        # Analyze task execution
        task_summary = self.history_tracker.analyze_task_execution(task_id, self.session_id)
        
        # Verify task summary
        self.assertEqual(task_summary.task_id, task_id)
        self.assertEqual(task_summary.status, TaskStatus.COMPLETED)
        self.assertEqual(task_summary.actions_count, 5)
        self.assertEqual(len(task_summary.files_modified), 2)
        self.assertEqual(len(task_summary.commands_executed), 1)
        self.assertEqual(len(task_summary.errors_encountered), 0)
        self.assertGreater(task_summary.success_rate, 0.8)
        
        # Verify verified outcomes
        self.assertGreater(len(task_summary.verified_outcomes), 0)
        
        # Check specific outcomes
        file_outcomes = [o for o in task_summary.verified_outcomes if o.outcome_type.startswith("file_")]
        command_outcomes = [o for o in task_summary.verified_outcomes if o.outcome_type == "command_executed"]
        
        self.assertEqual(len(file_outcomes), 2)  # create + modify
        self.assertEqual(len(command_outcomes), 1)
        
        # Verify all outcomes are successful
        for outcome in task_summary.verified_outcomes:
            self.assertEqual(outcome.status, OutcomeStatus.SUCCESS)
    
    def test_task_execution_with_errors(self):
        """Test task execution tracking when errors occur."""
        task_id = "test-task-002"
        
        # Simulate task with errors
        self.logger.log_action(
            ActionType.TASK_START,
            "Starting error-prone task",
            session_id=self.session_id,
            task_id=task_id
        )
        
        # Failed command execution
        self.logger.log_command(
            command="python broken_script.py",
            working_directory="/workspace",
            output="",
            error_output="SyntaxError: invalid syntax",
            exit_code=1,
            duration=0.5,
            session_id=self.session_id,
            task_id=task_id
        )
        
        # Error logging
        self.logger.log_error(
            error_type="SyntaxError",
            message="Script contains syntax errors",
            stack_trace="Traceback: line 5, invalid syntax",
            context={"file": "broken_script.py", "line": 5},
            session_id=self.session_id,
            task_id=task_id
        )
        
        # Analyze task execution
        task_summary = self.history_tracker.analyze_task_execution(task_id, self.session_id)
        
        # Verify task summary reflects errors
        self.assertEqual(task_summary.status, TaskStatus.ERROR)
        self.assertEqual(len(task_summary.errors_encountered), 1)
        self.assertLess(task_summary.success_rate, 0.5)
        
        # Verify error outcomes
        error_outcomes = [o for o in task_summary.verified_outcomes if o.outcome_type == "error_encountered"]
        failed_command_outcomes = [
            o for o in task_summary.verified_outcomes 
            if o.outcome_type == "command_executed" and o.status == OutcomeStatus.FAILURE
        ]
        
        self.assertEqual(len(error_outcomes), 1)
        self.assertEqual(len(failed_command_outcomes), 1)
    
    def test_multi_task_session_history(self):
        """Test comprehensive session history with multiple tasks."""
        # Task 1: Successful setup task
        task1_id = "setup-task"
        self.logger.log_action(ActionType.TASK_START, "Setup workspace", session_id=self.session_id, task_id=task1_id)
        self.logger.log_file_change("/workspace/config.json", "create", after_content='{"env": "test"}', session_id=self.session_id, task_id=task1_id)
        self.logger.log_command("mkdir -p /workspace/data", "/workspace", "Directory created", "", 0, 0.1, session_id=self.session_id, task_id=task1_id)
        self.logger.log_action(ActionType.TASK_COMPLETE, "Setup completed", session_id=self.session_id, task_id=task1_id)
        
        # Task 2: Data processing task with partial success
        task2_id = "process-task"
        self.logger.log_action(ActionType.TASK_START, "Process data files", session_id=self.session_id, task_id=task2_id)
        self.logger.log_file_change("/workspace/data/input.csv", "create", after_content="col1,col2\n1,2", session_id=self.session_id, task_id=task2_id)
        self.logger.log_command("python process.py", "/workspace", "Processing...", "", 0, 2.0, session_id=self.session_id, task_id=task2_id)
        self.logger.log_file_change("/workspace/data/output.csv", "create", after_content="result1,result2\n3,4", session_id=self.session_id, task_id=task2_id)
        self.logger.log_action(ActionType.TASK_COMPLETE, "Data processing completed", session_id=self.session_id, task_id=task2_id)
        
        # Task 3: Failed cleanup task
        task3_id = "cleanup-task"
        self.logger.log_action(ActionType.TASK_START, "Cleanup temporary files", session_id=self.session_id, task_id=task3_id)
        self.logger.log_command("rm -rf /workspace/temp", "/workspace", "", "Permission denied", 1, 0.1, session_id=self.session_id, task_id=task3_id)
        self.logger.log_error("PermissionError", "Cannot delete temporary files", session_id=self.session_id, task_id=task3_id)
        
        # Generate session history
        session_history = self.history_tracker.generate_session_history(self.session_id)
        
        # Verify session-level metrics
        self.assertEqual(session_history.session_id, self.session_id)
        self.assertEqual(len(session_history.task_summaries), 3)
        self.assertIsNotNone(session_history.start_time)
        self.assertIsNotNone(session_history.end_time)
        self.assertIsNotNone(session_history.duration)
        
        # Verify task statuses
        task_statuses = {task.task_id: task.status for task in session_history.task_summaries}
        self.assertEqual(task_statuses[task1_id], TaskStatus.COMPLETED)
        self.assertEqual(task_statuses[task2_id], TaskStatus.COMPLETED)
        self.assertEqual(task_statuses[task3_id], TaskStatus.ERROR)
        
        # Verify achievements and issues
        self.assertGreater(len(session_history.key_achievements), 0)
        self.assertGreater(len(session_history.remaining_issues), 0)
        
        # Verify overall success rate is reasonable (2/3 tasks successful)
        self.assertGreater(session_history.overall_success_rate, 0.5)
        self.assertLess(session_history.overall_success_rate, 1.0)
    
    def test_detailed_completion_summary_generation(self):
        """Test generation of detailed completion summary with verified data."""
        task_id = "summary-test-task"
        
        # Create a comprehensive task execution
        self.logger.log_action(ActionType.TASK_START, "Comprehensive test task", session_id=self.session_id, task_id=task_id)
        
        # Multiple file operations
        self.logger.log_file_change("/app/main.py", "create", after_content="print('Hello')", session_id=self.session_id, task_id=task_id)
        self.logger.log_file_change("/app/utils.py", "create", after_content="def helper(): pass", session_id=self.session_id, task_id=task_id)
        self.logger.log_file_change("/app/main.py", "modify", before_content="print('Hello')", after_content="print('Hello, World!')", session_id=self.session_id, task_id=task_id)
        
        # Multiple command executions
        self.logger.log_command("python -m py_compile main.py", "/app", "Compiled successfully", "", 0, 0.5, session_id=self.session_id, task_id=task_id)
        self.logger.log_command("python main.py", "/app", "Hello, World!", "", 0, 0.2, session_id=self.session_id, task_id=task_id)
        self.logger.log_command("python -m pytest tests/", "/app", "2 passed", "", 0, 1.0, session_id=self.session_id, task_id=task_id)
        
        self.logger.log_action(ActionType.TASK_COMPLETE, "Task completed successfully", session_id=self.session_id, task_id=task_id)
        
        # Generate detailed completion summary
        summary = self.history_tracker.generate_detailed_completion_summary(self.session_id)
        
        # Verify summary structure
        required_keys = [
            "session_id", "execution_period", "overall_metrics", 
            "task_details", "achievements", "remaining_issues", 
            "recommendations", "verification_summary"
        ]
        for key in required_keys:
            self.assertIn(key, summary)
        
        # Verify execution period
        self.assertEqual(summary["session_id"], self.session_id)
        self.assertIsNotNone(summary["execution_period"]["start_time"])
        self.assertIsNotNone(summary["execution_period"]["end_time"])
        self.assertGreater(summary["execution_period"]["duration_seconds"], 0)
        
        # Verify overall metrics
        metrics = summary["overall_metrics"]
        self.assertEqual(metrics["total_tasks"], 1)
        self.assertEqual(metrics["completed_tasks"], 1)
        self.assertEqual(metrics["failed_tasks"], 0)
        self.assertGreater(metrics["overall_success_rate"], 80)  # Should be high success rate
        self.assertEqual(metrics["total_files_modified"], 2)  # main.py and utils.py
        self.assertEqual(metrics["total_commands_executed"], 3)
        
        # Verify task details
        self.assertEqual(len(summary["task_details"]), 1)
        task_detail = summary["task_details"][0]
        self.assertEqual(task_detail["task_id"], task_id)
        self.assertEqual(task_detail["status"], "completed")
        self.assertGreater(len(task_detail["verified_outcomes"]), 0)
        
        # Verify verification summary
        verification = summary["verification_summary"]
        self.assertGreater(verification["total_outcomes_verified"], 0)
        self.assertGreater(verification["successful_outcomes"], 0)
        self.assertEqual(verification["failed_outcomes"], 0)
        self.assertIn("automatic", verification["verification_methods"])
    
    def test_outcome_verification_accuracy(self):
        """Test accuracy of outcome verification for different action types."""
        task_id = "verification-test"
        
        # Test file creation verification
        self.logger.log_file_change(
            "/test/new_file.py", 
            "create", 
            after_content="# New file content",
            session_id=self.session_id, 
            task_id=task_id
        )
        
        # Test successful command verification
        self.logger.log_command(
            "echo 'success'",
            "/test",
            "success",
            "",
            0,  # Success exit code
            0.1,
            session_id=self.session_id,
            task_id=task_id
        )
        
        # Test failed command verification
        self.logger.log_command(
            "false",  # Command that always fails
            "/test",
            "",
            "Command failed",
            1,  # Failure exit code
            0.1,
            session_id=self.session_id,
            task_id=task_id
        )
        
        # Test error verification
        self.logger.log_error(
            "TestError",
            "Intentional test error",
            stack_trace="Test stack trace",
            context={"test": True},
            session_id=self.session_id,
            task_id=task_id
        )
        
        # Analyze task and verify outcomes
        task_summary = self.history_tracker.analyze_task_execution(task_id, self.session_id)
        
        # Verify outcome types and statuses
        outcomes_by_type = {}
        for outcome in task_summary.verified_outcomes:
            if outcome.outcome_type not in outcomes_by_type:
                outcomes_by_type[outcome.outcome_type] = []
            outcomes_by_type[outcome.outcome_type].append(outcome)
        
        # Verify file creation outcome
        self.assertIn("file_created", outcomes_by_type)
        file_outcome = outcomes_by_type["file_created"][0]
        self.assertEqual(file_outcome.status, OutcomeStatus.SUCCESS)
        self.assertIn("file_path", file_outcome.evidence)
        self.assertIn("content_length", file_outcome.evidence)
        
        # Verify command outcomes
        self.assertIn("command_executed", outcomes_by_type)
        command_outcomes = outcomes_by_type["command_executed"]
        self.assertEqual(len(command_outcomes), 2)
        
        # Find successful and failed command outcomes
        successful_cmd = next(o for o in command_outcomes if o.status == OutcomeStatus.SUCCESS)
        failed_cmd = next(o for o in command_outcomes if o.status == OutcomeStatus.FAILURE)
        
        self.assertEqual(successful_cmd.evidence["exit_code"], 0)
        self.assertEqual(failed_cmd.evidence["exit_code"], 1)
        
        # Verify error outcome
        self.assertIn("error_encountered", outcomes_by_type)
        error_outcome = outcomes_by_type["error_encountered"][0]
        self.assertEqual(error_outcome.status, OutcomeStatus.FAILURE)
        self.assertEqual(error_outcome.evidence["error_type"], "TestError")
    
    def test_export_functionality(self):
        """Test export functionality for execution history."""
        task_id = "export-test"
        
        # Create simple task execution
        self.logger.log_action(ActionType.TASK_START, "Export test task", session_id=self.session_id, task_id=task_id)
        self.logger.log_file_change("/test/export.txt", "create", after_content="export data", session_id=self.session_id, task_id=task_id)
        self.logger.log_action(ActionType.TASK_COMPLETE, "Export test completed", session_id=self.session_id, task_id=task_id)
        
        # Test JSON export
        json_export = self.history_tracker.export_execution_history(self.session_id, format="json")
        self.assertIsInstance(json_export, str)
        
        # Verify JSON is valid
        parsed_json = json.loads(json_export)
        self.assertIn("session_id", parsed_json)
        self.assertEqual(parsed_json["session_id"], self.session_id)
        
        # Test Markdown export
        markdown_export = self.history_tracker.export_execution_history(self.session_id, format="markdown")
        self.assertIsInstance(markdown_export, str)
        self.assertIn("# Execution Summary", markdown_export)
        self.assertIn(self.session_id, markdown_export)
        
        # Test unsupported format
        with self.assertRaises(ValueError):
            self.history_tracker.export_execution_history(self.session_id, format="xml")
    
    def test_custom_verified_outcomes(self):
        """Test adding custom verified outcomes."""
        task_id = "custom-outcome-test"
        
        # Log a basic action
        action_id = self.logger.log_action(
            ActionType.TASK_START,
            "Custom outcome test",
            session_id=self.session_id,
            task_id=task_id
        )
        
        # Add custom verified outcome
        custom_outcome = VerifiedOutcome(
            action_id=action_id,
            outcome_type="custom_verification",
            status=OutcomeStatus.SUCCESS,
            description="Custom verification passed",
            evidence={"custom_data": "verified", "score": 95},
            verification_method="manual"
        )
        
        self.history_tracker.add_verified_outcome(custom_outcome)
        
        # Verify custom outcome is included in analysis
        task_summary = self.history_tracker.analyze_task_execution(task_id, self.session_id)
        
        # Find the custom outcome
        custom_outcomes = [
            o for o in task_summary.verified_outcomes 
            if o.outcome_type == "custom_verification"
        ]
        
        self.assertEqual(len(custom_outcomes), 1)
        custom_outcome_found = custom_outcomes[0]
        self.assertEqual(custom_outcome_found.status, OutcomeStatus.SUCCESS)
        self.assertEqual(custom_outcome_found.verification_method, "manual")
        self.assertEqual(custom_outcome_found.evidence["score"], 95)
    
    def test_large_session_performance(self):
        """Test performance with a large number of actions."""
        import time
        
        # Create a session with many actions
        num_tasks = 10
        actions_per_task = 20
        
        start_time = time.time()
        
        for task_num in range(num_tasks):
            task_id = f"perf-task-{task_num}"
            
            self.logger.log_action(ActionType.TASK_START, f"Performance test task {task_num}", session_id=self.session_id, task_id=task_id)
            
            for action_num in range(actions_per_task - 2):  # -2 for start and complete
                if action_num % 3 == 0:
                    self.logger.log_file_change(f"/test/file_{action_num}.py", "create", after_content=f"content_{action_num}", session_id=self.session_id, task_id=task_id)
                elif action_num % 3 == 1:
                    self.logger.log_command(f"echo {action_num}", "/test", f"output_{action_num}", "", 0, 0.1, session_id=self.session_id, task_id=task_id)
                else:
                    self.logger.log_action(ActionType.TASK_START, f"Sub-action {action_num}", session_id=self.session_id, task_id=task_id)
            
            self.logger.log_action(ActionType.TASK_COMPLETE, f"Task {task_num} completed", session_id=self.session_id, task_id=task_id)
        
        # Generate session history
        history_start = time.time()
        session_history = self.history_tracker.generate_session_history(self.session_id)
        history_end = time.time()
        
        # Generate detailed summary
        summary_start = time.time()
        detailed_summary = self.history_tracker.generate_detailed_completion_summary(self.session_id)
        summary_end = time.time()
        
        total_time = time.time() - start_time
        history_time = history_end - history_start
        summary_time = summary_end - summary_start
        
        print(f"Performance test results:")
        print(f"  Total actions: {num_tasks * actions_per_task}")
        print(f"  Total time: {total_time:.3f}s")
        print(f"  History generation: {history_time:.3f}s")
        print(f"  Summary generation: {summary_time:.3f}s")
        
        # Verify results
        self.assertEqual(len(session_history.task_summaries), num_tasks)
        self.assertEqual(detailed_summary["overall_metrics"]["total_tasks"], num_tasks)
        
        # Performance assertions - should handle large datasets reasonably
        self.assertLess(history_time, 5.0, "History generation too slow")
        self.assertLess(summary_time, 2.0, "Summary generation too slow")


if __name__ == '__main__':
    unittest.main()