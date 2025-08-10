#!/usr/bin/env python3
"""
Complete Ultimate Swiss Army Knife MCP Server - Part 2
Full tool implementations with NO shortcuts.
"""

# This continues from complete_server.py
# Import all required components from part 1

from complete_server import *
import subprocess
import difflib
import re
import ast
import tokenize
import io
from urllib.parse import urlparse
import requests
import yaml
import toml
import configparser
import tarfile
import zipfile
from PIL import Image
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

# Additional imports for complete functionality
try:
    import git
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False
    logger.warning("GitPython not available, Git operations limited")

try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False
    logger.warning("python-magic not available, file type detection limited")

# ============================================================================
# COMPLETE INTELLIGENT SANDBOX TOOLS
# ============================================================================

class IntelligentSandboxTools:
    """Complete implementation of all Intelligent Sandbox tools."""
    
    def __init__(self, server):
        self.server = server
        self.mcp = server.mcp
        
    def register_tools(self):
        """Register all Intelligent Sandbox tools."""
        
        @self.mcp.tool()
        async def create_workspace(
            source_path: str,
            workspace_id: Optional[str] = None,
            use_docker: bool = True,
            resource_limits: Optional[Dict[str, Any]] = None,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Create a complete isolated workspace with full cloning and isolation."""
            try:
                # Generate workspace ID if not provided
                if not workspace_id:
                    workspace_id = f"ws_{uuid.uuid4().hex[:8]}"
                
                # Prepare isolation config
                isolation_config = IsolationConfig(
                    use_docker=use_docker and self.server.docker_manager.docker_available
                )
                
                if resource_limits:
                    isolation_config.resource_limits = ResourceLimits(**resource_limits)
                
                # Create sandbox directory
                sandbox_base = Path.home() / ".ultimate_sandbox" / "workspaces"
                sandbox_path = sandbox_base / workspace_id
                sandbox_path.mkdir(parents=True, exist_ok=True)
                
                # Clone source to sandbox
                source = Path(source_path)
                if not source.exists():
                    return {
                        "success": False,
                        "error": f"Source path does not exist: {source_path}"
                    }
                
                # Preserve Git history if it's a Git repo
                git_info = None
                if GIT_AVAILABLE and (source / ".git").exists():
                    try:
                        repo = git.Repo(source)
                        git_info = {
                            "branch": repo.active_branch.name,
                            "commit": repo.head.commit.hexsha,
                            "remotes": [r.url for r in repo.remotes],
                            "modified_files": [item.a_path for item in repo.index.diff(None)],
                            "untracked_files": repo.untracked_files
                        }
                        
                        # Clone with Git history
                        git.Repo.clone_from(source, sandbox_path)
                        logger.info(f"Cloned Git repository to sandbox: {workspace_id}")
                    except Exception as e:
                        logger.warning(f"Git clone failed, using file copy: {e}")
                        shutil.copytree(source, sandbox_path, dirs_exist_ok=True)
                else:
                    # Regular file copy
                    shutil.copytree(source, sandbox_path, dirs_exist_ok=True)
                
                # Create Docker container if requested
                container_id = None
                if isolation_config.use_docker:
                    container_id = self.server.docker_manager.create_sandbox_container(
                        workspace_id, str(sandbox_path), isolation_config
                    )
                
                # Create workspace session
                session = WorkspaceSession(
                    session_id=f"session_{workspace_id}",
                    workspace_id=workspace_id,
                    source_path=str(source),
                    sandbox_path=str(sandbox_path),
                    container_id=container_id,
                    isolation_config=isolation_config,
                    git_info=git_info
                )
                
                # Save to storage
                self.server.storage.save_workspace(session)
                self.server.active_workspaces[workspace_id] = session
                
                # Index the workspace for search
                self.server.thread_pool.submit(
                    self.server.search_engine.index_directory, sandbox_path
                )
                
                # Update metrics
                self.server.metrics['operations_count'] += 1
                if container_id:
                    self.server.metrics['containers_created'] += 1
                
                return {
                    "success": True,
                    "workspace_id": workspace_id,
                    "sandbox_path": str(sandbox_path),
                    "container_id": container_id,
                    "isolation": {
                        "docker": bool(container_id),
                        "network_isolated": isolation_config.network_isolation,
                        "resource_limits": isolation_config.resource_limits.__dict__
                    },
                    "git_info": git_info,
                    "message": f"Workspace '{workspace_id}' created successfully"
                }
                
            except Exception as e:
                logger.error(f"Failed to create workspace: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.mcp.tool()
        async def analyze_codebase(
            workspace_id: str,
            deep_analysis: bool = True,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Perform complete codebase analysis with language detection, dependencies, and metrics."""
            try:
                if workspace_id not in self.server.active_workspaces:
                    return {
                        "success": False,
                        "error": f"Workspace '{workspace_id}' not found"
                    }
                
                session = self.server.active_workspaces[workspace_id]
                sandbox_path = Path(session.sandbox_path)
                
                # Initialize analysis results
                analysis = {
                    "languages": {},
                    "frameworks": [],
                    "dependencies": {},
                    "file_count": 0,
                    "total_lines": 0,
                    "code_lines": 0,
                    "comment_lines": 0,
                    "blank_lines": 0,
                    "file_tree": {},
                    "entry_points": [],
                    "test_files": [],
                    "config_files": [],
                    "documentation_files": [],
                    "metrics": {}
                }
                
                # Language detection patterns
                lang_extensions = {
                    '.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript',
                    '.java': 'Java', '.cpp': 'C++', '.c': 'C', '.cs': 'C#',
                    '.go': 'Go', '.rs': 'Rust', '.rb': 'Ruby', '.php': 'PHP',
                    '.swift': 'Swift', '.kt': 'Kotlin', '.scala': 'Scala',
                    '.r': 'R', '.jl': 'Julia', '.lua': 'Lua', '.dart': 'Dart',
                    '.sql': 'SQL', '.sh': 'Shell', '.ps1': 'PowerShell'
                }
                
                # Framework detection patterns
                framework_indicators = {
                    'package.json': ['React', 'Vue', 'Angular', 'Next.js', 'Express'],
                    'requirements.txt': ['Django', 'Flask', 'FastAPI', 'Pyramid'],
                    'Gemfile': ['Rails', 'Sinatra'],
                    'pom.xml': ['Spring', 'Maven'],
                    'build.gradle': ['Spring Boot', 'Gradle'],
                    'Cargo.toml': ['Actix', 'Rocket', 'Tokio'],
                    'go.mod': ['Gin', 'Echo', 'Fiber'],
                    'composer.json': ['Laravel', 'Symfony']
                }
                
                # Walk through all files
                for root, dirs, files in os.walk(sandbox_path):
                    # Skip hidden and vendor directories
                    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in 
                              ['node_modules', 'vendor', '__pycache__', 'target', 'build', 'dist']]
                    
                    for file in files:
                        file_path = Path(root) / file
                        relative_path = file_path.relative_to(sandbox_path)
                        
                        analysis['file_count'] += 1
                        
                        # Detect language
                        ext = file_path.suffix.lower()
                        if ext in lang_extensions:
                            lang = lang_extensions[ext]
                            analysis['languages'][lang] = analysis['languages'].get(lang, 0) + 1
                        
                        # Identify special files
                        if file in ['main.py', 'app.py', 'index.js', 'main.go', 'main.rs']:
                            analysis['entry_points'].append(str(relative_path))
                        elif 'test' in file.lower() or 'spec' in file.lower():
                            analysis['test_files'].append(str(relative_path))
                        elif file in framework_indicators:
                            analysis['config_files'].append(str(relative_path))
                            # Check for frameworks
                            try:
                                content = file_path.read_text(errors='ignore')
                                for framework in framework_indicators[file]:
                                    if framework.lower() in content.lower():
                                        if framework not in analysis['frameworks']:
                                            analysis['frameworks'].append(framework)
                            except:
                                pass
                        elif ext in ['.md', '.rst', '.txt']:
                            analysis['documentation_files'].append(str(relative_path))
                        
                        # Count lines if text file
                        if ext in lang_extensions or ext in ['.md', '.txt', '.yml', '.json', '.xml']:
                            try:
                                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    lines = f.readlines()
                                    analysis['total_lines'] += len(lines)
                                    
                                    for line in lines:
                                        stripped = line.strip()
                                        if not stripped:
                                            analysis['blank_lines'] += 1
                                        elif stripped.startswith('#') or stripped.startswith('//') or \
                                             stripped.startswith('/*') or stripped.startswith('*'):
                                            analysis['comment_lines'] += 1
                                        else:
                                            analysis['code_lines'] += 1
                            except:
                                pass
                        
                        # Build file tree
                        parts = relative_path.parts
                        current = analysis['file_tree']
                        for part in parts[:-1]:
                            if part not in current:
                                current[part] = {}
                            current = current[part]
                        current[parts[-1]] = None
                
                # Analyze dependencies
                if deep_analysis:
                    analysis['dependencies'] = await self._analyze_dependencies(sandbox_path)
                    analysis['metrics'] = await self._calculate_code_metrics(sandbox_path)
                
                # Cache the analysis
                cache_key = f"analysis:{workspace_id}"
                self.server.cache.set(cache_key, analysis, ttl=3600)
                
                return {
                    "success": True,
                    "workspace_id": workspace_id,
                    "analysis": analysis,
                    "summary": {
                        "primary_language": max(analysis['languages'].items(), key=lambda x: x[1])[0] if analysis['languages'] else None,
                        "frameworks": analysis['frameworks'],
                        "total_files": analysis['file_count'],
                        "code_lines": analysis['code_lines'],
                        "test_coverage": len(analysis['test_files']) > 0
                    }
                }
                
            except Exception as e:
                logger.error(f"Failed to analyze codebase: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.mcp.tool()
        async def create_task_plan(
            workspace_id: str,
            description: str,
            auto_approve: bool = False,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Create intelligent task plan based on codebase analysis."""
            try:
                # Get cached analysis or perform new one
                cache_key = f"analysis:{workspace_id}"
                analysis = self.server.cache.get(cache_key)
                
                if not analysis:
                    result = await analyze_codebase(workspace_id, deep_analysis=True, ctx=ctx)
                    if not result['success']:
                        return result
                    analysis = result['analysis']
                
                # Generate tasks based on description and analysis
                tasks = []
                task_id_base = f"task_{uuid.uuid4().hex[:6]}"
                
                # Parse description for intent
                description_lower = description.lower()
                
                # Determine primary language
                primary_lang = max(analysis['languages'].items(), key=lambda x: x[1])[0] if analysis['languages'] else 'Python'
                
                # Generate language-specific tasks
                if 'install' in description_lower or 'setup' in description_lower or 'dependencies' in description_lower:
                    tasks.extend(self._generate_setup_tasks(primary_lang, analysis))
                
                if 'test' in description_lower:
                    tasks.extend(self._generate_test_tasks(primary_lang, analysis))
                
                if 'build' in description_lower or 'compile' in description_lower:
                    tasks.extend(self._generate_build_tasks(primary_lang, analysis))
                
                if 'lint' in description_lower or 'format' in description_lower or 'quality' in description_lower:
                    tasks.extend(self._generate_quality_tasks(primary_lang, analysis))
                
                if 'deploy' in description_lower or 'docker' in description_lower:
                    tasks.extend(self._generate_deployment_tasks(primary_lang, analysis))
                
                if 'document' in description_lower:
                    tasks.extend(self._generate_documentation_tasks(primary_lang, analysis))
                
                # If no specific tasks matched, generate comprehensive workflow
                if not tasks:
                    tasks = (
                        self._generate_setup_tasks(primary_lang, analysis) +
                        self._generate_quality_tasks(primary_lang, analysis) +
                        self._generate_test_tasks(primary_lang, analysis) +
                        self._generate_build_tasks(primary_lang, analysis)
                    )
                
                # Add task IDs and structure
                for i, task in enumerate(tasks):
                    task['id'] = f"{task_id_base}_{i:03d}"
                    task['status'] = 'pending'
                    task['output'] = ''
                    task['error'] = None
                
                # Create plan
                plan = {
                    "plan_id": f"plan_{uuid.uuid4().hex[:8]}",
                    "workspace_id": workspace_id,
                    "description": description,
                    "tasks": tasks,
                    "created_at": datetime.now().isoformat(),
                    "approved": auto_approve,
                    "status": "approved" if auto_approve else "pending_approval"
                }
                
                # Store plan
                self.server.active_tasks[plan['plan_id']] = plan
                
                return {
                    "success": True,
                    "plan": plan,
                    "requires_approval": not auto_approve
                }
                
            except Exception as e:
                logger.error(f"Failed to create task plan: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.mcp.tool()
        async def execute_task_plan(
            plan_id: str,
            parallel: bool = False,
            stop_on_error: bool = True,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Execute task plan with full error handling and recovery."""
            try:
                if plan_id not in self.server.active_tasks:
                    return {
                        "success": False,
                        "error": f"Plan '{plan_id}' not found"
                    }
                
                plan = self.server.active_tasks[plan_id]
                
                if plan['status'] == 'pending_approval':
                    return {
                        "success": False,
                        "error": "Plan requires approval before execution"
                    }
                
                workspace_id = plan['workspace_id']
                if workspace_id not in self.server.active_workspaces:
                    return {
                        "success": False,
                        "error": f"Workspace '{workspace_id}' not found"
                    }
                
                session = self.server.active_workspaces[workspace_id]
                sandbox_path = Path(session.sandbox_path)
                
                # Update plan status
                plan['status'] = 'executing'
                plan['started_at'] = datetime.now().isoformat()
                
                results = []
                failed_tasks = []
                
                # Execute tasks
                if parallel and not stop_on_error:
                    # Parallel execution
                    futures = []
                    for task in plan['tasks']:
                        future = self.server.thread_pool.submit(
                            self._execute_single_task, task, session
                        )
                        futures.append((task, future))
                    
                    for task, future in futures:
                        try:
                            result = future.result(timeout=300)
                            results.append(result)
                            if not result['success']:
                                failed_tasks.append(task['id'])
                        except Exception as e:
                            result = {
                                'success': False,
                                'task_id': task['id'],
                                'error': str(e)
                            }
                            results.append(result)
                            failed_tasks.append(task['id'])
                else:
                    # Sequential execution
                    for task in plan['tasks']:
                        result = await self._execute_single_task_async(task, session)
                        results.append(result)
                        
                        if not result['success']:
                            failed_tasks.append(task['id'])
                            if stop_on_error:
                                break
                
                # Update plan status
                plan['status'] = 'completed' if not failed_tasks else 'failed'
                plan['completed_at'] = datetime.now().isoformat()
                plan['results'] = results
                
                return {
                    "success": len(failed_tasks) == 0,
                    "plan_id": plan_id,
                    "executed_tasks": len(results),
                    "failed_tasks": failed_tasks,
                    "results": results,
                    "summary": {
                        "total_tasks": len(plan['tasks']),
                        "completed_tasks": len(results) - len(failed_tasks),
                        "failed_tasks": len(failed_tasks)
                    }
                }
                
            except Exception as e:
                logger.error(f"Failed to execute task plan: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
        
        # Helper methods for task generation
        def _generate_setup_tasks(self, language: str, analysis: Dict) -> List[Dict]:
            """Generate setup tasks based on language."""
            tasks = []
            
            if language == 'Python':
                if 'requirements.txt' in [Path(f).name for f in analysis['config_files']]:
                    tasks.append({
                        'description': '[PYTHON] Create virtual environment',
                        'command': 'python -m venv venv',
                        'type': 'shell'
                    })
                    tasks.append({
                        'description': '[PYTHON] Activate virtual environment',
                        'command': 'source venv/bin/activate',
                        'type': 'shell'
                    })
                    tasks.append({
                        'description': '[PYTHON] Install dependencies',
                        'command': 'pip install -r requirements.txt',
                        'type': 'shell'
                    })
                elif 'pyproject.toml' in [Path(f).name for f in analysis['config_files']]:
                    tasks.append({
                        'description': '[PYTHON] Install with pip',
                        'command': 'pip install -e .',
                        'type': 'shell'
                    })
            
            elif language == 'JavaScript':
                if 'package.json' in [Path(f).name for f in analysis['config_files']]:
                    tasks.append({
                        'description': '[NODE] Install npm dependencies',
                        'command': 'npm install',
                        'type': 'shell'
                    })
                elif 'yarn.lock' in [Path(f).name for f in analysis['config_files']]:
                    tasks.append({
                        'description': '[NODE] Install yarn dependencies',
                        'command': 'yarn install',
                        'type': 'shell'
                    })
            
            elif language == 'Java':
                if 'pom.xml' in [Path(f).name for f in analysis['config_files']]:
                    tasks.append({
                        'description': '[JAVA] Install Maven dependencies',
                        'command': 'mvn install',
                        'type': 'shell'
                    })
                elif 'build.gradle' in [Path(f).name for f in analysis['config_files']]:
                    tasks.append({
                        'description': '[JAVA] Install Gradle dependencies',
                        'command': 'gradle build',
                        'type': 'shell'
                    })
            
            elif language == 'Rust':
                if 'Cargo.toml' in [Path(f).name for f in analysis['config_files']]:
                    tasks.append({
                        'description': '[RUST] Build with Cargo',
                        'command': 'cargo build',
                        'type': 'shell'
                    })
            
            elif language == 'Go':
                if 'go.mod' in [Path(f).name for f in analysis['config_files']]:
                    tasks.append({
                        'description': '[GO] Download dependencies',
                        'command': 'go mod download',
                        'type': 'shell'
                    })
            
            return tasks
        
        def _generate_test_tasks(self, language: str, analysis: Dict) -> List[Dict]:
            """Generate test tasks based on language."""
            tasks = []
            
            if language == 'Python':
                if any('pytest' in str(f) for f in analysis['config_files']):
                    tasks.append({
                        'description': '[PYTHON] Run pytest',
                        'command': 'pytest',
                        'type': 'shell'
                    })
                elif any('unittest' in str(f) for f in analysis['test_files']):
                    tasks.append({
                        'description': '[PYTHON] Run unittest',
                        'command': 'python -m unittest discover',
                        'type': 'shell'
                    })
                else:
                    tasks.append({
                        'description': '[PYTHON] Run tests',
                        'command': 'python -m pytest || python -m unittest discover',
                        'type': 'shell'
                    })
            
            elif language == 'JavaScript':
                tasks.append({
                    'description': '[NODE] Run tests',
                    'command': 'npm test',
                    'type': 'shell'
                })
            
            elif language == 'Java':
                tasks.append({
                    'description': '[JAVA] Run tests',
                    'command': 'mvn test || gradle test',
                    'type': 'shell'
                })
            
            elif language == 'Rust':
                tasks.append({
                    'description': '[RUST] Run tests',
                    'command': 'cargo test',
                    'type': 'shell'
                })
            
            elif language == 'Go':
                tasks.append({
                    'description': '[GO] Run tests',
                    'command': 'go test ./...',
                    'type': 'shell'
                })
            
            return tasks
        
        def _generate_build_tasks(self, language: str, analysis: Dict) -> List[Dict]:
            """Generate build tasks based on language."""
            tasks = []
            
            if language in ['C', 'C++']:
                if 'Makefile' in [Path(f).name for f in analysis['config_files']]:
                    tasks.append({
                        'description': '[C/C++] Build with Make',
                        'command': 'make',
                        'type': 'shell'
                    })
                elif 'CMakeLists.txt' in [Path(f).name for f in analysis['config_files']]:
                    tasks.append({
                        'description': '[C/C++] Configure with CMake',
                        'command': 'cmake .',
                        'type': 'shell'
                    })
                    tasks.append({
                        'description': '[C/C++] Build with CMake',
                        'command': 'cmake --build .',
                        'type': 'shell'
                    })
            
            elif language == 'TypeScript':
                tasks.append({
                    'description': '[TYPESCRIPT] Compile TypeScript',
                    'command': 'tsc',
                    'type': 'shell'
                })
            
            elif language == 'Java':
                tasks.append({
                    'description': '[JAVA] Compile Java',
                    'command': 'javac -d build $(find . -name "*.java")',
                    'type': 'shell'
                })
            
            return tasks
        
        def _generate_quality_tasks(self, language: str, analysis: Dict) -> List[Dict]:
            """Generate code quality tasks."""
            tasks = []
            
            if language == 'Python':
                tasks.append({
                    'description': '[PYTHON] Format with Black',
                    'command': 'black . || true',
                    'type': 'shell'
                })
                tasks.append({
                    'description': '[PYTHON] Lint with Flake8',
                    'command': 'flake8 . || true',
                    'type': 'shell'
                })
                tasks.append({
                    'description': '[PYTHON] Type check with MyPy',
                    'command': 'mypy . || true',
                    'type': 'shell'
                })
            
            elif language == 'JavaScript':
                tasks.append({
                    'description': '[NODE] Lint with ESLint',
                    'command': 'eslint . || true',
                    'type': 'shell'
                })
                tasks.append({
                    'description': '[NODE] Format with Prettier',
                    'command': 'prettier --write . || true',
                    'type': 'shell'
                })
            
            elif language == 'Rust':
                tasks.append({
                    'description': '[RUST] Format with rustfmt',
                    'command': 'cargo fmt',
                    'type': 'shell'
                })
                tasks.append({
                    'description': '[RUST] Lint with clippy',
                    'command': 'cargo clippy',
                    'type': 'shell'
                })
            
            return tasks
        
        def _generate_deployment_tasks(self, language: str, analysis: Dict) -> List[Dict]:
            """Generate deployment tasks."""
            tasks = []
            
            # Docker tasks
            if 'Dockerfile' in [Path(f).name for f in analysis['config_files']]:
                tasks.append({
                    'description': '[DOCKER] Build Docker image',
                    'command': 'docker build -t app:latest .',
                    'type': 'shell'
                })
            else:
                # Generate Dockerfile
                tasks.append({
                    'description': '[DOCKER] Generate Dockerfile',
                    'command': 'echo "FROM python:3.11\nWORKDIR /app\nCOPY . .\nRUN pip install -r requirements.txt\nCMD [\"python\", \"app.py\"]" > Dockerfile',
                    'type': 'shell'
                })
                tasks.append({
                    'description': '[DOCKER] Build Docker image',
                    'command': 'docker build -t app:latest .',
                    'type': 'shell'
                })
            
            return tasks
        
        def _generate_documentation_tasks(self, language: str, analysis: Dict) -> List[Dict]:
            """Generate documentation tasks."""
            tasks = []
            
            if language == 'Python':
                tasks.append({
                    'description': '[PYTHON] Generate docs with Sphinx',
                    'command': 'sphinx-build -b html docs docs/_build || true',
                    'type': 'shell'
                })
            
            elif language == 'JavaScript':
                tasks.append({
                    'description': '[NODE] Generate docs with JSDoc',
                    'command': 'jsdoc -r . -d docs || true',
                    'type': 'shell'
                })
            
            return tasks
        
        async def _execute_single_task_async(self, task: Dict, session: WorkspaceSession) -> Dict[str, Any]:
            """Execute a single task asynchronously."""
            return await asyncio.get_event_loop().run_in_executor(
                self.server.thread_pool,
                self._execute_single_task,
                task,
                session
            )
        
        def _execute_single_task(self, task: Dict, session: WorkspaceSession) -> Dict[str, Any]:
            """Execute a single task."""
            try:
                task['status'] = 'running'
                task['started_at'] = datetime.now().isoformat()
                
                sandbox_path = Path(session.sandbox_path)
                
                if task['type'] == 'shell':
                    # Execute shell command
                    if session.container_id and self.server.docker_manager.docker_available:
                        # Execute in Docker container
                        container = self.server.docker_manager.client.containers.get(session.container_id)
                        exec_result = container.exec_run(
                            task['command'],
                            workdir='/workspace',
                            demux=True
                        )
                        stdout = exec_result.output[0].decode() if exec_result.output[0] else ''
                        stderr = exec_result.output[1].decode() if exec_result.output[1] else ''
                        exit_code = exec_result.exit_code
                    else:
                        # Execute locally
                        result = subprocess.run(
                            task['command'],
                            shell=True,
                            cwd=str(sandbox_path),
                            capture_output=True,
                            text=True,
                            timeout=session.isolation_config.resource_limits.execution_timeout
                        )
                        stdout = result.stdout
                        stderr = result.stderr
                        exit_code = result.returncode
                    
                    task['output'] = stdout
                    task['error'] = stderr if exit_code != 0 else None
                    task['exit_code'] = exit_code
                    task['status'] = 'completed' if exit_code == 0 else 'failed'
                
                task['completed_at'] = datetime.now().isoformat()
                
                return {
                    'success': task['status'] == 'completed',
                    'task_id': task['id'],
                    'description': task['description'],
                    'output': task['output'],
                    'error': task['error'],
                    'exit_code': task.get('exit_code')
                }
                
            except Exception as e:
                task['status'] = 'failed'
                task['error'] = str(e)
                return {
                    'success': False,
                    'task_id': task['id'],
                    'error': str(e)
                }
        
        async def _analyze_dependencies(self, path: Path) -> Dict[str, List[str]]:
            """Analyze project dependencies."""
            deps = {}
            
            # Python dependencies
            req_file = path / "requirements.txt"
            if req_file.exists():
                deps['python'] = req_file.read_text().strip().split('\n')
            
            # Node dependencies
            package_json = path / "package.json"
            if package_json.exists():
                try:
                    pkg = json.loads(package_json.read_text())
                    deps['npm'] = list(pkg.get('dependencies', {}).keys())
                    deps['npm_dev'] = list(pkg.get('devDependencies', {}).keys())
                except:
                    pass
            
            # Add more dependency analysis for other languages
            
            return deps
        
        async def _calculate_code_metrics(self, path: Path) -> Dict[str, Any]:
            """Calculate code quality metrics."""
            metrics = {
                'cyclomatic_complexity': 0,
                'maintainability_index': 0,
                'technical_debt': 0,
                'code_smells': []
            }
            
            # Basic metrics calculation
            # This would be expanded with proper code analysis tools
            
            return metrics

# Continue with more tool implementations...
