"""
Integration tests for the complete task planning system.
"""

import pytest
from unittest.mock import Mock

from ..analyzer.models import CodebaseAnalysis, CodebaseStructure, DependencyGraph, CodeMetrics
from ..types import TaskStatus, ApprovalStatus, PlanStatus
from .planner import TaskPlanner
from .approval_workflow import ApprovalResponse


class TestTaskPlanningIntegration:
    """Integration tests for the complete task planning system."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.planner = TaskPlanner()
        
        # Create mock codebase analysis
        self.codebase_analysis = CodebaseAnalysis(
            structure=CodebaseStructure(
                root_path="/test/project",
                languages=['python', 'javascript'],
                frameworks=['django', 'react'],
                entry_points=['main.py', 'app.js'],
                config_files=['requirements.txt', 'package.json']
            ),
            dependencies=DependencyGraph(
                conflicts=[]
            ),
            patterns=[],
            metrics=CodeMetrics(
                lines_of_code=15000,
                cyclomatic_complexity=8,
                test_coverage=0.75
            ),
            summary="A Django-React web application",
            analysis_timestamp=None  # Will be set in __post_init__
        )
    
    def test_complete_workflow_approval(self):
        """Test complete workflow from plan creation to approval."""
        # 1. Create a plan
        plan = self.planner.create_plan(
            "Implement user authentication system",
            self.codebase_analysis
        )
        
        assert plan is not None
        assert len(plan.tasks) > 0
        assert plan.status == PlanStatus.DRAFT
        
        # 2. Submit for approval
        request_id = self.planner.submit_plan_for_approval(
            plan.id,
            {"priority": "high", "deadline": "2024-01-15"}
        )
        
        assert request_id is not None
        assert plan.status == PlanStatus.PENDING_APPROVAL
        assert plan.approval_status == ApprovalStatus.PENDING
        
        # 3. Get approval request
        approval_workflow = self.planner.get_approval_workflow()
        request = approval_workflow.get_approval_request(request_id)
        
        assert request is not None
        assert request.plan_id == plan.id
        assert len(request.tasks_summary) > 0
        
        # 4. Approve the plan
        success = self.planner.approve_plan(request_id, "Looks good to proceed")
        assert success is True
        
        # 5. Verify approval status
        updated_request = approval_workflow.get_approval_request(request_id)
        assert updated_request.status == ApprovalStatus.APPROVED
        assert updated_request.user_feedback == "Looks good to proceed"
    
    def test_complete_workflow_revision(self):
        """Test complete workflow with revision requests."""
        # 1. Create and submit plan
        plan = self.planner.create_plan(
            "Refactor authentication module",
            self.codebase_analysis
        )
        
        request_id = self.planner.submit_plan_for_approval(plan.id)
        
        # 2. Request revisions
        modifications = [
            "Add error handling task",
            "Change task 1 description to be more specific",
            "Add performance testing task"
        ]
        
        success = self.planner.request_plan_revision(
            request_id,
            "Needs some improvements",
            modifications
        )
        assert success is True
        
        # 3. Verify revision request
        approval_workflow = self.planner.get_approval_workflow()
        request = approval_workflow.get_approval_request(request_id)
        
        assert request.status == ApprovalStatus.NEEDS_REVISION
        assert request.modifications_requested == modifications
        
        # 4. Apply modifications
        applied_mods = approval_workflow.modify_plan_based_on_feedback(plan, modifications)
        assert len(applied_mods) == len(modifications)
        
        # 5. Resubmit and approve
        new_request_id = self.planner.submit_plan_for_approval(plan.id)
        success = self.planner.approve_plan(new_request_id, "Much better now")
        assert success is True
    
    def test_dynamic_status_management_integration(self):
        """Test integration with dynamic status management."""
        # 1. Create plan
        plan = self.planner.create_plan(
            "Implement API endpoints",
            self.codebase_analysis
        )
        
        # 2. Get status manager
        status_manager = self.planner.get_status_manager()
        
        # 3. Start executing tasks
        first_task = plan.tasks[0]
        
        # Update task status with progress
        success = self.planner.update_task_status_advanced(
            first_task.id,
            TaskStatus.IN_PROGRESS,
            "Started implementation",
            25.0
        )
        assert success is True
        
        # 4. Check progress
        progress = status_manager.get_task_progress(first_task.id)
        assert progress is not None
        assert progress.status == TaskStatus.IN_PROGRESS
        assert progress.progress_percentage == 25.0
        assert progress.start_time is not None
        
        # 5. Get plan progress
        plan_progress = self.planner.get_plan_progress(plan.id)
        assert plan_progress['total_tasks'] == len(plan.tasks)
        assert plan_progress['in_progress_tasks'] == 1
        
        # 6. Complete task
        success = self.planner.update_task_status_advanced(
            first_task.id,
            TaskStatus.COMPLETED,
            "Implementation finished"
        )
        assert success is True
        
        # 7. Verify completion
        progress = status_manager.get_task_progress(first_task.id)
        assert progress.status == TaskStatus.COMPLETED
        assert progress.progress_percentage == 100.0
        assert progress.end_time is not None
    
    def test_task_modification_and_replanning(self):
        """Test task modification and re-planning capabilities."""
        # 1. Create plan
        plan = self.planner.create_plan(
            "Build notification system",
            self.codebase_analysis
        )
        
        first_task = plan.tasks[0]
        original_description = first_task.description
        
        # 2. Modify task
        success = self.planner.modify_task(
            first_task.id,
            new_description="Build enhanced notification system with real-time updates",
            new_estimated_duration=120
        )
        assert success is True
        assert first_task.description != original_description
        assert first_task.estimated_duration == 120
        
        # 3. Re-plan task with new subtasks
        new_subtasks = [
            {
                'id': 'new_subtask_1',
                'description': 'Design notification architecture',
                'estimated_duration': 30
            },
            {
                'id': 'new_subtask_2',
                'description': 'Implement real-time WebSocket connection',
                'dependencies': ['new_subtask_1'],
                'estimated_duration': 45
            },
            {
                'id': 'new_subtask_3',
                'description': 'Create notification UI components',
                'dependencies': ['new_subtask_1'],
                'estimated_duration': 45
            }
        ]
        
        success = self.planner.replan_task(first_task.id, new_subtasks)
        assert success is True
        assert len(first_task.subtasks) == 3
        
        # 4. Verify new subtasks are tracked
        status_manager = self.planner.get_status_manager()
        for subtask_data in new_subtasks:
            progress = status_manager.get_task_progress(subtask_data['id'])
            assert progress is not None
            assert progress.estimated_duration == subtask_data['estimated_duration']
    
    def test_listeners_and_notifications(self):
        """Test event listeners and notifications."""
        # 1. Set up listeners
        approval_listener = Mock()
        status_listener = Mock()
        
        approval_workflow = self.planner.get_approval_workflow()
        status_manager = self.planner.get_status_manager()
        
        approval_workflow.add_approval_listener(approval_listener)
        status_manager.add_status_listener(status_listener)
        
        # 2. Create and submit plan
        plan = self.planner.create_plan(
            "Implement search functionality",
            self.codebase_analysis
        )
        
        request_id = self.planner.submit_plan_for_approval(plan.id)
        
        # 3. Verify approval listener was called
        approval_listener.assert_called_once()
        request = approval_listener.call_args[0][0]
        assert request.plan_id == plan.id
        
        # 4. Update task status
        first_task = plan.tasks[0]
        self.planner.update_task_status_advanced(
            first_task.id,
            TaskStatus.IN_PROGRESS,
            "Started work"
        )
        
        # 5. Verify status listener was called
        status_listener.assert_called_once()
        update = status_listener.call_args[0][0]
        assert update.task_id == first_task.id
        assert update.new_status == TaskStatus.IN_PROGRESS
    
    def test_error_handling_integration(self):
        """Test error handling across components."""
        # 1. Create plan
        plan = self.planner.create_plan(
            "Deploy application",
            self.codebase_analysis
        )
        
        # 2. Try to update nonexistent task
        success = self.planner.update_task_status_advanced(
            "nonexistent_task",
            TaskStatus.IN_PROGRESS
        )
        assert success is False
        
        # 3. Try to approve nonexistent request
        success = self.planner.approve_plan("nonexistent_request")
        assert success is False
        
        # 4. Try to modify nonexistent task
        success = self.planner.modify_task(
            "nonexistent_task",
            new_description="New description"
        )
        assert success is False
        
        # 5. Get nonexistent plan progress
        progress = self.planner.get_plan_progress("nonexistent_plan")
        assert progress == {}


if __name__ == "__main__":
    pytest.main([__file__])