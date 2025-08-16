"""
Integration tests for WorkspaceManager with ExecutionEngine.
"""

import os
import tempfile
import unittest
import shutil
from pathlib import Path

# Import the modules
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sandbox.core.workspace_manager import WorkspaceManager, WorkspaceConfig
from sandbox.core.execution_engine import ExecutionEngine
from sandbox.core.types import ResourceLimits, SecurityLevel


class TestWorkspaceExecutionIntegration(unittest.TestCase):
    """Test integration between WorkspaceManager and ExecutionEngine."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dirs = []
        self.temp_base_dir = tempfile.mkdtemp()
        self.temp_dirs.append(self.temp_base_dir)
        
        # Create workspace manager (without intelligent features for simpler testing)
        self.workspace_manager = WorkspaceManager(
            base_workspace_dir=self.temp_base_dir,
            enable_intelligent_features=False,
            max_concurrent_workspaces=5
        )
        
        # Create execution engine
        self.execution_engine = ExecutionEngine()
    
    def tearDown(self):
        """Clean up test environment."""
        # Shutdown workspace manager
        self.workspace_manager.shutdown()
        
        # Clean up temporary directories
        for temp_dir in self.temp_dirs:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
    
    def _create_test_python_project(self) -> str:
        """Create a test Python project."""
        project_dir = tempfile.mkdtemp()
        self.temp_dirs.append(project_dir)
        
        # Create main.py
        with open(os.path.join(project_dir, "main.py"), 'w') as f:
            f.write("""
def greet(name):
    return f"Hello, {name}!"

def calculate(a, b):
    return a + b

if __name__ == "__main__":
    print(greet("World"))
    print(f"2 + 3 = {calculate(2, 3)}")
""")
        
        # Create test.py
        with open(os.path.join(project_dir, "test.py"), 'w') as f:
            f.write("""
import main

def test_greet():
    result = main.greet("Test")
    assert result == "Hello, Test!"
    print("test_greet passed")

def test_calculate():
    result = main.calculate(5, 7)
    assert result == 12
    print("test_calculate passed")

if __name__ == "__main__":
    test_greet()
    test_calculate()
    print("All tests passed!")
""")
        
        # Create requirements.txt
        with open(os.path.join(project_dir, "requirements.txt"), 'w') as f:
            f.write("# No external dependencies for this test project\n")
        
        return project_dir
    
    def test_execute_python_in_workspace(self):
        """Test executing Python code in a workspace."""
        # Create test project
        project_dir = self._create_test_python_project()
        
        # Create workspace from project
        workspace = self.workspace_manager.create_workspace(
            "python-test-workspace",
            source_path=project_dir
        )
        
        # Create execution context
        context = self.workspace_manager.create_execution_context(
            "python-test-workspace",
            resource_limits=ResourceLimits(max_execution_time=30),
            security_level=SecurityLevel.MODERATE
        )
        
        self.assertIsNotNone(context)
        
        # Execute the main.py file
        main_file = workspace.workspace_path / "main.py"
        with open(main_file, 'r') as f:
            code = f.read()
        
        result = self.execution_engine.execute_python(code, context)
        
        self.assertTrue(result.success)
        self.assertIn("Hello, World!", result.output)
        self.assertIn("2 + 3 = 5", result.output)
        self.assertIsNone(result.error)
    
    def test_execute_tests_in_workspace(self):
        """Test executing tests in a workspace."""
        # Create test project
        project_dir = self._create_test_python_project()
        
        # Create workspace from project
        workspace = self.workspace_manager.create_workspace(
            "test-workspace",
            source_path=project_dir
        )
        
        # Create execution context
        context = self.workspace_manager.create_execution_context(
            "test-workspace",
            resource_limits=ResourceLimits(max_execution_time=30),
            security_level=SecurityLevel.MODERATE
        )
        
        # Execute the test.py file
        test_file = workspace.workspace_path / "test.py"
        with open(test_file, 'r') as f:
            test_code = f.read()
        
        result = self.execution_engine.execute_python(test_code, context)
        
        self.assertTrue(result.success)
        self.assertIn("test_greet passed", result.output)
        self.assertIn("test_calculate passed", result.output)
        self.assertIn("All tests passed!", result.output)
        self.assertIsNone(result.error)
    
    def test_workspace_isolation(self):
        """Test that workspaces are isolated from each other."""
        # Create two workspaces
        workspace1 = self.workspace_manager.create_workspace("isolation-test-1")
        workspace2 = self.workspace_manager.create_workspace("isolation-test-2")
        
        # Create execution contexts
        context1 = self.workspace_manager.create_execution_context("isolation-test-1")
        context2 = self.workspace_manager.create_execution_context("isolation-test-2")
        
        # Create a file in workspace1
        code1 = """
with open("workspace1_file.txt", "w") as f:
    f.write("This is from workspace 1")
print("File created in workspace 1")
"""
        
        result1 = self.execution_engine.execute_python(code1, context1)
        self.assertTrue(result1.success)
        
        # Try to read the file from workspace2 (should fail)
        code2 = """
try:
    with open("workspace1_file.txt", "r") as f:
        content = f.read()
    print(f"Found file: {content}")
except FileNotFoundError:
    print("File not found in workspace 2 (as expected)")
"""
        
        result2 = self.execution_engine.execute_python(code2, context2)
        self.assertTrue(result2.success)
        self.assertIn("File not found in workspace 2", result2.output)
        
        # Verify file exists in workspace1
        file1_path = workspace1.workspace_path / "workspace1_file.txt"
        self.assertTrue(file1_path.exists())
        
        # Verify file doesn't exist in workspace2
        file2_path = workspace2.workspace_path / "workspace1_file.txt"
        self.assertFalse(file2_path.exists())
    
    def test_workspace_environment_variables(self):
        """Test that workspace environment variables are available during execution."""
        # Create workspace
        workspace = self.workspace_manager.create_workspace("env-test-workspace")
        
        # Setup environment variables
        self.workspace_manager.setup_environment(
            "env-test-workspace",
            environment_vars={
                "TEST_VAR": "test_value",
                "WORKSPACE_NAME": "env-test-workspace",
                "CUSTOM_PATH": "/custom/path"
            }
        )
        
        # Create execution context
        context = self.workspace_manager.create_execution_context("env-test-workspace")
        
        # Test that environment variables are available
        code = """
import os
print(f"TEST_VAR: {os.environ.get('TEST_VAR', 'NOT_FOUND')}")
print(f"WORKSPACE_NAME: {os.environ.get('WORKSPACE_NAME', 'NOT_FOUND')}")
print(f"CUSTOM_PATH: {os.environ.get('CUSTOM_PATH', 'NOT_FOUND')}")
"""
        
        result = self.execution_engine.execute_python(code, context)
        
        self.assertTrue(result.success)
        self.assertIn("TEST_VAR: test_value", result.output)
        self.assertIn("WORKSPACE_NAME: env-test-workspace", result.output)
        self.assertIn("CUSTOM_PATH: /custom/path", result.output)
    
    def test_workspace_artifacts_directory(self):
        """Test that artifacts directory is available and writable."""
        # Create workspace
        workspace = self.workspace_manager.create_workspace("artifacts-test-workspace")
        
        # Create execution context
        context = self.workspace_manager.create_execution_context("artifacts-test-workspace")
        
        # Test creating artifacts
        code = f"""
import os
artifacts_dir = r"{context.artifacts_dir}"
print(f"Artifacts directory: {{artifacts_dir}}")
print(f"Artifacts directory exists: {{os.path.exists(artifacts_dir)}}")

# Create an artifact file
artifact_file = os.path.join(artifacts_dir, "test_artifact.txt")
with open(artifact_file, "w") as f:
    f.write("This is a test artifact")

print(f"Artifact created: {{os.path.exists(artifact_file)}}")

# List artifacts
artifacts = os.listdir(artifacts_dir)
print(f"Artifacts: {{artifacts}}")
"""
        
        result = self.execution_engine.execute_python(code, context)
        
        self.assertTrue(result.success)
        self.assertIn("Artifacts directory exists: True", result.output)
        self.assertIn("Artifact created: True", result.output)
        self.assertIn("test_artifact.txt", result.output)
        
        # Verify artifact file was actually created
        artifact_file = context.artifacts_dir / "test_artifact.txt"
        self.assertTrue(artifact_file.exists())
        
        with open(artifact_file, 'r') as f:
            content = f.read()
        self.assertEqual(content, "This is a test artifact")
    
    def test_multiple_workspaces_concurrent_execution(self):
        """Test executing code in multiple workspaces concurrently."""
        # Create multiple workspaces
        workspaces = []
        contexts = []
        
        for i in range(3):
            workspace_id = f"concurrent-test-{i}"
            workspace = self.workspace_manager.create_workspace(workspace_id)
            context = self.workspace_manager.create_execution_context(workspace_id)
            
            workspaces.append(workspace)
            contexts.append(context)
        
        # Execute different code in each workspace
        results = []
        
        for i, context in enumerate(contexts):
            code = f"""
import time
import os

workspace_id = "{context.workspace_id}"
print(f"Starting execution in workspace: {{workspace_id}}")

# Create a unique file for this workspace
filename = f"workspace_{{workspace_id}}_output.txt"
with open(filename, "w") as f:
    f.write(f"Output from {{workspace_id}}")

print(f"Created file: {{filename}}")
print(f"Workspace {{workspace_id}} execution complete")
"""
            
            result = self.execution_engine.execute_python(code, context)
            results.append(result)
        
        # Verify all executions succeeded
        for i, result in enumerate(results):
            self.assertTrue(result.success, f"Execution {i} failed: {result.error}")
            self.assertIn(f"concurrent-test-{i}", result.output)
            self.assertIn("execution complete", result.output)
        
        # Verify each workspace has its own file
        for i, workspace in enumerate(workspaces):
            expected_file = workspace.workspace_path / f"workspace_concurrent-test-{i}_output.txt"
            self.assertTrue(expected_file.exists())
            
            with open(expected_file, 'r') as f:
                content = f.read()
            self.assertEqual(content, f"Output from concurrent-test-{i}")
    
    def test_workspace_cleanup_after_execution(self):
        """Test that workspace cleanup works properly after execution."""
        # Create workspace
        workspace = self.workspace_manager.create_workspace("cleanup-test-workspace")
        workspace_path = workspace.workspace_path
        
        # Create execution context and execute some code
        context = self.workspace_manager.create_execution_context("cleanup-test-workspace")
        
        code = """
# Create some files
with open("test_file1.txt", "w") as f:
    f.write("Test file 1")

with open("test_file2.txt", "w") as f:
    f.write("Test file 2")

import os
os.makedirs("test_subdir", exist_ok=True)
with open("test_subdir/nested_file.txt", "w") as f:
    f.write("Nested file")

print("Files created successfully")
"""
        
        result = self.execution_engine.execute_python(code, context)
        self.assertTrue(result.success)
        
        # Verify files were created
        self.assertTrue((workspace_path / "test_file1.txt").exists())
        self.assertTrue((workspace_path / "test_file2.txt").exists())
        self.assertTrue((workspace_path / "test_subdir" / "nested_file.txt").exists())
        
        # Cleanup workspace
        cleanup_result = self.workspace_manager.cleanup_workspace("cleanup-test-workspace")
        self.assertTrue(cleanup_result)
        
        # Verify workspace is removed from manager
        retrieved_workspace = self.workspace_manager.get_workspace("cleanup-test-workspace")
        self.assertIsNone(retrieved_workspace)


if __name__ == '__main__':
    # Set up logging for tests
    import logging
    logging.basicConfig(level=logging.WARNING)
    
    # Run the tests
    unittest.main(verbosity=2)