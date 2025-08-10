"""
Abstract interfaces for action logging components.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from ..types import ActionType, FileChange, CommandInfo, ErrorInfo
from .models import Action, LogQuery, LogSummary


class ActionLoggerInterface(ABC):
    """Abstract interface for action logging operations."""
    
    @abstractmethod
    def log_action(self, action_type: ActionType, description: str,
                  details: dict = None, session_id: str = None,
                  task_id: str = None) -> str:
        """
        Log a general action.
        
        Args:
            action_type: Type of action being logged
            description: Description of the action
            details: Additional details about the action
            session_id: ID of the session this action belongs to
            task_id: ID of the task this action belongs to
            
        Returns:
            ID of the logged action
        """
        pass
    
    @abstractmethod
    def log_file_change(self, file_path: str, change_type: str,
                       before_content: str = None, after_content: str = None,
                       session_id: str = None, task_id: str = None) -> str:
        """
        Log a file change operation.
        
        Args:
            file_path: Path to the file that was changed
            change_type: Type of change (create, modify, delete)
            before_content: Content before the change
            after_content: Content after the change
            session_id: ID of the session this action belongs to
            task_id: ID of the task this action belongs to
            
        Returns:
            ID of the logged action
        """
        pass
    
    @abstractmethod
    def log_command(self, command: str, working_directory: str,
                   output: str, error_output: str, exit_code: int,
                   duration: float, session_id: str = None,
                   task_id: str = None) -> str:
        """
        Log a command execution.
        
        Args:
            command: The command that was executed
            working_directory: Directory where command was executed
            output: Standard output from the command
            error_output: Error output from the command
            exit_code: Exit code of the command
            duration: Duration of command execution in seconds
            session_id: ID of the session this action belongs to
            task_id: ID of the task this action belongs to
            
        Returns:
            ID of the logged action
        """
        pass
    
    @abstractmethod
    def log_error(self, error_type: str, message: str, stack_trace: str = None,
                 context: dict = None, session_id: str = None,
                 task_id: str = None) -> str:
        """
        Log an error that occurred.
        
        Args:
            error_type: Type of error
            message: Error message
            stack_trace: Stack trace if available
            context: Additional context about the error
            session_id: ID of the session this action belongs to
            task_id: ID of the task this action belongs to
            
        Returns:
            ID of the logged action
        """
        pass
    
    @abstractmethod
    def get_actions(self, query: LogQuery) -> List[Action]:
        """
        Retrieve actions based on query parameters.
        
        Args:
            query: Query parameters for filtering actions
            
        Returns:
            List of actions matching the query
        """
        pass
    
    @abstractmethod
    def get_execution_history(self, session_id: str) -> List[Action]:
        """
        Get the complete execution history for a session.
        
        Args:
            session_id: ID of the session
            
        Returns:
            List of all actions for the session
        """
        pass
    
    @abstractmethod
    def get_log_summary(self, session_id: str = None,
                       task_id: str = None) -> LogSummary:
        """
        Get a summary of logged actions.
        
        Args:
            session_id: Optional session ID to filter by
            task_id: Optional task ID to filter by
            
        Returns:
            LogSummary with statistics about the actions
        """
        pass
    
    @abstractmethod
    def export_logs(self, query: LogQuery, format: str = "json") -> str:
        """
        Export logs in the specified format.
        
        Args:
            query: Query parameters for filtering actions
            format: Export format (json, csv, etc.)
            
        Returns:
            Exported logs as a string
        """
        pass
    
    @abstractmethod
    def clear_logs(self, session_id: str = None, before_date: str = None) -> int:
        """
        Clear logs based on criteria.
        
        Args:
            session_id: Optional session ID to clear logs for
            before_date: Optional date to clear logs before
            
        Returns:
            Number of logs cleared
        """
        pass