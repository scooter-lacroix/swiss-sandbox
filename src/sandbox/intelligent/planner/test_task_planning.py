"""
Unit tests for task planning functionality.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock

from ..analyzer.models import (
    CodebaseAnalysis, CodebaseStructure, DependencyGraph, 
    Pattern, CodeMetrics
)
from ..types import TaskStatus, PlanStatus, ApprovalStatus
from .models import Task, Subtask, TaskPlan, CodebaseContext
from .planner import TaskPlanner


class TestTaskPlanner:
    """Test cases for TaskPlanner class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.planner = TaskPlanner()
        self.mock_analysis = self._create_mock_analysis()
    
    def _create_mock_analysis(self) -> CodebaseAnalysis:
        """Create a mock codebase analysis for testing."""
        structure = CodebaseStructure(
            root_path="/test/project",
            languages=["python", "javascript"],
            frameworks=["django", "react"],
            entry_points=["main.py", "app.js"],
            test_directories=["tests/", "test/"],
            config_files=["setup.py", "package.json"]
        )
        
        dependencies = DependencyGraph(
            dependencies=[],
            dependency_files=["requirements.txt", "package.json"]
        )
        
        patterns = [
            Pattern(
                name="MVC Architecture",
                type="architectural",
                confidence=0.8,
                description="Model-View-Controller pattern detected"
            ),
            Pattern(
                name="Repository Pattern",
                type="design",
                confidence=0.9,
                description="Repository pattern for data access"
            )
        ]
        
        metrics = CodeMetrics(
            lines_of_code=15000,
            cyclomatic_complexity=8.5,
            maintainability_index=75.0,
            test_coverage=0.85
        )
        
        return CodebaseAnalysis(
            structure=structure,
            dependencies=dependencies,
            patterns=patterns,
            metrics=metrics,
            summary="Well-structured Django/React application",
            analysis_timestamp=datetime.now()
        )
    
    def test_create_plan_basic(self):
        """Test basic plan creation."""
        task_description = "Implement user authentication system"
        
        plan = self.planner.create_plan(task_description, self.mock_analysis)
        
        assert plan is not None
        assert plan.description == task_description
        assert plan.status == PlanStatus.DRAFT
        assert plan.approval_status == ApprovalStatus.PENDING
        assert len(plan.tasks) > 0
        assert plan.codebase_context is not None
    
    def test_create_plan_implementation_task(self):
        """Test plan creation for implementation tasks."""
        task_description = "Implement new payment processing feature"
        
        plan = self.planner.create_plan(task_description, self.mock_analysis)
        
        # Should create multiple tasks for implementation
        assert len(plan.tasks) >= 3
        assert plan.metadata['task_type'] == 'implementation'
        
        # Check task ordering
        task_descriptions = [task.description for task in plan.tasks]
        assert any('analyze' in desc.lower() for desc in task_descriptions)
        assert any('implement' in desc.lower() for desc in task_descriptions)
    
    def test_create_plan_refactoring_task(self):
        """Test plan creation for refactoring tasks."""
        task_description = "Refactor database access layer"
        
        plan = self.planner.create_plan(task_description, self.mock_analysis)
        
        assert plan.metadata['task_type'] == 'refactoring'
        assert len(plan.tasks) >= 3
    
    def test_create_plan_debugging_task(self):
        """Test plan creation for debugging tasks."""
        task_description = "Fix memory leak in data processing module"
        
        plan = self.planner.create_plan(task_description, self.mock_analysis)
        
        assert plan.metadata['task_type'] == 'debugging'
        task_descriptions = [task.description for task in plan.tasks]
        assert any('reproduce' in desc.lower() for desc in task_descriptions)
        assert any('fix' in desc.lower() for desc in task_descriptions)
    
    def test_break_down_task_implementation(self):
        """Test task breakdown for implementation tasks."""
        task = Task(
            id="test_task",
            description="Implement user registration feature"
        )
        context = CodebaseContext(analysis=self.mock_analysis)
        
        subtasks = self.planner.break_down_task(task, context)
        
        assert len(subtasks) >= 3
        subtask_descriptions = [st.description for st in subtasks]
        assert any('analyze' in desc.lower() for desc in subtask_descriptions)
        assert any('setup' in desc.lower() or 'infrastructure' in desc.lower() for desc in subtask_descriptions)
        assert any('implement' in desc.lower() or 'core' in desc.lower() for desc in subtask_descriptions)
    
    def test_break_down_task_with_dependencies(self):
        """Test that subtask dependencies are set correctly."""
        task = Task(
            id="test_task",
            description="Create new API endpoint"
        )
        context = CodebaseContext(analysis=self.mock_analysis)
        
        subtasks = self.planner.break_down_task(task, context)
        
        # Check that later subtasks depend on earlier ones
        if len(subtasks) > 1:
            later_subtasks = subtasks[1:]
            for subtask in later_subtasks:
                assert len(subtask.dependencies) > 0
    
    def test_validate_plan_valid(self):
        """Test validation of a valid plan."""
        plan = self.planner.create_plan(
            "Implement feature X", self.mock_analysis
        )
        
        assert self.planner.validate_plan(plan) is True
    
    def test_validate_plan_empty(self):
        """Test validation of empty plan."""
        plan = TaskPlan(
            id="empty_plan",
            description="Empty plan",
            tasks=[]
        )
        
        assert self.planner.validate_plan(plan) is False
    
    def test_validate_plan_duplicate_task_ids(self):
        """Test validation fails with duplicate task IDs."""
        task1 = Task(id="duplicate", description="Task 1")
        task2 = Task(id="duplicate", description="Task 2")
        
        plan = TaskPlan(
            id="test_plan",
            description="Test plan",
            tasks=[task1, task2]
        )
        
        assert self.planner.validate_plan(plan) is False
    
    def test_validate_plan_missing_dependency(self):
        """Test validation fails with missing dependencies."""
        task1 = Task(
            id="task1", 
            description="Task 1",
            dependencies=["nonexistent_task"]
        )
        
        plan = TaskPlan(
            id="test_plan",
            description="Test plan",
            tasks=[task1]
        )
        
        assert self.planner.validate_plan(plan) is False
    
    def test_update_task_status(self):
        """Test updating task status."""
        plan = self.planner.create_plan(
            "Test task", self.mock_analysis
        )
        
        if plan.tasks:
            task_id = plan.tasks[0].id
            result = self.planner.update_task_status(
                plan.id, task_id, TaskStatus.IN_PROGRESS
            )
            
            assert result is True
            assert plan.tasks[0].status == TaskStatus.IN_PROGRESS
    
    def test_update_task_status_nonexistent(self):
        """Test updating status of nonexistent task."""
        plan = self.planner.create_plan(
            "Test task", self.mock_analysis
        )
        
        result = self.planner.update_task_status(
            plan.id, "nonexistent", TaskStatus.COMPLETED
        )
        
        assert result is False
    
    def test_estimate_duration_basic(self):
        """Test basic duration estimation."""
        task = Task(id="test", description="Simple task")
        context = CodebaseContext(analysis=self.mock_analysis)
        
        duration = self.planner.estimate_duration(task, context)
        
        assert duration > 0
        assert isinstance(duration, int)
    
    def test_estimate_duration_implementation_task(self):
        """Test duration estimation for implementation tasks."""
        task = Task(id="test", description="Implement complex feature")
        context = CodebaseContext(analysis=self.mock_analysis)
        
        duration = self.planner.estimate_duration(task, context)
        
        # Implementation tasks should take longer
        simple_task = Task(id="simple", description="Update documentation")
        simple_duration = self.planner.estimate_duration(simple_task, context)
        
        assert duration > simple_duration
    
    def test_estimate_duration_with_subtasks(self):
        """Test duration estimation considers subtasks."""
        task = Task(id="test", description="Task with subtasks")
        task.subtasks = [
            Subtask(id="sub1", description="Subtask 1"),
            Subtask(id="sub2", description="Subtask 2"),
            Subtask(id="sub3", description="Subtask 3")
        ]
        context = CodebaseContext(analysis=self.mock_analysis)
        
        duration = self.planner.estimate_duration(task, context)
        
        # Should account for subtasks
        assert duration >= 45  # 3 subtasks * 15 min each
    
    def test_resolve_dependencies_simple(self):
        """Test dependency resolution with simple dependencies."""
        task1 = Task(id="task1", description="Task 1", dependencies=[])
        task2 = Task(id="task2", description="Task 2", dependencies=["task1"])
        task3 = Task(id="task3", description="Task 3", dependencies=["task2"])
        
        tasks = [task3, task1, task2]  # Intentionally out of order
        ordered_tasks = self.planner.resolve_dependencies(tasks)
        
        # Should be ordered by dependencies
        task_ids = [task.id for task in ordered_tasks]
        assert task_ids.index("task1") < task_ids.index("task2")
        assert task_ids.index("task2") < task_ids.index("task3")
    
    def test_resolve_dependencies_complex(self):
        """Test dependency resolution with complex dependencies."""
        task1 = Task(id="task1", description="Task 1", dependencies=[])
        task2 = Task(id="task2", description="Task 2", dependencies=[])
        task3 = Task(id="task3", description="Task 3", dependencies=["task1", "task2"])
        task4 = Task(id="task4", description="Task 4", dependencies=["task3"])
        
        tasks = [task4, task3, task1, task2]  # Out of order
        ordered_tasks = self.planner.resolve_dependencies(tasks)
        
        task_ids = [task.id for task in ordered_tasks]
        
        # task1 and task2 should come before task3
        assert task_ids.index("task1") < task_ids.index("task3")
        assert task_ids.index("task2") < task_ids.index("task3")
        # task3 should come before task4
        assert task_ids.index("task3") < task_ids.index("task4")
    
    def test_resolve_dependencies_circular(self):
        """Test dependency resolution with circular dependencies."""
        task1 = Task(id="task1", description="Task 1", dependencies=["task2"])
        task2 = Task(id="task2", description="Task 2", dependencies=["task1"])
        
        tasks = [task1, task2]
        ordered_tasks = self.planner.resolve_dependencies(tasks)
        
        # Should return original order when circular dependencies exist
        assert len(ordered_tasks) == 2
    
    def test_get_plan(self):
        """Test retrieving a plan by ID."""
        plan = self.planner.create_plan(
            "Test task", self.mock_analysis
        )
        
        retrieved_plan = self.planner.get_plan(plan.id)
        
        assert retrieved_plan is not None
        assert retrieved_plan.id == plan.id
        assert retrieved_plan.description == plan.description
    
    def test_get_plan_nonexistent(self):
        """Test retrieving nonexistent plan."""
        plan = self.planner.get_plan("nonexistent_id")
        
        assert plan is None
    
    def test_task_classification(self):
        """Test task type classification."""
        test_cases = [
            ("Implement user authentication", "implementation"),
            ("Create new API endpoint", "implementation"),
            ("Refactor database layer", "refactoring"),
            ("Fix memory leak bug", "debugging"),
            ("Test payment processing", "testing"),
            ("Update user interface", "generic")
        ]
        
        context = CodebaseContext(analysis=self.mock_analysis)
        
        for description, expected_type in test_cases:
            task_type = self.planner._classify_task_type(description, context)
            assert task_type == expected_type, f"Failed for: {description}"
    
    def test_complexity_estimation(self):
        """Test task complexity estimation."""
        context = CodebaseContext(analysis=self.mock_analysis)
        
        high_complexity_tasks = [
            "Implement new microservices architecture",
            "Migrate to new framework",
            "Add security authentication system"
        ]
        
        medium_complexity_tasks = [
            "Refactor user management module",
            "Optimize database queries",
            "Enhance error handling"
        ]
        
        low_complexity_tasks = [
            "Fix typo in documentation",
            "Update configuration file",
            "Modify CSS styling"
        ]
        
        for task_desc in high_complexity_tasks:
            complexity = self.planner._estimate_task_complexity(task_desc, context)
            assert complexity in ['high', 'medium']  # Allow some flexibility
        
        for task_desc in low_complexity_tasks:
            complexity = self.planner._estimate_task_complexity(task_desc, context)
            assert complexity in ['low', 'medium']  # Allow some flexibility


class TestTaskPlanModel:
    """Test cases for TaskPlan model functionality."""
    
    def test_task_plan_creation(self):
        """Test TaskPlan creation and initialization."""
        plan = TaskPlan(
            id="test_plan",
            description="Test plan"
        )
        
        assert plan.id == "test_plan"
        assert plan.description == "Test plan"
        assert plan.status == PlanStatus.DRAFT
        assert plan.approval_status == ApprovalStatus.PENDING
        assert plan.created_at is not None
        assert len(plan.tasks) == 0
    
    def test_add_task(self):
        """Test adding tasks to a plan."""
        plan = TaskPlan(id="test_plan", description="Test plan")
        task = Task(id="task1", description="Test task")
        
        plan.add_task(task)
        
        assert len(plan.tasks) == 1
        assert plan.tasks[0] == task
    
    def test_get_task(self):
        """Test retrieving task by ID."""
        plan = TaskPlan(id="test_plan", description="Test plan")
        task = Task(id="task1", description="Test task")
        plan.add_task(task)
        
        retrieved_task = plan.get_task("task1")
        
        assert retrieved_task is not None
        assert retrieved_task.id == "task1"
    
    def test_get_next_task(self):
        """Test getting next task to execute."""
        plan = TaskPlan(id="test_plan", description="Test plan")
        
        task1 = Task(id="task1", description="Task 1", status=TaskStatus.NOT_STARTED)
        task2 = Task(id="task2", description="Task 2", 
                    status=TaskStatus.NOT_STARTED, dependencies=["task1"])
        
        plan.add_task(task1)
        plan.add_task(task2)
        
        next_task = plan.get_next_task()
        
        assert next_task is not None
        assert next_task.id == "task1"  # Should be task1 since it has no dependencies
    
    def test_is_completed(self):
        """Test plan completion status."""
        plan = TaskPlan(id="test_plan", description="Test plan")
        
        task1 = Task(id="task1", description="Task 1", status=TaskStatus.COMPLETED)
        task2 = Task(id="task2", description="Task 2", status=TaskStatus.COMPLETED)
        
        plan.add_task(task1)
        plan.add_task(task2)
        
        assert plan.is_completed is True
        
        # Add incomplete task
        task3 = Task(id="task3", description="Task 3", status=TaskStatus.NOT_STARTED)
        plan.add_task(task3)
        
        assert plan.is_completed is False
    
    def test_progress_percentage(self):
        """Test progress percentage calculation."""
        plan = TaskPlan(id="test_plan", description="Test plan")
        
        # Empty plan
        assert plan.progress_percentage == 0.0
        
        # Add tasks
        task1 = Task(id="task1", description="Task 1", status=TaskStatus.COMPLETED)
        task2 = Task(id="task2", description="Task 2", status=TaskStatus.NOT_STARTED)
        
        plan.add_task(task1)
        plan.add_task(task2)
        
        assert plan.progress_percentage == 50.0  # 1 out of 2 completed


class TestTaskModel:
    """Test cases for Task model functionality."""
    
    def test_task_creation(self):
        """Test Task creation and initialization."""
        task = Task(id="test_task", description="Test task")
        
        assert task.id == "test_task"
        assert task.description == "Test task"
        assert task.status == TaskStatus.NOT_STARTED
        assert len(task.subtasks) == 0
        assert len(task.dependencies) == 0
    
    def test_add_subtask(self):
        """Test adding subtasks to a task."""
        task = Task(id="test_task", description="Test task")
        subtask = Subtask(id="subtask1", description="Test subtask")
        
        task.add_subtask(subtask)
        
        assert len(task.subtasks) == 1
        assert task.subtasks[0] == subtask
    
    def test_get_subtask(self):
        """Test retrieving subtask by ID."""
        task = Task(id="test_task", description="Test task")
        subtask = Subtask(id="subtask1", description="Test subtask")
        task.add_subtask(subtask)
        
        retrieved_subtask = task.get_subtask("subtask1")
        
        assert retrieved_subtask is not None
        assert retrieved_subtask.id == "subtask1"
    
    def test_is_completed_no_subtasks(self):
        """Test completion status for task without subtasks."""
        task = Task(id="test_task", description="Test task", 
                   status=TaskStatus.COMPLETED)
        
        assert task.is_completed is True
        
        task.status = TaskStatus.IN_PROGRESS
        assert task.is_completed is False
    
    def test_is_completed_with_subtasks(self):
        """Test completion status for task with subtasks."""
        task = Task(id="test_task", description="Test task")
        
        subtask1 = Subtask(id="sub1", description="Subtask 1", 
                          status=TaskStatus.COMPLETED)
        subtask2 = Subtask(id="sub2", description="Subtask 2", 
                          status=TaskStatus.COMPLETED)
        
        task.add_subtask(subtask1)
        task.add_subtask(subtask2)
        
        assert task.is_completed is True
        
        # Add incomplete subtask
        subtask3 = Subtask(id="sub3", description="Subtask 3", 
                          status=TaskStatus.NOT_STARTED)
        task.add_subtask(subtask3)
        
        assert task.is_completed is False


if __name__ == "__main__":
    pytest.main([__file__])