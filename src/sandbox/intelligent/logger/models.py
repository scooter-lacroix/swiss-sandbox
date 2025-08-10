"""
Data models for action logging.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, List
from ..types import ActionType, FileChange, CommandInfo, ErrorInfo


@dataclass
class Action:
    """Represents a logged action in the sandbox."""
    id: str
    timestamp: datetime
    action_type: ActionType
    description: str
    details: Dict[str, Any] = field(default_factory=dict)
    file_changes: List[FileChange] = field(default_factory=list)
    command_info: Optional[CommandInfo] = None
    error_info: Optional[ErrorInfo] = None
    session_id: Optional[str] = None
    task_id: Optional[str] = None
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now()


@dataclass
class LogQuery:
    """Query parameters for retrieving logs."""
    session_id: Optional[str] = None
    task_id: Optional[str] = None
    action_types: Optional[List[ActionType]] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: Optional[int] = None
    offset: int = 0


@dataclass
class LogSummary:
    """Summary of logged actions."""
    total_actions: int
    actions_by_type: Dict[ActionType, int] = field(default_factory=dict)
    files_modified: int = 0
    commands_executed: int = 0
    errors_encountered: int = 0
    time_range: tuple = None  # (start_time, end_time)
    
    def add_action(self, action: Action) -> None:
        """Add an action to the summary statistics."""
        self.total_actions += 1
        
        if action.action_type in self.actions_by_type:
            self.actions_by_type[action.action_type] += 1
        else:
            self.actions_by_type[action.action_type] = 1
        
        if action.file_changes:
            self.files_modified += len(action.file_changes)
        
        if action.command_info:
            self.commands_executed += 1
        
        if action.error_info:
            self.errors_encountered += 1