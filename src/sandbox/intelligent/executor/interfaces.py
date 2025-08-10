"""
Abstract interfaces for task execution components.
"""

from abc import ABC, abstractmethod
from typing import List
from ..planner.models import TaskPlan, Task
from .models import ExecutionResult, TaskResult, RetryContext, SandboxExecutor


class ExecutionEngineInterface(ABC):
    """Abstract interface for task execution operations."""
    
    @abstractmethod
    def execute_plan(self, plan: TaskPlan) -> ExecutionResult:
        """
        Execute a complete task plan sequentially.
        
        Args:
            plan: The task plan to execute
            
        Returns:
            ExecutionResult containing the results of all tasks
        """
        pass
    
    @abstractmethod
    def execute_task(self, task: Task, sandbox_executor: SandboxExecutor) -> TaskResult:
        """
        Execute a single task within the sandbox environment.
        
        Args:
            task: The task to execute
            sandbox_executor: Sandbox execution configuration
            
        Returns:
            TaskResult containing the execution result
        """
        pass
    
    @abstractmethod
    def handle_error(self, task: Task, error: Exception, 
                    sandbox_executor: SandboxExecutor) -> RetryContext:
        """
        Handle an error that occurred during task execution.
        
        Args:
            task: The task that failed
            error: The exception that occurred
            sandbox_executor: Sandbox execution configuration
            
        Returns:
            RetryContext with information for potential retry
        """
        pass
    
    @abstractmethod
    def retry_task(self, retry_context: RetryContext, 
                  sandbox_executor: SandboxExecutor) -> TaskResult:
        """
        Retry a failed task with enhanced context.
        
        Args:
            retry_context: Context information from the failed attempt
            sandbox_executor: Sandbox execution configuration
            
        Returns:
            TaskResult from the retry attempt
        """
        pass
    
    @abstractmethod
    def validate_environment(self, sandbox_executor: SandboxExecutor) -> bool:
        """
        Validate that the sandbox environment is ready for execution.
        
        Args:
            sandbox_executor: Sandbox execution configuration
            
        Returns:
            True if the environment is ready
        """
        pass


class SandboxExecutorInterface(ABC):
    """Abstract interface for sandbox command execution."""
    
    @abstractmethod
    def execute_command(self, command: str, working_dir: str = None, 
                       timeout: int = None) -> 'CommandInfo':
        """
        Execute a command within the sandbox environment.
        
        Args:
            command: The command to execute
            working_dir: Working directory for the command
            timeout: Timeout in seconds
            
        Returns:
            CommandInfo with execution results
        """
        pass
    
    @abstractmethod
    def create_file(self, file_path: str, content: str) -> bool:
        """
        Create a file within the sandbox.
        
        Args:
            file_path: Path to the file to create
            content: Content of the file
            
        Returns:
            True if the file was created successfully
        """
        pass
    
    @abstractmethod
    def modify_file(self, file_path: str, content: str) -> bool:
        """
        Modify an existing file within the sandbox.
        
        Args:
            file_path: Path to the file to modify
            content: New content of the file
            
        Returns:
            True if the file was modified successfully
        """
        pass
    
    @abstractmethod
    def delete_file(self, file_path: str) -> bool:
        """
        Delete a file within the sandbox.
        
        Args:
            file_path: Path to the file to delete
            
        Returns:
            True if the file was deleted successfully
        """
        pass
    
    @abstractmethod
    def install_package(self, package_name: str, package_manager: str = "auto") -> bool:
        """
        Install a package within the sandbox environment.
        
        Args:
            package_name: Name of the package to install
            package_manager: Package manager to use (pip, npm, etc.)
            
        Returns:
            True if the package was installed successfully
        """
        pass