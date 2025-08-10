"""
Development toolchain support for the SandboxExecutor.

Provides specialized support for build systems, test runners, development tools,
and IDE integrations with comprehensive history tracking and outcome verification.
"""

import os
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from ..types import CommandInfo, ActionType
from ..logger import ExecutionHistoryTracker, VerifiedOutcome, OutcomeStatus
from .sandbox_executor import SandboxExecutor


class ToolchainType(Enum):
    """Types of development toolchains supported."""
    PYTHON = "python"
    NODEJS = "nodejs"
    JAVA = "java"
    RUST = "rust"
    GO = "go"
    DOTNET = "dotnet"
    RUBY = "ruby"
    PHP = "php"
    GENERIC = "generic"


class BuildSystem(Enum):
    """Types of build systems supported."""
    MAKE = "make"
    CMAKE = "cmake"
    GRADLE = "gradle"
    MAVEN = "maven"
    NPM = "npm"
    YARN = "yarn"
    CARGO = "cargo"
    GO_BUILD = "go"
    DOTNET_BUILD = "dotnet"
    SETUPTOOLS = "setuptools"
    POETRY = "poetry"
    WEBPACK = "webpack"
    VITE = "vite"
    GENERIC = "generic"


class TestFramework(Enum):
    """Types of test frameworks supported."""
    PYTEST = "pytest"
    UNITTEST = "unittest"
    JEST = "jest"
    MOCHA = "mocha"
    JUNIT = "junit"
    TESTNG = "testng"
    CARGO_TEST = "cargo_test"
    GO_TEST = "go_test"
    RSPEC = "rspec"
    PHPUNIT = "phpunit"
    GENERIC = "generic"


@dataclass
class ToolchainConfig:
    """Configuration for a development toolchain."""
    toolchain_type: ToolchainType
    build_system: BuildSystem
    test_framework: TestFramework
    build_commands: List[str]
    test_commands: List[str]
    lint_commands: List[str]
    format_commands: List[str]
    install_commands: List[str]
    clean_commands: List[str]
    environment_vars: Dict[str, str]
    working_directory: Optional[str] = None


@dataclass
class BuildResult:
    """Result of a build operation."""
    success: bool
    duration: float
    output: str
    error_output: str
    artifacts_created: List[str]
    warnings_count: int
    errors_count: int
    build_system: BuildSystem
    verified_outcome: VerifiedOutcome


@dataclass
class TestResult:
    """Result of a test operation."""
    success: bool
    duration: float
    output: str
    error_output: str
    tests_run: int
    tests_passed: int
    tests_failed: int
    tests_skipped: int
    coverage_percentage: Optional[float]
    test_framework: TestFramework
    verified_outcome: VerifiedOutcome


class DevelopmentToolchainSupport:
    """
    Provides comprehensive development toolchain support with history tracking.
    
    Integrates with ExecutionHistoryTracker for verified outcome reporting and
    provides specialized support for common development workflows.
    """
    
    def __init__(self, sandbox_executor: SandboxExecutor, 
                 history_tracker: ExecutionHistoryTracker = None):
        """
        Initialize development toolchain support.
        
        Args:
            sandbox_executor: SandboxExecutor instance for command execution
            history_tracker: ExecutionHistoryTracker for outcome verification
        """
        self.executor = sandbox_executor
        # Create history tracker with the executor's logger if not provided
        if history_tracker is None:
            self.history_tracker = ExecutionHistoryTracker(sandbox_executor.logger)
        else:
            self.history_tracker = history_tracker
        self.workspace_path = Path(sandbox_executor.workspace_path)
        
        # Initialize toolchain-specific configurations first
        self._toolchain_configs = self._initialize_toolchain_configs()
        
        # Detect toolchain configuration
        self.toolchain_config = self._detect_toolchain_config()
    
    def _detect_toolchain_config(self) -> ToolchainConfig:
        """Detect the development toolchain configuration from workspace."""
        toolchain_type = self._detect_toolchain_type()
        build_system = self._detect_build_system()
        test_framework = self._detect_test_framework()
        
        # Get the configuration for the detected toolchain
        config_key = f"{toolchain_type.value}_{build_system.value}"
        base_config = self._toolchain_configs.get(config_key, self._get_generic_config())
        
        return ToolchainConfig(
            toolchain_type=toolchain_type,
            build_system=build_system,
            test_framework=test_framework,
            **base_config
        )
    
    def _detect_toolchain_type(self) -> ToolchainType:
        """Detect the primary toolchain type from workspace files."""
        if (self.workspace_path / "pyproject.toml").exists() or \
           (self.workspace_path / "setup.py").exists() or \
           (self.workspace_path / "requirements.txt").exists():
            return ToolchainType.PYTHON
        
        if (self.workspace_path / "package.json").exists():
            return ToolchainType.NODEJS
        
        if (self.workspace_path / "pom.xml").exists() or \
           (self.workspace_path / "build.gradle").exists():
            return ToolchainType.JAVA
        
        if (self.workspace_path / "Cargo.toml").exists():
            return ToolchainType.RUST
        
        if (self.workspace_path / "go.mod").exists():
            return ToolchainType.GO
        
        if (self.workspace_path / "*.csproj").exists() or \
           (self.workspace_path / "*.sln").exists():
            return ToolchainType.DOTNET
        
        if (self.workspace_path / "Gemfile").exists():
            return ToolchainType.RUBY
        
        if (self.workspace_path / "composer.json").exists():
            return ToolchainType.PHP
        
        return ToolchainType.GENERIC
    
    def _detect_build_system(self) -> BuildSystem:
        """Detect the build system from workspace files."""
        if (self.workspace_path / "Makefile").exists():
            return BuildSystem.MAKE
        
        if (self.workspace_path / "CMakeLists.txt").exists():
            return BuildSystem.CMAKE
        
        if (self.workspace_path / "build.gradle").exists():
            return BuildSystem.GRADLE
        
        if (self.workspace_path / "pom.xml").exists():
            return BuildSystem.MAVEN
        
        if (self.workspace_path / "package.json").exists():
            if (self.workspace_path / "yarn.lock").exists():
                return BuildSystem.YARN
            return BuildSystem.NPM
        
        if (self.workspace_path / "Cargo.toml").exists():
            return BuildSystem.CARGO
        
        if (self.workspace_path / "go.mod").exists():
            return BuildSystem.GO_BUILD
        
        if (self.workspace_path / "pyproject.toml").exists():
            # Check if poetry is used
            try:
                with open(self.workspace_path / "pyproject.toml") as f:
                    content = f.read()
                    if "[tool.poetry]" in content:
                        return BuildSystem.POETRY
            except Exception:
                pass
            return BuildSystem.SETUPTOOLS
        
        if (self.workspace_path / "webpack.config.js").exists():
            return BuildSystem.WEBPACK
        
        if (self.workspace_path / "vite.config.js").exists() or \
           (self.workspace_path / "vite.config.ts").exists():
            return BuildSystem.VITE
        
        return BuildSystem.GENERIC
    
    def _detect_test_framework(self) -> TestFramework:
        """Detect the test framework from workspace files and dependencies."""
        # Python test frameworks
        if self._has_dependency("pytest"):
            return TestFramework.PYTEST
        
        # Node.js test frameworks
        if self._has_dependency("jest"):
            return TestFramework.JEST
        
        if self._has_dependency("mocha"):
            return TestFramework.MOCHA
        
        # Java test frameworks
        if self._has_dependency("junit"):
            return TestFramework.JUNIT
        
        if self._has_dependency("testng"):
            return TestFramework.TESTNG
        
        # Language-specific defaults
        if (self.workspace_path / "Cargo.toml").exists():
            return TestFramework.CARGO_TEST
        
        if (self.workspace_path / "go.mod").exists():
            return TestFramework.GO_TEST
        
        if (self.workspace_path / "Gemfile").exists():
            return TestFramework.RSPEC
        
        if (self.workspace_path / "composer.json").exists():
            return TestFramework.PHPUNIT
        
        # Python default
        if any((self.workspace_path / "test").glob("test_*.py")) or \
           any((self.workspace_path / "tests").glob("test_*.py")):
            return TestFramework.UNITTEST
        
        return TestFramework.GENERIC
    
    def _has_dependency(self, dependency_name: str) -> bool:
        """Check if a dependency is present in the project."""
        # Check Python dependencies
        if (self.workspace_path / "requirements.txt").exists():
            try:
                with open(self.workspace_path / "requirements.txt") as f:
                    return dependency_name in f.read()
            except Exception:
                pass
        
        if (self.workspace_path / "pyproject.toml").exists():
            try:
                with open(self.workspace_path / "pyproject.toml") as f:
                    return dependency_name in f.read()
            except Exception:
                pass
        
        # Check Node.js dependencies
        if (self.workspace_path / "package.json").exists():
            try:
                with open(self.workspace_path / "package.json") as f:
                    package_data = json.load(f)
                    deps = package_data.get("dependencies", {})
                    dev_deps = package_data.get("devDependencies", {})
                    return dependency_name in deps or dependency_name in dev_deps
            except Exception:
                pass
        
        # Check Java Maven dependencies
        if (self.workspace_path / "pom.xml").exists():
            try:
                with open(self.workspace_path / "pom.xml") as f:
                    return dependency_name in f.read()
            except Exception:
                pass
        
        return False
    
    def _initialize_toolchain_configs(self) -> Dict[str, Dict[str, Any]]:
        """Initialize toolchain-specific configurations."""
        return {
            "python_setuptools": {
                "build_commands": ["python setup.py build"],
                "test_commands": ["python -m pytest", "python -m unittest discover"],
                "lint_commands": ["flake8", "pylint", "black --check"],
                "format_commands": ["black", "isort"],
                "install_commands": ["pip install -e ."],
                "clean_commands": ["python setup.py clean --all"],
                "environment_vars": {"PYTHONPATH": "."}
            },
            "python_poetry": {
                "build_commands": ["poetry build"],
                "test_commands": ["poetry run pytest", "poetry run python -m unittest"],
                "lint_commands": ["poetry run flake8", "poetry run black --check"],
                "format_commands": ["poetry run black", "poetry run isort"],
                "install_commands": ["poetry install"],
                "clean_commands": ["poetry cache clear --all pypi"],
                "environment_vars": {}
            },
            "nodejs_npm": {
                "build_commands": ["npm run build", "npm run compile"],
                "test_commands": ["npm test", "npm run test"],
                "lint_commands": ["npm run lint", "eslint ."],
                "format_commands": ["npm run format", "prettier --write ."],
                "install_commands": ["npm install"],
                "clean_commands": ["npm run clean", "rm -rf node_modules"],
                "environment_vars": {"NODE_ENV": "development"}
            },
            "nodejs_yarn": {
                "build_commands": ["yarn build", "yarn compile"],
                "test_commands": ["yarn test"],
                "lint_commands": ["yarn lint"],
                "format_commands": ["yarn format"],
                "install_commands": ["yarn install"],
                "clean_commands": ["yarn clean", "rm -rf node_modules"],
                "environment_vars": {"NODE_ENV": "development"}
            },
            "java_maven": {
                "build_commands": ["mvn compile", "mvn package"],
                "test_commands": ["mvn test"],
                "lint_commands": ["mvn checkstyle:check"],
                "format_commands": ["mvn fmt:format"],
                "install_commands": ["mvn install"],
                "clean_commands": ["mvn clean"],
                "environment_vars": {"MAVEN_OPTS": "-Xmx1024m"}
            },
            "java_gradle": {
                "build_commands": ["./gradlew build", "gradle build"],
                "test_commands": ["./gradlew test", "gradle test"],
                "lint_commands": ["./gradlew checkstyleMain"],
                "format_commands": ["./gradlew spotlessApply"],
                "install_commands": ["./gradlew assemble"],
                "clean_commands": ["./gradlew clean"],
                "environment_vars": {"GRADLE_OPTS": "-Xmx1024m"}
            },
            "rust_cargo": {
                "build_commands": ["cargo build", "cargo build --release"],
                "test_commands": ["cargo test"],
                "lint_commands": ["cargo clippy"],
                "format_commands": ["cargo fmt"],
                "install_commands": ["cargo fetch"],
                "clean_commands": ["cargo clean"],
                "environment_vars": {"RUST_BACKTRACE": "1"}
            },
            "go_go": {
                "build_commands": ["go build", "go build ./..."],
                "test_commands": ["go test ./..."],
                "lint_commands": ["golint ./...", "go vet ./..."],
                "format_commands": ["go fmt ./..."],
                "install_commands": ["go mod download"],
                "clean_commands": ["go clean", "go mod tidy"],
                "environment_vars": {"GO111MODULE": "on"}
            }
        }
    
    def _get_generic_config(self) -> Dict[str, Any]:
        """Get generic configuration for unknown toolchains."""
        return {
            "build_commands": ["make", "make build"],
            "test_commands": ["make test"],
            "lint_commands": ["make lint"],
            "format_commands": ["make format"],
            "install_commands": ["make install"],
            "clean_commands": ["make clean"],
            "environment_vars": {}
        }
    
    def build_project(self, build_command: str = None, 
                     verify_artifacts: bool = True) -> BuildResult:
        """
        Build the project using the detected or specified build system.
        
        Args:
            build_command: Custom build command (uses detected if None)
            verify_artifacts: Whether to verify build artifacts were created
            
        Returns:
            BuildResult with comprehensive build information
        """
        # Determine build command
        if build_command is None:
            build_commands = self.toolchain_config.build_commands
            build_command = build_commands[0] if build_commands else "make"
        
        # Record build artifacts before build
        artifacts_before = self._get_build_artifacts()
        
        # Execute build command with environment variables
        env_vars = self.toolchain_config.environment_vars.copy()
        working_dir = self.toolchain_config.working_directory or str(self.workspace_path)
        
        result = self.executor.execute_command(
            build_command,
            working_dir=working_dir,
            env_vars=env_vars
        )
        
        # Record build artifacts after build
        artifacts_after = self._get_build_artifacts()
        artifacts_created = list(set(artifacts_after) - set(artifacts_before))
        
        # Parse build output for warnings and errors
        warnings_count = self._count_build_warnings(result.output, result.error_output)
        errors_count = self._count_build_errors(result.output, result.error_output)
        
        # Create verified outcome
        outcome_status = OutcomeStatus.SUCCESS if result.exit_code == 0 else OutcomeStatus.FAILURE
        outcome_details = {
            "build_system": self.toolchain_config.build_system.value,
            "command": build_command,
            "exit_code": result.exit_code,
            "artifacts_created": len(artifacts_created),
            "warnings": warnings_count,
            "errors": errors_count
        }
        
        if verify_artifacts and result.exit_code == 0 and not artifacts_created:
            outcome_status = OutcomeStatus.PARTIAL
            outcome_details["warning"] = "Build succeeded but no artifacts were created"
        
        verified_outcome = VerifiedOutcome(
            action_id=f"build_{self.executor.session_id}_{int(result.timestamp.timestamp())}",
            outcome_type="build",
            status=outcome_status,
            description=f"Build using {self.toolchain_config.build_system.value}",
            evidence=outcome_details,
            verification_method="artifact_analysis"
        )
        
        # Track with history tracker
        self.history_tracker.add_verified_outcome(verified_outcome)
        
        return BuildResult(
            success=result.exit_code == 0,
            duration=result.duration,
            output=result.output,
            error_output=result.error_output,
            artifacts_created=artifacts_created,
            warnings_count=warnings_count,
            errors_count=errors_count,
            build_system=self.toolchain_config.build_system,
            verified_outcome=verified_outcome
        )
    
    def run_tests(self, test_command: str = None, 
                  coverage: bool = True) -> TestResult:
        """
        Run tests using the detected or specified test framework.
        
        Args:
            test_command: Custom test command (uses detected if None)
            coverage: Whether to collect coverage information
            
        Returns:
            TestResult with comprehensive test information
        """
        # Determine test command
        if test_command is None:
            test_commands = self.toolchain_config.test_commands
            test_command = test_commands[0] if test_commands else "make test"
        
        # Add coverage flags if requested
        if coverage:
            test_command = self._add_coverage_flags(test_command)
        
        # Execute test command with environment variables
        env_vars = self.toolchain_config.environment_vars.copy()
        working_dir = self.toolchain_config.working_directory or str(self.workspace_path)
        
        result = self.executor.execute_command(
            test_command,
            working_dir=working_dir,
            env_vars=env_vars
        )
        
        # Parse test output
        test_stats = self._parse_test_output(result.output, result.error_output)
        coverage_percentage = self._extract_coverage_percentage(result.output, result.error_output)
        
        # Create verified outcome
        outcome_status = OutcomeStatus.SUCCESS if result.exit_code == 0 else OutcomeStatus.FAILURE
        if result.exit_code == 0 and test_stats["tests_failed"] > 0:
            outcome_status = OutcomeStatus.PARTIAL
        
        outcome_details = {
            "test_framework": self.toolchain_config.test_framework.value,
            "command": test_command,
            "exit_code": result.exit_code,
            "tests_run": test_stats["tests_run"],
            "tests_passed": test_stats["tests_passed"],
            "tests_failed": test_stats["tests_failed"],
            "tests_skipped": test_stats["tests_skipped"],
            "coverage_percentage": coverage_percentage
        }
        
        verified_outcome = VerifiedOutcome(
            action_id=f"test_{self.executor.session_id}_{int(result.timestamp.timestamp())}",
            outcome_type="test",
            status=outcome_status,
            description=f"Test using {self.toolchain_config.test_framework.value}",
            evidence=outcome_details,
            verification_method="test_output_analysis"
        )
        
        # Track with history tracker
        self.history_tracker.add_verified_outcome(verified_outcome)
        
        return TestResult(
            success=result.exit_code == 0,
            duration=result.duration,
            output=result.output,
            error_output=result.error_output,
            tests_run=test_stats["tests_run"],
            tests_passed=test_stats["tests_passed"],
            tests_failed=test_stats["tests_failed"],
            tests_skipped=test_stats["tests_skipped"],
            coverage_percentage=coverage_percentage,
            test_framework=self.toolchain_config.test_framework,
            verified_outcome=verified_outcome
        )
    
    def lint_code(self, lint_command: str = None) -> CommandInfo:
        """
        Run code linting using the detected or specified linter.
        
        Args:
            lint_command: Custom lint command (uses detected if None)
            
        Returns:
            CommandInfo with lint results
        """
        if lint_command is None:
            lint_commands = self.toolchain_config.lint_commands
            lint_command = lint_commands[0] if lint_commands else "echo 'No linter configured'"
        
        env_vars = self.toolchain_config.environment_vars.copy()
        working_dir = self.toolchain_config.working_directory or str(self.workspace_path)
        
        result = self.executor.execute_command(
            lint_command,
            working_dir=working_dir,
            env_vars=env_vars
        )
        
        # Create verified outcome for linting
        issues_count = self._count_lint_issues(result.output, result.error_output)
        outcome_status = OutcomeStatus.SUCCESS if result.exit_code == 0 else OutcomeStatus.FAILURE
        
        verified_outcome = VerifiedOutcome(
            action_id=f"lint_{self.executor.session_id}_{int(result.timestamp.timestamp())}",
            outcome_type="lint",
            status=outcome_status,
            description=f"Code linting",
            evidence={
                "command": lint_command,
                "exit_code": result.exit_code,
                "issues_found": issues_count
            },
            verification_method="lint_output_analysis"
        )
        
        # Track with history tracker
        self.history_tracker.add_verified_outcome(verified_outcome)
        
        return result
    
    def format_code(self, format_command: str = None) -> CommandInfo:
        """
        Format code using the detected or specified formatter.
        
        Args:
            format_command: Custom format command (uses detected if None)
            
        Returns:
            CommandInfo with format results
        """
        if format_command is None:
            format_commands = self.toolchain_config.format_commands
            format_command = format_commands[0] if format_commands else "echo 'No formatter configured'"
        
        env_vars = self.toolchain_config.environment_vars.copy()
        working_dir = self.toolchain_config.working_directory or str(self.workspace_path)
        
        result = self.executor.execute_command(
            format_command,
            working_dir=working_dir,
            env_vars=env_vars
        )
        
        # Create verified outcome for formatting
        verified_outcome = VerifiedOutcome(
            action_id=f"format_{self.executor.session_id}_{int(result.timestamp.timestamp())}",
            outcome_type="format",
            status=OutcomeStatus.SUCCESS if result.exit_code == 0 else OutcomeStatus.FAILURE,
            description="Code formatting",
            evidence={
                "command": format_command,
                "exit_code": result.exit_code
            },
            verification_method="command_exit_code"
        )
        
        # Track with history tracker
        self.history_tracker.add_verified_outcome(verified_outcome)
        
        return result
    
    def install_dependencies(self, install_command: str = None) -> CommandInfo:
        """
        Install project dependencies using the detected package manager.
        
        Args:
            install_command: Custom install command (uses detected if None)
            
        Returns:
            CommandInfo with installation results
        """
        if install_command is None:
            install_commands = self.toolchain_config.install_commands
            install_command = install_commands[0] if install_commands else "echo 'No install command configured'"
        
        env_vars = self.toolchain_config.environment_vars.copy()
        working_dir = self.toolchain_config.working_directory or str(self.workspace_path)
        
        result = self.executor.execute_command(
            install_command,
            working_dir=working_dir,
            env_vars=env_vars
        )
        
        # Create verified outcome for dependency installation
        verified_outcome = VerifiedOutcome(
            action_id=f"install_{self.executor.session_id}_{int(result.timestamp.timestamp())}",
            outcome_type="install_dependencies",
            status=OutcomeStatus.SUCCESS if result.exit_code == 0 else OutcomeStatus.FAILURE,
            description="Dependency installation",
            evidence={
                "command": install_command,
                "exit_code": result.exit_code,
                "build_system": self.toolchain_config.build_system.value
            },
            verification_method="command_exit_code"
        )
        
        # Track with history tracker
        self.history_tracker.add_verified_outcome(verified_outcome)
        
        return result
    
    def clean_project(self, clean_command: str = None) -> CommandInfo:
        """
        Clean project build artifacts using the detected build system.
        
        Args:
            clean_command: Custom clean command (uses detected if None)
            
        Returns:
            CommandInfo with clean results
        """
        if clean_command is None:
            clean_commands = self.toolchain_config.clean_commands
            clean_command = clean_commands[0] if clean_commands else "echo 'No clean command configured'"
        
        env_vars = self.toolchain_config.environment_vars.copy()
        working_dir = self.toolchain_config.working_directory or str(self.workspace_path)
        
        result = self.executor.execute_command(
            clean_command,
            working_dir=working_dir,
            env_vars=env_vars
        )
        
        # Create verified outcome for cleaning
        verified_outcome = VerifiedOutcome(
            action_id=f"clean_{self.executor.session_id}_{int(result.timestamp.timestamp())}",
            outcome_type="clean",
            status=OutcomeStatus.SUCCESS if result.exit_code == 0 else OutcomeStatus.FAILURE,
            description="Project cleanup",
            evidence={
                "command": clean_command,
                "exit_code": result.exit_code
            },
            verification_method="command_exit_code"
        )
        
        # Track with history tracker
        self.history_tracker.add_verified_outcome(verified_outcome)
        
        return result
    
    def run_development_workflow(self, steps: List[str] = None) -> Dict[str, Any]:
        """
        Run a complete development workflow with multiple steps.
        
        Args:
            steps: List of workflow steps (default: install, lint, test, build)
            
        Returns:
            Dictionary with results from each workflow step
        """
        if steps is None:
            steps = ["install", "lint", "test", "build"]
        
        workflow_results = {}
        overall_success = True
        
        for step in steps:
            try:
                if step == "install":
                    result = self.install_dependencies()
                    workflow_results["install"] = {
                        "success": result.exit_code == 0,
                        "duration": result.duration,
                        "command": result.command
                    }
                elif step == "lint":
                    result = self.lint_code()
                    workflow_results["lint"] = {
                        "success": result.exit_code == 0,
                        "duration": result.duration,
                        "command": result.command
                    }
                elif step == "test":
                    result = self.run_tests()
                    workflow_results["test"] = {
                        "success": result.success,
                        "duration": result.duration,
                        "tests_run": result.tests_run,
                        "tests_passed": result.tests_passed,
                        "tests_failed": result.tests_failed,
                        "coverage": result.coverage_percentage
                    }
                elif step == "build":
                    result = self.build_project()
                    workflow_results["build"] = {
                        "success": result.success,
                        "duration": result.duration,
                        "artifacts_created": len(result.artifacts_created),
                        "warnings": result.warnings_count,
                        "errors": result.errors_count
                    }
                elif step == "format":
                    result = self.format_code()
                    workflow_results["format"] = {
                        "success": result.exit_code == 0,
                        "duration": result.duration,
                        "command": result.command
                    }
                elif step == "clean":
                    result = self.clean_project()
                    workflow_results["clean"] = {
                        "success": result.exit_code == 0,
                        "duration": result.duration,
                        "command": result.command
                    }
                
                # Update overall success
                step_success = workflow_results.get(step, {}).get("success", False)
                overall_success = overall_success and step_success
                
            except Exception as e:
                workflow_results[step] = {
                    "success": False,
                    "error": str(e),
                    "duration": 0.0
                }
                overall_success = False
        
        # Create overall workflow outcome
        verified_outcome = VerifiedOutcome(
            action_id=f"workflow_{self.executor.session_id}_{int(datetime.now().timestamp())}",
            outcome_type="development_workflow",
            status=OutcomeStatus.SUCCESS if overall_success else OutcomeStatus.FAILURE,
            description="Complete development workflow",
            evidence={
                "steps_executed": steps,
                "overall_success": overall_success,
                "step_results": workflow_results
            },
            verification_method="workflow_step_analysis"
        )
        
        # Track workflow with history tracker
        self.history_tracker.add_verified_outcome(verified_outcome)
        
        return {
            "overall_success": overall_success,
            "steps": workflow_results,
            "toolchain_config": {
                "toolchain_type": self.toolchain_config.toolchain_type.value,
                "build_system": self.toolchain_config.build_system.value,
                "test_framework": self.toolchain_config.test_framework.value
            },
            "verified_outcome": verified_outcome
        }
    
    def get_toolchain_summary(self) -> Dict[str, Any]:
        """Get a summary of the detected toolchain configuration."""
        return {
            "toolchain_type": self.toolchain_config.toolchain_type.value,
            "build_system": self.toolchain_config.build_system.value,
            "test_framework": self.toolchain_config.test_framework.value,
            "workspace_path": str(self.workspace_path),
            "build_commands": self.toolchain_config.build_commands,
            "test_commands": self.toolchain_config.test_commands,
            "lint_commands": self.toolchain_config.lint_commands,
            "format_commands": self.toolchain_config.format_commands,
            "install_commands": self.toolchain_config.install_commands,
            "clean_commands": self.toolchain_config.clean_commands,
            "environment_vars": self.toolchain_config.environment_vars
        }
    
    def export_workflow_summary(self, format: str = "json") -> str:
        """
        Export development workflow summary using ExecutionHistoryTracker.
        
        Args:
            format: Export format ("json" or "markdown")
            
        Returns:
            Formatted workflow summary
        """
        return self.history_tracker.export_execution_history(
            session_id=self.executor.session_id,
            format=format
        )
    
    # Helper methods for parsing and analysis
    
    def _get_build_artifacts(self) -> List[str]:
        """Get list of potential build artifacts in the workspace."""
        artifacts = []
        
        # Common build artifact patterns
        patterns = [
            "**/*.jar", "**/*.war", "**/*.ear",  # Java
            "**/target/**", "**/build/**",       # Build directories
            "**/*.whl", "**/*.egg", "**/dist/**", # Python
            "**/node_modules/**", "**/build/**", # Node.js
            "**/target/release/**", "**/target/debug/**", # Rust
            "**/*.exe", "**/*.dll", "**/*.so",   # Binaries
            "**/*.a", "**/*.lib"                 # Libraries
        ]
        
        for pattern in patterns:
            try:
                artifacts.extend([str(p) for p in self.workspace_path.glob(pattern) if p.is_file()])
            except Exception:
                continue
        
        return artifacts
    
    def _count_build_warnings(self, output: str, error_output: str) -> int:
        """Count build warnings in output."""
        combined_output = f"{output}\n{error_output}"
        warning_patterns = [
            r"warning:",
            r"warn:",
            r"\bwarning\b",
            r"deprecated",
            r"caution"
        ]
        
        count = 0
        for pattern in warning_patterns:
            count += len(re.findall(pattern, combined_output, re.IGNORECASE))
        
        return count
    
    def _count_build_errors(self, output: str, error_output: str) -> int:
        """Count build errors in output."""
        combined_output = f"{output}\n{error_output}"
        error_patterns = [
            r"error:",
            r"err:",
            r"\berror\b",
            r"failed",
            r"exception"
        ]
        
        count = 0
        for pattern in error_patterns:
            count += len(re.findall(pattern, combined_output, re.IGNORECASE))
        
        return count
    
    def _add_coverage_flags(self, test_command: str) -> str:
        """Add coverage flags to test command based on framework."""
        if "pytest" in test_command:
            return f"{test_command} --cov=."
        elif "jest" in test_command:
            return f"{test_command} --coverage"
        elif "go test" in test_command:
            return f"{test_command} -cover"
        elif "cargo test" in test_command:
            return f"cargo tarpaulin"
        
        return test_command
    
    def _parse_test_output(self, output: str, error_output: str) -> Dict[str, int]:
        """Parse test output to extract test statistics."""
        combined_output = f"{output}\n{error_output}"
        
        stats = {
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "tests_skipped": 0
        }
        
        # Pytest patterns
        pytest_match = re.search(r"(\d+) passed.*?(\d+) failed.*?(\d+) skipped", combined_output)
        if pytest_match:
            stats["tests_passed"] = int(pytest_match.group(1))
            stats["tests_failed"] = int(pytest_match.group(2))
            stats["tests_skipped"] = int(pytest_match.group(3))
            stats["tests_run"] = stats["tests_passed"] + stats["tests_failed"] + stats["tests_skipped"]
            return stats
        
        # Jest patterns
        jest_match = re.search(r"Tests:\s+(\d+) failed.*?(\d+) passed.*?(\d+) total", combined_output)
        if jest_match:
            stats["tests_failed"] = int(jest_match.group(1))
            stats["tests_passed"] = int(jest_match.group(2))
            stats["tests_run"] = int(jest_match.group(3))
            return stats
        
        # Generic patterns
        run_match = re.search(r"(\d+) tests? run", combined_output, re.IGNORECASE)
        if run_match:
            stats["tests_run"] = int(run_match.group(1))
        
        passed_match = re.search(r"(\d+) passed", combined_output, re.IGNORECASE)
        if passed_match:
            stats["tests_passed"] = int(passed_match.group(1))
        
        failed_match = re.search(r"(\d+) failed", combined_output, re.IGNORECASE)
        if failed_match:
            stats["tests_failed"] = int(failed_match.group(1))
        
        return stats
    
    def _extract_coverage_percentage(self, output: str, error_output: str) -> Optional[float]:
        """Extract coverage percentage from test output."""
        combined_output = f"{output}\n{error_output}"
        
        # Common coverage patterns
        patterns = [
            r"coverage:\s*(\d+(?:\.\d+)?)%",
            r"(\d+(?:\.\d+)?)%\s*coverage",
            r"Total coverage:\s*(\d+(?:\.\d+)?)%"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, combined_output, re.IGNORECASE)
            if match:
                return float(match.group(1))
        
        return None
    
    def _count_lint_issues(self, output: str, error_output: str) -> int:
        """Count linting issues in output."""
        combined_output = f"{output}\n{error_output}"
        
        # Count lines that look like lint issues
        issue_patterns = [
            r"^\s*\S+:\d+:\d+:",  # file:line:col: format
            r"^\s*\S+\(\d+,\d+\):",  # file(line,col): format
            r"error:",
            r"warning:",
            r"info:"
        ]
        
        count = 0
        for line in combined_output.split('\n'):
            for pattern in issue_patterns:
                if re.match(pattern, line):
                    count += 1
                    break
        
        return count