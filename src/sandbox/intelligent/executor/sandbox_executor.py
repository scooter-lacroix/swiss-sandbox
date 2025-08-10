"""
Enhanced SandboxExecutor with comprehensive logging integration and unrestricted command execution.
"""

import os
import subprocess
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
from ..types import CommandInfo, FileChange, ActionType
from ..logger import create_logger, ActionLoggerInterface
from .interfaces import SandboxExecutorInterface


class SandboxExecutor(SandboxExecutorInterface):
    """
    Enhanced sandbox command executor with comprehensive logging integration.
    
    Provides unrestricted command execution within a sandboxed environment while
    maintaining detailed logs of all operations through the DatabaseActionLogger.
    """
    
    def __init__(self, workspace_path: str, isolation_enabled: bool = True,
                 logger: ActionLoggerInterface = None, session_id: str = None,
                 task_id: str = None):
        """
        Initialize the SandboxExecutor with logging integration.
        
        Args:
            workspace_path: Path to the sandbox workspace
            isolation_enabled: Whether to enforce path isolation
            logger: Action logger instance (creates database logger if None)
            session_id: Session identifier for logging
            task_id: Task identifier for logging
        """
        self.workspace_path = Path(workspace_path)
        self.isolation_enabled = isolation_enabled
        self.session_id = session_id or str(uuid.uuid4())
        self.task_id = task_id
        
        # Initialize logger - use database logger by default for persistent tracking
        if logger is None:
            db_path = self.workspace_path / ".sandbox" / "command_history.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self.logger = create_logger("database", str(db_path))
        else:
            self.logger = logger
        
        # Ensure workspace directory exists
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize command execution environment
        self._setup_environment()
    
    def _setup_environment(self) -> None:
        """Set up the sandbox execution environment."""
        # Create necessary directories
        (self.workspace_path / ".sandbox").mkdir(exist_ok=True)
        (self.workspace_path / ".sandbox" / "tmp").mkdir(exist_ok=True)
        
        # Log environment setup
        self.logger.log_action(
            action_type=ActionType.ENVIRONMENT_SETUP,
            description=f"Initialized sandbox environment at {self.workspace_path}",
            details={
                "workspace_path": str(self.workspace_path),
                "isolation_enabled": self.isolation_enabled,
                "session_id": self.session_id
            },
            session_id=self.session_id,
            task_id=self.task_id
        )
    
    def execute_command(self, command: str, working_dir: str = None, 
                       timeout: int = None, env_vars: Dict[str, str] = None) -> CommandInfo:
        """
        Execute a command within the sandbox environment with comprehensive logging.
        
        Args:
            command: The command to execute
            working_dir: Working directory for the command
            timeout: Timeout in seconds (default: 300)
            env_vars: Additional environment variables
            
        Returns:
            CommandInfo with execution results
        """
        start_time = time.time()
        work_dir = Path(working_dir) if working_dir else self.workspace_path
        timeout = timeout or 300
        
        # Ensure working directory is within workspace for security
        if self.isolation_enabled:
            try:
                work_dir.resolve().relative_to(self.workspace_path.resolve())
            except ValueError:
                error_msg = f"Working directory {work_dir} is outside workspace"
                command_info = CommandInfo(
                    command=command,
                    working_directory=str(work_dir),
                    output="",
                    error_output=error_msg,
                    exit_code=-1,
                    duration=0.0
                )
                
                # Log the security violation
                self.logger.log_command(
                    command=command,
                    working_directory=str(work_dir),
                    output="",
                    error_output=error_msg,
                    exit_code=-1,
                    duration=0.0,
                    session_id=self.session_id,
                    task_id=self.task_id
                )
                
                raise PermissionError(error_msg)
        
        # Prepare environment variables
        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)
        
        # Add sandbox-specific environment variables
        env.update({
            'SANDBOX_WORKSPACE': str(self.workspace_path),
            'SANDBOX_SESSION_ID': self.session_id,
            'SANDBOX_TMP': str(self.workspace_path / ".sandbox" / "tmp")
        })
        
        try:
            # Execute the command with full output capture
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env
            )
            
            command_info = CommandInfo(
                command=command,
                working_directory=str(work_dir),
                output=result.stdout,
                error_output=result.stderr,
                exit_code=result.returncode,
                duration=time.time() - start_time
            )
            
        except subprocess.TimeoutExpired as e:
            command_info = CommandInfo(
                command=command,
                working_directory=str(work_dir),
                output=e.stdout.decode() if e.stdout else "",
                error_output=f"Command timed out after {timeout} seconds",
                exit_code=-1,
                duration=time.time() - start_time
            )
            
        except Exception as e:
            command_info = CommandInfo(
                command=command,
                working_directory=str(work_dir),
                output="",
                error_output=f"Command execution failed: {str(e)}",
                exit_code=-1,
                duration=time.time() - start_time
            )
        
        # Log the command execution using DatabaseActionLogger.log_command()
        self.logger.log_command(
            command=command_info.command,
            working_directory=command_info.working_directory,
            output=command_info.output,
            error_output=command_info.error_output,
            exit_code=command_info.exit_code,
            duration=command_info.duration,
            session_id=self.session_id,
            task_id=self.task_id
        )
        
        return command_info
    
    def create_file(self, file_path: str, content: str) -> bool:
        """
        Create a file within the sandbox with logging.
        
        Args:
            file_path: Path to the file to create
            content: Content of the file
            
        Returns:
            True if the file was created successfully
            
        Raises:
            PermissionError: If file path is outside workspace
        """
        try:
            full_path = self._resolve_path(file_path)
            
            # Create parent directories if they don't exist
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write the file
            full_path.write_text(content, encoding='utf-8')
            
            # Log the file creation
            self.logger.log_file_change(
                file_path=str(full_path),
                change_type="create",
                before_content=None,
                after_content=content,
                session_id=self.session_id,
                task_id=self.task_id
            )
            
            return True
            
        except PermissionError:
            # Re-raise permission errors for security violations
            raise
        except Exception as e:
            # Log the error
            self.logger.log_error(
                error_type=type(e).__name__,
                message=f"Failed to create file {file_path}: {str(e)}",
                context={
                    "file_path": file_path,
                    "operation": "create_file"
                },
                session_id=self.session_id,
                task_id=self.task_id
            )
            return False
    
    def modify_file(self, file_path: str, content: str) -> bool:
        """
        Modify an existing file within the sandbox with logging.
        
        Args:
            file_path: Path to the file to modify
            content: New content of the file
            
        Returns:
            True if the file was modified successfully
            
        Raises:
            PermissionError: If file path is outside workspace
        """
        try:
            full_path = self._resolve_path(file_path)
            
            # Read existing content for tracking
            before_content = None
            if full_path.exists():
                before_content = full_path.read_text(encoding='utf-8')
            
            # Write the new content
            full_path.write_text(content, encoding='utf-8')
            
            # Log the file modification
            self.logger.log_file_change(
                file_path=str(full_path),
                change_type="modify",
                before_content=before_content,
                after_content=content,
                session_id=self.session_id,
                task_id=self.task_id
            )
            
            return True
            
        except PermissionError:
            # Re-raise permission errors for security violations
            raise
        except Exception as e:
            # Log the error
            self.logger.log_error(
                error_type=type(e).__name__,
                message=f"Failed to modify file {file_path}: {str(e)}",
                context={
                    "file_path": file_path,
                    "operation": "modify_file"
                },
                session_id=self.session_id,
                task_id=self.task_id
            )
            return False
    
    def delete_file(self, file_path: str) -> bool:
        """
        Delete a file within the sandbox with logging.
        
        Args:
            file_path: Path to the file to delete
            
        Returns:
            True if the file was deleted successfully
            
        Raises:
            PermissionError: If file path is outside workspace
        """
        try:
            full_path = self._resolve_path(file_path)
            
            # Read existing content for tracking
            before_content = None
            if full_path.exists():
                before_content = full_path.read_text(encoding='utf-8')
            
            # Delete the file
            if full_path.exists():
                full_path.unlink()
            
            # Log the file deletion
            self.logger.log_file_change(
                file_path=str(full_path),
                change_type="delete",
                before_content=before_content,
                after_content=None,
                session_id=self.session_id,
                task_id=self.task_id
            )
            
            return True
            
        except PermissionError:
            # Re-raise permission errors for security violations
            raise
        except Exception as e:
            # Log the error
            self.logger.log_error(
                error_type=type(e).__name__,
                message=f"Failed to delete file {file_path}: {str(e)}",
                context={
                    "file_path": file_path,
                    "operation": "delete_file"
                },
                session_id=self.session_id,
                task_id=self.task_id
            )
            return False
    
    def install_package(self, package_name: str, package_manager: str = "auto") -> bool:
        """
        Install a package within the sandbox environment with logging.
        
        Args:
            package_name: Name of the package to install
            package_manager: Package manager to use (pip, npm, yarn, apt, etc.)
            
        Returns:
            True if the package was installed successfully
        """
        # Determine package manager if auto
        if package_manager == "auto":
            package_manager = self._detect_package_manager()
        
        # Build install command based on package manager
        install_commands = {
            "pip": f"pip install {package_name}",
            "pip3": f"pip3 install {package_name}",
            "npm": f"npm install {package_name}",
            "yarn": f"yarn add {package_name}",
            "apt": f"apt-get update && apt-get install -y {package_name}",
            "apt-get": f"apt-get update && apt-get install -y {package_name}",
            "yum": f"yum install -y {package_name}",
            "dnf": f"dnf install -y {package_name}",
            "brew": f"brew install {package_name}",
            "conda": f"conda install -y {package_name}",
            "gem": f"gem install {package_name}",
            "cargo": f"cargo install {package_name}",
            "go": f"go install {package_name}",
        }
        
        command = install_commands.get(package_manager)
        if not command:
            # Log unsupported package manager
            self.logger.log_error(
                error_type="UnsupportedPackageManager",
                message=f"Unsupported package manager: {package_manager}",
                context={
                    "package_name": package_name,
                    "package_manager": package_manager,
                    "supported_managers": list(install_commands.keys())
                },
                session_id=self.session_id,
                task_id=self.task_id
            )
            return False
        
        # Execute the install command
        result = self.execute_command(command)
        success = result.exit_code == 0
        
        # Log the package installation result
        self.logger.log_action(
            action_type=ActionType.PACKAGE_INSTALL,
            description=f"Install package {package_name} using {package_manager}",
            details={
                "package_name": package_name,
                "package_manager": package_manager,
                "command": command,
                "success": success,
                "exit_code": result.exit_code
            },
            session_id=self.session_id,
            task_id=self.task_id
        )
        
        return success
    
    def _detect_package_manager(self) -> str:
        """Detect the appropriate package manager for the workspace."""
        # Check for language-specific package files
        if (self.workspace_path / "package.json").exists():
            # Check if yarn.lock exists to prefer yarn over npm
            if (self.workspace_path / "yarn.lock").exists():
                return "yarn"
            return "npm"
        
        if (self.workspace_path / "requirements.txt").exists() or \
           (self.workspace_path / "pyproject.toml").exists() or \
           (self.workspace_path / "setup.py").exists():
            return "pip"
        
        if (self.workspace_path / "Gemfile").exists():
            return "gem"
        
        if (self.workspace_path / "Cargo.toml").exists():
            return "cargo"
        
        if (self.workspace_path / "go.mod").exists():
            return "go"
        
        if (self.workspace_path / "environment.yml").exists():
            return "conda"
        
        # Default to pip for Python environments
        return "pip"
    
    def _resolve_path(self, file_path: str) -> Path:
        """
        Resolve a file path within the workspace with security validation.
        
        Args:
            file_path: File path to resolve
            
        Returns:
            Resolved Path object
            
        Raises:
            PermissionError: If path is outside workspace when isolation is enabled
        """
        path = Path(file_path)
        
        # If it's not absolute, make it relative to workspace
        if not path.is_absolute():
            path = self.workspace_path / path
        
        # Ensure path is within workspace for security
        if self.isolation_enabled:
            try:
                path.resolve().relative_to(self.workspace_path.resolve())
            except ValueError:
                raise PermissionError(f"Path {file_path} is outside workspace")
        
        return path
    
    def execute_shell_script(self, script_content: str, script_name: str = None) -> CommandInfo:
        """
        Execute a shell script within the sandbox.
        
        Args:
            script_content: Content of the shell script
            script_name: Optional name for the script file
            
        Returns:
            CommandInfo with execution results
        """
        script_name = script_name or f"script_{int(time.time())}.sh"
        script_path = self.workspace_path / ".sandbox" / "tmp" / script_name
        
        try:
            # Create the script file
            script_path.write_text(script_content, encoding='utf-8')
            script_path.chmod(0o755)  # Make executable
            
            # Execute the script
            result = self.execute_command(f"bash {script_path}")
            
            # Clean up the script file
            script_path.unlink()
            
            return result
            
        except Exception as e:
            # Log the error
            self.logger.log_error(
                error_type=type(e).__name__,
                message=f"Failed to execute shell script: {str(e)}",
                context={
                    "script_name": script_name,
                    "script_content": script_content[:200] + "..." if len(script_content) > 200 else script_content
                },
                session_id=self.session_id,
                task_id=self.task_id
            )
            
            return CommandInfo(
                command=f"bash {script_path}",
                working_directory=str(self.workspace_path),
                output="",
                error_output=f"Script execution failed: {str(e)}",
                exit_code=-1,
                duration=0.0
            )
    
    def configure_system(self, config_commands: List[str]) -> List[CommandInfo]:
        """
        Execute system configuration commands within the sandbox.
        
        Args:
            config_commands: List of configuration commands to execute
            
        Returns:
            List of CommandInfo results for each command
        """
        results = []
        
        for command in config_commands:
            result = self.execute_command(command)
            results.append(result)
            
            # Log configuration step
            self.logger.log_action(
                action_type=ActionType.SYSTEM_CONFIG,
                description=f"System configuration command: {command}",
                details={
                    "command": command,
                    "success": result.exit_code == 0,
                    "exit_code": result.exit_code
                },
                session_id=self.session_id,
                task_id=self.task_id
            )
        
        return results
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all operations performed in this session.
        
        Returns:
            Dictionary containing execution summary
        """
        if hasattr(self.logger, 'get_log_summary'):
            summary = self.logger.get_log_summary(session_id=self.session_id)
            return {
                "session_id": self.session_id,
                "task_id": self.task_id,
                "workspace_path": str(self.workspace_path),
                "total_actions": summary.total_actions,
                "commands_executed": summary.commands_executed,
                "files_modified": summary.files_modified,
                "errors_encountered": summary.errors_encountered,
                "time_range": summary.time_range
            }
        else:
            return {
                "session_id": self.session_id,
                "task_id": self.task_id,
                "workspace_path": str(self.workspace_path),
                "message": "Detailed summary not available with current logger"
            }
    
    def export_execution_log(self, format: str = "json") -> str:
        """
        Export the execution log for this session.
        
        Args:
            format: Export format ("json" or "csv")
            
        Returns:
            Formatted log data as string
        """
        if hasattr(self.logger, 'export_logs'):
            from ..logger.models import LogQuery
            query = LogQuery(session_id=self.session_id)
            return self.logger.export_logs(query, format)
        else:
            return f"Log export not available with current logger type"
    
    def cleanup_session(self) -> None:
        """Clean up session-specific resources and temporary files."""
        try:
            # Clean up temporary files
            tmp_dir = self.workspace_path / ".sandbox" / "tmp"
            if tmp_dir.exists():
                import shutil
                shutil.rmtree(tmp_dir)
                tmp_dir.mkdir(exist_ok=True)
            
            # Log cleanup
            self.logger.log_action(
                action_type=ActionType.SESSION_CLEANUP,
                description=f"Cleaned up session {self.session_id}",
                details={
                    "session_id": self.session_id,
                    "workspace_path": str(self.workspace_path)
                },
                session_id=self.session_id,
                task_id=self.task_id
            )
            
        except Exception as e:
            self.logger.log_error(
                error_type=type(e).__name__,
                message=f"Failed to cleanup session: {str(e)}",
                context={"session_id": self.session_id},
                session_id=self.session_id,
                task_id=self.task_id
            )