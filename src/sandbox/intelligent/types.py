"""
Common types and enums for the intelligent sandbox system.
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass


class WorkspaceStatus(Enum):
    """Status of a sandbox workspace."""
    CREATING = "creating"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLEANING_UP = "cleaning_up"
    DESTROYED = "destroyed"


class TaskStatus(Enum):
    """Status of a task in the execution plan."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ERROR = "error"


class PlanStatus(Enum):
    """Status of a task plan."""
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class ApprovalStatus(Enum):
    """Approval status for task plans."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


class ActionType(Enum):
    """Types of actions that can be logged."""
    FILE_CREATE = "file_create"
    FILE_MODIFY = "file_modify"
    FILE_DELETE = "file_delete"
    COMMAND_EXECUTE = "command_execute"
    TASK_START = "task_start"
    TASK_COMPLETE = "task_complete"
    TASK_ERROR = "task_error"
    WORKSPACE_CREATE = "workspace_create"
    WORKSPACE_DESTROY = "workspace_destroy"
    ENVIRONMENT_SETUP = "environment_setup"
    PACKAGE_INSTALL = "package_install"
    SYSTEM_CONFIG = "system_config"
    SESSION_CLEANUP = "session_cleanup"


@dataclass
class ErrorInfo:
    """Information about an error that occurred during task execution."""
    error_type: str
    message: str
    stack_trace: Optional[str] = None
    context: Dict[str, Any] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.context is None:
            self.context = {}


@dataclass
class FileChange:
    """Information about a file change."""
    file_path: str
    change_type: str  # create, modify, delete
    before_content: Optional[str] = None
    after_content: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class CommandInfo:
    """Information about a command execution."""
    command: str
    working_directory: str
    output: str
    error_output: str
    exit_code: int
    duration: float
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()