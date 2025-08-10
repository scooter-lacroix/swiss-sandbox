"""
Data models for task execution.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any, Callable
from ..types import ErrorInfo, CommandInfo, FileChange
from ..planner.models import Task


@dataclass
class AttemptInfo:
    """Information about a task execution attempt."""
    attempt_number: int
    timestamp: datetime
    duration: float  # seconds
    success: bool
    error_info: Optional[ErrorInfo] = None
    changes_made: List[FileChange] = field(default_factory=list)
    commands_executed: List[CommandInfo] = field(default_factory=list)


@dataclass
class ErrorRecoveryStrategy:
    """Strategy for recovering from specific types of errors."""
    error_type: str
    description: str
    recovery_function: Optional[Callable] = None
    suggested_actions: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    success_probability: float = 0.5  # 0.0 to 1.0


@dataclass
class RetryContext:
    """Context information for retrying a failed task."""
    original_task: Task
    error_info: ErrorInfo
    previous_attempts: List[AttemptInfo] = field(default_factory=list)
    suggested_approaches: List[str] = field(default_factory=list)
    environment_state: Dict[str, Any] = field(default_factory=dict)
    recovery_strategies: List[ErrorRecoveryStrategy] = field(default_factory=list)
    max_retries: int = 3
    backoff_multiplier: float = 1.5  # Exponential backoff
    base_delay: float = 1.0  # Base delay in seconds
    
    @property
    def can_retry(self) -> bool:
        """Check if the task can be retried."""
        return len(self.previous_attempts) < self.max_retries
    
    @property
    def next_delay(self) -> float:
        """Calculate the delay before the next retry attempt."""
        if not self.previous_attempts:
            return self.base_delay
        
        attempt_count = len(self.previous_attempts)
        return self.base_delay * (self.backoff_multiplier ** attempt_count)
    
    def add_recovery_strategy(self, strategy: ErrorRecoveryStrategy) -> None:
        """Add a recovery strategy for this retry context."""
        self.recovery_strategies.append(strategy)
    
    def get_best_recovery_strategy(self) -> Optional[ErrorRecoveryStrategy]:
        """Get the recovery strategy with the highest success probability."""
        if not self.recovery_strategies:
            return None
        
        return max(self.recovery_strategies, key=lambda s: s.success_probability)


@dataclass
class TaskResult:
    """Result of executing a single task."""
    task_id: str
    success: bool
    duration: float  # seconds
    changes_made: List[FileChange] = field(default_factory=list)
    commands_executed: List[CommandInfo] = field(default_factory=list)
    error_info: Optional[ErrorInfo] = None
    output: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """Result of executing a complete task plan."""
    plan_id: str
    success: bool
    total_duration: float  # seconds
    tasks_completed: int
    tasks_failed: int
    task_results: List[TaskResult] = field(default_factory=list)
    summary: str = ""
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def add_task_result(self, result: TaskResult) -> None:
        """Add a task result to the execution result."""
        self.task_results.append(result)
        if result.success:
            self.tasks_completed += 1
        else:
            self.tasks_failed += 1


@dataclass
class SandboxExecutor:
    """Configuration and state for sandbox command execution."""
    workspace_path: str
    isolation_enabled: bool = True
    resource_limits: Dict[str, Any] = field(default_factory=dict)
    allowed_commands: Optional[List[str]] = None  # None means all commands allowed
    environment_vars: Dict[str, str] = field(default_factory=dict)
    timeout: int = 300  # seconds
    
    def is_command_allowed(self, command: str) -> bool:
        """Check if a command is allowed to be executed."""
        if self.allowed_commands is None:
            return True  # All commands allowed
        
        # Extract the base command (first word)
        base_command = command.strip().split()[0] if command.strip() else ""
        return base_command in self.allowed_commands