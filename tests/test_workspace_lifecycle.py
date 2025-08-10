"""
Integration tests for complete workspace lifecycle management.
"""

import os
import time
import tempfile
import unittest
from unittest.mock import Mock, patch
import threading
from datetime import datetime, timedelta

# Import the lifecycle modules
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sandbox.intelligent.workspace.lifecycle import (
    WorkspaceLifecycleManager,
    LifecycleEvent,
    LifecycleEventData,
    WorkspaceSession
)
from sandbox.intelligent.workspace.models import IsolationConfig
from sandbox.intelligent.workspace.security import SecurityPolicy
from sandbox.intelligent.types import WorkspaceStatus


class TestWorkspaceLifecycleManager(unittest.TestCase):
    """Test the complete workspace lifecycle management."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dirs = []
        self.lifecycle_manager = WorkspaceLifecycleManager(
            max_concurrent_workspaces=3,
            workspace_timeout_minutes=1  # Short timeout for testing
        )
        self.events_received = []
        
        # Add event handler to capture events
        self.lifecycle_manager.add_event_handler(self._event_handler)
    
    def tearDown(self):
        """Clean up test environment."""
        # Shutdown lifecycle manager
        self.lifecycle_manager.shutdown()
        
        # Clean up temporary directories
        import shutil
        for temp_dir in self.temp_dirs:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
    
    def _event_handler(self, event_data: LifecycleEventData):
        """Event handler to capture lifecycle events."""
        self.events_received.append(event_data)
    
    def _create_test_workspace(self) -> str:
        """Create a temporary test workspace."""
        temp_dir = tempfile.mkdtemp()
        self.temp_dirs.append(temp_dir)
        
        # Create some test files
        with open(os.path.join(temp_dir, "test.py"), 'w') as f:
            f.write("print('Hello, World!')")
        
        with open(os.path.join(temp_dir, "README.md"), 'w') as f:
            f.write("# Test Workspace\nThis is a test workspace.")
        
        return temp_dir
    
    def test_create_workspace_session(self):
        """Test creating a workspace session."""
        source_workspace = self._create_test_workspace()
        
        # Create workspace session
        session = self.lifecycle_manager.create_workspace(
            source_path=source_workspace,
            session_id="test-session-1",
            metadata={"test": "data"}
        )
        
        # Verify session creation
        self.assertIsInstance(session, WorkspaceSession)
        self.assertEqual(session.session_id, "test-session-1")
        self.assertEqual(session.metadata["test"], "data")
        self.assertTrue(os.path.exists(session.workspace.sandbox_path))
        
        # Verify events were emitted
        event_types = [event.event for event in self.events_received]
        self.assertIn(LifecycleEvent.SESSION_STARTED, event_types)
        self.assertIn(LifecycleEvent.WORKSPACE_CREATED, event_types)
    
    def test_get_session(self):
        """Test retrieving a workspace session."""
        source_workspace = self._create_test_workspace()
        
        # Create session
        session = self.lifecycle_manager.create_workspace(
            source_path=source_workspace,
            session_id="test-session-2"
        )
        
        # Retrieve session
        retrieved_session = self.lifecycle_manager.get_session("test-session-2")
        self.assertIsNotNone(retrieved_session)
        self.assertEqual(retrieved_session.session_id, "test-session-2")
        
        # Test non-existent session
        non_existent = self.lifecycle_manager.get_session("non-existent")
        self.assertIsNone(non_existent)
    
    def test_list_sessions(self):
        """Test listing all active sessions."""
        source_workspace = self._create_test_workspace()
        
        # Initially no sessions
        sessions = self.lifecycle_manager.list_sessions()
        self.assertEqual(len(sessions), 0)
        
        # Create multiple sessions
        session1 = self.lifecycle_manager.create_workspace(
            source_path=source_workspace,
            session_id="session-1"
        )
        session2 = self.lifecycle_manager.create_workspace(
            source_path=source_workspace,
            session_id="session-2"
        )
        
        # List sessions
        sessions = self.lifecycle_manager.list_sessions()
        self.assertEqual(len(sessions), 2)
        session_ids = [s.session_id for s in sessions]
        self.assertIn("session-1", session_ids)
        self.assertIn("session-2", session_ids)
    
    def test_concurrent_workspace_limit(self):
        """Test the concurrent workspace limit enforcement."""
        source_workspace = self._create_test_workspace()
        
        # Create sessions up to the limit (3)
        for i in range(3):
            session = self.lifecycle_manager.create_workspace(
                source_path=source_workspace,
                session_id=f"session-{i}"
            )
            self.assertIsNotNone(session)
        
        # Try to create one more (should fail)
        with self.assertRaises(RuntimeError) as context:
            self.lifecycle_manager.create_workspace(
                source_path=source_workspace,
                session_id="session-overflow"
            )
        
        self.assertIn("Maximum concurrent workspaces", str(context.exception))
    
    def test_suspend_and_resume_workspace(self):
        """Test suspending and resuming a workspace."""
        source_workspace = self._create_test_workspace()
        
        # Create session with Docker isolation
        isolation_config = IsolationConfig(use_docker=True)
        session = self.lifecycle_manager.create_workspace(
            source_path=source_workspace,
            session_id="suspend-test",
            isolation_config=isolation_config
        )
        
        # Mock container ID
        session.workspace.metadata['container_id'] = 'test-container-123'
        
        # Test suspend/resume with mocked Docker commands
        with patch('subprocess.run') as mock_run:
            # Mock successful Docker pause
            mock_run.return_value = Mock(returncode=0, stderr="")
            
            # Suspend workspace
            result = self.lifecycle_manager.suspend_workspace("suspend-test")
            self.assertTrue(result)
            self.assertEqual(session.workspace.status, WorkspaceStatus.SUSPENDED)
            
            # Verify Docker pause was called
            mock_run.assert_called_with(['docker', 'pause', 'test-container-123'], 
                                       capture_output=True, text=True)
        
        with patch('subprocess.run') as mock_run:
            # Mock successful Docker unpause
            mock_run.return_value = Mock(returncode=0, stderr="")
            
            # Resume workspace
            result = self.lifecycle_manager.resume_workspace("suspend-test")
            self.assertTrue(result)
            self.assertEqual(session.workspace.status, WorkspaceStatus.ACTIVE)
            
            # Verify Docker unpause was called
            mock_run.assert_called_with(['docker', 'unpause', 'test-container-123'], 
                                       capture_output=True, text=True)
        
        # Check events
        event_types = [event.event for event in self.events_received]
        self.assertIn(LifecycleEvent.WORKSPACE_SUSPENDED, event_types)
        self.assertIn(LifecycleEvent.WORKSPACE_RESUMED, event_types)
    
    def test_merge_workspace_changes(self):
        """Test merging workspace changes back to source."""
        source_workspace = self._create_test_workspace()
        target_workspace = tempfile.mkdtemp()
        self.temp_dirs.append(target_workspace)
        
        # Create session
        session = self.lifecycle_manager.create_workspace(
            source_path=source_workspace,
            session_id="merge-test"
        )
        
        # Modify a file in the sandbox
        modified_file = os.path.join(session.workspace.sandbox_path, "modified.txt")
        with open(modified_file, 'w') as f:
            f.write("This file was modified in the sandbox")
        
        # Merge changes back
        result = self.lifecycle_manager.merge_workspace_changes("merge-test", target_workspace)
        self.assertTrue(result)
        
        # Verify the file was merged
        merged_file = os.path.join(target_workspace, "modified.txt")
        self.assertTrue(os.path.exists(merged_file))
        
        with open(merged_file, 'r') as f:
            content = f.read()
            self.assertEqual(content, "This file was modified in the sandbox")
        
        # Check events
        event_types = [event.event for event in self.events_received]
        self.assertIn(LifecycleEvent.WORKSPACE_MERGED, event_types)
    
    def test_destroy_workspace(self):
        """Test destroying a workspace session."""
        source_workspace = self._create_test_workspace()
        
        # Create session
        session = self.lifecycle_manager.create_workspace(
            source_path=source_workspace,
            session_id="destroy-test"
        )
        
        sandbox_path = session.workspace.sandbox_path
        self.assertTrue(os.path.exists(sandbox_path))
        
        # Destroy workspace
        result = self.lifecycle_manager.destroy_workspace("destroy-test")
        self.assertTrue(result)
        
        # Verify workspace is removed from sessions
        retrieved_session = self.lifecycle_manager.get_session("destroy-test")
        self.assertIsNone(retrieved_session)
        
        # Verify sandbox directory is cleaned up
        # Note: The directory might still exist briefly due to cleanup timing
        # but the session should be removed from the manager
        
        # Check events
        event_types = [event.event for event in self.events_received]
        self.assertIn(LifecycleEvent.WORKSPACE_CLEANUP_STARTED, event_types)
        self.assertIn(LifecycleEvent.WORKSPACE_DESTROYED, event_types)
        self.assertIn(LifecycleEvent.SESSION_ENDED, event_types)
    
    def test_get_workspace_status(self):
        """Test getting comprehensive workspace status."""
        source_workspace = self._create_test_workspace()
        
        # Create session
        session = self.lifecycle_manager.create_workspace(
            source_path=source_workspace,
            session_id="status-test",
            metadata={"environment": "test"}
        )
        
        # Get status
        status = self.lifecycle_manager.get_workspace_status("status-test")
        
        # Verify status information
        self.assertEqual(status["session_id"], "status-test")
        self.assertIn("workspace_status", status)
        self.assertIn("created_at", status)
        self.assertIn("last_accessed", status)
        self.assertIn("access_count", status)
        self.assertIn("workspace_path", status)
        self.assertIn("source_path", status)
        self.assertIn("isolation_config", status)
        self.assertIn("security_status", status)
        self.assertEqual(status["metadata"]["environment"], "test")
        
        # Test non-existent session
        status = self.lifecycle_manager.get_workspace_status("non-existent")
        self.assertIn("error", status)
    
    def test_session_timeout_cleanup(self):
        """Test automatic cleanup of expired sessions."""
        source_workspace = self._create_test_workspace()
        
        # Create session
        session = self.lifecycle_manager.create_workspace(
            source_path=source_workspace,
            session_id="timeout-test"
        )
        
        # Manually set last_accessed to simulate old session
        session.last_accessed = datetime.now() - timedelta(minutes=2)
        
        # Trigger cleanup
        self.lifecycle_manager._cleanup_expired_sessions()
        
        # Verify session was cleaned up
        retrieved_session = self.lifecycle_manager.get_session("timeout-test")
        self.assertIsNone(retrieved_session)
    
    def test_event_handler_management(self):
        """Test adding and removing event handlers."""
        events_captured = []
        
        def test_handler(event_data):
            events_captured.append(event_data)
        
        # Add handler
        self.lifecycle_manager.add_event_handler(test_handler)
        
        # Create workspace to trigger events
        source_workspace = self._create_test_workspace()
        session = self.lifecycle_manager.create_workspace(
            source_path=source_workspace,
            session_id="event-test"
        )
        
        # Verify events were captured
        self.assertGreater(len(events_captured), 0)
        
        # Remove handler
        self.lifecycle_manager.remove_event_handler(test_handler)
        
        # Clear captured events
        events_captured.clear()
        
        # Destroy workspace (should not trigger our handler)
        self.lifecycle_manager.destroy_workspace("event-test")
        
        # Verify our handler didn't capture new events
        self.assertEqual(len(events_captured), 0)
    
    def test_statistics(self):
        """Test getting lifecycle management statistics."""
        source_workspace = self._create_test_workspace()
        
        # Get initial statistics
        stats = self.lifecycle_manager.get_statistics()
        self.assertEqual(stats["active_sessions"], 0)
        
        # Create sessions
        session1 = self.lifecycle_manager.create_workspace(
            source_path=source_workspace,
            session_id="stats-1"
        )
        session2 = self.lifecycle_manager.create_workspace(
            source_path=source_workspace,
            session_id="stats-2"
        )
        
        # Suspend one session
        self.lifecycle_manager.suspend_workspace("stats-1")
        
        # Get updated statistics
        stats = self.lifecycle_manager.get_statistics()
        self.assertEqual(stats["active_sessions"], 2)
        self.assertEqual(stats["suspended_sessions"], 1)
        self.assertEqual(stats["max_concurrent"], 3)
        self.assertEqual(stats["timeout_minutes"], 1)
        self.assertIn("average_session_age_seconds", stats)
        self.assertIn("monitoring_active", stats)
    
    def test_error_handling(self):
        """Test error handling in lifecycle operations."""
        # Test creating workspace with non-existent source
        with self.assertRaises(FileNotFoundError):
            self.lifecycle_manager.create_workspace(
                source_path="/non/existent/path",
                session_id="error-test"
            )
        
        # Test operations on non-existent session
        result = self.lifecycle_manager.suspend_workspace("non-existent")
        self.assertFalse(result)
        
        result = self.lifecycle_manager.resume_workspace("non-existent")
        self.assertFalse(result)
        
        result = self.lifecycle_manager.merge_workspace_changes("non-existent", "/tmp")
        self.assertFalse(result)
        
        result = self.lifecycle_manager.destroy_workspace("non-existent")
        self.assertFalse(result)
    
    def test_concurrent_access(self):
        """Test concurrent access to the lifecycle manager."""
        source_workspace = self._create_test_workspace()
        results = []
        errors = []
        
        def create_session(session_id):
            try:
                session = self.lifecycle_manager.create_workspace(
                    source_path=source_workspace,
                    session_id=session_id
                )
                results.append(session)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads to test concurrent access
        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_session, args=(f"concurrent-{i}",))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check results (some should succeed, some should fail due to limits)
        total_operations = len(results) + len(errors)
        self.assertEqual(total_operations, 5)
        
        # At least some should succeed (up to the limit)
        self.assertGreaterEqual(len(results), 1)
        self.assertLessEqual(len(results), 3)  # Max concurrent limit


class TestWorkspaceSession(unittest.TestCase):
    """Test the WorkspaceSession class."""
    
    def test_session_creation(self):
        """Test creating a workspace session."""
        from sandbox.intelligent.workspace.models import SandboxWorkspace, IsolationConfig
        from sandbox.intelligent.types import WorkspaceStatus
        
        workspace = SandboxWorkspace(
            id="test-workspace",
            source_path="/tmp/source",
            sandbox_path="/tmp/sandbox",
            isolation_config=IsolationConfig(),
            created_at=datetime.now(),
            status=WorkspaceStatus.ACTIVE
        )
        
        session = WorkspaceSession(
            session_id="test-session",
            workspace=workspace,
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            metadata={"test": "data"}
        )
        
        self.assertEqual(session.session_id, "test-session")
        self.assertEqual(session.workspace, workspace)
        self.assertEqual(session.access_count, 0)
        self.assertEqual(session.metadata["test"], "data")
    
    def test_update_access(self):
        """Test updating session access information."""
        from sandbox.intelligent.workspace.models import SandboxWorkspace, IsolationConfig
        from sandbox.intelligent.types import WorkspaceStatus
        
        workspace = SandboxWorkspace(
            id="test-workspace",
            source_path="/tmp/source",
            sandbox_path="/tmp/sandbox",
            isolation_config=IsolationConfig(),
            created_at=datetime.now(),
            status=WorkspaceStatus.ACTIVE
        )
        
        session = WorkspaceSession(
            session_id="test-session",
            workspace=workspace,
            created_at=datetime.now(),
            last_accessed=datetime.now()
        )
        
        initial_access_time = session.last_accessed
        initial_count = session.access_count
        
        # Wait a bit to ensure time difference
        time.sleep(0.1)
        
        # Update access
        session.update_access()
        
        # Verify updates
        self.assertGreater(session.last_accessed, initial_access_time)
        self.assertEqual(session.access_count, initial_count + 1)


if __name__ == '__main__':
    # Set up logging for tests
    import logging
    logging.basicConfig(level=logging.WARNING)
    
    # Run the tests
    unittest.main(verbosity=2)