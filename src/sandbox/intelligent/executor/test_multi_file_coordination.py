"""
Integration tests for multi-file operation coordination.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from .multi_file_coordinator import (
    MultiFileCoordinator, FileOperation, FileConflict, MultiFileTransaction
)
from .engine import SandboxCommandExecutor


class TestMultiFileCoordinator(unittest.TestCase):
    """Test cases for MultiFileCoordinator."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.coordinator = MultiFileCoordinator(self.temp_dir)
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_create_transaction(self):
        """Test creating a multi-file transaction."""
        operations = [
            FileOperation(
                operation_type="create",
                file_path="file1.txt",
                content="Content 1"
            ),
            FileOperation(
                operation_type="create",
                file_path="file2.txt",
                content="Content 2"
            )
        ]
        
        transaction = self.coordinator.create_transaction("test_tx", operations)
        
        self.assertEqual(transaction.transaction_id, "test_tx")
        self.assertEqual(len(transaction.operations), 2)
        self.assertIn("test_tx", self.coordinator.active_transactions)
    
    def test_execute_simple_transaction(self):
        """Test executing a simple transaction without conflicts."""
        operations = [
            FileOperation(
                operation_type="create",
                file_path="file1.txt",
                content="Hello World"
            ),
            FileOperation(
                operation_type="create",
                file_path="subdir/file2.txt",
                content="Hello Subdir"
            )
        ]
        
        transaction = self.coordinator.create_transaction("simple_tx", operations)
        success = self.coordinator.execute_transaction("simple_tx")
        
        self.assertTrue(success)
        
        # Verify files were created
        file1_path = Path(self.temp_dir) / "file1.txt"
        file2_path = Path(self.temp_dir) / "subdir" / "file2.txt"
        
        self.assertTrue(file1_path.exists())
        self.assertTrue(file2_path.exists())
        self.assertEqual(file1_path.read_text(), "Hello World")
        self.assertEqual(file2_path.read_text(), "Hello Subdir")
    
    def test_execute_transaction_with_dependencies(self):
        """Test executing a transaction with operation dependencies."""
        operations = [
            FileOperation(
                operation_type="create",
                file_path="base.txt",
                content="Base content"
            ),
            FileOperation(
                operation_type="create",
                file_path="dependent.txt",
                content="Dependent content",
                dependencies=["base.txt"]
            )
        ]
        
        transaction = self.coordinator.create_transaction("dep_tx", operations)
        success = self.coordinator.execute_transaction("dep_tx")
        
        self.assertTrue(success)
        
        # Verify both files were created
        base_path = Path(self.temp_dir) / "base.txt"
        dep_path = Path(self.temp_dir) / "dependent.txt"
        
        self.assertTrue(base_path.exists())
        self.assertTrue(dep_path.exists())
    
    def test_detect_content_conflicts(self):
        """Test detection of content conflicts."""
        operations = [
            FileOperation(
                operation_type="create",
                file_path="conflict.txt",
                content="Content 1"
            ),
            FileOperation(
                operation_type="modify",
                file_path="conflict.txt",
                content="Content 2"
            )
        ]
        
        transaction = self.coordinator.create_transaction("conflict_tx", operations)
        
        self.assertGreater(len(transaction.conflicts), 0)
        conflict = transaction.conflicts[0]
        self.assertEqual(conflict.conflict_type, "content")
        self.assertIn("conflict.txt", conflict.affected_files)
    
    def test_detect_circular_dependencies(self):
        """Test detection of circular dependencies."""
        operations = [
            FileOperation(
                operation_type="create",
                file_path="file1.txt",
                content="Content 1",
                dependencies=["file2.txt"]
            ),
            FileOperation(
                operation_type="create",
                file_path="file2.txt",
                content="Content 2",
                dependencies=["file1.txt"]
            )
        ]
        
        transaction = self.coordinator.create_transaction("circular_tx", operations)
        
        circular_conflicts = [c for c in transaction.conflicts if c.conflict_type == "circular"]
        self.assertGreater(len(circular_conflicts), 0)
        self.assertEqual(circular_conflicts[0].severity, "critical")
    
    def test_rollback_on_failure(self):
        """Test transaction rollback when an operation fails."""
        # Create an existing file to modify
        existing_file = Path(self.temp_dir) / "existing.txt"
        existing_file.write_text("Original content")
        
        operations = [
            FileOperation(
                operation_type="modify",
                file_path="existing.txt",
                content="Modified content"
            ),
            FileOperation(
                operation_type="create",
                file_path="/invalid/path/file.txt",  # This will fail
                content="This should not be created"
            )
        ]
        
        transaction = self.coordinator.create_transaction("rollback_tx", operations)
        
        with self.assertRaises(RuntimeError):
            self.coordinator.execute_transaction("rollback_tx")
        
        # Verify rollback occurred - original file should be restored
        self.assertTrue(existing_file.exists())
        self.assertEqual(existing_file.read_text(), "Original content")
    
    def test_backup_and_restore(self):
        """Test backup creation and restoration."""
        # Create existing files
        file1 = Path(self.temp_dir) / "file1.txt"
        file2 = Path(self.temp_dir) / "file2.txt"
        file1.write_text("Original 1")
        file2.write_text("Original 2")
        
        operations = [
            FileOperation(
                operation_type="modify",
                file_path="file1.txt",
                content="Modified 1"
            ),
            FileOperation(
                operation_type="delete",
                file_path="file2.txt"
            )
        ]
        
        transaction = self.coordinator.create_transaction("backup_tx", operations)
        
        # Execute successfully
        success = self.coordinator.execute_transaction("backup_tx")
        self.assertTrue(success)
        
        # Verify changes were applied
        self.assertEqual(file1.read_text(), "Modified 1")
        self.assertFalse(file2.exists())
    
    def test_operation_ordering_by_dependencies(self):
        """Test that operations are executed in dependency order."""
        execution_order = []
        
        # Mock the _execute_operation method to track execution order
        original_execute = self.coordinator._execute_operation
        
        def mock_execute(operation, transaction):
            execution_order.append(operation.file_path)
            return original_execute(operation, transaction)
        
        self.coordinator._execute_operation = mock_execute
        
        operations = [
            FileOperation(
                operation_type="create",
                file_path="c.txt",
                content="C",
                dependencies=["a.txt", "b.txt"]
            ),
            FileOperation(
                operation_type="create",
                file_path="a.txt",
                content="A"
            ),
            FileOperation(
                operation_type="create",
                file_path="b.txt",
                content="B",
                dependencies=["a.txt"]
            )
        ]
        
        transaction = self.coordinator.create_transaction("order_tx", operations)
        success = self.coordinator.execute_transaction("order_tx")
        
        self.assertTrue(success)
        
        # Verify execution order respects dependencies
        self.assertEqual(execution_order[0], "a.txt")  # No dependencies
        self.assertEqual(execution_order[1], "b.txt")  # Depends on a.txt
        self.assertEqual(execution_order[2], "c.txt")  # Depends on a.txt and b.txt
    
    def test_conflict_resolution(self):
        """Test conflict resolution mechanisms."""
        operations = [
            FileOperation(
                operation_type="modify",
                file_path="conflict.txt",
                content="Content 1"
            ),
            FileOperation(
                operation_type="modify",
                file_path="conflict.txt",
                content="Content 2"
            )
        ]
        
        transaction = self.coordinator.create_transaction("resolve_tx", operations)
        
        # Should have a content conflict
        self.assertGreater(len(transaction.conflicts), 0)
        
        # Resolve the conflict by merging
        success = self.coordinator.resolve_conflict("resolve_tx", 0, "merge")
        self.assertTrue(success)
        
        # Conflict should be removed
        updated_transaction = self.coordinator.get_transaction_status("resolve_tx")
        self.assertEqual(len(updated_transaction.conflicts), 0)
    
    def test_missing_dependency_detection(self):
        """Test detection of missing dependencies."""
        operations = [
            FileOperation(
                operation_type="create",
                file_path="dependent.txt",
                content="Depends on missing file",
                dependencies=["missing.txt"]
            )
        ]
        
        transaction = self.coordinator.create_transaction("missing_tx", operations)
        
        dependency_conflicts = [c for c in transaction.conflicts if c.conflict_type == "dependency"]
        self.assertGreater(len(dependency_conflicts), 0)
        self.assertIn("missing.txt", dependency_conflicts[0].description)


class TestSandboxCommandExecutorMultiFile(unittest.TestCase):
    """Test cases for SandboxCommandExecutor multi-file operations."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.executor = SandboxCommandExecutor(self.temp_dir)
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_create_file_operation(self):
        """Test creating FileOperation objects."""
        operation = self.executor.create_file_operation(
            operation_type="create",
            file_path="test.txt",
            content="Test content",
            dependencies=["dep.txt"]
        )
        
        self.assertEqual(operation.operation_type, "create")
        self.assertEqual(operation.file_path, "test.txt")
        self.assertEqual(operation.content, "Test content")
        self.assertEqual(operation.dependencies, ["dep.txt"])
    
    def test_execute_multi_file_operation_success(self):
        """Test successful multi-file operation execution."""
        operations = [
            self.executor.create_file_operation(
                operation_type="create",
                file_path="file1.txt",
                content="Content 1"
            ),
            self.executor.create_file_operation(
                operation_type="create",
                file_path="file2.txt",
                content="Content 2"
            )
        ]
        
        success = self.executor.execute_multi_file_operation(operations)
        
        self.assertTrue(success)
        
        # Verify files were created
        file1_path = Path(self.temp_dir) / "file1.txt"
        file2_path = Path(self.temp_dir) / "file2.txt"
        
        self.assertTrue(file1_path.exists())
        self.assertTrue(file2_path.exists())
        
        # Verify file changes were tracked
        changes = self.executor.get_file_changes()
        self.assertEqual(len(changes), 2)
        self.assertEqual(changes[0].change_type, "create")
        self.assertEqual(changes[1].change_type, "create")
    
    def test_execute_multi_file_operation_with_conflicts(self):
        """Test multi-file operation with critical conflicts."""
        operations = [
            self.executor.create_file_operation(
                operation_type="create",
                file_path="conflict.txt",
                content="Content 1"
            ),
            self.executor.create_file_operation(
                operation_type="delete",
                file_path="conflict.txt"
            )
        ]
        
        success = self.executor.execute_multi_file_operation(operations)
        
        # Should fail due to critical conflict
        self.assertFalse(success)
    
    def test_multi_file_operation_with_dependencies(self):
        """Test multi-file operation with proper dependency handling."""
        operations = [
            self.executor.create_file_operation(
                operation_type="create",
                file_path="base.txt",
                content="Base file"
            ),
            self.executor.create_file_operation(
                operation_type="create",
                file_path="dependent.txt",
                content="Dependent file",
                dependencies=["base.txt"]
            ),
            self.executor.create_file_operation(
                operation_type="create",
                file_path="final.txt",
                content="Final file",
                dependencies=["dependent.txt"]
            )
        ]
        
        success = self.executor.execute_multi_file_operation(operations)
        
        self.assertTrue(success)
        
        # Verify all files were created
        base_path = Path(self.temp_dir) / "base.txt"
        dep_path = Path(self.temp_dir) / "dependent.txt"
        final_path = Path(self.temp_dir) / "final.txt"
        
        self.assertTrue(base_path.exists())
        self.assertTrue(dep_path.exists())
        self.assertTrue(final_path.exists())
        
        # Verify file changes were tracked in correct order
        changes = self.executor.get_file_changes()
        self.assertEqual(len(changes), 3)
        
        # Changes should be recorded in dependency order
        change_files = [change.file_path.split('/')[-1] for change in changes]
        self.assertEqual(change_files[0], "base.txt")
        self.assertEqual(change_files[1], "dependent.txt")
        self.assertEqual(change_files[2], "final.txt")


class TestComplexMultiFileScenarios(unittest.TestCase):
    """Test cases for complex multi-file scenarios."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.coordinator = MultiFileCoordinator(self.temp_dir)
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_large_scale_refactoring_scenario(self):
        """Test a large-scale refactoring scenario with multiple files."""
        # Create initial files
        initial_files = {
            "src/main.py": "from utils import helper\n\ndef main():\n    helper.do_something()",
            "src/utils.py": "def do_something():\n    print('Hello')",
            "tests/test_main.py": "import main\n\ndef test_main():\n    main.main()"
        }
        
        for file_path, content in initial_files.items():
            full_path = Path(self.temp_dir) / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
        
        # Refactoring operations: rename utils.py to helpers.py and update imports
        operations = [
            FileOperation(
                operation_type="create",
                file_path="src/helpers.py",
                content="def do_something():\n    print('Hello from helpers')"
            ),
            FileOperation(
                operation_type="modify",
                file_path="src/main.py",
                content="from helpers import do_something\n\ndef main():\n    do_something()",
                dependencies=["src/helpers.py"]
            ),
            FileOperation(
                operation_type="delete",
                file_path="src/utils.py",
                dependencies=["src/main.py"]
            )
        ]
        
        transaction = self.coordinator.create_transaction("refactor_tx", operations)
        success = self.coordinator.execute_transaction("refactor_tx")
        
        self.assertTrue(success)
        
        # Verify refactoring was successful
        helpers_path = Path(self.temp_dir) / "src" / "helpers.py"
        main_path = Path(self.temp_dir) / "src" / "main.py"
        utils_path = Path(self.temp_dir) / "src" / "utils.py"
        
        self.assertTrue(helpers_path.exists())
        self.assertTrue(main_path.exists())
        self.assertFalse(utils_path.exists())
        
        # Verify content was updated correctly
        main_content = main_path.read_text()
        self.assertIn("from helpers import", main_content)
        self.assertNotIn("from utils import", main_content)
    
    def test_database_migration_scenario(self):
        """Test a database migration-like scenario with multiple dependent files."""
        operations = [
            # Create migration file
            FileOperation(
                operation_type="create",
                file_path="migrations/001_create_users.sql",
                content="CREATE TABLE users (id INT, name VARCHAR(100));"
            ),
            # Create model file that depends on migration
            FileOperation(
                operation_type="create",
                file_path="models/user.py",
                content="class User:\n    def __init__(self, id, name):\n        self.id = id\n        self.name = name",
                dependencies=["migrations/001_create_users.sql"]
            ),
            # Create service that depends on model
            FileOperation(
                operation_type="create",
                file_path="services/user_service.py",
                content="from models.user import User\n\nclass UserService:\n    def create_user(self, name):\n        return User(1, name)",
                dependencies=["models/user.py"]
            ),
            # Create API that depends on service
            FileOperation(
                operation_type="create",
                file_path="api/user_api.py",
                content="from services.user_service import UserService\n\ndef create_user_endpoint(name):\n    service = UserService()\n    return service.create_user(name)",
                dependencies=["services/user_service.py"]
            )
        ]
        
        transaction = self.coordinator.create_transaction("migration_tx", operations)
        success = self.coordinator.execute_transaction("migration_tx")
        
        self.assertTrue(success)
        
        # Verify all files were created in correct order
        migration_path = Path(self.temp_dir) / "migrations" / "001_create_users.sql"
        model_path = Path(self.temp_dir) / "models" / "user.py"
        service_path = Path(self.temp_dir) / "services" / "user_service.py"
        api_path = Path(self.temp_dir) / "api" / "user_api.py"
        
        self.assertTrue(migration_path.exists())
        self.assertTrue(model_path.exists())
        self.assertTrue(service_path.exists())
        self.assertTrue(api_path.exists())
    
    def test_rollback_complex_scenario(self):
        """Test rollback in a complex scenario with partial completion."""
        # Create some existing files
        existing_files = {
            "config.py": "DEBUG = True",
            "app.py": "from config import DEBUG\n\nif DEBUG:\n    print('Debug mode')"
        }
        
        for file_path, content in existing_files.items():
            full_path = Path(self.temp_dir) / file_path
            full_path.write_text(content)
        
        operations = [
            # This should succeed
            FileOperation(
                operation_type="modify",
                file_path="config.py",
                content="DEBUG = False\nPRODUCTION = True"
            ),
            # This should succeed
            FileOperation(
                operation_type="create",
                file_path="new_feature.py",
                content="def new_feature():\n    return 'New feature'",
                dependencies=["config.py"]
            ),
            # This should fail (invalid path)
            FileOperation(
                operation_type="create",
                file_path="/invalid/absolute/path.py",
                content="This will fail",
                dependencies=["new_feature.py"]
            )
        ]
        
        transaction = self.coordinator.create_transaction("complex_rollback_tx", operations)
        
        with self.assertRaises(RuntimeError):
            self.coordinator.execute_transaction("complex_rollback_tx")
        
        # Verify rollback occurred
        config_path = Path(self.temp_dir) / "config.py"
        new_feature_path = Path(self.temp_dir) / "new_feature.py"
        
        # Original file should be restored
        self.assertTrue(config_path.exists())
        self.assertEqual(config_path.read_text(), "DEBUG = True")
        
        # New file should not exist (rolled back)
        self.assertFalse(new_feature_path.exists())


if __name__ == '__main__':
    unittest.main()