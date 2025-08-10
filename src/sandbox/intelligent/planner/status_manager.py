"""
Dynamic task status management system for real-time tracking and updates.
"""

import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from threading import Lock
from dataclasses import dataclass, field

from ..types import TaskStatus, ErrorInfo
from .models import Task, TaskPlan, Subtask


@dataclass
class TaskProgress:
    """Represents the progress of a task."""
    task_id: str
    status: TaskStatus
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    estimated_duration: Optional[int] = None  # minutes
    actual_duration: Optional[int] = None  # minutes
    progress_percentage: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)
    error_info: Optional[ErrorInfo] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def elapsed_time(self) -> Optional[int]:
        """Get elapsed time in minutes since task started."""
        if not self.start_time:
            return None
        
        end_time = self.end_time or datetime.now()
        delta = end_time - self.start_time
        return int(delta.total_seconds() / 60)
    
    @property
    def remaining_time(self) -> Optional[int]:
        """Estimate remaining time in minutes."""
        if not self.estimated_duration or not self.start_time:
            return None
        
        elapsed = self.elapsed_time
        if elapsed is None:
            return self.estimated_duration
        
        if self.progress_percentage > 0:
            total_estimated = elapsed / (self.progress_percentage / 100)
            return max(0, int(total_estimated - elapsed))
        
        return max(0, self.estimated_duration - elapsed)


@dataclass
class StatusUpdate:
    """Represents a status update event."""
    task_id: str
    old_status: TaskStatus
    new_status: TaskStatus
    timestamp: datetime = field(default_factory=datetime.now)
    message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class DynamicStatusManager:
    """
    Manages dynamic task status updates with real-time tracking,
    progress estimation, and modification capabilities.
    """
    
    def __init__(self):
        self._task_progress: Dict[str, TaskProgress] = {}
        self._status_history: Dict[str, List[StatusUpdate]] = {}
        self._status_listeners: List[Callable[[StatusUpdate], None]] = []
        self._lock = Lock()
        self._plans: Dict[str, TaskPlan] = {}
    
    def register_plan(self, plan: TaskPlan) -> None:
        """Register a task plan for status management."""
        with self._lock:
            self._plans[plan.id] = plan
            
            # Initialize progress tracking for all tasks and subtasks
            for task in plan.tasks:
                self._initialize_task_progress(task)
                for subtask in task.subtasks:
                    self._initialize_subtask_progress(subtask, task.id)
    
    def update_task_status(self, task_id: str, new_status: TaskStatus,
                          message: Optional[str] = None,
                          progress_percentage: Optional[float] = None,
                          error_info: Optional[ErrorInfo] = None) -> bool:
        """Update task status with real-time tracking."""
        with self._lock:
            if task_id not in self._task_progress:
                return False
            
            progress = self._task_progress[task_id]
            old_status = progress.status
            
            # Update progress information
            progress.status = new_status
            progress.last_updated = datetime.now()
            
            if progress_percentage is not None:
                progress.progress_percentage = max(0, min(100, progress_percentage))
            
            if error_info:
                progress.error_info = error_info
            
            # Handle status-specific updates
            if new_status == TaskStatus.IN_PROGRESS and not progress.start_time:
                progress.start_time = datetime.now()
                if progress_percentage is None:
                    progress.progress_percentage = 5.0  # Started
            
            elif new_status == TaskStatus.COMPLETED:
                progress.end_time = datetime.now()
                progress.progress_percentage = 100.0
                if progress.start_time:
                    delta = progress.end_time - progress.start_time
                    progress.actual_duration = int(delta.total_seconds() / 60)
            
            elif new_status == TaskStatus.ERROR:
                progress.end_time = datetime.now()
                if progress.start_time:
                    delta = progress.end_time - progress.start_time
                    progress.actual_duration = int(delta.total_seconds() / 60)
            
            # Create status update event
            update = StatusUpdate(
                task_id=task_id,
                old_status=old_status,
                new_status=new_status,
                message=message
            )
            
            # Record in history
            if task_id not in self._status_history:
                self._status_history[task_id] = []
            self._status_history[task_id].append(update)
            
            # Update the actual task/subtask object
            self._update_task_object(task_id, new_status, error_info)
            
            # Notify listeners
            self._notify_status_listeners(update)
            
            return True
    
    def get_task_progress(self, task_id: str) -> Optional[TaskProgress]:
        """Get current progress information for a task."""
        with self._lock:
            return self._task_progress.get(task_id)
    
    def get_plan_progress(self, plan_id: str) -> Dict[str, Any]:
        """Get overall progress information for a plan."""
        with self._lock:
            if plan_id not in self._plans:
                return {}
            
            plan = self._plans[plan_id]
            total_tasks = len(plan.tasks)
            completed_tasks = 0
            in_progress_tasks = 0
            error_tasks = 0
            
            total_estimated_duration = 0
            total_actual_duration = 0
            
            for task in plan.tasks:
                progress = self._task_progress.get(task.id)
                if progress:
                    if progress.status == TaskStatus.COMPLETED:
                        completed_tasks += 1
                    elif progress.status == TaskStatus.IN_PROGRESS:
                        in_progress_tasks += 1
                    elif progress.status == TaskStatus.ERROR:
                        error_tasks += 1
                    
                    if progress.estimated_duration:
                        total_estimated_duration += progress.estimated_duration
                    if progress.actual_duration:
                        total_actual_duration += progress.actual_duration
            
            completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
            
            return {
                'plan_id': plan_id,
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'in_progress_tasks': in_progress_tasks,
                'error_tasks': error_tasks,
                'completion_percentage': completion_percentage,
                'estimated_total_duration': total_estimated_duration,
                'actual_total_duration': total_actual_duration,
                'estimated_remaining_time': self._calculate_remaining_time(plan_id)
            }
    
    def modify_task(self, task_id: str, new_description: Optional[str] = None,
                   new_estimated_duration: Optional[int] = None,
                   add_dependencies: Optional[List[str]] = None,
                   remove_dependencies: Optional[List[str]] = None) -> bool:
        """Modify task properties and trigger re-planning if needed."""
        with self._lock:
            # Find the task in all plans
            task_obj = None
            plan_obj = None
            
            for plan in self._plans.values():
                task_obj = plan.get_task(task_id)
                if task_obj:
                    plan_obj = plan
                    break
                
                # Check subtasks
                for task in plan.tasks:
                    subtask = task.get_subtask(task_id)
                    if subtask:
                        task_obj = subtask
                        plan_obj = plan
                        break
                if task_obj:
                    break
            
            if not task_obj:
                return False
            
            # Apply modifications
            if new_description:
                task_obj.description = new_description
            
            if new_estimated_duration:
                task_obj.estimated_duration = new_estimated_duration
                # Update progress tracking
                if task_id in self._task_progress:
                    self._task_progress[task_id].estimated_duration = new_estimated_duration
            
            if add_dependencies:
                for dep in add_dependencies:
                    if dep not in task_obj.dependencies:
                        task_obj.dependencies.append(dep)
            
            if remove_dependencies:
                for dep in remove_dependencies:
                    if dep in task_obj.dependencies:
                        task_obj.dependencies.remove(dep)
            
            # Mark plan as needing re-validation
            if plan_obj:
                plan_obj.metadata['needs_revalidation'] = True
                plan_obj.metadata['last_modified'] = datetime.now()
            
            return True
    
    def replan_from_task(self, task_id: str, new_subtasks: List[Dict[str, Any]]) -> bool:
        """Re-plan a task by replacing its subtasks."""
        with self._lock:
            # Find the task
            task_obj = None
            plan_obj = None
            
            for plan in self._plans.values():
                task_obj = plan.get_task(task_id)
                if task_obj:
                    plan_obj = plan
                    break
            
            if not task_obj:
                return False
            
            # Clear existing subtasks from progress tracking
            for subtask in task_obj.subtasks:
                if subtask.id in self._task_progress:
                    del self._task_progress[subtask.id]
                if subtask.id in self._status_history:
                    del self._status_history[subtask.id]
            
            # Replace subtasks
            task_obj.subtasks.clear()
            
            for subtask_data in new_subtasks:
                subtask = Subtask(
                    id=subtask_data.get('id', f"{task_id}_{len(task_obj.subtasks)}"),
                    description=subtask_data['description'],
                    dependencies=subtask_data.get('dependencies', []),
                    estimated_duration=subtask_data.get('estimated_duration')
                )
                task_obj.subtasks.append(subtask)
                self._initialize_subtask_progress(subtask, task_id)
            
            # Mark plan as modified
            if plan_obj:
                plan_obj.metadata['needs_revalidation'] = True
                plan_obj.metadata['last_modified'] = datetime.now()
            
            return True
    
    def get_status_history(self, task_id: str) -> List[StatusUpdate]:
        """Get the status update history for a task."""
        with self._lock:
            return self._status_history.get(task_id, []).copy()
    
    def add_status_listener(self, listener: Callable[[StatusUpdate], None]) -> None:
        """Add a listener for status update events."""
        with self._lock:
            self._status_listeners.append(listener)
    
    def remove_status_listener(self, listener: Callable[[StatusUpdate], None]) -> None:
        """Remove a status update listener."""
        with self._lock:
            if listener in self._status_listeners:
                self._status_listeners.remove(listener)
    
    def get_active_tasks(self, plan_id: Optional[str] = None) -> List[TaskProgress]:
        """Get all currently active (in-progress) tasks."""
        with self._lock:
            active_tasks = []
            
            for task_id, progress in self._task_progress.items():
                if progress.status == TaskStatus.IN_PROGRESS:
                    if plan_id is None:
                        active_tasks.append(progress)
                    else:
                        # Check if task belongs to the specified plan
                        if plan_id in self._plans:
                            plan = self._plans[plan_id]
                            if any(task.id == task_id for task in plan.tasks):
                                active_tasks.append(progress)
                            else:
                                # Check subtasks
                                for task in plan.tasks:
                                    if any(subtask.id == task_id for subtask in task.subtasks):
                                        active_tasks.append(progress)
                                        break
            
            return active_tasks
    
    def _initialize_task_progress(self, task: Task) -> None:
        """Initialize progress tracking for a task."""
        self._task_progress[task.id] = TaskProgress(
            task_id=task.id,
            status=task.status,
            estimated_duration=task.estimated_duration
        )
        self._status_history[task.id] = []
    
    def _initialize_subtask_progress(self, subtask: Subtask, parent_task_id: str) -> None:
        """Initialize progress tracking for a subtask."""
        self._task_progress[subtask.id] = TaskProgress(
            task_id=subtask.id,
            status=subtask.status,
            estimated_duration=subtask.estimated_duration,
            metadata={'parent_task_id': parent_task_id}
        )
        self._status_history[subtask.id] = []
    
    def _update_task_object(self, task_id: str, status: TaskStatus, 
                           error_info: Optional[ErrorInfo]) -> None:
        """Update the actual task/subtask object with new status."""
        for plan in self._plans.values():
            # Check main tasks
            task = plan.get_task(task_id)
            if task:
                task.status = status
                if error_info:
                    task.error_info = error_info
                return
            
            # Check subtasks
            for main_task in plan.tasks:
                subtask = main_task.get_subtask(task_id)
                if subtask:
                    subtask.status = status
                    if error_info:
                        subtask.error_info = error_info
                    return
    
    def _notify_status_listeners(self, update: StatusUpdate) -> None:
        """Notify all registered status listeners."""
        for listener in self._status_listeners:
            try:
                listener(update)
            except Exception:
                # Ignore listener errors to prevent cascading failures
                pass
    
    def _calculate_remaining_time(self, plan_id: str) -> Optional[int]:
        """Calculate estimated remaining time for a plan."""
        if plan_id not in self._plans:
            return None
        
        plan = self._plans[plan_id]
        total_remaining = 0
        
        for task in plan.tasks:
            progress = self._task_progress.get(task.id)
            if progress and progress.status not in [TaskStatus.COMPLETED, TaskStatus.ERROR]:
                remaining = progress.remaining_time
                if remaining:
                    total_remaining += remaining
                elif progress.estimated_duration:
                    total_remaining += progress.estimated_duration
        
        return total_remaining if total_remaining > 0 else None