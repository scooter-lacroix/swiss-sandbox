"""
Unit tests for the core WorkspaceManager.
"""

import os
import tempfile
import unittest
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Import the workspace manager
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sandbox.core.workspace_manager import (
    WorkspaceManager,
    WorkspaceConfig,
    Workspace
)
from sandbox.core.types import ResourceLimits, SecurityLevel, ExecutionContext


class TestWorkspaceConfig(unittest.TestCase):
    """Test WorkspaceConfig data class."""
    
    def test_default_config(self):
        """Test default workspace configuration."""
        config = WorkspaceConfig(workspace_id="test-workspace")
        
        self.assertEqual(config.workspace_id, "test-workspace")
        self.assertTrue(config.use_isolation)
        self.assertFalse(config.use_docker)
        self.assertEqual(config.container_image, "python:3.11-slim")
        self.assertEqual(config.cpu_limit, "1.0")
        self.assertEqual(config.memory_limit, "512M")
        self.assertTrue(config.cleanup_on_exit)
    
    def test_custom_config(self):
        """Test custom workspace configuration."""
        config = WorkspaceConfig(
            workspace_id="custom-workspace",
            use_docker=True,
            container_image="ubuntu:22.04",
            cpu_limit="2.0",
            memory_limit="1G",
            environment_vars={"TEST_VAR": "test_value"}
        )
        
        self.assertEqual(config.workspace_id, "custom-workspace")
        self.assertTrue(config.use_docker)
        self.assertEqual(config.container_image, "ubuntu:22.04")
        self.assertEqual(config.cpu_limit, "2.0")
        self.assertEqual(config.memory_limit, "1G")
        self.assertEqual(config.environment_vars["TEST_VAR"], "test_value")


class TestWorkspace(unittest.TestCase):
    """Test Workspace data class."""
    
    def test_workspace_creation(self):
        """Test workspace creation."""
        workspace_path = Path("/tmp/test-workspace")
        workspace = Workspace(
            workspace_id="test-workspace",
            workspace_path=workspace_path
        )
        
        self.assertEqual(workspace.workspace_id, "test-workspace")
        self.assertEqual(workspace.workspace_path, workspace_path)
        self.assertIsNotNone(workspace.created_at)
        self.assertIsNotNone(workspace.last_accessed)
        self.assertFalse(workspace.is_isolated)
    
    def test_update_access(self):
        """Test updating workspace access time."""
        workspace = Workspace(
            workspace_id="test-workspace",
            workspace_path=Path("/tmp/test")
        )
        
        original_access_time = workspace.last_accessed
        
        # Wait a bit and update access
        import time
        time.sleep(0.1)
        workspace.update_access()
        
        self.assertGreater(workspace.last_accessed, original_access_time)


class TestWorkspaceManager(unittest.TestCase):
    """Test the WorkspaceManager class."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dirs = []
        self.temp_base_dir = tempfile.mkdtemp()
        self.temp_dirs.append(self.temp_base_dir)
        
        # Create workspace manager with intelligent features disabled for simpler testing
        self.workspace_manager = WorkspaceManager(
            base_workspace_dir=self.temp_base_dir,
            enable_intelligent_features=False,
            max_concurrent_workspaces=3
        )
    
    def tearDown(self):
        """Clean up test environment."""
        # Shutdown workspace manager
        self.workspace_manager.shutdown()
        
        # Clean up temporary directories
        for temp_dir in self.temp_dirs:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
    
    def _create_test_source_dir(self) -> str:
        """Create a test source directory with some files."""
        source_dir = tempfile.mkdtemp()
        self.temp_dirs.append(source_dir)
        
        # Create some test files
        with open(os.path.join(source_dir, "test.py"), 'w') as f:
            f.write("print('Hello, World!')")
        
        with open(os.path.join(source_dir, "README.md"), 'w') as f:
            f.write("# Test Project\nThis is a test project.")
        
        # Create a subdirectory
        sub_dir = os.path.join(source_dir, "subdir")
        os.makedirs(sub_dir)
        with open(os.path.join(sub_dir, "sub_file.txt"), 'w') as f:
            f.write("This is a file in a subdirectory.")
        
        return source_dir
    
    def test_create_simple_workspace(self):
        """Test creating a simple workspace without source."""
        workspace = self.workspace_manager.create_workspace("test-workspace-1")
        
        self.assertIsInstance(workspace, Workspace)
        self.assertEqual(workspace.workspace_id, "test-workspace-1")
        self.assertTrue(workspace.workspace_path.exists())
        self.assertFalse(workspace.is_isolated)
        self.assertIn("simple_workspace", workspace.metadata)
    
    def test_create_workspace_with_source(self):
        """Test creating a workspace with source files."""
        source_dir = self._create_test_source_dir()
        
        workspace = self.workspace_manager.create_workspace(
            "test-workspace-2",
            source_path=source_dir
        )
        
        self.assertIsInstance(workspace, Workspace)
        self.assertEqual(workspace.workspace_id, "test-workspace-2")
        self.assertTrue(workspace.workspace_path.exists())
        self.assertEqual(workspace.source_path, Path(source_dir))
        
        # Check that files were copied
        test_file = workspace.workspace_path / "test.py"
        self.assertTrue(test_file.exists())
        
        readme_file = workspace.workspace_path / "README.md"
        self.assertTrue(readme_file.exists())
        
        # Check subdirectory was copied
        sub_file = workspace.workspace_path / "subdir" / "sub_file.txt"
        self.assertTrue(sub_file.exists())
    
    def test_create_workspace_with_config(self):
        """Test creating a workspace with custom configuration."""
        config = WorkspaceConfig(
            workspace_id="test-workspace-3",
            use_isolation=False,
            environment_vars={"TEST_VAR": "test_value"}
        )
        
        workspace = self.workspace_manager.create_workspace(
            "test-workspace-3",
            config=config
        )
        
        self.assertEqual(workspace.config, config)
        self.assertEqual(workspace.config.environment_vars["TEST_VAR"], "test_value")
    
    def test_get_workspace(self):
        """Test retrieving a workspace."""
        # Create workspace
        workspace = self.workspace_manager.create_workspace("test-workspace-4")
        
        # Retrieve workspace
        retrieved = self.workspace_manager.get_workspace("test-workspace-4")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.workspace_id, "test-workspace-4")
        
        # Test non-existent workspace
        non_existent = self.workspace_manager.get_workspace("non-existent")
        self.assertIsNone(non_existent)
    
    def test_list_workspaces(self):
        """Test listing all workspaces."""
        # Initially no workspaces
        workspaces = self.workspace_manager.list_workspaces()
        self.assertEqual(len(workspaces), 0)
        
        # Create multiple workspaces
        self.workspace_manager.create_workspace("workspace-1")
        self.workspace_manager.create_workspace("workspace-2")
        self.workspace_manager.create_workspace("workspace-3")
        
        # List workspaces
        workspaces = self.workspace_manager.list_workspaces()
        self.assertEqual(len(workspaces), 3)
        
        workspace_ids = [w.workspace_id for w in workspaces]
        self.assertIn("workspace-1", workspace_ids)
        self.assertIn("workspace-2", workspace_ids)
        self.assertIn("workspace-3", workspace_ids)
    
    def test_get_workspace_path(self):
        """Test getting workspace path."""
        workspace = self.workspace_manager.create_workspace("test-workspace-5")
        
        path = self.workspace_manager.get_workspace_path("test-workspace-5")
        self.assertIsNotNone(path)
        self.assertEqual(path, workspace.workspace_path)
        
        # Test non-existent workspace
        path = self.workspace_manager.get_workspace_path("non-existent")
        self.assertIsNone(path)
    
    def test_setup_environment(self):
        """Test setting up workspace environment."""
        workspace = self.workspace_manager.create_workspace("test-workspace-6")
        
        # Setup environment
        result = self.workspace_manager.setup_environment(
            "test-workspace-6",
            environment_vars={"TEST_VAR": "test_value", "ANOTHER_VAR": "another_value"},
            python_path=["/custom/path"]
        )
        
        self.assertTrue(result)
        
        # Check that environment variables were set
        updated_workspace = self.workspace_manager.get_workspace("test-workspace-6")
        env_vars = updated_workspace.metadata.get('environment_vars', {})
        self.assertEqual(env_vars["TEST_VAR"], "test_value")
        self.assertEqual(env_vars["ANOTHER_VAR"], "another_value")
        
        # Check Python path
        python_path = updated_workspace.metadata.get('python_path', [])
        self.assertIn("/custom/path", python_path)
    
    def test_setup_environment_nonexistent_workspace(self):
        """Test setting up environment for non-existent workspace."""
        result = self.workspace_manager.setup_environment(
            "non-existent",
            environment_vars={"TEST_VAR": "test_value"}
        )
        
        self.assertFalse(result)
    
    def test_cleanup_workspace(self):
        """Test cleaning up a workspace."""
        workspace = self.workspace_manager.create_workspace("test-workspace-7")
        workspace_path = workspace.workspace_path
        
        # Verify workspace exists
        self.assertTrue(workspace_path.exists())
        self.assertIsNotNone(self.workspace_manager.get_workspace("test-workspace-7"))
        
        # Cleanup workspace
        result = self.workspace_manager.cleanup_workspace("test-workspace-7")
        self.assertTrue(result)
        
        # Verify workspace is removed
        self.assertIsNone(self.workspace_manager.get_workspace("test-workspace-7"))
        # Note: Directory might still exist briefly due to cleanup timing
    
    def test_cleanup_nonexistent_workspace(self):
        """Test cleaning up a non-existent workspace."""
        result = self.workspace_manager.cleanup_workspace("non-existent")
        self.assertFalse(result)  # Should return False but not crash
    
    def test_get_workspace_status(self):
        """Test getting workspace status."""
        source_dir = self._create_test_source_dir()
        workspace = self.workspace_manager.create_workspace(
            "test-workspace-8",
            source_path=source_dir
        )
        
        status = self.workspace_manager.get_workspace_status("test-workspace-8")
        
        self.assertEqual(status["workspace_id"], "test-workspace-8")
        self.assertIn("workspace_path", status)
        self.assertIn("source_path", status)
        self.assertIn("created_at", status)
        self.assertIn("last_accessed", status)
        self.assertIn("is_isolated", status)
        self.assertIn("metadata", status)
        self.assertFalse(status["is_isolated"])
    
    def test_get_status_nonexistent_workspace(self):
        """Test getting status for non-existent workspace."""
        status = self.workspace_manager.get_workspace_status("non-existent")
        self.assertIn("error", status)
        self.assertEqual(status["error"], "Workspace not found")
    
    def test_create_execution_context(self):
        """Test creating execution context for workspace."""
        workspace = self.workspace_manager.create_workspace("test-workspace-9")
        
        # Setup some environment variables
        self.workspace_manager.setup_environment(
            "test-workspace-9",
            environment_vars={"TEST_VAR": "test_value"}
        )
        
        # Create execution context
        context = self.workspace_manager.create_execution_context(
            "test-workspace-9",
            resource_limits=ResourceLimits(max_execution_time=60),
            security_level=SecurityLevel.HIGH
        )
        
        self.assertIsInstance(context, ExecutionContext)
        self.assertEqual(context.workspace_id, "test-workspace-9")
        self.assertEqual(context.environment_vars["TEST_VAR"], "test_value")
        self.assertEqual(context.resource_limits.max_execution_time, 60)
        self.assertEqual(context.security_level, SecurityLevel.HIGH)
        self.assertIsNotNone(context.artifacts_dir)
        self.assertTrue(context.artifacts_dir.exists())
    
    def test_create_execution_context_nonexistent_workspace(self):
        """Test creating execution context for non-existent workspace."""
        context = self.workspace_manager.create_execution_context("non-existent")
        self.assertIsNone(context)
    
    def test_concurrent_workspace_limit(self):
        """Test the concurrent workspace limit enforcement."""
        # Create workspaces up to the limit (3)
        for i in range(3):
            workspace = self.workspace_manager.create_workspace(f"workspace-{i}")
            self.assertIsNotNone(workspace)
        
        # Try to create one more (should trigger cleanup of oldest)
        workspace = self.workspace_manager.create_workspace("workspace-overflow")
        self.assertIsNotNone(workspace)
        
        # Should still have 3 workspaces (oldest was cleaned up)
        workspaces = self.workspace_manager.list_workspaces()
        self.assertEqual(len(workspaces), 3)
    
    def test_duplicate_workspace_id(self):
        """Test creating workspace with duplicate ID."""
        self.workspace_manager.create_workspace("duplicate-test")
        
        with self.assertRaises(ValueError) as context:
            self.workspace_manager.create_workspace("duplicate-test")
        
        self.assertIn("already exists", str(context.exception))
    
    def test_get_statistics(self):
        """Test getting workspace manager statistics."""
        # Create some workspaces
        self.workspace_manager.create_workspace("stats-1")
        self.workspace_manager.create_workspace("stats-2")
        
        stats = self.workspace_manager.get_statistics()
        
        self.assertEqual(stats["active_workspaces"], 2)
        self.assertEqual(stats["max_concurrent"], 3)
        self.assertFalse(stats["intelligent_features_enabled"])
        self.assertIn("base_workspace_dir", stats)
    
    def test_shutdown(self):
        """Test shutting down the workspace manager."""
        # Create some workspaces
        self.workspace_manager.create_workspace("shutdown-1")
        self.workspace_manager.create_workspace("shutdown-2")
        
        # Verify workspaces exist
        self.assertEqual(len(self.workspace_manager.list_workspaces()), 2)
        
        # Shutdown
        self.workspace_manager.shutdown()
        
        # Verify workspaces are cleaned up
        self.assertEqual(len(self.workspace_manager.list_workspaces()), 0)


class TestWorkspaceManagerWithIntelligentFeatures(unittest.TestCase):
    """Test WorkspaceManager with intelligent features enabled."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dirs = []
        self.temp_base_dir = tempfile.mkdtemp()
        self.temp_dirs.append(self.temp_base_dir)
    
    def tearDown(self):
        """Clean up test environment."""
        # Clean up temporary directories
        for temp_dir in self.temp_dirs:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
    
    @patch('sandbox.core.workspace_manager.WorkspaceLifecycleManager')
    def test_intelligent_features_initialization(self, mock_lifecycle_manager):
        """Test initialization with intelligent features."""
        mock_lifecycle_instance = Mock()
        mock_lifecycle_manager.return_value = mock_lifecycle_instance
        
        workspace_manager = WorkspaceManager(
            base_workspace_dir=self.temp_base_dir,
            enable_intelligent_features=True
        )
        
        # Verify lifecycle manager was created
        mock_lifecycle_manager.assert_called_once()
        self.assertTrue(workspace_manager._intelligent_enabled)
        self.assertEqual(workspace_manager._lifecycle_manager, mock_lifecycle_instance)
        
        # Cleanup
        workspace_manager.shutdown()
    
    @patch('sandbox.core.workspace_manager.WorkspaceLifecycleManager')
    def test_intelligent_features_failure_fallback(self, mock_lifecycle_manager):
        """Test fallback when intelligent features fail to initialize."""
        mock_lifecycle_manager.side_effect = Exception("Failed to initialize")
        
        workspace_manager = WorkspaceManager(
            base_workspace_dir=self.temp_base_dir,
            enable_intelligent_features=True
        )
        
        # Should fall back to simple mode
        self.assertFalse(workspace_manager._intelligent_enabled)
        self.assertIsNone(workspace_manager._lifecycle_manager)
        
        # Cleanup
        workspace_manager.shutdown()
    
    @patch('sandbox.core.workspace_manager.WorkspaceLifecycleManager')
    def test_create_intelligent_workspace(self, mock_lifecycle_manager):
        """Test creating workspace with intelligent features."""
        # Setup mock
        mock_lifecycle_instance = Mock()
        mock_session = Mock()
        mock_session.workspace.sandbox_path = "/tmp/intelligent-workspace"
        mock_lifecycle_instance.create_workspace.return_value = mock_session
        mock_lifecycle_manager.return_value = mock_lifecycle_instance
        
        workspace_manager = WorkspaceManager(
            base_workspace_dir=self.temp_base_dir,
            enable_intelligent_features=True
        )
        
        # Create workspace with isolation
        config = WorkspaceConfig(
            workspace_id="intelligent-test",
            use_isolation=True,
            use_docker=True
        )
        
        workspace = workspace_manager.create_workspace(
            "intelligent-test",
            source_path="/tmp/source",
            config=config
        )
        
        # Verify intelligent workspace was created
        mock_lifecycle_instance.create_workspace.assert_called_once()
        self.assertTrue(workspace.is_isolated)
        self.assertEqual(workspace.session, mock_session)
        self.assertIn("intelligent_workspace", workspace.metadata)
        
        # Cleanup
        workspace_manager.shutdown()


if __name__ == '__main__':
    # Set up logging for tests
    import logging
    logging.basicConfig(level=logging.WARNING)
    
    # Run the tests
    unittest.main(verbosity=2)