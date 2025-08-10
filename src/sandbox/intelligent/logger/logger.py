"""
Concrete implementation of action logging functionality.
"""

import uuid
import json
from datetime import datetime
from typing import List, Dict, Any
from ..types import ActionType, FileChange, CommandInfo, ErrorInfo
from .interfaces import ActionLoggerInterface
from .models import Action, LogQuery, LogSummary


class ActionLogger(ActionLoggerInterface):
    """
    Concrete implementation of comprehensive action logging with
    detailed tracking of all sandbox activities.
    """
    
    def __init__(self):
        self._actions: List[Action] = []
        self._actions_by_id: Dict[str, Action] = {}
    
    def log_action(self, action_type: ActionType, description: str,
                  details: dict = None, session_id: str = None,
                  task_id: str = None) -> str:
        """Log a general action."""
        action_id = str(uuid.uuid4())
        
        action = Action(
            id=action_id,
            timestamp=datetime.now(),
            action_type=action_type,
            description=description,
            details=details or {},
            session_id=session_id,
            task_id=task_id
        )
        
        self._actions.append(action)
        self._actions_by_id[action_id] = action
        
        return action_id
    
    def log_file_change(self, file_path: str, change_type: str,
                       before_content: str = None, after_content: str = None,
                       session_id: str = None, task_id: str = None) -> str:
        """Log a file change operation."""
        file_change = FileChange(
            file_path=file_path,
            change_type=change_type,
            before_content=before_content,
            after_content=after_content
        )
        
        # Determine action type based on change type
        action_type_map = {
            "create": ActionType.FILE_CREATE,
            "modify": ActionType.FILE_MODIFY,
            "delete": ActionType.FILE_DELETE
        }
        action_type = action_type_map.get(change_type, ActionType.FILE_MODIFY)
        
        action_id = str(uuid.uuid4())
        action = Action(
            id=action_id,
            timestamp=datetime.now(),
            action_type=action_type,
            description=f"{change_type.title()} file: {file_path}",
            file_changes=[file_change],
            session_id=session_id,
            task_id=task_id
        )
        
        self._actions.append(action)
        self._actions_by_id[action_id] = action
        
        return action_id
    
    def log_command(self, command: str, working_directory: str,
                   output: str, error_output: str, exit_code: int,
                   duration: float, session_id: str = None,
                   task_id: str = None) -> str:
        """Log a command execution."""
        command_info = CommandInfo(
            command=command,
            working_directory=working_directory,
            output=output,
            error_output=error_output,
            exit_code=exit_code,
            duration=duration
        )
        
        action_id = str(uuid.uuid4())
        action = Action(
            id=action_id,
            timestamp=datetime.now(),
            action_type=ActionType.COMMAND_EXECUTE,
            description=f"Execute command: {command}",
            command_info=command_info,
            session_id=session_id,
            task_id=task_id
        )
        
        self._actions.append(action)
        self._actions_by_id[action_id] = action
        
        return action_id
    
    def log_error(self, error_type: str, message: str, stack_trace: str = None,
                 context: dict = None, session_id: str = None,
                 task_id: str = None) -> str:
        """Log an error that occurred."""
        error_info = ErrorInfo(
            error_type=error_type,
            message=message,
            stack_trace=stack_trace,
            context=context or {}
        )
        
        action_id = str(uuid.uuid4())
        action = Action(
            id=action_id,
            timestamp=datetime.now(),
            action_type=ActionType.TASK_ERROR,
            description=f"Error: {message}",
            error_info=error_info,
            session_id=session_id,
            task_id=task_id
        )
        
        self._actions.append(action)
        self._actions_by_id[action_id] = action
        
        return action_id
    
    def get_actions(self, query: LogQuery) -> List[Action]:
        """Retrieve actions based on query parameters."""
        filtered_actions = self._actions
        
        # Filter by session_id
        if query.session_id:
            filtered_actions = [a for a in filtered_actions if a.session_id == query.session_id]
        
        # Filter by task_id
        if query.task_id:
            filtered_actions = [a for a in filtered_actions if a.task_id == query.task_id]
        
        # Filter by action types
        if query.action_types:
            filtered_actions = [a for a in filtered_actions if a.action_type in query.action_types]
        
        # Filter by time range
        if query.start_time:
            filtered_actions = [a for a in filtered_actions if a.timestamp >= query.start_time]
        
        if query.end_time:
            filtered_actions = [a for a in filtered_actions if a.timestamp <= query.end_time]
        
        # Sort by timestamp
        filtered_actions.sort(key=lambda a: a.timestamp)
        
        # Apply offset and limit
        if query.offset:
            filtered_actions = filtered_actions[query.offset:]
        
        if query.limit:
            filtered_actions = filtered_actions[:query.limit]
        
        return filtered_actions
    
    def get_execution_history(self, session_id: str) -> List[Action]:
        """Get the complete execution history for a session."""
        query = LogQuery(session_id=session_id)
        return self.get_actions(query)
    
    def get_log_summary(self, session_id: str = None,
                       task_id: str = None) -> LogSummary:
        """Get a summary of logged actions."""
        query = LogQuery(session_id=session_id, task_id=task_id)
        actions = self.get_actions(query)
        
        summary = LogSummary(total_actions=0)
        
        if actions:
            summary.time_range = (
                min(a.timestamp for a in actions),
                max(a.timestamp for a in actions)
            )
        
        for action in actions:
            summary.add_action(action)
        
        return summary
    
    def export_logs(self, query: LogQuery, format: str = "json") -> str:
        """Export logs in the specified format."""
        actions = self.get_actions(query)
        
        if format.lower() == "json":
            # Convert actions to dictionaries for JSON serialization
            actions_data = []
            for action in actions:
                action_dict = {
                    "id": action.id,
                    "timestamp": action.timestamp.isoformat(),
                    "action_type": action.action_type.value,
                    "description": action.description,
                    "details": action.details,
                    "session_id": action.session_id,
                    "task_id": action.task_id
                }
                
                if action.file_changes:
                    action_dict["file_changes"] = [
                        {
                            "file_path": fc.file_path,
                            "change_type": fc.change_type,
                            "timestamp": fc.timestamp.isoformat()
                        }
                        for fc in action.file_changes
                    ]
                
                if action.command_info:
                    action_dict["command_info"] = {
                        "command": action.command_info.command,
                        "working_directory": action.command_info.working_directory,
                        "exit_code": action.command_info.exit_code,
                        "duration": action.command_info.duration
                    }
                
                if action.error_info:
                    action_dict["error_info"] = {
                        "error_type": action.error_info.error_type,
                        "message": action.error_info.message,
                        "context": action.error_info.context
                    }
                
                actions_data.append(action_dict)
            
            return json.dumps(actions_data, indent=2)
        
        # TODO: Implement other export formats (CSV, etc.)
        raise ValueError(f"Unsupported export format: {format}")
    
    def clear_logs(self, session_id: str = None, before_date: str = None) -> int:
        """Clear logs based on criteria."""
        initial_count = len(self._actions)
        
        if session_id:
            self._actions = [a for a in self._actions if a.session_id != session_id]
            # Update the by_id dictionary
            self._actions_by_id = {a.id: a for a in self._actions}
        
        if before_date:
            cutoff_date = datetime.fromisoformat(before_date)
            self._actions = [a for a in self._actions if a.timestamp >= cutoff_date]
            # Update the by_id dictionary
            self._actions_by_id = {a.id: a for a in self._actions}
        
        return initial_count - len(self._actions)