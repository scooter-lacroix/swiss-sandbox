"""
Unit tests for SandboxExecutor with logging integration.
"""

import unittest
import tempfile
import shutil
import os
import sqlite3
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.sandbox.intelligent.executor.sandbox_executor import SandboxExecutor
from src.sandbox.intelligent.logger import create_logger
from src.sandbox.intelligent.types import CommandInfo


class TestSandboxExecutor(unittest.TestCase):
    """Test cases for SandboxExecutor implementation."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.workspace_path = Path(self.test_dir) / "workspace"
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        
        # Create a test database logger
        self.db_path = self.workspace_path / ".sandbox" / "test_commands.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger = create_logger("database", str(self.db_path))
        
        self.executor = SandboxExecutor(
            workspace_path=str(self.workspace_path),
            logger=self.logger,
            session_id="test_session",
            task_id="test_task"
        )
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test SandboxExecutor initialization."""
        self.assertEqual(self.executor.workspace_path, self.workspace_path)
        self.assertTrue(self.executor.isolation_enabled)
        self.assertEqual(self.executor.session_id, "test_session")
        self.assertEqual(self.executor.task_id, "test_task")
        self.assertIsNotNone(self.executor.logger)
        
        # Check that workspace and sandbox directories were created
        self.assertTrue(self.workspace_path.exists())
        self.assertTrue((self.workspace_path / ".sandbox").exists())
        self.assertTrue((self.workspace_path / ".sandbox" / "tmp").exists())
    
    def test_execute_command_success(self):
        """Test successful command execution."""
        result = self.executor.execute_command("echo 'Hello World'")
        
        self.assertIsInstance(result, CommandInfo)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Hello World", result.output)
        self.assertEqual(result.error_output, "")
        self.assertGreater(result.duration, 0)
        
        # Verify command was logged to database
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM command_info WHERE command LIKE '%echo%'")
            count = cursor.fetchone()[0]
            self.assertGreater(count, 0)
    
    def test_execute_command_failure(self):
        """Test command execution failure."""
        result = self.executor.execute_command("nonexistent_command_xyz")
        
        self.assertIsInstance(result, CommandInfo)
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("not found", result.error_output.lower())
        
        # Verify failed command was logged
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM command_info WHERE exit_code != 0")
            count = cursor.fetchone()[0]
            self.assertGreater(count, 0)
    
    def test_execute_command_timeout(self):
        """Test command execution timeout."""
        result = self.executor.execute_command("sleep 10", timeout=1)
        
        self.assertIsInstance(result, CommandInfo)
        self.assertEqual(result.exit_code, -1)
        self.assertIn("timed out", result.error_output.lower())
    
    def test_execute_command_with_working_directory(self):
        """Test command execution with custom working directory."""
        # Create a subdirectory
        subdir = self.workspace_path / "subdir"
        subdir.mkdir()
        
        result = self.executor.execute_command("pwd", working_dir=str(subdir))
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn("subdir", result.output)
    
    def test_execute_command_isolation_violation(self):
        """Test that commands outside workspace are blocked when isolation is enabled."""
        with self.assertRaises(PermissionError):
            self.executor.execute_command("echo test", working_dir="/tmp")
    
    def test_execute_command_with_env_vars(self):
        """Test command execution with custom environment variables."""
        result = self.executor.execute_command(
            "echo $TEST_VAR", 
            env_vars={"TEST_VAR": "test_value"}
        )
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test_value", result.output)
    
    def test_create_file(self):
        """Test file creation with logging."""
        file_path = "test_file.txt"
        content = "This is a test file"
        
        success = self.executor.create_file(file_path, content)
        
        self.assertTrue(success)
        
        # Verify file was created
        full_path = self.workspace_path / file_path
        self.assertTrue(full_path.exists())
        self.assertEqual(full_path.read_text(), content)
        
        # Verify file creation was logged
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM file_changes WHERE change_type = 'create'")
            count = cursor.fetchone()[0]
            self.assertGreater(count, 0)
    
    def test_create_file_with_subdirectories(self):
        """Test file creation in subdirectories."""
        file_path = "subdir/nested/test_file.txt"
        content = "Nested file content"
        
        success = self.executor.create_file(file_path, content)
        
        self.assertTrue(success)
        
        # Verify file and directories were created
        full_path = self.workspace_path / file_path
        self.assertTrue(full_path.exists())
        self.assertEqual(full_path.read_text(), content)
    
    def test_modify_file(self):
        """Test file modification with logging."""
        file_path = "modify_test.txt"
        original_content = "Original content"
        new_content = "Modified content"
        
        # Create the file first
        full_path = self.workspace_path / file_path
        full_path.write_text(original_content)
        
        success = self.executor.modify_file(file_path, new_content)
        
        self.assertTrue(success)
        self.assertEqual(full_path.read_text(), new_content)
        
        # Verify modification was logged
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM file_changes WHERE change_type = 'modify'")
            count = cursor.fetchone()[0]
            self.assertGreater(count, 0)
    
    def test_delete_file(self):
        """Test file deletion with logging."""
        file_path = "delete_test.txt"
        content = "File to be deleted"
        
        # Create the file first
        full_path = self.workspace_path / file_path
        full_path.write_text(content)
        self.assertTrue(full_path.exists())
        
        success = self.executor.delete_file(file_path)
        
        self.assertTrue(success)
        self.assertFalse(full_path.exists())
        
        # Verify deletion was logged
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM file_changes WHERE change_type = 'delete'")
            count = cursor.fetchone()[0]
            self.assertGreater(count, 0)
    
    def test_file_operations_isolation(self):
        """Test that file operations respect workspace isolation."""
        with self.assertRaises(PermissionError):
            self.executor.create_file("/tmp/outside_workspace.txt", "content")
        
        with self.assertRaises(PermissionError):
            self.executor.modify_file("/tmp/outside_workspace.txt", "content")
        
        with self.assertRaises(PermissionError):
            self.executor.delete_file("/tmp/outside_workspace.txt")
    
    def test_install_package_pip(self):
        """Test package installation with pip."""
        # Mock the execute_command method to simulate successful installation
        with patch.object(self.executor, 'execute_command') as mock_execute:
            mock_execute.return_value = CommandInfo(
                command="pip install requests",
                working_directory=str(self.workspace_path),
                output="Successfully installed requests",
                error_output="",
                exit_code=0,
                duration=1.0
            )
            
            success = self.executor.install_package("requests", "pip")
            
            self.assertTrue(success)
            mock_execute.assert_called_once_with("pip install requests")
    
    def test_install_package_npm(self):
        """Test package installation with npm."""
        # Create package.json to trigger npm detection
        (self.workspace_path / "package.json").write_text('{"name": "test"}')
        
        with patch.object(self.executor, 'execute_command') as mock_execute:
            mock_execute.return_value = CommandInfo(
                command="npm install lodash",
                working_directory=str(self.workspace_path),
                output="added 1 package",
                error_output="",
                exit_code=0,
                duration=2.0
            )
            
            success = self.executor.install_package("lodash", "auto")
            
            self.assertTrue(success)
            mock_execute.assert_called_once_with("npm install lodash")
    
    def test_install_package_yarn(self):
        """Test package installation with yarn when yarn.lock exists."""
        # Create package.json and yarn.lock to trigger yarn detection
        (self.workspace_path / "package.json").write_text('{"name": "test"}')
        (self.workspace_path / "yarn.lock").write_text("")
        
        with patch.object(self.executor, 'execute_command') as mock_execute:
            mock_execute.return_value = CommandInfo(
                command="yarn add lodash",
                working_directory=str(self.workspace_path),
                output="success Saved 1 new dependency",
                error_output="",
                exit_code=0,
                duration=2.0
            )
            
            success = self.executor.install_package("lodash", "auto")
            
            self.assertTrue(success)
            mock_execute.assert_called_once_with("yarn add lodash")
    
    def test_install_package_unsupported_manager(self):
        """Test handling of unsupported package manager."""
        success = self.executor.install_package("test", "unsupported_manager")
        
        self.assertFalse(success)
        
        # Verify error was logged
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM error_info WHERE error_type = 'UnsupportedPackageManager'")
            count = cursor.fetchone()[0]
            self.assertGreater(count, 0)
    
    def test_execute_shell_script(self):
        """Test shell script execution."""
        script_content = """#!/bin/bash
echo "Script executed successfully"
exit 0
"""
        
        result = self.executor.execute_shell_script(script_content, "test_script.sh")
        
        self.assertIsInstance(result, CommandInfo)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Script executed successfully", result.output)
    
    def test_configure_system(self):
        """Test system configuration commands."""
        config_commands = [
            "echo 'Setting up environment'",
            "mkdir -p config_dir",
            "echo 'Configuration complete'"
        ]
        
        results = self.executor.configure_system(config_commands)
        
        self.assertEqual(len(results), 3)
        for result in results:
            self.assertIsInstance(result, CommandInfo)
            self.assertEqual(result.exit_code, 0)
        
        # Verify config directory was created
        self.assertTrue((self.workspace_path / "config_dir").exists())
    
    def test_get_execution_summary(self):
        """Test execution summary generation."""
        # Perform some operations
        self.executor.execute_command("echo 'test'")
        self.executor.create_file("summary_test.txt", "content")
        
        summary = self.executor.get_execution_summary()
        
        self.assertIsInstance(summary, dict)
        self.assertEqual(summary["session_id"], "test_session")
        self.assertEqual(summary["task_id"], "test_task")
        self.assertIn("total_actions", summary)
        self.assertIn("commands_executed", summary)
        self.assertIn("files_modified", summary)
    
    def test_export_execution_log(self):
        """Test execution log export."""
        # Perform some operations
        self.executor.execute_command("echo 'export test'")
        self.executor.create_file("export_test.txt", "content")
        
        # Test JSON export
        json_log = self.executor.export_execution_log("json")
        self.assertIsInstance(json_log, str)
        self.assertIn("export test", json_log)
        
        # Test CSV export
        csv_log = self.executor.export_execution_log("csv")
        self.assertIsInstance(csv_log, str)
        self.assertIn("export test", csv_log)
    
    def test_cleanup_session(self):
        """Test session cleanup."""
        # Create some temporary files
        tmp_file = self.workspace_path / ".sandbox" / "tmp" / "temp_file.txt"
        tmp_file.write_text("temporary content")
        self.assertTrue(tmp_file.exists())
        
        self.executor.cleanup_session()
        
        # Verify temporary files were cleaned up
        self.assertFalse(tmp_file.exists())
        # But tmp directory should still exist
        self.assertTrue((self.workspace_path / ".sandbox" / "tmp").exists())
    
    def test_detect_package_manager(self):
        """Test package manager detection."""
        # Test npm detection
        (self.workspace_path / "package.json").write_text('{"name": "test"}')
        self.assertEqual(self.executor._detect_package_manager(), "npm")
        
        # Test yarn detection (yarn.lock takes precedence)
        (self.workspace_path / "yarn.lock").write_text("")
        self.assertEqual(self.executor._detect_package_manager(), "yarn")
        
        # Clean up and test pip detection
        (self.workspace_path / "package.json").unlink()
        (self.workspace_path / "yarn.lock").unlink()
        (self.workspace_path / "requirements.txt").write_text("requests==2.25.1")
        self.assertEqual(self.executor._detect_package_manager(), "pip")
        
        # Test pyproject.toml detection
        (self.workspace_path / "requirements.txt").unlink()
        (self.workspace_path / "pyproject.toml").write_text("[tool.poetry]")
        self.assertEqual(self.executor._detect_package_manager(), "pip")
    
    def test_resolve_path_security(self):
        """Test path resolution security."""
        # Test normal path resolution
        path = self.executor._resolve_path("test.txt")
        self.assertEqual(path, self.workspace_path / "test.txt")
        
        # Test absolute path within workspace
        abs_path = str(self.workspace_path / "abs_test.txt")
        resolved = self.executor._resolve_path(abs_path)
        self.assertEqual(resolved, Path(abs_path))
        
        # Test path outside workspace (should raise PermissionError)
        with self.assertRaises(PermissionError):
            self.executor._resolve_path("/tmp/outside.txt")
        
        with self.assertRaises(PermissionError):
            self.executor._resolve_path("../outside.txt")
    
    def test_logging_integration(self):
        """Test comprehensive logging integration."""
        # Perform various operations
        self.executor.execute_command("echo 'logging test'")
        self.executor.create_file("log_test.txt", "content")
        self.executor.modify_file("log_test.txt", "modified content")
        self.executor.delete_file("log_test.txt")
        
        # Verify all operations were logged
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            
            # Check command logging (via actions table)
            cursor.execute("""
                SELECT COUNT(*) FROM command_info ci 
                JOIN actions a ON ci.action_id = a.id 
                WHERE a.session_id = ?
            """, ("test_session",))
            command_count = cursor.fetchone()[0]
            self.assertGreater(command_count, 0)
            
            # Check file change logging (via actions table)
            cursor.execute("""
                SELECT COUNT(*) FROM file_changes fc 
                JOIN actions a ON fc.action_id = a.id 
                WHERE a.session_id = ?
            """, ("test_session",))
            file_change_count = cursor.fetchone()[0]
            self.assertEqual(file_change_count, 3)  # create, modify, delete
            
            # Check action logging
            cursor.execute("SELECT COUNT(*) FROM actions WHERE session_id = ?", ("test_session",))
            action_count = cursor.fetchone()[0]
            self.assertGreater(action_count, 0)
    
    def test_error_logging(self):
        """Test error logging functionality."""
        # Mock the write_text method to raise a non-permission error
        with patch.object(Path, 'write_text', side_effect=OSError("Disk full")):
            success = self.executor.create_file("test.txt", "content")
            self.assertFalse(success)
        
        # Verify error was logged (via actions table)
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM error_info ei 
                JOIN actions a ON ei.action_id = a.id 
                WHERE a.session_id = ?
            """, ("test_session",))
            error_count = cursor.fetchone()[0]
            self.assertGreater(error_count, 0)


class TestSandboxExecutorIntegration(unittest.TestCase):
    """Integration tests for SandboxExecutor with real operations."""
    
    def setUp(self):
        """Set up integration test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.workspace_path = Path(self.test_dir) / "integration_workspace"
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        
        self.executor = SandboxExecutor(
            workspace_path=str(self.workspace_path),
            session_id="integration_test",
            task_id="integration_task"
        )
    
    def tearDown(self):
        """Clean up integration test environment."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_python_development_workflow(self):
        """Test a complete Python development workflow."""
        # Create a Python project structure
        self.executor.create_file("main.py", """
def hello_world():
    return "Hello, World!"

if __name__ == "__main__":
    print(hello_world())
""")
        
        self.executor.create_file("requirements.txt", "requests==2.25.1\n")
        
        self.executor.create_file("test_main.py", """
import unittest
from main import hello_world

class TestMain(unittest.TestCase):
    def test_hello_world(self):
        self.assertEqual(hello_world(), "Hello, World!")

if __name__ == "__main__":
    unittest.main()
""")
        
        # Run the Python script
        result = self.executor.execute_command("python main.py")
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Hello, World!", result.output)
        
        # Run the tests
        result = self.executor.execute_command("python -m unittest test_main.py")
        self.assertEqual(result.exit_code, 0)
        
        # Get execution summary
        summary = self.executor.get_execution_summary()
        self.assertGreater(summary["total_actions"], 0)
        self.assertGreater(summary["commands_executed"], 0)
        self.assertGreater(summary["files_modified"], 0)
    
    def test_nodejs_development_workflow(self):
        """Test a Node.js development workflow."""
        # Create package.json
        self.executor.create_file("package.json", """{
  "name": "test-project",
  "version": "1.0.0",
  "description": "Test project",
  "main": "index.js",
  "scripts": {
    "test": "echo \\"Error: no test specified\\" && exit 1"
  }
}""")
        
        # Create main JavaScript file
        self.executor.create_file("index.js", """
function greet(name) {
    return `Hello, ${name}!`;
}

console.log(greet('World'));
module.exports = { greet };
""")
        
        # Run the Node.js script
        result = self.executor.execute_command("node index.js")
        if result.exit_code == 0:  # Only test if Node.js is available
            self.assertIn("Hello, World!", result.output)
    
    def test_git_operations(self):
        """Test Git operations within the sandbox."""
        # Initialize git repository
        result = self.executor.execute_command("git init")
        if result.exit_code != 0:
            self.skipTest("Git not available in test environment")
        
        # Configure git
        self.executor.execute_command("git config user.email 'test@example.com'")
        self.executor.execute_command("git config user.name 'Test User'")
        
        # Create and commit a file
        self.executor.create_file("README.md", "# Test Project\n\nThis is a test project.")
        
        result = self.executor.execute_command("git add README.md")
        self.assertEqual(result.exit_code, 0)
        
        result = self.executor.execute_command("git commit -m 'Initial commit'")
        self.assertEqual(result.exit_code, 0)
        
        # Check git status
        result = self.executor.execute_command("git status")
        self.assertEqual(result.exit_code, 0)
        self.assertIn("nothing to commit", result.output)


if __name__ == '__main__':
    unittest.main()