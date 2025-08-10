"""
Tests for approval workflow system.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock

from ..types import ApprovalStatus, PlanStatus, TaskStatus
from .models import TaskPlan, Task, Subtask
from .approval_workflow import (
    ApprovalWorkflow, ApprovalRequest, ApprovalResponse, ModificationRequest
)


class TestApprovalWorkflow:
    """Test cases for ApprovalWorkflow."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.workflow = ApprovalWorkflow()
        
        # Create a test plan
        self.task1 = Task(
            id="task1",
            description="Implement feature A",
            estimated_duration=60
        )
        
        self.subtask1 = Subtask(
            id="subtask1",
            description="Design feature A",
            estimated_duration=30
        )
        
        self.task1.subtasks = [self.subtask1]
        
        self.task2 = Task(
            id="task2",
            description="Test feature A",
            dependencies=["task1"],
            estimated_duration=30
        )
        
        self.plan = TaskPlan(
            id="plan1",
            description="Feature A development",
            tasks=[self.task1, self.task2]
        )
    
    def test_submit_for_approval(self):
        """Test submitting a plan for approval."""
        request_id = self.workflow.submit_for_approval(self.plan)
        
        assert request_id is not None
        assert len(request_id) > 0
        
        # Check that request was created
        request = self.workflow.get_approval_request(request_id)
        assert request is not None
        assert request.plan_id == "plan1"
        assert request.plan_description == "Feature A development"
        assert request.status == ApprovalStatus.PENDING
        assert len(request.tasks_summary) > 0
        
        # Check that plan status was updated
        assert self.plan.status == PlanStatus.PENDING_APPROVAL
        assert self.plan.approval_status == ApprovalStatus.PENDING
    
    def test_submit_for_approval_with_context(self):
        """Test submitting a plan with additional context."""
        context = {"priority": "high", "deadline": "2024-01-15"}
        request_id = self.workflow.submit_for_approval(self.plan, context)
        
        request = self.workflow.get_approval_request(request_id)
        assert request.metadata == context
    
    def test_respond_to_approval_approved(self):
        """Test responding to approval with approval."""
        request_id = self.workflow.submit_for_approval(self.plan)
        
        response = ApprovalResponse(
            request_id=request_id,
            status=ApprovalStatus.APPROVED,
            feedback="Looks good to proceed"
        )
        
        result = self.workflow.respond_to_approval(request_id, response)
        assert result is True
        
        # Check that request was updated
        request = self.workflow.get_approval_request(request_id)
        assert request.status == ApprovalStatus.APPROVED
        assert request.user_feedback == "Looks good to proceed"
        assert request.approved_at is not None
        
        # Check history
        history = self.workflow.get_approval_history(request_id)
        assert len(history) == 1
        assert history[0].status == ApprovalStatus.APPROVED
    
    def test_respond_to_approval_rejected(self):
        """Test responding to approval with rejection."""
        request_id = self.workflow.submit_for_approval(self.plan)
        
        response = ApprovalResponse(
            request_id=request_id,
            status=ApprovalStatus.REJECTED,
            feedback="Too complex, needs simplification"
        )
        
        result = self.workflow.respond_to_approval(request_id, response)
        assert result is True
        
        request = self.workflow.get_approval_request(request_id)
        assert request.status == ApprovalStatus.REJECTED
        assert request.rejected_at is not None
    
    def test_respond_to_approval_needs_revision(self):
        """Test responding to approval with revision request."""
        request_id = self.workflow.submit_for_approval(self.plan)
        
        modifications = [
            "Change task 1 description to be more specific",
            "Add error handling task"
        ]
        
        response = ApprovalResponse(
            request_id=request_id,
            status=ApprovalStatus.NEEDS_REVISION,
            feedback="Needs some modifications",
            modifications_requested=modifications
        )
        
        result = self.workflow.respond_to_approval(request_id, response)
        assert result is True
        
        request = self.workflow.get_approval_request(request_id)
        assert request.status == ApprovalStatus.NEEDS_REVISION
        assert request.modifications_requested == modifications
    
    def test_respond_to_nonexistent_request(self):
        """Test responding to nonexistent approval request."""
        response = ApprovalResponse(
            request_id="nonexistent",
            status=ApprovalStatus.APPROVED
        )
        
        result = self.workflow.respond_to_approval("nonexistent", response)
        assert result is False
    
    def test_get_pending_approvals(self):
        """Test getting pending approval requests."""
        # Initially no pending approvals
        pending = self.workflow.get_pending_approvals()
        assert len(pending) == 0
        
        # Submit for approval
        request_id = self.workflow.submit_for_approval(self.plan)
        
        pending = self.workflow.get_pending_approvals()
        assert len(pending) == 1
        assert pending[0].id == request_id
        
        # Approve the request
        response = ApprovalResponse(
            request_id=request_id,
            status=ApprovalStatus.APPROVED
        )
        self.workflow.respond_to_approval(request_id, response)
        
        # Should no longer be pending
        pending = self.workflow.get_pending_approvals()
        assert len(pending) == 0
    
    def test_modify_plan_based_on_feedback(self):
        """Test modifying a plan based on user feedback."""
        modifications = [
            "Change description of task 1",
            "Add new task for validation",
            "Remove unnecessary subtask"
        ]
        
        applied = self.workflow.modify_plan_based_on_feedback(self.plan, modifications)
        
        assert len(applied) == len(modifications)
        assert all(isinstance(mod, ModificationRequest) for mod in applied)
        
        # Check that plan metadata was updated
        assert 'last_modified' in self.plan.metadata
        assert self.plan.metadata['modification_count'] == len(modifications)
    
    def test_get_plan_modifications(self):
        """Test getting modifications applied to a plan."""
        # Initially no modifications
        modifications = self.workflow.get_plan_modifications("plan1")
        assert len(modifications) == 0
        
        # Apply some modifications
        mod_requests = ["Change task description", "Add error handling"]
        self.workflow.modify_plan_based_on_feedback(self.plan, mod_requests)
        
        modifications = self.workflow.get_plan_modifications("plan1")
        assert len(modifications) == 2
    
    def test_approval_listeners(self):
        """Test approval request listeners."""
        # Create mock listener
        listener = Mock()
        self.workflow.add_approval_listener(listener)
        
        # Submit for approval
        request_id = self.workflow.submit_for_approval(self.plan)
        
        # Check listener was called
        listener.assert_called_once()
        request = listener.call_args[0][0]
        assert isinstance(request, ApprovalRequest)
        assert request.plan_id == "plan1"
        
        # Remove listener
        self.workflow.remove_approval_listener(listener)
        listener.reset_mock()
        
        # Submit another plan
        plan2 = TaskPlan(id="plan2", description="Test plan 2")
        self.workflow.submit_for_approval(plan2)
        
        # Listener should not be called
        listener.assert_not_called()
    
    def test_response_listeners(self):
        """Test approval response listeners."""
        request_id = self.workflow.submit_for_approval(self.plan)
        
        # Create mock listener
        listener = Mock()
        self.workflow.add_response_listener(listener)
        
        # Respond to approval
        response = ApprovalResponse(
            request_id=request_id,
            status=ApprovalStatus.APPROVED
        )
        self.workflow.respond_to_approval(request_id, response)
        
        # Check listener was called
        listener.assert_called_once()
        response_arg = listener.call_args[0][0]
        assert isinstance(response_arg, ApprovalResponse)
        assert response_arg.status == ApprovalStatus.APPROVED
    
    def test_create_approval_summary(self):
        """Test creating approval summary."""
        request_id = self.workflow.submit_for_approval(self.plan)
        
        summary = self.workflow.create_approval_summary(request_id)
        
        assert summary['request_id'] == request_id
        assert summary['plan_id'] == "plan1"
        assert summary['plan_description'] == "Feature A development"
        assert summary['status'] == ApprovalStatus.PENDING.value
        assert summary['task_count'] == 2
        assert summary['subtask_count'] == 1
        assert summary['estimated_total_duration'] == 120  # 60 + 30 + 30
        assert len(summary['tasks_summary']) > 0
        assert summary['response_count'] == 0
    
    def test_create_approval_summary_nonexistent(self):
        """Test creating summary for nonexistent request."""
        summary = self.workflow.create_approval_summary("nonexistent")
        assert summary == {}
    
    def test_create_approval_summary_with_responses(self):
        """Test creating summary with response history."""
        request_id = self.workflow.submit_for_approval(self.plan)
        
        # Add some responses
        response1 = ApprovalResponse(
            request_id=request_id,
            status=ApprovalStatus.NEEDS_REVISION,
            feedback="Needs changes"
        )
        self.workflow.respond_to_approval(request_id, response1)
        
        response2 = ApprovalResponse(
            request_id=request_id,
            status=ApprovalStatus.APPROVED,
            feedback="Looks good now"
        )
        self.workflow.respond_to_approval(request_id, response2)
        
        summary = self.workflow.create_approval_summary(request_id)
        assert summary['response_count'] == 2
        assert summary['last_response_at'] is not None


class TestApprovalRequest:
    """Test cases for ApprovalRequest model."""
    
    def test_approval_request_creation(self):
        """Test creating approval request."""
        request = ApprovalRequest(
            id="req1",
            plan_id="plan1",
            plan_description="Test plan",
            tasks_summary=["Task 1", "Task 2"]
        )
        
        assert request.id == "req1"
        assert request.plan_id == "plan1"
        assert request.status == ApprovalStatus.PENDING
        assert isinstance(request.requested_at, datetime)
        assert len(request.tasks_summary) == 2


class TestApprovalResponse:
    """Test cases for ApprovalResponse model."""
    
    def test_approval_response_creation(self):
        """Test creating approval response."""
        response = ApprovalResponse(
            request_id="req1",
            status=ApprovalStatus.APPROVED,
            feedback="Approved with minor concerns"
        )
        
        assert response.request_id == "req1"
        assert response.status == ApprovalStatus.APPROVED
        assert response.feedback == "Approved with minor concerns"
        assert isinstance(response.timestamp, datetime)


class TestModificationRequest:
    """Test cases for ModificationRequest model."""
    
    def test_modification_request_creation(self):
        """Test creating modification request."""
        modification = ModificationRequest(
            id="mod1",
            plan_id="plan1",
            task_id="task1",
            modification_type="description",
            old_value="Old description",
            new_value="New description",
            reason="User requested change"
        )
        
        assert modification.id == "mod1"
        assert modification.plan_id == "plan1"
        assert modification.task_id == "task1"
        assert modification.modification_type == "description"
        assert isinstance(modification.timestamp, datetime)


if __name__ == "__main__":
    pytest.main([__file__])