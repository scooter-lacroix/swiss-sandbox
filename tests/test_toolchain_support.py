"""
Unit and integration tests for DevelopmentToolchainSupport.
"""

import unittest
import tempfile
import shutil
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.sandbox.intelligent.executor.sandbox_executor import SandboxExecutor
from src.sandbox.intelligent.executor.toolchain_support import (
    DevelopmentToolchainSupport, ToolchainType, BuildSystem, TestFramework,
    BuildResult, TestResult
)
from src.sandbox.intelligent.logger import ExecutionHistoryTracker
from src.sandbox.intelligent.types import CommandInfo


class TestDevelopmentToolchainSupport(unittest.TestCase):
    """Test cases for DevelopmentToolchainSupport."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.workspace_path = Path(self.test_dir) / "workspace"
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        
        # Create mock executor and history tracker
        self.mock_executor = Mock(spec=SandboxExecutor)
        self.mock_executor.workspace_path = str(self.workspace_path)
        self.mock_executor.session_id = "test_session"
        self.mock_executor.logger = Mock()
        
        self.mock_history_tracker = Mock(spec=ExecutionHistoryTracker)
        
        # Create toolchain support instance
        self.toolchain_support = DevelopmentToolchainSupport(
            sandbox_executor=self.mock_executor,
            history_tracker=self.mock_history_tracker
        )
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_detect_python_toolchain(self):
        """Test detection of Python toolchain."""
        # Create Python project files
        (self.workspace_path / "pyproject.toml").write_text("""
[tool.poetry]
name = "test-project"
version = "0.1.0"

[tool.poetry.dependencies]
python = "^3.8"
pytest = "^6.0"
""")
        
        # Recreate toolchain support to trigger detection
        toolchain_support = DevelopmentToolchainSupport(
            sandbox_executor=self.mock_executor,
            history_tracker=self.mock_history_tracker
        )
        
        self.assertEqual(toolchain_support.toolchain_config.toolchain_type, ToolchainType.PYTHON)
        self.assertEqual(toolchain_support.toolchain_config.build_system, BuildSystem.POETRY)
        self.assertEqual(toolchain_support.toolchain_config.test_framework, TestFramework.PYTEST)
    
    def test_detect_nodejs_toolchain(self):
        """Test detection of Node.js toolchain."""
        # Create Node.js project files
        package_json = {
            "name": "test-project",
            "version": "1.0.0",
            "dependencies": {},
            "devDependencies": {
                "jest": "^27.0.0"
            }
        }
        (self.workspace_path / "package.json").write_text(json.dumps(package_json))
        (self.workspace_path / "yarn.lock").write_text("")
        
        # Recreate toolchain support to trigger detection
        toolchain_support = DevelopmentToolchainSupport(
            sandbox_executor=self.mock_executor,
            history_tracker=self.mock_history_tracker
        )
        
        self.assertEqual(toolchain_support.toolchain_config.toolchain_type, ToolchainType.NODEJS)
        self.assertEqual(toolchain_support.toolchain_config.build_system, BuildSystem.YARN)
        self.assertEqual(toolchain_support.toolchain_config.test_framework, TestFramework.JEST)
    
    def test_detect_java_maven_toolchain(self):
        """Test detection of Java Maven toolchain."""
        # Create Maven project file
        (self.workspace_path / "pom.xml").write_text("""
<project>
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>test-project</artifactId>
    <version>1.0.0</version>
    <dependencies>
        <dependency>
            <groupId>junit</groupId>
            <artifactId>junit</artifactId>
            <version>4.13.2</version>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
""")
        
        # Recreate toolchain support to trigger detection
        toolchain_support = DevelopmentToolchainSupport(
            sandbox_executor=self.mock_executor,
            history_tracker=self.mock_history_tracker
        )
        
        self.assertEqual(toolchain_support.toolchain_config.toolchain_type, ToolchainType.JAVA)
        self.assertEqual(toolchain_support.toolchain_config.build_system, BuildSystem.MAVEN)
        self.assertEqual(toolchain_support.toolchain_config.test_framework, TestFramework.JUNIT)
    
    def test_detect_rust_toolchain(self):
        """Test detection of Rust toolchain."""
        # Create Rust project file
        (self.workspace_path / "Cargo.toml").write_text("""
[package]
name = "test-project"
version = "0.1.0"
edition = "2021"

[dependencies]
""")
        
        # Recreate toolchain support to trigger detection
        toolchain_support = DevelopmentToolchainSupport(
            sandbox_executor=self.mock_executor,
            history_tracker=self.mock_history_tracker
        )
        
        self.assertEqual(toolchain_support.toolchain_config.toolchain_type, ToolchainType.RUST)
        self.assertEqual(toolchain_support.toolchain_config.build_system, BuildSystem.CARGO)
        self.assertEqual(toolchain_support.toolchain_config.test_framework, TestFramework.CARGO_TEST)
    
    def test_build_project_success(self):
        """Test successful project build."""
        # Mock successful command execution
        mock_result = CommandInfo(
            command="poetry build",
            working_directory=str(self.workspace_path),
            output="Building test-project (0.1.0)\nBuilt successfully",
            error_output="",
            exit_code=0,
            duration=2.5
        )
        self.mock_executor.execute_command.return_value = mock_result
        
        # Mock the _get_build_artifacts method to simulate artifacts being created
        with patch.object(self.toolchain_support, '_get_build_artifacts') as mock_get_artifacts:
            # First call (before build) returns empty list
            # Second call (after build) returns artifacts
            mock_get_artifacts.side_effect = [[], ["dist/test-project-0.1.0.tar.gz"]]
            
            result = self.toolchain_support.build_project()
        
        self.assertIsInstance(result, BuildResult)
        self.assertTrue(result.success)
        self.assertEqual(result.duration, 2.5)
        self.assertGreater(len(result.artifacts_created), 0)
        self.assertEqual(result.warnings_count, 0)
        self.assertEqual(result.errors_count, 0)
        
        # Verify history tracking was called
        self.mock_history_tracker.add_verified_outcome.assert_called_once()
    
    def test_build_project_failure(self):
        """Test failed project build."""
        # Mock failed command execution
        mock_result = CommandInfo(
            command="poetry build",
            working_directory=str(self.workspace_path),
            output="",
            error_output="Error: Build failed due to syntax error",
            exit_code=1,
            duration=1.0
        )
        self.mock_executor.execute_command.return_value = mock_result
        
        result = self.toolchain_support.build_project()
        
        self.assertIsInstance(result, BuildResult)
        self.assertFalse(result.success)
        self.assertEqual(result.duration, 1.0)
        self.assertGreater(result.errors_count, 0)
        
        # Verify history tracking was called
        self.mock_history_tracker.add_verified_outcome.assert_called_once()
    
    def test_run_tests_success(self):
        """Test successful test execution."""
        # Mock successful test execution
        mock_result = CommandInfo(
            command="poetry run pytest --cov=.",
            working_directory=str(self.workspace_path),
            output="===== 5 passed, 0 failed, 1 skipped in 2.34s =====\nCoverage: 85%",
            error_output="",
            exit_code=0,
            duration=2.34
        )
        self.mock_executor.execute_command.return_value = mock_result
        
        result = self.toolchain_support.run_tests()
        
        self.assertIsInstance(result, TestResult)
        self.assertTrue(result.success)
        self.assertEqual(result.duration, 2.34)
        self.assertEqual(result.tests_run, 6)  # 5 passed + 1 skipped
        self.assertEqual(result.tests_passed, 5)
        self.assertEqual(result.tests_failed, 0)
        self.assertEqual(result.tests_skipped, 1)
        self.assertEqual(result.coverage_percentage, 85.0)
        
        # Verify history tracking was called
        self.mock_history_tracker.add_verified_outcome.assert_called_once()
    
    def test_run_tests_with_failures(self):
        """Test test execution with failures."""
        # Mock test execution with failures
        mock_result = CommandInfo(
            command="poetry run pytest",
            working_directory=str(self.workspace_path),
            output="===== 3 passed, 2 failed, 0 skipped in 1.56s =====",
            error_output="",
            exit_code=1,
            duration=1.56
        )
        self.mock_executor.execute_command.return_value = mock_result
        
        result = self.toolchain_support.run_tests()
        
        self.assertIsInstance(result, TestResult)
        self.assertFalse(result.success)
        self.assertEqual(result.tests_run, 5)
        self.assertEqual(result.tests_passed, 3)
        self.assertEqual(result.tests_failed, 2)
        self.assertEqual(result.tests_skipped, 0)
        
        # Verify history tracking was called
        self.mock_history_tracker.add_verified_outcome.assert_called_once()
    
    def test_lint_code(self):
        """Test code linting."""
        # Mock lint execution
        mock_result = CommandInfo(
            command="poetry run flake8",
            working_directory=str(self.workspace_path),
            output="./src/main.py:10:1: E302 expected 2 blank lines\n./src/main.py:15:80: E501 line too long",
            error_output="",
            exit_code=1,
            duration=0.8
        )
        self.mock_executor.execute_command.return_value = mock_result
        
        result = self.toolchain_support.lint_code()
        
        self.assertIsInstance(result, CommandInfo)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("E302", result.output)
        self.assertIn("E501", result.output)
        
        # Verify history tracking was called
        self.mock_history_tracker.add_verified_outcome.assert_called_once()
    
    def test_format_code(self):
        """Test code formatting."""
        # Mock format execution
        mock_result = CommandInfo(
            command="poetry run black",
            working_directory=str(self.workspace_path),
            output="reformatted 3 files",
            error_output="",
            exit_code=0,
            duration=1.2
        )
        self.mock_executor.execute_command.return_value = mock_result
        
        result = self.toolchain_support.format_code()
        
        self.assertIsInstance(result, CommandInfo)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("reformatted", result.output)
        
        # Verify history tracking was called
        self.mock_history_tracker.add_verified_outcome.assert_called_once()
    
    def test_install_dependencies(self):
        """Test dependency installation."""
        # Mock install execution
        mock_result = CommandInfo(
            command="poetry install",
            working_directory=str(self.workspace_path),
            output="Installing dependencies from lock file\nInstalled 25 packages",
            error_output="",
            exit_code=0,
            duration=15.3
        )
        self.mock_executor.execute_command.return_value = mock_result
        
        result = self.toolchain_support.install_dependencies()
        
        self.assertIsInstance(result, CommandInfo)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Installing dependencies", result.output)
        
        # Verify history tracking was called
        self.mock_history_tracker.add_verified_outcome.assert_called_once()
    
    def test_clean_project(self):
        """Test project cleaning."""
        # Mock clean execution
        mock_result = CommandInfo(
            command="poetry cache clear --all pypi",
            working_directory=str(self.workspace_path),
            output="Cache cleared successfully",
            error_output="",
            exit_code=0,
            duration=0.5
        )
        self.mock_executor.execute_command.return_value = mock_result
        
        result = self.toolchain_support.clean_project()
        
        self.assertIsInstance(result, CommandInfo)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Cache cleared", result.output)
        
        # Verify history tracking was called
        self.mock_history_tracker.add_verified_outcome.assert_called_once()
    
    def test_run_development_workflow(self):
        """Test complete development workflow."""
        # Mock all command executions
        mock_results = {
            "poetry install": CommandInfo(
                command="poetry install",
                working_directory=str(self.workspace_path),
                output="Installed successfully",
                error_output="",
                exit_code=0,
                duration=5.0
            ),
            "poetry run flake8": CommandInfo(
                command="poetry run flake8",
                working_directory=str(self.workspace_path),
                output="No issues found",
                error_output="",
                exit_code=0,
                duration=1.0
            ),
            "poetry run pytest --cov=.": CommandInfo(
                command="poetry run pytest --cov=.",
                working_directory=str(self.workspace_path),
                output="===== 10 passed in 3.45s =====\nCoverage: 90%",
                error_output="",
                exit_code=0,
                duration=3.45
            ),
            "poetry build": CommandInfo(
                command="poetry build",
                working_directory=str(self.workspace_path),
                output="Built successfully",
                error_output="",
                exit_code=0,
                duration=2.0
            )
        }
        
        def mock_execute_command(command, **kwargs):
            return mock_results.get(command, mock_results["poetry install"])
        
        self.mock_executor.execute_command.side_effect = mock_execute_command
        
        # Mock the _get_build_artifacts method for the workflow test
        with patch.object(self.toolchain_support, '_get_build_artifacts') as mock_get_artifacts:
            mock_get_artifacts.side_effect = [[], ["dist/test-project-0.1.0.tar.gz"]]
            
            result = self.toolchain_support.run_development_workflow()
        
        self.assertIsInstance(result, dict)
        self.assertTrue(result["overall_success"])
        self.assertIn("install", result["steps"])
        self.assertIn("lint", result["steps"])
        self.assertIn("test", result["steps"])
        self.assertIn("build", result["steps"])
        
        # Verify all steps succeeded
        for step_name, step_result in result["steps"].items():
            self.assertTrue(step_result["success"], f"Step {step_name} failed")
        
        # Verify history tracking was called for workflow
        self.mock_history_tracker.add_verified_outcome.assert_called()
    
    def test_run_development_workflow_with_failure(self):
        """Test development workflow with a failing step."""
        # Create a list to track call order
        call_order = []
        
        def mock_execute_command(command, **kwargs):
            call_order.append(command)
            if "install" in command:
                return CommandInfo(
                    command=command,
                    working_directory=str(self.workspace_path),
                    output="Installed successfully",
                    error_output="",
                    exit_code=0,
                    duration=5.0
                )
            elif "flake8" in command or "lint" in command:
                return CommandInfo(
                    command=command,
                    working_directory=str(self.workspace_path),
                    output="",
                    error_output="Linting failed with errors",
                    exit_code=1,
                    duration=1.0
                )
            else:
                return CommandInfo(
                    command=command,
                    working_directory=str(self.workspace_path),
                    output="Command executed",
                    error_output="",
                    exit_code=0,
                    duration=1.0
                )
        
        self.mock_executor.execute_command.side_effect = mock_execute_command
        
        result = self.toolchain_support.run_development_workflow(steps=["install", "lint"])
        
        self.assertIsInstance(result, dict)
        self.assertFalse(result["overall_success"])
        self.assertTrue(result["steps"]["install"]["success"])
        self.assertFalse(result["steps"]["lint"]["success"])
        
        # Verify history tracking was called for workflow
        self.mock_history_tracker.add_verified_outcome.assert_called()
    
    def test_get_toolchain_summary(self):
        """Test toolchain summary generation."""
        summary = self.toolchain_support.get_toolchain_summary()
        
        self.assertIsInstance(summary, dict)
        self.assertIn("toolchain_type", summary)
        self.assertIn("build_system", summary)
        self.assertIn("test_framework", summary)
        self.assertIn("workspace_path", summary)
        self.assertIn("build_commands", summary)
        self.assertIn("test_commands", summary)
        self.assertIn("lint_commands", summary)
        self.assertIn("format_commands", summary)
        self.assertIn("install_commands", summary)
        self.assertIn("clean_commands", summary)
        self.assertIn("environment_vars", summary)
    
    def test_export_workflow_summary(self):
        """Test workflow summary export."""
        # Mock history tracker export
        self.mock_history_tracker.export_execution_history.return_value = '{"summary": "test"}'
        
        result = self.toolchain_support.export_workflow_summary("json")
        
        self.assertEqual(result, '{"summary": "test"}')
        self.mock_history_tracker.export_execution_history.assert_called_once_with(
            session_id="test_session",
            format="json"
        )
    
    def test_custom_commands(self):
        """Test using custom commands instead of detected ones."""
        # Mock custom command execution
        mock_result = CommandInfo(
            command="custom build command",
            working_directory=str(self.workspace_path),
            output="Custom build completed",
            error_output="",
            exit_code=0,
            duration=1.5
        )
        self.mock_executor.execute_command.return_value = mock_result
        
        result = self.toolchain_support.build_project("custom build command")
        
        self.assertTrue(result.success)
        self.mock_executor.execute_command.assert_called_with(
            "custom build command",
            working_dir=str(self.workspace_path),
            env_vars={}
        )
    
    def test_parse_test_output_patterns(self):
        """Test parsing of various test output patterns."""
        # Test pytest pattern
        pytest_output = "===== 15 passed, 2 failed, 3 skipped in 5.67s ====="
        stats = self.toolchain_support._parse_test_output(pytest_output, "")
        self.assertEqual(stats["tests_passed"], 15)
        self.assertEqual(stats["tests_failed"], 2)
        self.assertEqual(stats["tests_skipped"], 3)
        self.assertEqual(stats["tests_run"], 20)
        
        # Test jest pattern
        jest_output = "Tests: 1 failed, 9 passed, 10 total"
        stats = self.toolchain_support._parse_test_output(jest_output, "")
        self.assertEqual(stats["tests_failed"], 1)
        self.assertEqual(stats["tests_passed"], 9)
        self.assertEqual(stats["tests_run"], 10)
    
    def test_extract_coverage_percentage(self):
        """Test extraction of coverage percentage from output."""
        # Test various coverage formats
        outputs = [
            "Total coverage: 85.5%",
            "Coverage: 92%",
            "85.5% coverage achieved"
        ]
        
        for output in outputs:
            coverage = self.toolchain_support._extract_coverage_percentage(output, "")
            self.assertIsNotNone(coverage)
            self.assertGreater(coverage, 0)
    
    def test_count_build_warnings_and_errors(self):
        """Test counting of build warnings and errors."""
        output_with_warnings = """
        warning: deprecated function used
        src/main.py:10: warning: unused variable
        error: compilation failed
        """
        
        warnings = self.toolchain_support._count_build_warnings(output_with_warnings, "")
        errors = self.toolchain_support._count_build_errors(output_with_warnings, "")
        
        self.assertGreater(warnings, 0)
        self.assertGreater(errors, 0)


class TestToolchainSupportIntegration(unittest.TestCase):
    """Integration tests for DevelopmentToolchainSupport with real SandboxExecutor."""
    
    def setUp(self):
        """Set up integration test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.workspace_path = Path(self.test_dir) / "integration_workspace"
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        
        # Create real SandboxExecutor
        self.executor = SandboxExecutor(
            workspace_path=str(self.workspace_path),
            session_id="integration_test",
            task_id="toolchain_test"
        )
        
        # Create real ExecutionHistoryTracker
        self.history_tracker = ExecutionHistoryTracker()
        
        # Create toolchain support
        self.toolchain_support = DevelopmentToolchainSupport(
            sandbox_executor=self.executor,
            history_tracker=self.history_tracker
        )
    
    def tearDown(self):
        """Clean up integration test environment."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_python_project_workflow(self):
        """Test complete Python project workflow."""
        # Create a simple Python project
        (self.workspace_path / "pyproject.toml").write_text("""
[build-system]
requires = ["setuptools", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "test-project"
version = "0.1.0"
description = "Test project"
""")
        
        (self.workspace_path / "setup.py").write_text("""
from setuptools import setup, find_packages

setup(
    name="test-project",
    version="0.1.0",
    packages=find_packages(),
)
""")
        
        # Create source code
        src_dir = self.workspace_path / "src"
        src_dir.mkdir()
        (src_dir / "__init__.py").write_text("")
        (src_dir / "main.py").write_text("""
def hello_world():
    return "Hello, World!"

if __name__ == "__main__":
    print(hello_world())
""")
        
        # Create tests
        tests_dir = self.workspace_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "__init__.py").write_text("")
        (tests_dir / "test_main.py").write_text("""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from main import hello_world

class TestMain(unittest.TestCase):
    def test_hello_world(self):
        self.assertEqual(hello_world(), "Hello, World!")

if __name__ == "__main__":
    unittest.main()
""")
        
        # Recreate toolchain support to detect the Python project
        toolchain_support = DevelopmentToolchainSupport(
            sandbox_executor=self.executor,
            history_tracker=self.history_tracker
        )
        
        # Test toolchain detection
        summary = toolchain_support.get_toolchain_summary()
        self.assertEqual(summary["toolchain_type"], "python")
        
        # Test individual operations
        try:
            # Test dependency installation (may fail in test environment)
            install_result = toolchain_support.install_dependencies()
            print(f"Install result: {install_result.exit_code}")
        except Exception as e:
            print(f"Install failed (expected in test env): {e}")
        
        # Test running tests
        test_result = toolchain_support.run_tests("python -m unittest discover tests")
        print(f"Test result: success={test_result.success}, tests_run={test_result.tests_run}")
        
        # Test building (simple case)
        build_result = toolchain_support.build_project("python setup.py build")
        print(f"Build result: success={build_result.success}")
        
        # Get execution summary
        execution_summary = self.executor.get_execution_summary()
        print(f"Total commands executed: {execution_summary['commands_executed']}")
        
        # Verify history tracking
        self.assertGreater(len(self.history_tracker.operations), 0)
    
    def test_generic_project_workflow(self):
        """Test workflow with generic/unknown project type."""
        # Create a Makefile-based project
        (self.workspace_path / "Makefile").write_text("""
.PHONY: build test clean install

build:
\techo "Building project..."
\tmkdir -p build
\techo "Build complete" > build/output.txt

test:
\techo "Running tests..."
\techo "All tests passed"

clean:
\techo "Cleaning project..."
\trm -rf build

install:
\techo "Installing dependencies..."
\techo "Dependencies installed"

lint:
\techo "Linting code..."
\techo "No issues found"

format:
\techo "Formatting code..."
\techo "Code formatted"
""")
        
        # Create source files
        (self.workspace_path / "main.c").write_text("""
#include <stdio.h>

int main() {
    printf("Hello, World!\\n");
    return 0;
}
""")
        
        # Recreate toolchain support to detect the generic project
        toolchain_support = DevelopmentToolchainSupport(
            sandbox_executor=self.executor,
            history_tracker=self.history_tracker
        )
        
        # Test toolchain detection
        summary = toolchain_support.get_toolchain_summary()
        self.assertEqual(summary["toolchain_type"], "generic")
        self.assertEqual(summary["build_system"], "make")
        
        # Test complete workflow
        workflow_result = toolchain_support.run_development_workflow()
        
        print(f"Workflow success: {workflow_result['overall_success']}")
        for step, result in workflow_result["steps"].items():
            print(f"  {step}: success={result['success']}, duration={result['duration']}")
        
        # Verify workflow tracking
        self.assertGreater(len(self.history_tracker.workflows), 0)
        
        # Test export functionality
        json_summary = toolchain_support.export_workflow_summary("json")
        self.assertIsInstance(json_summary, str)
        self.assertIn("operations", json_summary)
        
        markdown_summary = toolchain_support.export_workflow_summary("markdown")
        self.assertIsInstance(markdown_summary, str)
        self.assertIn("Execution Summary", markdown_summary)


if __name__ == '__main__':
    unittest.main()