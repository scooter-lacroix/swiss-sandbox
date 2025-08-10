"""
Data models for task planning.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from ..types import TaskStatus, PlanStatus, ApprovalStatus, ErrorInfo
from ..analyzer.models import CodebaseAnalysis


@dataclass
class Subtask:
    """Represents a subtask within a larger task."""
    id: str
    description: str
    status: TaskStatus = TaskStatus.NOT_STARTED
    dependencies: List[str] = field(default_factory=list)
    estimated_duration: Optional[int] = None  # minutes
    actual_duration: Optional[int] = None
    error_info: Optional[ErrorInfo] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Task:
    """Represents a task in the execution plan."""
    id: str
    description: str
    status: TaskStatus = TaskStatus.NOT_STARTED
    subtasks: List[Subtask] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    estimated_duration: Optional[int] = None  # minutes
    actual_duration: Optional[int] = None
    error_info: Optional[ErrorInfo] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_subtask(self, subtask: Subtask) -> None:
        """Add a subtask to this task."""
        self.subtasks.append(subtask)
    
    def get_subtask(self, subtask_id: str) -> Optional[Subtask]:
        """Get a subtask by ID."""
        for subtask in self.subtasks:
            if subtask.id == subtask_id:
                return subtask
        return None
    
    @property
    def is_completed(self) -> bool:
        """Check if all subtasks are completed."""
        if not self.subtasks:
            return self.status == TaskStatus.COMPLETED
        return all(subtask.status == TaskStatus.COMPLETED for subtask in self.subtasks)


@dataclass
class CodebaseContext:
    """Context information about the codebase for task planning."""
    analysis: CodebaseAnalysis
    key_files: List[str] = field(default_factory=list)
    important_patterns: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class TaskPlan:
    """Represents a complete task execution plan."""
    id: str
    description: str
    tasks: List[Task] = field(default_factory=list)
    codebase_context: Optional[CodebaseContext] = None
    created_at: datetime = None
    status: PlanStatus = PlanStatus.DRAFT
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def add_task(self, task: Task) -> None:
        """Add a task to the plan."""
        self.tasks.append(task)
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None
    
    def get_next_task(self) -> Optional[Task]:
        """Get the next task that should be executed."""
        for task in self.tasks:
            if task.status == TaskStatus.NOT_STARTED:
                # Check if all dependencies are completed
                dependencies_met = all(
                    self.get_task(dep_id) and self.get_task(dep_id).status == TaskStatus.COMPLETED
                    for dep_id in task.dependencies
                )
                if dependencies_met:
                    return task
        return None
    
    @property
    def is_completed(self) -> bool:
        """Check if all tasks in the plan are completed."""
        return all(task.is_completed for task in self.tasks)
    
    @property
    def progress_percentage(self) -> float:
        """Calculate the completion percentage of the plan."""
        if not self.tasks:
            return 0.0
        
        completed_tasks = sum(1 for task in self.tasks if task.is_completed)
        return (completed_tasks / len(self.tasks)) * 100.0