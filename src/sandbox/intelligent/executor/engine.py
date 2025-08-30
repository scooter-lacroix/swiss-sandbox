"""
Concrete implementation of task execution functionality.
"""

import os
import subprocess
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from ..planner.models import TaskPlan, Task
from ..types import TaskStatus, ErrorInfo, CommandInfo, FileChange, ActionType
from .interfaces import ExecutionEngineInterface, SandboxExecutorInterface
from .models import (
    ExecutionResult, TaskResult, RetryContext, SandboxExecutor, 
    AttemptInfo, ErrorRecoveryStrategy
)
from .multi_file_coordinator import MultiFileCoordinator, FileOperation, MultiFileTransaction


class SandboxCommandExecutor(SandboxExecutorInterface):
    """
    Concrete implementation of sandbox command execution with file tracking.
    """
    
    def __init__(self, workspace_path: str, isolation_enabled: bool = True):
        self.workspace_path = Path(workspace_path)
        self.isolation_enabled = isolation_enabled
        self.file_changes: List[FileChange] = []
        self.commands_executed: List[CommandInfo] = []
        self.multi_file_coordinator = MultiFileCoordinator(workspace_path)
        
        # Ensure workspace directory exists
        self.workspace_path.mkdir(parents=True, exist_ok=True)
    
    def execute_command(self, command: str, working_dir: Optional[str] = None,
                       timeout: Optional[int] = None) -> CommandInfo:
        """Execute a command within the sandbox environment."""
        start_time = time.time()
        work_dir = Path(working_dir) if working_dir else self.workspace_path

        # Ensure working directory is within workspace for security
        if self.isolation_enabled:
            try:
                work_dir.resolve().relative_to(self.workspace_path.resolve())
            except ValueError:
                raise PermissionError(f"Working directory {work_dir} is outside workspace")

        # Use provided timeout, or environment variable, or default
        if timeout is None:
            env_timeout = os.getenv('SANDBOX_COMMAND_TIMEOUT')
            if env_timeout:
                try:
                    if env_timeout.lower() in ('none', '0'):
                        timeout = None
                    else:
                        timeout = int(env_timeout)
                except ValueError:
                    timeout = 300  # fallback to 5 minutes
            else:
                timeout = 300  # default 5 minutes

        try:
            if timeout is not None:
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=str(work_dir),
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
            else:
                # No timeout - run without timeout parameter
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=str(work_dir),
                    capture_output=True,
                    text=True
                )
            
            command_info = CommandInfo(
                command=command,
                working_directory=str(work_dir),
                output=result.stdout or "",
                error_output=result.stderr or "",
                exit_code=result.returncode,
                duration=time.time() - start_time
            )
            
        except subprocess.TimeoutExpired:
            command_info = CommandInfo(
                command=command,
                working_directory=str(work_dir),
                output="",
                error_output="Command timed out",
                exit_code=-1,
                duration=time.time() - start_time
            )
        except Exception as e:
            command_info = CommandInfo(
                command=command,
                working_directory=str(work_dir),
                output="",
                error_output=str(e),
                exit_code=-1,
                duration=time.time() - start_time
            )
        
        self.commands_executed.append(command_info)
        return command_info
    
    def create_file(self, file_path: str, content: str) -> bool:
        """Create a file within the sandbox."""
        try:
            full_path = self._resolve_path(file_path)
            
            # Create parent directories if they don't exist
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Track the change
            file_change = FileChange(
                file_path=str(full_path),
                change_type="create",
                before_content=None,
                after_content=content
            )
            
            # Write the file
            full_path.write_text(content, encoding='utf-8')
            
            self.file_changes.append(file_change)
            return True
            
        except Exception as e:
            print(f"Error creating file {file_path}: {e}")
            return False
    
    def modify_file(self, file_path: str, content: str) -> bool:
        """Modify an existing file within the sandbox."""
        try:
            full_path = self._resolve_path(file_path)
            
            # Read existing content for tracking
            before_content = None
            if full_path.exists():
                before_content = full_path.read_text(encoding='utf-8')
            
            # Track the change
            file_change = FileChange(
                file_path=str(full_path),
                change_type="modify",
                before_content=before_content,
                after_content=content
            )
            
            # Write the new content
            full_path.write_text(content, encoding='utf-8')
            
            self.file_changes.append(file_change)
            return True
            
        except Exception as e:
            print(f"Error modifying file {file_path}: {e}")
            return False
    
    def delete_file(self, file_path: str) -> bool:
        """Delete a file within the sandbox."""
        try:
            full_path = self._resolve_path(file_path)
            
            # Read existing content for tracking
            before_content = None
            if full_path.exists():
                before_content = full_path.read_text(encoding='utf-8')
            
            # Track the change
            file_change = FileChange(
                file_path=str(full_path),
                change_type="delete",
                before_content=before_content,
                after_content=None
            )
            
            # Delete the file
            if full_path.exists():
                full_path.unlink()
            
            self.file_changes.append(file_change)
            return True
            
        except Exception as e:
            print(f"Error deleting file {file_path}: {e}")
            return False
    
    def install_package(self, package_name: str, package_manager: str = "auto") -> bool:
        """Install a package within the sandbox environment."""
        # Determine package manager if auto
        if package_manager == "auto":
            if (self.workspace_path / "package.json").exists():
                package_manager = "npm"
            elif (self.workspace_path / "requirements.txt").exists() or (self.workspace_path / "pyproject.toml").exists():
                package_manager = "pip"
            else:
                package_manager = "pip"  # Default to pip
        
        # Build install command
        if package_manager == "pip":
            command = f"pip install {package_name}"
        elif package_manager == "npm":
            command = f"npm install {package_name}"
        elif package_manager == "yarn":
            command = f"yarn add {package_name}"
        else:
            print(f"Unsupported package manager: {package_manager}")
            return False
        
        # Execute the install command
        result = self.execute_command(command)
        return result.exit_code == 0
    
    def _resolve_path(self, file_path: str) -> Path:
        """Resolve a file path within the workspace."""
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
    
    def get_file_changes(self) -> List[FileChange]:
        """Get all file changes made during execution."""
        return self.file_changes.copy()
    
    def get_commands_executed(self) -> List[CommandInfo]:
        """Get all commands executed during execution."""
        return self.commands_executed.copy()
    
    def clear_history(self) -> None:
        """Clear the execution history."""
        self.file_changes.clear()
        self.commands_executed.clear()
    
    def execute_multi_file_operation(self, operations: List[FileOperation],
                                   transaction_id: Optional[str] = None) -> bool:
        """Execute multiple file operations as a coordinated transaction."""
        if not transaction_id:
            transaction_id = f"tx_{int(time.time())}"
        
        try:
            # Create and execute transaction
            transaction = self.multi_file_coordinator.create_transaction(
                transaction_id, operations
            )
            
            # Check for conflicts
            if transaction.conflicts:
                critical_conflicts = [c for c in transaction.conflicts if c.severity == "critical"]
                if critical_conflicts:
                    raise ValueError(f"Critical conflicts detected: "
                                   f"{[c.description for c in critical_conflicts]}")
            
            # Execute the transaction
            success = self.multi_file_coordinator.execute_transaction(transaction_id)
            
            # Record file changes for tracking
            for operation in transaction.completed_operations:
                if operation.operation_type == "create":
                    file_change = FileChange(
                        file_path=operation.file_path,
                        change_type="create",
                        before_content=None,
                        after_content=operation.content if operation.content is not None else ""
                    )
                elif operation.operation_type == "modify":
                    file_change = FileChange(
                        file_path=operation.file_path,
                        change_type="modify",
                        before_content=None,  # Would need to be captured before
                        after_content=operation.content if operation.content is not None else ""
                    )
                elif operation.operation_type == "delete":
                    file_change = FileChange(
                        file_path=operation.file_path,
                        change_type="delete",
                        before_content=None,  # Would need to be captured before
                        after_content=None
                    )
                else:
                    continue
                
                self.file_changes.append(file_change)
            
            return success
            
        except Exception as e:
            print(f"Multi-file operation failed: {e}")
            return False
    
    def create_file_operation(self, operation_type: str, file_path: str,
                            content: Optional[str] = None, target_path: Optional[str] = None,
                            dependencies: Optional[List[str]] = None) -> FileOperation:
        """Create a FileOperation object."""
        return FileOperation(
            operation_type=operation_type,
            file_path=file_path,
            content=content,
            target_path=target_path,
            dependencies=dependencies or []
        )


class ErrorRecoveryManager:
    """Manages error recovery strategies and context analysis."""
    
    def __init__(self):
        self._recovery_strategies: Dict[str, List[ErrorRecoveryStrategy]] = {}
        self._initialize_default_strategies()
    
    def _initialize_default_strategies(self) -> None:
        """Initialize default recovery strategies for common error types."""
        # File permission errors
        self.register_strategy(ErrorRecoveryStrategy(
            error_type="PermissionError",
            description="Fix file permission issues",
            suggested_actions=[
                "Check file permissions",
                "Ensure workspace directory is writable",
                "Verify file ownership"
            ],
            success_probability=0.8
        ))
        
        # Command not found errors
        self.register_strategy(ErrorRecoveryStrategy(
            error_type="CommandNotFound",
            description="Install missing command or package",
            suggested_actions=[
                "Install required package",
                "Check PATH environment variable",
                "Use alternative command"
            ],
            success_probability=0.7
        ))
        
        # Timeout errors
        self.register_strategy(ErrorRecoveryStrategy(
            error_type="TimeoutError",
            description="Handle command timeouts",
            suggested_actions=[
                "Increase timeout duration",
                "Break down into smaller operations",
                "Check system resources"
            ],
            success_probability=0.6
        ))
        
        # Syntax errors
        self.register_strategy(ErrorRecoveryStrategy(
            error_type="SyntaxError",
            description="Fix code syntax issues",
            suggested_actions=[
                "Review code syntax",
                "Check language version compatibility",
                "Validate file encoding"
            ],
            success_probability=0.9
        ))
        
        # Value errors
        self.register_strategy(ErrorRecoveryStrategy(
            error_type="ValueError",
            description="Fix value-related issues",
            suggested_actions=[
                "Validate input parameters",
                "Check data types and formats",
                "Verify value ranges and constraints"
            ],
            success_probability=0.7
        ))
        
        # File not found errors
        self.register_strategy(ErrorRecoveryStrategy(
            error_type="FileNotFoundError",
            description="Handle missing files",
            suggested_actions=[
                "Check file path and existence",
                "Create missing directories",
                "Verify file permissions"
            ],
            success_probability=0.8
        ))
        
        # Runtime errors
        self.register_strategy(ErrorRecoveryStrategy(
            error_type="RuntimeError",
            description="Handle runtime issues",
            suggested_actions=[
                "Check system resources",
                "Verify environment configuration",
                "Review execution context"
            ],
            success_probability=0.6
        ))
    
    def register_strategy(self, strategy: ErrorRecoveryStrategy) -> None:
        """Register a new recovery strategy."""
        if strategy.error_type not in self._recovery_strategies:
            self._recovery_strategies[strategy.error_type] = []
        self._recovery_strategies[strategy.error_type].append(strategy)
    
    def get_strategies_for_error(self, error_type: str) -> List[ErrorRecoveryStrategy]:
        """Get recovery strategies for a specific error type."""
        return self._recovery_strategies.get(error_type, [])
    
    def analyze_error_context(self, error_info: ErrorInfo, 
                            environment_state: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze error context to provide enhanced recovery information."""
        context = {
            "error_analysis": {
                "type": error_info.error_type,
                "message": error_info.message,
                "timestamp": error_info.timestamp,
                "context": error_info.context
            },
            "environment_analysis": environment_state,
            "recovery_suggestions": []
        }
        
        # Add specific analysis based on error type
        if "Permission" in error_info.error_type:
            context["recovery_suggestions"].extend([
                "Check file/directory permissions",
                "Verify workspace isolation settings",
                "Ensure proper user context"
            ])
        
        elif "Command" in error_info.message or "not found" in error_info.message.lower():
            context["recovery_suggestions"].extend([
                "Install missing dependencies",
                "Check PATH environment variable",
                "Verify command spelling and availability"
            ])
        
        elif "timeout" in error_info.message.lower() or "TimeoutError" in error_info.error_type:
            context["recovery_suggestions"].extend([
                "Increase operation timeout",
                "Check system resource availability",
                "Break operation into smaller steps"
            ])
        
        # Add general recovery suggestions if none were added
        if not context["recovery_suggestions"]:
            context["recovery_suggestions"].extend([
                "Review error details and context",
                "Check system resources and environment",
                "Verify task requirements and dependencies"
            ])
        
        return context


class ExecutionEngine(ExecutionEngineInterface):
    """
    Concrete implementation of task execution with comprehensive error
    handling, recovery, and sandbox command execution.
    """
    
    def __init__(self):
        self._execution_history: List[ExecutionResult] = []
        self._error_recovery_manager = ErrorRecoveryManager()
    
    def execute_plan(self, plan: TaskPlan) -> ExecutionResult:
        """Execute a complete task plan sequentially."""
        start_time = time.time()
        
        result = ExecutionResult(
            plan_id=plan.id,
            success=True,
            total_duration=0.0,
            tasks_completed=0,
            tasks_failed=0
        )
        
        # Determine workspace path
        workspace_path = "/tmp/sandbox"
        if plan.codebase_context and plan.codebase_context.analysis:
            root_path = plan.codebase_context.analysis.structure.root_path
            if root_path:
                workspace_path = root_path
        
        # Create sandbox command executor
        sandbox_executor = SandboxCommandExecutor(workspace_path)
        
        # Validate environment before execution
        if not self.validate_environment(SandboxExecutor(workspace_path=workspace_path)):
            result.success = False
            result.summary = "Failed to validate sandbox environment"
            return result
        
        # Execute tasks sequentially based on dependencies
        remaining_tasks = plan.tasks.copy()
        
        while remaining_tasks:
            # Find next executable task (dependencies met)
            next_task = None
            tasks_to_remove = []
            
            for task in remaining_tasks:
                if task.status == TaskStatus.COMPLETED:
                    tasks_to_remove.append(task)
                    continue
                
                # Check if all dependencies are completed
                dependencies_met = all(
                    dep_task and dep_task.status == TaskStatus.COMPLETED
                    for dep_id in task.dependencies
                    if (dep_task := plan.get_task(dep_id)) is not None
                )
                
                if dependencies_met and task.status == TaskStatus.NOT_STARTED:
                    next_task = task
                    break
            
            # Remove completed tasks from remaining list
            for task in tasks_to_remove:
                remaining_tasks.remove(task)
            
            if not next_task:
                # No more executable tasks - check if we're done or stuck
                incomplete_tasks = [t for t in remaining_tasks if t.status != TaskStatus.COMPLETED]
                if incomplete_tasks:
                    result.success = False
                    result.summary = f"Execution stuck - {len(incomplete_tasks)} tasks cannot proceed due to unmet dependencies"
                break
            
            # Execute the next task
            next_task.status = TaskStatus.IN_PROGRESS
            task_result = self.execute_task(next_task, sandbox_executor)
            result.add_task_result(task_result)
            
            if task_result.success:
                next_task.status = TaskStatus.COMPLETED
                next_task.actual_duration = int(task_result.duration / 60)  # Convert to minutes
            else:
                next_task.status = TaskStatus.ERROR
                next_task.error_info = task_result.error_info
                result.success = False
                
                # For now, stop execution on first error
                # TODO: Add configuration for error handling strategy
                break
        
        result.total_duration = time.time() - start_time
        result.summary = self._generate_execution_summary(result)
        
        self._execution_history.append(result)
        return result
    
    def execute_task(self, task: Task, sandbox_executor: SandboxCommandExecutor) -> TaskResult:
        """Execute a single task within the sandbox environment."""
        start_time = time.time()
        
        task_result = TaskResult(
            task_id=task.id,
            success=False,
            duration=0.0
        )
        
        try:
            # Clear previous execution history for this task
            sandbox_executor.clear_history()
            
            # Execute subtasks if they exist
            if task.subtasks:
                for subtask in task.subtasks:
                    if subtask.status == TaskStatus.COMPLETED:
                        continue
                    
                    subtask.status = TaskStatus.IN_PROGRESS
                    subtask_success = self._execute_subtask(subtask, sandbox_executor)
                    
                    if subtask_success:
                        subtask.status = TaskStatus.COMPLETED
                    else:
                        subtask.status = TaskStatus.ERROR
                        task_result.success = False
                        task_result.output += f"Subtask failed: {subtask.description}\n"
                        break
                else:
                    # All subtasks completed successfully
                    task_result.success = True
                    task_result.output = f"All subtasks completed for: {task.description}"
            else:
                # Execute the main task
                task_result.success = self._execute_main_task(task, sandbox_executor)
                task_result.output = f"Executed task: {task.description}"
            
            # Collect file changes and commands from sandbox executor
            task_result.changes_made = sandbox_executor.get_file_changes()
            task_result.commands_executed = sandbox_executor.get_commands_executed()
            
        except Exception as e:
            error_info = ErrorInfo(
                error_type=type(e).__name__,
                message=str(e),
                stack_trace=traceback.format_exc(),
                context={
                    "task_id": task.id or "",
                    "task_description": task.description or "",
                    "workspace_path": str(sandbox_executor.workspace_path)
                }
            )
            task_result.error_info = error_info
            task_result.success = False
            task_result.output = f"Task execution failed: {str(e)}"
        
        task_result.duration = time.time() - start_time
        return task_result
    
    def _execute_subtask(self, subtask, sandbox_executor: SandboxCommandExecutor) -> bool:
        """Execute a single subtask."""
        try:
            # This is a placeholder implementation
            # In a real implementation, this would parse the subtask description
            # and execute appropriate actions (file operations, commands, etc.)
            
            # For now, just simulate execution
            if "create file" in subtask.description.lower():
                # Example: create a simple file
                return sandbox_executor.create_file("example.txt", "# Example file\n")
            elif "run command" in subtask.description.lower():
                # Example: run a simple command
                result = sandbox_executor.execute_command("echo 'Hello from subtask'")
                return result.exit_code == 0
            else:
                # Default success for other tasks
                return True
                
        except Exception as e:
            print(f"Subtask execution error: {e}")
            return False
    
    def _execute_main_task(self, task: Task, sandbox_executor: SandboxCommandExecutor) -> bool:
        """Execute the main task logic."""
        try:
            # This is a placeholder implementation
            # In a real implementation, this would parse the task description
            # and execute appropriate actions based on the task type
            
            # For demonstration, let's handle some common task patterns
            description = task.description.lower()
            
            if "create" in description and "file" in description:
                # Create a file based on task description
                filename = f"task_{task.id}_output.txt"
                content = f"# Output from task: {task.description}\n# Created at: {datetime.now()}\n"
                return sandbox_executor.create_file(filename, content)
            
            elif "install" in description and "package" in description:
                # Extract package name (simplified)
                words = task.description.split()
                package_name = "requests"  # Default package for demo
                for i, word in enumerate(words):
                    if word.lower() == "install" and i + 1 < len(words):
                        package_name = words[i + 1]
                        break
                return sandbox_executor.install_package(package_name)
            
            elif "run" in description or "execute" in description:
                # Execute a command
                command = "echo 'Task executed successfully'"
                result = sandbox_executor.execute_command(command)
                return result.exit_code == 0
            
            else:
                # Default success for other task types
                return True
                
        except Exception as e:
            print(f"Main task execution error: {e}")
            return False
    
    def handle_error(self, task: Task, error: Exception, 
                    sandbox_executor: SandboxCommandExecutor) -> RetryContext:
        """Handle an error that occurred during task execution with comprehensive analysis."""
        # Create detailed error information
        error_info = ErrorInfo(
            error_type=type(error).__name__,
            message=str(error),
            stack_trace=traceback.format_exc(),
            context={
                "task_id": task.id,
                "task_description": task.description,
                "workspace_path": str(sandbox_executor.workspace_path),
                "file_changes_count": len(sandbox_executor.get_file_changes()),
                "commands_executed_count": len(sandbox_executor.get_commands_executed())
            }
        )
        
        # Gather environment state
        environment_state = {
            "workspace_path": str(sandbox_executor.workspace_path),
            "workspace_exists": sandbox_executor.workspace_path.exists(),
            "workspace_writable": os.access(str(sandbox_executor.workspace_path), os.W_OK),
            "recent_file_changes": [
                {"path": fc.file_path, "type": fc.change_type} 
                for fc in sandbox_executor.get_file_changes()[-5:]  # Last 5 changes
            ],
            "recent_commands": [
                {"command": cmd.command, "exit_code": cmd.exit_code}
                for cmd in sandbox_executor.get_commands_executed()[-3:]  # Last 3 commands
            ]
        }
        
        # Get recovery strategies for this error type
        recovery_strategies = self._error_recovery_manager.get_strategies_for_error(
            error_info.error_type
        )
        
        # Analyze error context for enhanced suggestions
        error_analysis = self._error_recovery_manager.analyze_error_context(
            error_info, environment_state
        )
        
        # Create retry context with comprehensive information
        retry_context = RetryContext(
            original_task=task,
            error_info=error_info,
            suggested_approaches=error_analysis["recovery_suggestions"],
            environment_state=environment_state,
            recovery_strategies=recovery_strategies
        )
        
        return retry_context
    
    def retry_task(self, retry_context: RetryContext, 
                  sandbox_executor: SandboxCommandExecutor) -> TaskResult:
        """Retry a failed task with enhanced context and recovery strategies."""
        if not retry_context.can_retry:
            return TaskResult(
                task_id=retry_context.original_task.id,
                success=False,
                duration=0.0,
                error_info=ErrorInfo(
                    error_type="MaxRetriesExceeded",
                    message=f"Maximum number of retries ({retry_context.max_retries}) exceeded",
                    context={
                        "total_attempts": len(retry_context.previous_attempts),
                        "last_error": retry_context.error_info.message or ""
                    }
                )
            )
        
        # Apply exponential backoff delay
        delay = retry_context.next_delay
        if delay > 0:
            time.sleep(delay)
        
        # Record the retry attempt
        attempt = AttemptInfo(
            attempt_number=len(retry_context.previous_attempts) + 1,
            timestamp=datetime.now(),
            duration=0.0,
            success=False
        )
        
        # Apply recovery strategies before retry
        self._apply_recovery_strategies(retry_context, sandbox_executor)
        
        # Execute the task again with enhanced context
        start_time = time.time()
        
        try:
            # Clear previous execution state
            sandbox_executor.clear_history()
            
            # Execute with recovery context
            result = self._execute_task_with_recovery_context(
                retry_context.original_task, 
                sandbox_executor, 
                retry_context
            )
            
        except Exception as e:
            # Handle retry execution errors
            result = TaskResult(
                task_id=retry_context.original_task.id,
                success=False,
                duration=time.time() - start_time,
                error_info=ErrorInfo(
                    error_type=type(e).__name__,
                    message=str(e),
                    stack_trace=traceback.format_exc(),
                    context={"retry_attempt": attempt.attempt_number}
                )
            )
        
        # Update attempt information
        attempt.duration = result.duration
        attempt.success = result.success
        attempt.error_info = result.error_info
        attempt.changes_made = sandbox_executor.get_file_changes()
        attempt.commands_executed = sandbox_executor.get_commands_executed()
        
        retry_context.previous_attempts.append(attempt)
        
        return result
    
    def _apply_recovery_strategies(self, retry_context: RetryContext, 
                                 sandbox_executor: SandboxCommandExecutor) -> None:
        """Apply recovery strategies before retrying a task."""
        best_strategy = retry_context.get_best_recovery_strategy()
        
        if best_strategy and best_strategy.recovery_function:
            try:
                best_strategy.recovery_function(retry_context, sandbox_executor)
            except Exception as e:
                print(f"Recovery strategy failed: {e}")
        
        # Apply common recovery actions based on error type
        error_type = retry_context.error_info.error_type
        
        if "Permission" in error_type:
            self._recover_from_permission_error(retry_context, sandbox_executor)
        elif "Command" in retry_context.error_info.message:
            self._recover_from_command_error(retry_context, sandbox_executor)
        elif "timeout" in retry_context.error_info.message.lower():
            self._recover_from_timeout_error(retry_context, sandbox_executor)
    
    def _recover_from_permission_error(self, retry_context: RetryContext, 
                                     sandbox_executor: SandboxCommandExecutor) -> None:
        """Recover from permission-related errors."""
        try:
            # Ensure workspace directory has proper permissions
            workspace_path = sandbox_executor.workspace_path
            if workspace_path.exists():
                os.chmod(str(workspace_path), 0o755)
                
            # Try to fix permissions on recently modified files
            for file_change in sandbox_executor.get_file_changes():
                file_path = Path(file_change.file_path)
                if file_path.exists():
                    os.chmod(str(file_path), 0o644)
                    
        except Exception as e:
            print(f"Permission recovery failed: {e}")
    
    def _recover_from_command_error(self, retry_context: RetryContext, 
                                  sandbox_executor: SandboxCommandExecutor) -> None:
        """Recover from command execution errors."""
        # This is a placeholder for command-specific recovery
        # In a real implementation, this might try to install missing packages
        # or suggest alternative commands
        pass
    
    def _recover_from_timeout_error(self, retry_context: RetryContext, 
                                  sandbox_executor: SandboxCommandExecutor) -> None:
        """Recover from timeout errors."""
        # Increase timeout for future operations
        # This is a placeholder - in practice, you might adjust sandbox_executor settings
        pass
    
    def _execute_task_with_recovery_context(self, task: Task, 
                                          sandbox_executor: SandboxCommandExecutor,
                                          retry_context: RetryContext) -> TaskResult:
        """Execute a task with additional recovery context."""
        # This is similar to execute_task but with recovery context awareness
        # For now, we'll use the standard execute_task method
        # In a full implementation, this could modify execution based on recovery context
        return self.execute_task(task, sandbox_executor)
    
    def validate_environment(self, sandbox_executor: SandboxExecutor) -> bool:
        """Validate that the sandbox environment is ready for execution."""
        # TODO: Implement environment validation
        # Check if workspace exists, permissions are correct, etc.
        return True
    
    def _generate_execution_summary(self, result: ExecutionResult) -> str:
        """Generate a summary of the execution result."""
        total_tasks = result.tasks_completed + result.tasks_failed
        success_rate = (result.tasks_completed / total_tasks * 100) if total_tasks > 0 else 0
        
        summary = f"""
        Execution Summary:
        - Total tasks: {total_tasks}
        - Completed: {result.tasks_completed}
        - Failed: {result.tasks_failed}
        - Success rate: {success_rate:.1f}%
        - Total duration: {result.total_duration:.2f} seconds
        - Overall success: {result.success}
        """
        
        return summary.strip()
    
    def get_execution_history(self) -> List[ExecutionResult]:
        """Get the history of all executions."""
        return self._execution_history.copy()