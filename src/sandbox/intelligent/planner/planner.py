"""
Concrete implementation of task planning functionality.
"""

import uuid
import re
from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict, deque
from ..analyzer.models import CodebaseAnalysis, Pattern
from ..types import TaskStatus, ErrorInfo, ApprovalStatus
from .interfaces import TaskPlannerInterface
from .models import TaskPlan, Task, Subtask, CodebaseContext
from .status_manager import DynamicStatusManager
from .approval_workflow import ApprovalWorkflow


class TaskPlanner(TaskPlannerInterface):
    """
    Concrete implementation of intelligent task planning with dynamic
    task breakdown and dependency resolution.
    """
    
    def __init__(self):
        self._plans: Dict[str, TaskPlan] = {}  # Store plans by ID
        self._task_templates = self._initialize_task_templates()
        self._language_templates = self._initialize_language_templates()
        self._status_manager = DynamicStatusManager()
        self._approval_workflow = ApprovalWorkflow()
    
    def create_plan(self, task_description: str, 
                   codebase_analysis: CodebaseAnalysis) -> TaskPlan:
        """Create a detailed task plan from a high-level description."""
        plan_id = str(uuid.uuid4())
        
        # Create enhanced codebase context
        context = self._build_codebase_context(codebase_analysis)
        
        # Analyze task type and complexity
        task_type = self._classify_task_type(task_description, context)
        complexity = self._estimate_task_complexity(task_description, context)
        
        # Generate main tasks using intelligent breakdown
        main_tasks = self._decompose_high_level_task(
            task_description, context, task_type, complexity
        )
        
        # Resolve dependencies between tasks
        ordered_tasks = self.resolve_dependencies(main_tasks)
        
        # Create the plan
        plan = TaskPlan(
            id=plan_id,
            description=task_description,
            tasks=ordered_tasks,
            codebase_context=context,
            metadata={
                'task_type': task_type,
                'complexity': complexity,
                'estimated_total_duration': sum(
                    self.estimate_duration(task, context) for task in ordered_tasks
                )
            }
        )
        
        self._plans[plan_id] = plan
        
        # Register plan with status manager for dynamic tracking
        self._status_manager.register_plan(plan)
        
        return plan
    
    def break_down_task(self, task: Task, context: CodebaseContext) -> List[Subtask]:
        """Break down a task into smaller, actionable subtasks."""
        subtasks = []
        
        # Analyze task description for breakdown patterns
        task_keywords = self._extract_task_keywords(task.description)
        
        # Apply context-aware breakdown strategies
        if 'implement' in task_keywords or 'create' in task_keywords:
            subtasks.extend(self._create_implementation_subtasks(task, context))
        elif 'refactor' in task_keywords or 'modify' in task_keywords:
            subtasks.extend(self._create_refactoring_subtasks(task, context))
        elif 'test' in task_keywords:
            subtasks.extend(self._create_testing_subtasks(task, context))
        elif 'fix' in task_keywords or 'debug' in task_keywords:
            subtasks.extend(self._create_debugging_subtasks(task, context))
        else:
            # Generic breakdown
            subtasks.extend(self._create_generic_subtasks(task, context))
        
        # Add common subtasks if applicable
        if self._needs_testing(task, context):
            subtasks.append(self._create_testing_subtask(task))
        
        if self._needs_documentation(task, context):
            subtasks.append(self._create_documentation_subtask(task))
        
        # Set dependencies between subtasks
        self._set_subtask_dependencies(subtasks)
        
        return subtasks
    
    def validate_plan(self, plan: TaskPlan) -> bool:
        """Validate that a task plan is well-formed and executable."""
        if not plan.tasks:
            return False
        
        # Check for circular dependencies
        if self._has_circular_dependencies(plan.tasks):
            return False
        
        # Validate task IDs are unique
        task_ids = set()
        for task in plan.tasks:
            if task.id in task_ids:
                return False
            task_ids.add(task.id)
            
            # Check subtask IDs are unique within task
            subtask_ids = set()
            for subtask in task.subtasks:
                if subtask.id in subtask_ids:
                    return False
                subtask_ids.add(subtask.id)
        
        # Validate dependencies exist
        all_task_ids = {task.id for task in plan.tasks}
        for task in plan.tasks:
            for dep_id in task.dependencies:
                if dep_id not in all_task_ids:
                    return False
        
        # Validate subtask dependencies
        for task in plan.tasks:
            subtask_ids = {subtask.id for subtask in task.subtasks}
            for subtask in task.subtasks:
                for dep_id in subtask.dependencies:
                    if dep_id not in subtask_ids:
                        return False
        
        return True
    
    def update_task_status(self, plan_id: str, task_id: str, 
                          status: TaskStatus) -> bool:
        """Update the status of a specific task."""
        if plan_id not in self._plans:
            return False
        
        # Use status manager for dynamic tracking
        return self._status_manager.update_task_status(task_id, status)
    
    def estimate_duration(self, task: Task, context: CodebaseContext) -> int:
        """Estimate the duration for completing a task."""
        base_duration = 30  # 30 minutes base
        
        # Adjust based on task complexity indicators
        task_lower = task.description.lower()
        
        # Task type multipliers
        if any(keyword in task_lower for keyword in ['implement', 'create', 'build']):
            base_duration *= 2.0
        elif any(keyword in task_lower for keyword in ['refactor', 'restructure']):
            base_duration *= 1.8
        elif any(keyword in task_lower for keyword in ['fix', 'debug', 'resolve']):
            base_duration *= 1.5
        elif any(keyword in task_lower for keyword in ['test', 'validate']):
            base_duration *= 1.2
        
        # Codebase complexity adjustments
        if context.analysis.metrics.lines_of_code > 50000:
            base_duration *= 2.0
        elif context.analysis.metrics.lines_of_code > 10000:
            base_duration *= 1.5
        
        # Framework complexity
        complex_frameworks = ['react', 'angular', 'vue', 'django', 'spring', 'rails']
        if any(fw in context.analysis.structure.frameworks for fw in complex_frameworks):
            base_duration *= 1.3
        
        # Language complexity
        complex_languages = ['c++', 'rust', 'haskell', 'scala']
        if any(lang in context.analysis.structure.languages for lang in complex_languages):
            base_duration *= 1.4
        
        # Subtask count adjustment
        if task.subtasks:
            subtask_duration = sum(15 for _ in task.subtasks)  # 15 min per subtask
            base_duration = max(base_duration, subtask_duration)
        
        return int(base_duration)
    
    def resolve_dependencies(self, tasks: List[Task]) -> List[Task]:
        """Resolve and order tasks based on their dependencies using topological sort."""
        if not tasks:
            return tasks
        
        # Build dependency graph
        task_map = {task.id: task for task in tasks}
        in_degree = defaultdict(int)
        graph = defaultdict(list)
        
        # Initialize in-degree count
        for task in tasks:
            in_degree[task.id] = 0
        
        # Build graph and calculate in-degrees
        for task in tasks:
            for dep_id in task.dependencies:
                if dep_id in task_map:
                    graph[dep_id].append(task.id)
                    in_degree[task.id] += 1
        
        # Topological sort using Kahn's algorithm
        queue = deque([task_id for task_id in in_degree if in_degree[task_id] == 0])
        result = []
        
        while queue:
            current_id = queue.popleft()
            result.append(task_map[current_id])
            
            # Reduce in-degree for dependent tasks
            for dependent_id in graph[current_id]:
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    queue.append(dependent_id)
        
        # Check for circular dependencies
        if len(result) != len(tasks):
            # Return original order if circular dependencies exist
            return tasks
        
        return result
    
    def get_plan(self, plan_id: str) -> TaskPlan:
        """Get a plan by ID."""
        return self._plans.get(plan_id)
    
    def get_status_manager(self) -> DynamicStatusManager:
        """Get the dynamic status manager for advanced status operations."""
        return self._status_manager
    
    def update_task_status_advanced(self, task_id: str, status: TaskStatus,
                                   message: Optional[str] = None,
                                   progress_percentage: Optional[float] = None,
                                   error_info: Optional[ErrorInfo] = None) -> bool:
        """Update task status with advanced tracking features."""
        return self._status_manager.update_task_status(
            task_id, status, message, progress_percentage, error_info
        )
    
    def get_plan_progress(self, plan_id: str) -> Dict[str, any]:
        """Get comprehensive progress information for a plan."""
        return self._status_manager.get_plan_progress(plan_id)
    
    def modify_task(self, task_id: str, **kwargs) -> bool:
        """Modify task properties with re-planning support."""
        return self._status_manager.modify_task(task_id, **kwargs)
    
    def replan_task(self, task_id: str, new_subtasks: List[Dict[str, any]]) -> bool:
        """Re-plan a task with new subtasks."""
        return self._status_manager.replan_from_task(task_id, new_subtasks)
    
    def get_approval_workflow(self) -> ApprovalWorkflow:
        """Get the approval workflow manager."""
        return self._approval_workflow
    
    def submit_plan_for_approval(self, plan_id: str, 
                                additional_context: Optional[Dict[str, any]] = None) -> Optional[str]:
        """Submit a plan for user approval."""
        plan = self.get_plan(plan_id)
        if not plan:
            return None
        
        return self._approval_workflow.submit_for_approval(plan, additional_context)
    
    def approve_plan(self, request_id: str, feedback: Optional[str] = None) -> bool:
        """Approve a plan."""
        from .approval_workflow import ApprovalResponse
        response = ApprovalResponse(
            request_id=request_id,
            status=ApprovalStatus.APPROVED,
            feedback=feedback
        )
        return self._approval_workflow.respond_to_approval(request_id, response)
    
    def reject_plan(self, request_id: str, feedback: Optional[str] = None) -> bool:
        """Reject a plan."""
        from .approval_workflow import ApprovalResponse
        response = ApprovalResponse(
            request_id=request_id,
            status=ApprovalStatus.REJECTED,
            feedback=feedback
        )
        return self._approval_workflow.respond_to_approval(request_id, response)
    
    def request_plan_revision(self, request_id: str, feedback: Optional[str] = None,
                             modifications: Optional[List[str]] = None) -> bool:
        """Request revisions to a plan."""
        from .approval_workflow import ApprovalResponse
        response = ApprovalResponse(
            request_id=request_id,
            status=ApprovalStatus.NEEDS_REVISION,
            feedback=feedback,
            modifications_requested=modifications or []
        )
        return self._approval_workflow.respond_to_approval(request_id, response)
    
    def _initialize_task_templates(self) -> Dict[str, Dict]:
        """Initialize task breakdown templates for different task types."""
        return {
            'implementation': {
                'patterns': ['implement', 'create', 'build', 'develop', 'add'],
                'subtasks': [
                    'Analyze requirements and design approach',
                    'Set up necessary infrastructure/dependencies',
                    'Implement core functionality',
                    'Add error handling and validation',
                    'Write unit tests',
                    'Integration testing',
                    'Documentation updates'
                ]
            },
            'refactoring': {
                'patterns': ['refactor', 'restructure', 'reorganize', 'optimize'],
                'subtasks': [
                    'Analyze current implementation',
                    'Identify refactoring opportunities',
                    'Create refactoring plan',
                    'Implement changes incrementally',
                    'Update tests',
                    'Verify functionality unchanged'
                ]
            },
            'debugging': {
                'patterns': ['fix', 'debug', 'resolve', 'troubleshoot'],
                'subtasks': [
                    'Reproduce the issue',
                    'Analyze error logs and stack traces',
                    'Identify root cause',
                    'Implement fix',
                    'Test fix thoroughly',
                    'Add regression tests'
                ]
            },
            'testing': {
                'patterns': ['test', 'validate', 'verify'],
                'subtasks': [
                    'Analyze testing requirements',
                    'Set up test environment',
                    'Write test cases',
                    'Implement test automation',
                    'Execute tests and analyze results',
                    'Update test documentation'
                ]
            }
        }
    
    def _initialize_language_templates(self) -> Dict[str, Dict]:
        """Initialize language-specific task templates."""
        return {
            'python': {
                'setup_tasks': [
                    'Create virtual environment (python -m venv venv)',
                    'Activate virtual environment (source venv/bin/activate)',
                    'Install dependencies (pip install -r requirements.txt)',
                    'Install development dependencies (pip install -e .[dev])'
                ],
                'test_tasks': [
                    'Run unit tests (python -m pytest)',
                    'Run tests with coverage (pytest --cov=.)',
                    'Run linting (flake8 . or pylint .)',
                    'Run type checking (mypy .)'
                ],
                'build_tasks': [
                    'Build package (python setup.py build)',
                    'Create distribution (python setup.py sdist bdist_wheel)',
                    'Install package locally (pip install -e .)'
                ]
            },
            'javascript': {
                'setup_tasks': [
                    'Install Node.js dependencies (npm install)',
                    'Install development dependencies (npm install --dev)',
                    'Verify package.json configuration',
                    'Set up environment variables'
                ],
                'test_tasks': [
                    'Run unit tests (npm test)',
                    'Run tests with coverage (npm run test:coverage)',
                    'Run linting (npm run lint)',
                    'Run type checking (npm run type-check)'
                ],
                'build_tasks': [
                    'Build application (npm run build)',
                    'Bundle assets (npm run bundle)',
                    'Optimize for production (npm run build:prod)'
                ]
            },
            'java': {
                'setup_tasks': [
                    'Verify Java version compatibility',
                    'Download Maven/Gradle dependencies (mvn dependency:resolve)',
                    'Compile source code (mvn compile)',
                    'Set up IDE configuration'
                ],
                'test_tasks': [
                    'Run unit tests (mvn test)',
                    'Run integration tests (mvn verify)',
                    'Generate test reports (mvn surefire-report:report)',
                    'Check code coverage (mvn jacoco:report)'
                ],
                'build_tasks': [
                    'Compile and package (mvn package)',
                    'Create JAR file (mvn jar:jar)',
                    'Install to local repository (mvn install)'
                ]
            },
            'rust': {
                'setup_tasks': [
                    'Check Rust toolchain (rustc --version)',
                    'Update dependencies (cargo update)',
                    'Build dependencies (cargo build)',
                    'Check for compilation errors (cargo check)'
                ],
                'test_tasks': [
                    'Run unit tests (cargo test)',
                    'Run integration tests (cargo test --test integration)',
                    'Run benchmarks (cargo bench)',
                    'Check code formatting (cargo fmt --check)'
                ],
                'build_tasks': [
                    'Build in debug mode (cargo build)',
                    'Build in release mode (cargo build --release)',
                    'Create documentation (cargo doc)'
                ]
            },
            'go': {
                'setup_tasks': [
                    'Initialize Go module (go mod init)',
                    'Download dependencies (go mod download)',
                    'Verify dependencies (go mod verify)',
                    'Tidy up dependencies (go mod tidy)'
                ],
                'test_tasks': [
                    'Run unit tests (go test ./...)',
                    'Run tests with coverage (go test -cover ./...)',
                    'Run race condition tests (go test -race ./...)',
                    'Run benchmarks (go test -bench=.)'
                ],
                'build_tasks': [
                    'Build application (go build)',
                    'Build for multiple platforms (go build -o app)',
                    'Create binary distribution'
                ]
            }
        }
    
    def _build_codebase_context(self, analysis: CodebaseAnalysis) -> CodebaseContext:
        """Build enhanced codebase context from analysis."""
        # Identify key files based on patterns and structure
        key_files = []
        key_files.extend(analysis.structure.entry_points)
        key_files.extend(analysis.structure.config_files[:5])  # Top 5 config files
        
        # Extract important patterns
        important_patterns = [
            pattern.name for pattern in analysis.patterns 
            if pattern.confidence > 0.7
        ]
        
        # Generate constraints based on codebase
        constraints = []
        if 'typescript' in analysis.structure.languages:
            constraints.append('Maintain TypeScript type safety')
        if 'python' in analysis.structure.languages:
            constraints.append('Follow PEP 8 style guidelines')
        if analysis.metrics.test_coverage < 0.8:
            constraints.append('Improve test coverage')
        
        # Generate recommendations
        recommendations = []
        if analysis.metrics.cyclomatic_complexity > 10:
            recommendations.append('Consider breaking down complex functions')
        if analysis.dependencies.conflicts:
            recommendations.append('Resolve dependency conflicts')
        
        return CodebaseContext(
            analysis=analysis,
            key_files=key_files,
            important_patterns=important_patterns,
            constraints=constraints,
            recommendations=recommendations
        )
    
    def _classify_task_type(self, description: str, context: CodebaseContext) -> str:
        """Classify the type of task based on description and context."""
        desc_lower = description.lower()
        
        for task_type, template in self._task_templates.items():
            if any(pattern in desc_lower for pattern in template['patterns']):
                return task_type
        
        return 'generic'
    
    def _estimate_task_complexity(self, description: str, context: CodebaseContext) -> str:
        """Estimate task complexity (low, medium, high)."""
        complexity_indicators = {
            'high': ['architecture', 'framework', 'migration', 'integration', 'security'],
            'medium': ['refactor', 'optimize', 'enhance', 'extend'],
            'low': ['fix', 'update', 'modify', 'adjust']
        }
        
        desc_lower = description.lower()
        
        for complexity, indicators in complexity_indicators.items():
            if any(indicator in desc_lower for indicator in indicators):
                return complexity
        
        # Consider codebase size
        if context.analysis.metrics.lines_of_code > 50000:
            return 'high'
        elif context.analysis.metrics.lines_of_code > 10000:
            return 'medium'
        
        return 'low'
    
    def _decompose_high_level_task(self, description: str, context: CodebaseContext, 
                                  task_type: str, complexity: str) -> List[Task]:
        """Decompose a high-level task into main tasks with language-specific considerations."""
        tasks = []
        
        # Check if this is a language-specific task that can benefit from specialized templates
        language_specific_tasks = self._generate_language_specific_tasks(description, context)
        
        if language_specific_tasks:
            # Use language-specific tasks only, don't add generic ones
            tasks.extend(language_specific_tasks)
        elif task_type in self._task_templates:
            # Use generic templates but enhance with language context
            template = self._task_templates[task_type]
            for i, subtask_desc in enumerate(template['subtasks']):
                task_id = str(uuid.uuid4())
                
                # Enhance description with language context
                enhanced_desc = self._enhance_task_with_language_context(
                    subtask_desc, description, context
                )
                
                task = Task(
                    id=task_id,
                    description=enhanced_desc,
                    status=TaskStatus.NOT_STARTED,
                    metadata={
                        'template_type': task_type, 
                        'order': i,
                        'languages': context.analysis.structure.languages,
                        'frameworks': context.analysis.structure.frameworks
                    }
                )
                
                # Add dependencies for sequential tasks
                if i > 0:
                    task.dependencies.append(tasks[i-1].id)
                
                tasks.append(task)
        else:
            # Generic task breakdown
            main_task = Task(
                id=str(uuid.uuid4()),
                description=description,
                status=TaskStatus.NOT_STARTED
            )
            tasks.append(main_task)
        
        return tasks
    
    def _generate_language_specific_tasks(self, description: str, context: CodebaseContext) -> List[Task]:
        """Generate language-specific tasks based on the codebase analysis."""
        tasks = []
        desc_lower = description.lower()
        languages = context.analysis.structure.languages
        frameworks = context.analysis.structure.frameworks
        
        # Check for full workflow tasks first (most comprehensive)
        if any(keyword in desc_lower for keyword in ['workflow', 'pipeline', 'complete', 'full']):
            tasks.extend(self._create_full_workflow_tasks(languages, frameworks, description))
        # Check for specific task types only if not a full workflow
        elif any(keyword in desc_lower for keyword in ['install', 'setup', 'dependencies', 'environment']):
            tasks.extend(self._create_setup_tasks(languages, frameworks, description))
        elif any(keyword in desc_lower for keyword in ['test', 'testing', 'validate', 'verify']):
            tasks.extend(self._create_testing_tasks(languages, frameworks, description))
        elif any(keyword in desc_lower for keyword in ['build', 'compile', 'package', 'bundle']):
            tasks.extend(self._create_build_tasks(languages, frameworks, description))
        
        return tasks
    
    def _create_setup_tasks(self, languages: List[str], frameworks: List[str], description: str) -> List[Task]:
        """Create language-specific setup tasks."""
        tasks = []
        
        for language in languages:
            if language in self._language_templates:
                template = self._language_templates[language]
                for setup_task in template.get('setup_tasks', []):
                    task_id = str(uuid.uuid4())
                    task = Task(
                        id=task_id,
                        description=f"[{language.upper()}] {setup_task}",
                        status=TaskStatus.NOT_STARTED,
                        metadata={
                            'language': language,
                            'task_type': 'setup',
                            'original_description': description
                        }
                    )
                    tasks.append(task)
        
        # Add framework-specific setup tasks
        framework_setup = self._get_framework_setup_tasks(frameworks)
        for setup_task in framework_setup:
            task_id = str(uuid.uuid4())
            task = Task(
                id=task_id,
                description=setup_task,
                status=TaskStatus.NOT_STARTED,
                metadata={
                    'task_type': 'framework_setup',
                    'frameworks': frameworks,
                    'original_description': description
                }
            )
            tasks.append(task)
        
        return tasks
    
    def _create_testing_tasks(self, languages: List[str], frameworks: List[str], description: str) -> List[Task]:
        """Create language-specific testing tasks."""
        tasks = []
        
        for language in languages:
            if language in self._language_templates:
                template = self._language_templates[language]
                for test_task in template.get('test_tasks', []):
                    task_id = str(uuid.uuid4())
                    task = Task(
                        id=task_id,
                        description=f"[{language.upper()}] {test_task}",
                        status=TaskStatus.NOT_STARTED,
                        metadata={
                            'language': language,
                            'task_type': 'testing',
                            'original_description': description
                        }
                    )
                    tasks.append(task)
        
        return tasks
    
    def _create_build_tasks(self, languages: List[str], frameworks: List[str], description: str) -> List[Task]:
        """Create language-specific build tasks."""
        tasks = []
        
        for language in languages:
            if language in self._language_templates:
                template = self._language_templates[language]
                for build_task in template.get('build_tasks', []):
                    task_id = str(uuid.uuid4())
                    task = Task(
                        id=task_id,
                        description=f"[{language.upper()}] {build_task}",
                        status=TaskStatus.NOT_STARTED,
                        metadata={
                            'language': language,
                            'task_type': 'build',
                            'original_description': description
                        }
                    )
                    tasks.append(task)
        
        return tasks
    
    def _create_full_workflow_tasks(self, languages: List[str], frameworks: List[str], description: str) -> List[Task]:
        """Create a complete workflow with setup, test, and build tasks for all languages."""
        tasks = []
        
        # Create setup tasks for all languages
        setup_tasks = self._create_setup_tasks(languages, frameworks, description)
        tasks.extend(setup_tasks)
        
        # Create testing tasks for all languages
        test_tasks = self._create_testing_tasks(languages, frameworks, description)
        # Make test tasks depend on setup tasks
        if setup_tasks and test_tasks:
            for test_task in test_tasks:
                test_task.dependencies.extend([task.id for task in setup_tasks])
        tasks.extend(test_tasks)
        
        # Create build tasks for all languages
        build_tasks = self._create_build_tasks(languages, frameworks, description)
        # Make build tasks depend on test tasks
        if test_tasks and build_tasks:
            for build_task in build_tasks:
                build_task.dependencies.extend([task.id for task in test_tasks])
        elif setup_tasks and build_tasks:
            # If no test tasks, depend on setup tasks
            for build_task in build_tasks:
                build_task.dependencies.extend([task.id for task in setup_tasks])
        tasks.extend(build_tasks)
        
        return tasks
    
    def _get_framework_setup_tasks(self, frameworks: List[str]) -> List[str]:
        """Get framework-specific setup tasks."""
        setup_tasks = []
        
        framework_setups = {
            'react': ['Verify React dependencies', 'Set up React development environment'],
            'vue': ['Verify Vue.js dependencies', 'Set up Vue development environment'],
            'angular': ['Verify Angular CLI', 'Set up Angular development environment'],
            'django': ['Set up Django settings', 'Run Django migrations (python manage.py migrate)'],
            'flask': ['Set up Flask configuration', 'Initialize Flask application'],
            'express': ['Verify Express.js setup', 'Configure Express middleware'],
            'spring': ['Verify Spring Boot configuration', 'Set up Spring profiles'],
            'docker': ['Build Docker images (docker build -t app .)', 'Set up Docker compose environment']
        }
        
        for framework in frameworks:
            if framework in framework_setups:
                setup_tasks.extend(framework_setups[framework])
        
        return setup_tasks
    
    def _enhance_task_with_language_context(self, subtask_desc: str, original_desc: str, context: CodebaseContext) -> str:
        """Enhance a generic task description with language-specific context."""
        languages = context.analysis.structure.languages
        frameworks = context.analysis.structure.frameworks
        
        # Add language context to generic descriptions
        if 'dependencies' in subtask_desc.lower() and languages:
            lang_examples = []
            for lang in languages[:2]:  # Show first 2 languages
                if lang == 'python':
                    lang_examples.append('pip install -r requirements.txt')
                elif lang == 'javascript':
                    lang_examples.append('npm install')
                elif lang == 'java':
                    lang_examples.append('mvn dependency:resolve')
                elif lang == 'rust':
                    lang_examples.append('cargo build')
            
            if lang_examples:
                return f"{subtask_desc} ({', '.join(lang_examples)})"
        
        if 'test' in subtask_desc.lower() and languages:
            test_examples = []
            for lang in languages[:2]:
                if lang == 'python':
                    test_examples.append('pytest')
                elif lang == 'javascript':
                    test_examples.append('npm test')
                elif lang == 'java':
                    test_examples.append('mvn test')
                elif lang == 'rust':
                    test_examples.append('cargo test')
            
            if test_examples:
                return f"{subtask_desc} ({', '.join(test_examples)})"
        
        return f"{subtask_desc} for: {original_desc}"
    
    def _extract_task_keywords(self, description: str) -> Set[str]:
        """Extract relevant keywords from task description."""
        keywords = set()
        desc_lower = description.lower()
        
        # Common task action words
        action_words = [
            'implement', 'create', 'build', 'develop', 'add',
            'refactor', 'modify', 'update', 'change', 'improve',
            'fix', 'debug', 'resolve', 'troubleshoot',
            'test', 'validate', 'verify', 'check'
        ]
        
        for word in action_words:
            if word in desc_lower:
                keywords.add(word)
        
        return keywords
    
    def _create_implementation_subtasks(self, task: Task, context: CodebaseContext) -> List[Subtask]:
        """Create subtasks for implementation tasks."""
        subtasks = []
        base_id = task.id
        
        subtasks.append(Subtask(
            id=f"{base_id}_analysis",
            description="Analyze requirements and design approach",
            dependencies=[]
        ))
        
        subtasks.append(Subtask(
            id=f"{base_id}_setup",
            description="Set up necessary infrastructure and dependencies",
            dependencies=[f"{base_id}_analysis"]
        ))
        
        subtasks.append(Subtask(
            id=f"{base_id}_core",
            description="Implement core functionality",
            dependencies=[f"{base_id}_setup"]
        ))
        
        subtasks.append(Subtask(
            id=f"{base_id}_validation",
            description="Add error handling and validation",
            dependencies=[f"{base_id}_core"]
        ))
        
        return subtasks
    
    def _create_refactoring_subtasks(self, task: Task, context: CodebaseContext) -> List[Subtask]:
        """Create subtasks for refactoring tasks."""
        subtasks = []
        base_id = task.id
        
        subtasks.append(Subtask(
            id=f"{base_id}_analyze",
            description="Analyze current implementation",
            dependencies=[]
        ))
        
        subtasks.append(Subtask(
            id=f"{base_id}_plan",
            description="Create refactoring plan",
            dependencies=[f"{base_id}_analyze"]
        ))
        
        subtasks.append(Subtask(
            id=f"{base_id}_refactor",
            description="Implement refactoring changes",
            dependencies=[f"{base_id}_plan"]
        ))
        
        return subtasks
    
    def _create_testing_subtasks(self, task: Task, context: CodebaseContext) -> List[Subtask]:
        """Create subtasks for testing tasks."""
        subtasks = []
        base_id = task.id
        
        subtasks.append(Subtask(
            id=f"{base_id}_test_plan",
            description="Analyze testing requirements and create test plan",
            dependencies=[]
        ))
        
        subtasks.append(Subtask(
            id=f"{base_id}_test_impl",
            description="Implement test cases",
            dependencies=[f"{base_id}_test_plan"]
        ))
        
        return subtasks
    
    def _create_debugging_subtasks(self, task: Task, context: CodebaseContext) -> List[Subtask]:
        """Create subtasks for debugging tasks."""
        subtasks = []
        base_id = task.id
        
        subtasks.append(Subtask(
            id=f"{base_id}_reproduce",
            description="Reproduce the issue",
            dependencies=[]
        ))
        
        subtasks.append(Subtask(
            id=f"{base_id}_diagnose",
            description="Analyze and identify root cause",
            dependencies=[f"{base_id}_reproduce"]
        ))
        
        subtasks.append(Subtask(
            id=f"{base_id}_fix",
            description="Implement fix",
            dependencies=[f"{base_id}_diagnose"]
        ))
        
        return subtasks
    
    def _create_generic_subtasks(self, task: Task, context: CodebaseContext) -> List[Subtask]:
        """Create generic subtasks for unclassified tasks."""
        subtasks = []
        base_id = task.id
        
        subtasks.append(Subtask(
            id=f"{base_id}_prepare",
            description="Prepare and analyze task requirements",
            dependencies=[]
        ))
        
        subtasks.append(Subtask(
            id=f"{base_id}_execute",
            description="Execute main task implementation",
            dependencies=[f"{base_id}_prepare"]
        ))
        
        return subtasks
    
    def _needs_testing(self, task: Task, context: CodebaseContext) -> bool:
        """Determine if task needs testing subtasks."""
        task_lower = task.description.lower()
        return ('implement' in task_lower or 'create' in task_lower) and 'test' not in task_lower
    
    def _needs_documentation(self, task: Task, context: CodebaseContext) -> bool:
        """Determine if task needs documentation subtasks."""
        task_lower = task.description.lower()
        return 'implement' in task_lower or 'create' in task_lower
    
    def _create_testing_subtask(self, task: Task) -> Subtask:
        """Create a testing subtask."""
        return Subtask(
            id=f"{task.id}_testing",
            description=f"Write tests for: {task.description}",
            dependencies=[task.id]
        )
    
    def _create_documentation_subtask(self, task: Task) -> Subtask:
        """Create a documentation subtask."""
        return Subtask(
            id=f"{task.id}_docs",
            description=f"Update documentation for: {task.description}",
            dependencies=[task.id]
        )
    
    def _set_subtask_dependencies(self, subtasks: List[Subtask]) -> None:
        """Set appropriate dependencies between subtasks."""
        # Dependencies are already set in the creation methods
        pass
    
    def _has_circular_dependencies(self, tasks: List[Task]) -> bool:
        """Check if tasks have circular dependencies."""
        task_ids = {task.id for task in tasks}
        visited = set()
        rec_stack = set()
        
        def has_cycle(task_id: str) -> bool:
            if task_id in rec_stack:
                return True
            if task_id in visited:
                return False
            
            visited.add(task_id)
            rec_stack.add(task_id)
            
            # Find task and check its dependencies
            for task in tasks:
                if task.id == task_id:
                    for dep_id in task.dependencies:
                        if dep_id in task_ids and has_cycle(dep_id):
                            return True
                    break
            
            rec_stack.remove(task_id)
            return False
        
        for task in tasks:
            if task.id not in visited:
                if has_cycle(task.id):
                    return True
        
        return False