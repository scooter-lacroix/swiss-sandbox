"""
Approval workflow system for task plans with user interaction and feedback handling.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from threading import Lock

from ..types import ApprovalStatus, PlanStatus
from .models import TaskPlan, Task


@dataclass
class ApprovalRequest:
    """Represents an approval request for a task plan."""
    id: str
    plan_id: str
    plan_description: str
    tasks_summary: List[str]
    requested_at: datetime = field(default_factory=datetime.now)
    status: ApprovalStatus = ApprovalStatus.PENDING
    user_feedback: Optional[str] = None
    modifications_requested: List[str] = field(default_factory=list)
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ApprovalResponse:
    """Represents a user's response to an approval request."""
    request_id: str
    status: ApprovalStatus
    feedback: Optional[str] = None
    modifications_requested: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModificationRequest:
    """Represents a specific modification request for a task plan."""
    id: str
    plan_id: str
    task_id: Optional[str] = None  # None for plan-level modifications
    modification_type: str = "description"  # description, duration, dependencies, add_task, remove_task
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    reason: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


class ApprovalWorkflow:
    """
    Manages approval workflows for task plans with user interaction,
    feedback handling, and plan modification capabilities.
    """
    
    def __init__(self):
        self._approval_requests: Dict[str, ApprovalRequest] = {}
        self._approval_history: Dict[str, List[ApprovalResponse]] = {}
        self._modification_requests: Dict[str, List[ModificationRequest]] = {}
        self._approval_listeners: List[Callable[[ApprovalRequest], None]] = []
        self._response_listeners: List[Callable[[ApprovalResponse], None]] = []
        self._lock = Lock()
    
    def submit_for_approval(self, plan: TaskPlan, 
                           additional_context: Optional[Dict[str, Any]] = None) -> str:
        """
        Submit a task plan for user approval.
        
        Args:
            plan: The task plan to submit for approval
            additional_context: Optional additional context information
            
        Returns:
            Approval request ID
        """
        with self._lock:
            request_id = str(uuid.uuid4())
            
            # Create tasks summary
            tasks_summary = []
            for task in plan.tasks:
                task_summary = f"• {task.description}"
                if task.estimated_duration:
                    task_summary += f" (Est: {task.estimated_duration} min)"
                if task.dependencies:
                    task_summary += f" [Depends on: {', '.join(task.dependencies)}]"
                tasks_summary.append(task_summary)
                
                # Add subtasks if any
                for subtask in task.subtasks:
                    subtask_summary = f"  - {subtask.description}"
                    if subtask.estimated_duration:
                        subtask_summary += f" (Est: {subtask.estimated_duration} min)"
                    tasks_summary.append(subtask_summary)
            
            # Create approval request
            request = ApprovalRequest(
                id=request_id,
                plan_id=plan.id,
                plan_description=plan.description,
                tasks_summary=tasks_summary,
                metadata=additional_context or {}
            )
            
            self._approval_requests[request_id] = request
            self._approval_history[request_id] = []
            
            # Update plan status
            plan.status = PlanStatus.PENDING_APPROVAL
            plan.approval_status = ApprovalStatus.PENDING
            
            # Notify listeners
            self._notify_approval_listeners(request)
            
            return request_id
    
    def respond_to_approval(self, request_id: str, response: ApprovalResponse) -> bool:
        """
        Process a user's response to an approval request.
        
        Args:
            request_id: ID of the approval request
            response: User's response
            
        Returns:
            True if the response was processed successfully
        """
        with self._lock:
            if request_id not in self._approval_requests:
                return False
            
            request = self._approval_requests[request_id]
            
            # Update request status
            request.status = response.status
            request.user_feedback = response.feedback
            request.modifications_requested = response.modifications_requested.copy()
            
            if response.status == ApprovalStatus.APPROVED:
                request.approved_at = datetime.now()
            elif response.status == ApprovalStatus.REJECTED:
                request.rejected_at = datetime.now()
            
            # Record response in history
            self._approval_history[request_id].append(response)
            
            # Process modifications if requested
            if response.status == ApprovalStatus.NEEDS_REVISION:
                self._process_modification_requests(request.plan_id, response.modifications_requested)
            
            # Notify listeners
            self._notify_response_listeners(response)
            
            return True
    
    def get_approval_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get an approval request by ID."""
        with self._lock:
            return self._approval_requests.get(request_id)
    
    def get_pending_approvals(self) -> List[ApprovalRequest]:
        """Get all pending approval requests."""
        with self._lock:
            return [
                request for request in self._approval_requests.values()
                if request.status == ApprovalStatus.PENDING
            ]
    
    def get_approval_history(self, request_id: str) -> List[ApprovalResponse]:
        """Get the approval history for a request."""
        with self._lock:
            return self._approval_history.get(request_id, []).copy()
    
    def modify_plan_based_on_feedback(self, plan: TaskPlan, 
                                     modifications: List[str]) -> List[ModificationRequest]:
        """
        Apply modifications to a plan based on user feedback.
        
        Args:
            plan: The task plan to modify
            modifications: List of modification descriptions
            
        Returns:
            List of modification requests that were applied
        """
        with self._lock:
            applied_modifications = []
            
            for modification_desc in modifications:
                modification = self._parse_modification_request(plan.id, modification_desc)
                if modification:
                    success = self._apply_modification(plan, modification)
                    if success:
                        applied_modifications.append(modification)
                        
                        # Store modification request
                        if plan.id not in self._modification_requests:
                            self._modification_requests[plan.id] = []
                        self._modification_requests[plan.id].append(modification)
            
            # Mark plan as modified
            plan.metadata['last_modified'] = datetime.now()
            plan.metadata['modification_count'] = plan.metadata.get('modification_count', 0) + len(applied_modifications)
            
            return applied_modifications
    
    def get_plan_modifications(self, plan_id: str) -> List[ModificationRequest]:
        """Get all modifications applied to a plan."""
        with self._lock:
            return self._modification_requests.get(plan_id, []).copy()
    
    def add_approval_listener(self, listener: Callable[[ApprovalRequest], None]) -> None:
        """Add a listener for approval request events."""
        with self._lock:
            self._approval_listeners.append(listener)
    
    def add_response_listener(self, listener: Callable[[ApprovalResponse], None]) -> None:
        """Add a listener for approval response events."""
        with self._lock:
            self._response_listeners.append(listener)
    
    def remove_approval_listener(self, listener: Callable[[ApprovalRequest], None]) -> None:
        """Remove an approval request listener."""
        with self._lock:
            if listener in self._approval_listeners:
                self._approval_listeners.remove(listener)
    
    def remove_response_listener(self, listener: Callable[[ApprovalResponse], None]) -> None:
        """Remove an approval response listener."""
        with self._lock:
            if listener in self._response_listeners:
                self._response_listeners.remove(listener)
    
    def create_approval_summary(self, request_id: str) -> Dict[str, Any]:
        """Create a comprehensive summary for an approval request."""
        with self._lock:
            if request_id not in self._approval_requests:
                return {}
            
            request = self._approval_requests[request_id]
            history = self._approval_history.get(request_id, [])
            
            # Calculate estimated total duration
            total_duration = 0
            task_count = 0
            subtask_count = 0
            
            for task_summary in request.tasks_summary:
                if task_summary.startswith('•'):  # Main task
                    task_count += 1
                    # Extract duration if present
                    if '(Est:' in task_summary:
                        try:
                            duration_str = task_summary.split('(Est:')[1].split('min)')[0].strip()
                            total_duration += int(duration_str)
                        except (IndexError, ValueError):
                            pass
                elif task_summary.startswith('  -'):  # Subtask
                    subtask_count += 1
                    # Extract duration if present
                    if '(Est:' in task_summary:
                        try:
                            duration_str = task_summary.split('(Est:')[1].split('min)')[0].strip()
                            total_duration += int(duration_str)
                        except (IndexError, ValueError):
                            pass
            
            return {
                'request_id': request_id,
                'plan_id': request.plan_id,
                'plan_description': request.plan_description,
                'status': request.status.value,
                'requested_at': request.requested_at.isoformat(),
                'task_count': task_count,
                'subtask_count': subtask_count,
                'estimated_total_duration': total_duration,
                'tasks_summary': request.tasks_summary,
                'user_feedback': request.user_feedback,
                'modifications_requested': request.modifications_requested,
                'response_count': len(history),
                'last_response_at': history[-1].timestamp.isoformat() if history else None
            }
    
    def _process_modification_requests(self, plan_id: str, modifications: List[str]) -> None:
        """Process modification requests for a plan."""
        # This would typically trigger a re-planning process
        # For now, we just store the requests
        if plan_id not in self._modification_requests:
            self._modification_requests[plan_id] = []
        
        for modification_desc in modifications:
            modification = self._parse_modification_request(plan_id, modification_desc)
            if modification:
                self._modification_requests[plan_id].append(modification)
    
    def _parse_modification_request(self, plan_id: str, description: str) -> Optional[ModificationRequest]:
        """Parse a modification request from a description string."""
        modification_id = str(uuid.uuid4())
        
        # Simple parsing logic - in a real implementation, this would be more sophisticated
        description_lower = description.lower()
        
        if 'change description' in description_lower or 'modify description' in description_lower:
            return ModificationRequest(
                id=modification_id,
                plan_id=plan_id,
                modification_type='description',
                reason=description
            )
        elif 'change duration' in description_lower or 'modify duration' in description_lower:
            return ModificationRequest(
                id=modification_id,
                plan_id=plan_id,
                modification_type='duration',
                reason=description
            )
        elif 'add task' in description_lower:
            return ModificationRequest(
                id=modification_id,
                plan_id=plan_id,
                modification_type='add_task',
                reason=description
            )
        elif 'remove task' in description_lower:
            return ModificationRequest(
                id=modification_id,
                plan_id=plan_id,
                modification_type='remove_task',
                reason=description
            )
        else:
            # Generic modification
            return ModificationRequest(
                id=modification_id,
                plan_id=plan_id,
                modification_type='generic',
                reason=description
            )
    
    def _apply_modification(self, plan: TaskPlan, modification: ModificationRequest) -> bool:
        """Apply a modification to a task plan."""
        try:
            if modification.modification_type == 'description':
                # This would require more context about what to change
                plan.metadata['pending_description_change'] = modification.reason
                return True
            elif modification.modification_type == 'add_task':
                # This would require task creation logic
                plan.metadata['pending_task_addition'] = modification.reason
                return True
            elif modification.modification_type == 'remove_task':
                # This would require task removal logic
                plan.metadata['pending_task_removal'] = modification.reason
                return True
            else:
                # Generic modification
                plan.metadata['pending_modification'] = modification.reason
                return True
        except Exception:
            return False
    
    def _notify_approval_listeners(self, request: ApprovalRequest) -> None:
        """Notify all approval request listeners."""
        for listener in self._approval_listeners:
            try:
                listener(request)
            except Exception:
                # Ignore listener errors
                pass
    
    def _notify_response_listeners(self, response: ApprovalResponse) -> None:
        """Notify all response listeners."""
        for listener in self._response_listeners:
            try:
                listener(response)
            except Exception:
                # Ignore listener errors
                pass