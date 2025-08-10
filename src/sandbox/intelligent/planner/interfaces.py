"""
Abstract interfaces for task planning components.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Callable
from ..analyzer.models import CodebaseAnalysis
from ..types import TaskStatus, ErrorInfo
from .models import TaskPlan, Task, Subtask, CodebaseContext


class TaskPlannerInterface(ABC):
    """Abstract interface for task planning operations."""
    
    @abstractmethod
    def create_plan(self, task_description: str, 
                   codebase_analysis: CodebaseAnalysis) -> TaskPlan:
        """
        Create a detailed task plan from a high-level description.
        
        Args:
            task_description: High-level description of what needs to be done
            codebase_analysis: Analysis of the codebase context
            
        Returns:
            TaskPlan with detailed breakdown of tasks
        """
        pass
    
    @abstractmethod
    def break_down_task(self, task: Task, context: CodebaseContext) -> List[Subtask]:
        """
        Break down a task into smaller, actionable subtasks.
        
        Args:
            task: The task to break down
            context: Codebase context for informed breakdown
            
        Returns:
            List of subtasks
        """
        pass
    
    @abstractmethod
    def validate_plan(self, plan: TaskPlan) -> bool:
        """
        Validate that a task plan is well-formed and executable.
        
        Args:
            plan: The task plan to validate
            
        Returns:
            True if the plan is valid
        """
        pass
    
    @abstractmethod
    def update_task_status(self, plan_id: str, task_id: str, 
                          status: 'TaskStatus') -> bool:
        """
        Update the status of a specific task.
        
        Args:
            plan_id: ID of the plan containing the task
            task_id: ID of the task to update
            status: New status for the task
            
        Returns:
            True if the status was updated successfully
        """
        pass
    
    @abstractmethod
    def estimate_duration(self, task: Task, context: CodebaseContext) -> int:
        """
        Estimate the duration for completing a task.
        
        Args:
            task: The task to estimate
            context: Codebase context for informed estimation
            
        Returns:
            Estimated duration in minutes
        """
        pass
    
    @abstractmethod
    def resolve_dependencies(self, tasks: List[Task]) -> List[Task]:
        """
        Resolve and order tasks based on their dependencies.
        
        Args:
            tasks: List of tasks to order
            
        Returns:
            List of tasks in dependency-resolved order
        """
        pass


class DynamicStatusManagerInterface(ABC):
    """Abstract interface for dynamic task status management."""
    
    @abstractmethod
    def register_plan(self, plan: TaskPlan) -> None:
        """
        Register a task plan for status management.
        
        Args:
            plan: The task plan to register
        """
        pass
    
    @abstractmethod
    def update_task_status(self, task_id: str, new_status: TaskStatus,
                          message: Optional[str] = None,
                          progress_percentage: Optional[float] = None,
                          error_info: Optional[ErrorInfo] = None) -> bool:
        """
        Update task status with real-time tracking.
        
        Args:
            task_id: ID of the task to update
            new_status: New status for the task
            message: Optional status message
            progress_percentage: Optional progress percentage (0-100)
            error_info: Optional error information
            
        Returns:
            True if the status was updated successfully
        """
        pass
    
    @abstractmethod
    def get_task_progress(self, task_id: str) -> Optional['TaskProgress']:
        """
        Get current progress information for a task.
        
        Args:
            task_id: ID of the task
            
        Returns:
            TaskProgress object or None if not found
        """
        pass
    
    @abstractmethod
    def get_plan_progress(self, plan_id: str) -> Dict[str, Any]:
        """
        Get overall progress information for a plan.
        
        Args:
            plan_id: ID of the plan
            
        Returns:
            Dictionary with plan progress information
        """
        pass
    
    @abstractmethod
    def modify_task(self, task_id: str, new_description: Optional[str] = None,
                   new_estimated_duration: Optional[int] = None,
                   add_dependencies: Optional[List[str]] = None,
                   remove_dependencies: Optional[List[str]] = None) -> bool:
        """
        Modify task properties and trigger re-planning if needed.
        
        Args:
            task_id: ID of the task to modify
            new_description: New task description
            new_estimated_duration: New estimated duration in minutes
            add_dependencies: Dependencies to add
            remove_dependencies: Dependencies to remove
            
        Returns:
            True if the task was modified successfully
        """
        pass
    
    @abstractmethod
    def replan_from_task(self, task_id: str, new_subtasks: List[Dict[str, Any]]) -> bool:
        """
        Re-plan a task by replacing its subtasks.
        
        Args:
            task_id: ID of the task to re-plan
            new_subtasks: List of new subtask definitions
            
        Returns:
            True if re-planning was successful
        """
        pass
    
    @abstractmethod
    def add_status_listener(self, listener: Callable[['StatusUpdate'], None]) -> None:
        """
        Add a listener for status update events.
        
        Args:
            listener: Function to call on status updates
        """
        pass
    
    @abstractmethod
    def get_active_tasks(self, plan_id: Optional[str] = None) -> List['TaskProgress']:
        """
        Get all currently active (in-progress) tasks.
        
        Args:
            plan_id: Optional plan ID to filter by
            
        Returns:
            List of active task progress objects
        """
        pass


class ApprovalWorkflowInterface(ABC):
    """Abstract interface for approval workflow management."""
    
    @abstractmethod
    def submit_for_approval(self, plan: 'TaskPlan', 
                           additional_context: Optional[Dict[str, Any]] = None) -> str:
        """
        Submit a task plan for user approval.
        
        Args:
            plan: The task plan to submit for approval
            additional_context: Optional additional context information
            
        Returns:
            Approval request ID
        """
        pass
    
    @abstractmethod
    def respond_to_approval(self, request_id: str, response: 'ApprovalResponse') -> bool:
        """
        Process a user's response to an approval request.
        
        Args:
            request_id: ID of the approval request
            response: User's response
            
        Returns:
            True if the response was processed successfully
        """
        pass
    
    @abstractmethod
    def get_approval_request(self, request_id: str) -> Optional['ApprovalRequest']:
        """
        Get an approval request by ID.
        
        Args:
            request_id: ID of the approval request
            
        Returns:
            ApprovalRequest object or None if not found
        """
        pass
    
    @abstractmethod
    def get_pending_approvals(self) -> List['ApprovalRequest']:
        """
        Get all pending approval requests.
        
        Returns:
            List of pending approval requests
        """
        pass
    
    @abstractmethod
    def modify_plan_based_on_feedback(self, plan: 'TaskPlan', 
                                     modifications: List[str]) -> List['ModificationRequest']:
        """
        Apply modifications to a plan based on user feedback.
        
        Args:
            plan: The task plan to modify
            modifications: List of modification descriptions
            
        Returns:
            List of modification requests that were applied
        """
        pass