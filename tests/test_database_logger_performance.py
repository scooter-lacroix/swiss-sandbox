"""
Performance tests for the database action logger.
Tests storage and retrieval performance with large datasets.
"""

import unittest
import time
import tempfile
import os
from datetime import datetime, timedelta

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sandbox.intelligent.logger.database import DatabaseActionLogger
from sandbox.intelligent.logger.models import LogQuery
from sandbox.intelligent.types import ActionType


class TestDatabaseLoggerPerformance(unittest.TestCase):
    """Performance test cases for DatabaseActionLogger."""
    
    def setUp(self):
        """Set up test fixtures with temporary database."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_logger = DatabaseActionLogger(self.temp_db.name)
        
    def tearDown(self):
        """Clean up temporary database."""
        try:
            os.unlink(self.temp_db.name)
        except OSError:
            pass
    
    def test_bulk_insert_performance(self):
        """Test performance of bulk logging operations."""
        num_actions = 1000
        start_time = time.time()
        
        # Log many actions
        for i in range(num_actions):
            self.db_logger.log_action(
                action_type=ActionType.TASK_START,
                description=f"Test action {i}",
                details={"index": i, "data": f"test_data_{i}"},
                session_id=f"session_{i % 10}",  # 10 different sessions
                task_id=f"task_{i % 100}"  # 100 different tasks
            )
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"Bulk insert of {num_actions} actions took {duration:.3f} seconds")
        print(f"Average: {duration/num_actions*1000:.3f} ms per action")
        
        # Performance assertion - should be able to log at least 100 actions per second
        self.assertLess(duration, num_actions / 100, 
                       f"Bulk insert too slow: {duration:.3f}s for {num_actions} actions")
    
    def test_query_performance_with_indexes(self):
        """Test query performance with indexed columns."""
        # Insert test data
        num_actions = 5000
        sessions = [f"session_{i}" for i in range(10)]
        tasks = [f"task_{i}" for i in range(50)]
        
        for i in range(num_actions):
            self.db_logger.log_action(
                action_type=ActionType.TASK_START,
                description=f"Test action {i}",
                session_id=sessions[i % len(sessions)],
                task_id=tasks[i % len(tasks)]
            )
        
        # Test session_id query performance
        start_time = time.time()
        query = LogQuery(session_id="session_5")
        results = self.db_logger.get_actions(query)
        end_time = time.time()
        
        session_query_time = end_time - start_time
        print(f"Session query returned {len(results)} results in {session_query_time:.3f} seconds")
        
        # Test task_id query performance
        start_time = time.time()
        query = LogQuery(task_id="task_25")
        results = self.db_logger.get_actions(query)
        end_time = time.time()
        
        task_query_time = end_time - start_time
        print(f"Task query returned {len(results)} results in {task_query_time:.3f} seconds")
        
        # Test action_type query performance
        start_time = time.time()
        query = LogQuery(action_types=[ActionType.TASK_START])
        results = self.db_logger.get_actions(query)
        end_time = time.time()
        
        type_query_time = end_time - start_time
        print(f"Type query returned {len(results)} results in {type_query_time:.3f} seconds")
        
        # Performance assertions - queries should be fast with indexes
        self.assertLess(session_query_time, 0.1, "Session query too slow")
        self.assertLess(task_query_time, 0.1, "Task query too slow")
        self.assertLess(type_query_time, 0.1, "Type query too slow")
    
    def test_time_range_query_performance(self):
        """Test performance of time-based queries."""
        # Insert actions over a time range
        base_time = datetime.now() - timedelta(hours=24)
        num_actions = 2000
        
        for i in range(num_actions):
            # Simulate actions spread over 24 hours
            action_time = base_time + timedelta(minutes=i * 0.72)  # ~1.44 actions per minute
            
            # We need to manually set the timestamp for testing
            action_id = self.db_logger.log_action(
                action_type=ActionType.TASK_START,
                description=f"Timed action {i}",
                session_id="time_test_session"
            )
        
        # Test recent actions query (last hour)
        start_time = time.time()
        query = LogQuery(
            start_time=datetime.now() - timedelta(hours=1),
            session_id="time_test_session"
        )
        results = self.db_logger.get_actions(query)
        end_time = time.time()
        
        recent_query_time = end_time - start_time
        print(f"Recent actions query returned {len(results)} results in {recent_query_time:.3f} seconds")
        
        # Test time range query (6 hour window)
        start_time = time.time()
        query = LogQuery(
            start_time=datetime.now() - timedelta(hours=12),
            end_time=datetime.now() - timedelta(hours=6),
            session_id="time_test_session"
        )
        results = self.db_logger.get_actions(query)
        end_time = time.time()
        
        range_query_time = end_time - start_time
        print(f"Time range query returned {len(results)} results in {range_query_time:.3f} seconds")
        
        # Performance assertions
        self.assertLess(recent_query_time, 0.1, "Recent actions query too slow")
        self.assertLess(range_query_time, 0.1, "Time range query too slow")
    
    def test_complex_query_performance(self):
        """Test performance of complex queries with multiple filters."""
        # Insert diverse test data
        num_actions = 3000
        action_types = [ActionType.TASK_START, ActionType.FILE_CREATE, ActionType.COMMAND_EXECUTE, ActionType.TASK_ERROR]
        
        for i in range(num_actions):
            action_type = action_types[i % len(action_types)]
            
            if action_type == ActionType.FILE_CREATE:
                self.db_logger.log_file_change(
                    file_path=f"/test/file_{i}.py",
                    change_type="create",
                    after_content=f"content_{i}",
                    session_id=f"session_{i % 5}",
                    task_id=f"task_{i % 20}"
                )
            elif action_type == ActionType.COMMAND_EXECUTE:
                self.db_logger.log_command(
                    command=f"test_command_{i}",
                    working_directory="/test",
                    output=f"output_{i}",
                    error_output="",
                    exit_code=0,
                    duration=0.1,
                    session_id=f"session_{i % 5}",
                    task_id=f"task_{i % 20}"
                )
            elif action_type == ActionType.TASK_ERROR:
                self.db_logger.log_error(
                    error_type="TestError",
                    message=f"Test error {i}",
                    session_id=f"session_{i % 5}",
                    task_id=f"task_{i % 20}"
                )
            else:
                self.db_logger.log_action(
                    action_type=action_type,
                    description=f"Action {i}",
                    session_id=f"session_{i % 5}",
                    task_id=f"task_{i % 20}"
                )
        
        # Test complex query with multiple filters
        start_time = time.time()
        query = LogQuery(
            session_id="session_2",
            action_types=[ActionType.FILE_CREATE, ActionType.COMMAND_EXECUTE],
            limit=100
        )
        results = self.db_logger.get_actions(query)
        end_time = time.time()
        
        complex_query_time = end_time - start_time
        print(f"Complex query returned {len(results)} results in {complex_query_time:.3f} seconds")
        
        # Verify results are correct
        for action in results:
            self.assertEqual(action.session_id, "session_2")
            self.assertIn(action.action_type, [ActionType.FILE_CREATE, ActionType.COMMAND_EXECUTE])
        
        # Performance assertion
        self.assertLess(complex_query_time, 0.2, "Complex query too slow")
    
    def test_summary_generation_performance(self):
        """Test performance of log summary generation."""
        # Insert test data with various types
        num_actions = 2000
        
        for i in range(num_actions):
            if i % 4 == 0:
                self.db_logger.log_file_change(
                    file_path=f"/test/file_{i}.py",
                    change_type="modify",
                    session_id="summary_test"
                )
            elif i % 4 == 1:
                self.db_logger.log_command(
                    command=f"command_{i}",
                    working_directory="/test",
                    output="output",
                    error_output="",
                    exit_code=0,
                    duration=0.1,
                    session_id="summary_test"
                )
            elif i % 4 == 2:
                self.db_logger.log_error(
                    error_type="TestError",
                    message=f"Error {i}",
                    session_id="summary_test"
                )
            else:
                self.db_logger.log_action(
                    action_type=ActionType.TASK_COMPLETE,
                    description=f"Complete {i}",
                    session_id="summary_test"
                )
        
        # Test summary generation performance
        start_time = time.time()
        summary = self.db_logger.get_log_summary(session_id="summary_test")
        end_time = time.time()
        
        summary_time = end_time - start_time
        print(f"Summary generation took {summary_time:.3f} seconds")
        print(f"Summary: {summary.total_actions} actions, {summary.files_modified} files, "
              f"{summary.commands_executed} commands, {summary.errors_encountered} errors")
        
        # Verify summary accuracy
        self.assertEqual(summary.total_actions, num_actions)
        self.assertEqual(summary.files_modified, num_actions // 4)
        self.assertEqual(summary.commands_executed, num_actions // 4)
        self.assertEqual(summary.errors_encountered, num_actions // 4)
        
        # Performance assertion
        self.assertLess(summary_time, 0.5, "Summary generation too slow")
    
    def test_export_performance(self):
        """Test performance of log export functionality."""
        # Insert test data
        num_actions = 1000
        
        for i in range(num_actions):
            self.db_logger.log_action(
                action_type=ActionType.TASK_START,
                description=f"Export test action {i}",
                details={"index": i, "data": f"export_data_{i}"},
                session_id="export_test"
            )
        
        # Test JSON export performance
        start_time = time.time()
        query = LogQuery(session_id="export_test")
        json_export = self.db_logger.export_logs(query, format="json")
        end_time = time.time()
        
        json_export_time = end_time - start_time
        print(f"JSON export of {num_actions} actions took {json_export_time:.3f} seconds")
        print(f"Export size: {len(json_export)} characters")
        
        # Test CSV export performance
        start_time = time.time()
        csv_export = self.db_logger.export_logs(query, format="csv")
        end_time = time.time()
        
        csv_export_time = end_time - start_time
        print(f"CSV export of {num_actions} actions took {csv_export_time:.3f} seconds")
        print(f"Export size: {len(csv_export)} characters")
        
        # Performance assertions
        self.assertLess(json_export_time, 2.0, "JSON export too slow")
        self.assertLess(csv_export_time, 2.0, "CSV export too slow")
        
        # Verify exports contain data
        self.assertGreater(len(json_export), 1000)
        self.assertGreater(len(csv_export), 1000)
    
    def test_database_cleanup_performance(self):
        """Test performance of database cleanup operations."""
        # Insert test data with different timestamps
        num_actions = 2000
        
        for i in range(num_actions):
            self.db_logger.log_action(
                action_type=ActionType.TASK_START,
                description=f"Cleanup test action {i}",
                session_id=f"cleanup_session_{i % 10}"
            )
        
        # Test session-based cleanup performance
        start_time = time.time()
        cleared_count = self.db_logger.clear_logs(session_id="cleanup_session_5")
        end_time = time.time()
        
        cleanup_time = end_time - start_time
        print(f"Cleared {cleared_count} logs in {cleanup_time:.3f} seconds")
        
        # Performance assertion
        self.assertLess(cleanup_time, 1.0, "Cleanup operation too slow")
        
        # Verify cleanup worked
        query = LogQuery(session_id="cleanup_session_5")
        remaining_actions = self.db_logger.get_actions(query)
        self.assertEqual(len(remaining_actions), 0)
    
    def test_database_statistics(self):
        """Test database statistics collection performance."""
        # Insert test data
        num_actions = 1000
        
        for i in range(num_actions):
            if i % 3 == 0:
                self.db_logger.log_file_change(f"/file_{i}.py", "create", session_id="stats_test")
            elif i % 3 == 1:
                self.db_logger.log_command(f"cmd_{i}", "/", "out", "", 0, 0.1, session_id="stats_test")
            else:
                self.db_logger.log_error("Error", f"msg_{i}", session_id="stats_test")
        
        # Test statistics collection performance
        start_time = time.time()
        stats = self.db_logger.get_database_stats()
        end_time = time.time()
        
        stats_time = end_time - start_time
        print(f"Database statistics collection took {stats_time:.3f} seconds")
        print(f"Stats: {stats}")
        
        # Verify statistics
        self.assertEqual(stats['actions_count'], num_actions)
        self.assertGreater(stats['file_changes_count'], 0)
        self.assertGreater(stats['command_info_count'], 0)
        self.assertGreater(stats['error_info_count'], 0)
        
        # Performance assertion
        self.assertLess(stats_time, 0.1, "Statistics collection too slow")
    
    def test_concurrent_access_simulation(self):
        """Test performance under simulated concurrent access."""
        import threading
        import queue
        
        num_threads = 5
        actions_per_thread = 200
        results_queue = queue.Queue()
        
        def worker_thread(thread_id):
            """Worker thread that performs logging operations."""
            start_time = time.time()
            
            for i in range(actions_per_thread):
                self.db_logger.log_action(
                    action_type=ActionType.TASK_START,
                    description=f"Thread {thread_id} action {i}",
                    session_id=f"thread_{thread_id}"
                )
            
            end_time = time.time()
            results_queue.put((thread_id, end_time - start_time))
        
        # Start all threads
        threads = []
        overall_start = time.time()
        
        for thread_id in range(num_threads):
            thread = threading.Thread(target=worker_thread, args=(thread_id,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        overall_end = time.time()
        overall_time = overall_end - overall_start
        
        # Collect results
        thread_times = []
        while not results_queue.empty():
            thread_id, thread_time = results_queue.get()
            thread_times.append(thread_time)
            print(f"Thread {thread_id} completed in {thread_time:.3f} seconds")
        
        print(f"Overall concurrent test took {overall_time:.3f} seconds")
        print(f"Average thread time: {sum(thread_times)/len(thread_times):.3f} seconds")
        
        # Verify all actions were logged
        total_expected = num_threads * actions_per_thread
        query = LogQuery()
        all_actions = self.db_logger.get_actions(query)
        
        # Note: This test might have some actions from other tests, so we check minimum
        self.assertGreaterEqual(len(all_actions), total_expected)
        
        # Performance assertion - concurrent access shouldn't be too slow
        self.assertLess(overall_time, 10.0, "Concurrent access too slow")


if __name__ == '__main__':
    unittest.main()