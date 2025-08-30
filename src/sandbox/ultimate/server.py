#!/usr/bin/env python3
"""
Ultimate Swiss Army Knife MCP Server

This unified MCP server combines:
1. Intelligent Sandbox functionality (workspace isolation, task planning, execution)
2. CodeIndexer functionality (advanced search, file manipulation, indexing)
3. Original Sandbox tools (Manim, Python execution, web apps)

Creating the ultimate AI development environment.
"""

import sys
import os
import json
import logging
import uuid
import tempfile
import shutil
import io
import traceback
import subprocess
import threading
import time
import socket
import base64
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

# Add the src directory to Python path
project_root = Path(__file__).parent.parent.parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

# Import FastMCP
from fastmcp import FastMCP

# Import Intelligent Sandbox components
from sandbox.intelligent.workspace.cloner import WorkspaceCloner
from sandbox.intelligent.workspace.lifecycle import WorkspaceLifecycleManager
from sandbox.intelligent.analyzer.analyzer import CodebaseAnalyzer
from sandbox.intelligent.planner.planner import TaskPlanner
from sandbox.intelligent.executor.engine import ExecutionEngine
from sandbox.intelligent.logger.logger import ActionLogger
from sandbox.intelligent.cache.cache_manager import CacheManager
from sandbox.intelligent.config import get_config_manager

# Import Original Sandbox components (if available)
try:
    # Use WorkspaceManager as a replacement for SandboxManager
    from sandbox.core.workspace_manager import WorkspaceManager as SandboxManager
    from sandbox.core.artifact_manager import ArtifactManager
    from sandbox.migration.legacy_functionality import ManimExecutor, WebAppManager
    from pathlib import Path

    class WebAppBuilder:
        """Simple wrapper for WebAppManager to provide build() method."""
        def __init__(self):
            self.manager = WebAppManager(Path.cwd())

        def build(self, app_code: str, port: int):
            """Build and launch web app."""
            # Create a temporary artifacts directory for the web app
            import tempfile
            artifacts_dir = Path(tempfile.mkdtemp())
            return self.manager.launch_web_app(app_code, 'flask', artifacts_dir)

    ORIGINAL_SANDBOX_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Some original sandbox components not available: {e}")
    ORIGINAL_SANDBOX_AVAILABLE = False

# Import execution support components
from sandbox.core.resource_manager import get_resource_manager
from sandbox.core.security import get_security_manager, SecurityLevel
from sandbox.core.connection_manager import get_connection_manager, initialize_connection_manager

# Set up logging to file to avoid MCP protocol interference
log_file = Path(tempfile.gettempdir()) / "sandbox_mcp_server.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stderr) if os.getenv('SANDBOX_MCP_DEBUG') else logging.NullHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.info("Ultimate MCP Server starting up...")


# Global state for execution context
class ExecutionContext:
    def __init__(self):
        # Compute project_root dynamically from current file location
        current_file = Path(__file__).resolve()
        if 'src/sandbox' in str(current_file):
            # Installed package: go from src/sandbox/ultimate/server.py to project root
            self.project_root = current_file.parent.parent.parent.parent
        else:
            # Development: assume file is in project root
            self.project_root = current_file.parent
        self.venv_path = self.project_root / ".venv"
        self.artifacts_dir = None
        self.web_servers = {}  # Track running web servers
        self.execution_globals = {}  # Persistent globals across executions
        self._setup_environment()
    
    def _setup_environment(self):
        """Setup sys.path and virtual environment with robust path detection."""
        # Compute absolute paths
        project_root_str = str(self.project_root)
        project_parent_str = str(self.project_root.parent)  # Add parent to find 'sandbox' package
        
        # Detect venv site-packages dynamically
        venv_site_packages = None
        if self.venv_path.exists():
            # Try multiple Python versions
            for py_version in ['python3.11', 'python3.12', 'python3.10', 'python3.9']:
                candidate = self.venv_path / "lib" / py_version / "site-packages"
                if candidate.exists():
                    venv_site_packages = candidate
                    break
        
        # De-duplicate sys.path using OrderedDict to preserve order
        from collections import OrderedDict
        current_paths = OrderedDict.fromkeys(sys.path)
        
        # Paths to add (parent first for package imports, then project root)
        paths_to_add = [project_parent_str, project_root_str]
        if venv_site_packages:
            paths_to_add.append(str(venv_site_packages))
        
        # Add new paths at the beginning, preserving order and avoiding duplicates
        new_sys_path = []
        for path in paths_to_add:
            if path not in current_paths:
                new_sys_path.append(path)
                current_paths[path] = None  # Mark as added
        
        # Rebuild sys.path with new paths first
        sys.path[:] = new_sys_path + list(current_paths.keys())
        
        # Set up virtual environment activation
        if self.venv_path.exists():
            venv_python = self.venv_path / "bin" / "python"
            venv_bin = self.venv_path / "bin"
            
            if venv_python.exists():
                # Set environment variables for venv activation
                os.environ['VIRTUAL_ENV'] = str(self.venv_path)
                
                # Prepend venv/bin to PATH if not already present
                current_path = os.environ.get('PATH', '')
                venv_bin_str = str(venv_bin)
                if venv_bin_str not in current_path.split(os.pathsep):
                    os.environ['PATH'] = f"{venv_bin_str}{os.pathsep}{current_path}"

                # Ensure system paths are included in PATH
                system_paths = ['/bin', '/usr/bin', '/usr/local/bin']
                current_path_list = os.environ.get('PATH', '').split(os.pathsep)
                for sys_path in system_paths:
                    if sys_path not in current_path_list:
                        current_path_list.append(sys_path)
                os.environ['PATH'] = os.pathsep.join(current_path_list)
                
                # Update sys.executable to point to venv python
                sys.executable = str(venv_python)
        
        logger.info(f"Project root: {self.project_root}")
        logger.info(f"Virtual env: {self.venv_path if self.venv_path.exists() else 'Not found'}")
        logger.info(f"sys.executable: {sys.executable}")
        logger.info(f"sys.path (first 5): {sys.path[:5]}")
        logger.info(f"VIRTUAL_ENV: {os.environ.get('VIRTUAL_ENV', 'Not set')}")
    
    def create_artifacts_dir(self) -> str:
        """Create a temporary directory for execution artifacts."""
        execution_id = str(uuid.uuid4())[:8]
        self.artifacts_dir = Path(tempfile.gettempdir()) / f"sandbox_artifacts_{execution_id}"
        self.artifacts_dir.mkdir(exist_ok=True)
        return str(self.artifacts_dir)
    
    def cleanup_artifacts(self):
        """Clean up artifacts directory."""
        if self.artifacts_dir and self.artifacts_dir.exists():
            shutil.rmtree(self.artifacts_dir, ignore_errors=True)


def monkey_patch_matplotlib():
    """Monkey patch matplotlib to save plots to artifacts directory."""
    try:
        import matplotlib
        matplotlib.use('Agg')  # Use non-interactive backend
        import matplotlib.pyplot as plt
        
        # Get the current ExecutionContext
        ctx = globals().get('ctx')
        if not ctx:
            return False
        
        original_show = plt.show
        
        def patched_show(*args, **kwargs):
            if ctx.artifacts_dir:
                figure_path = ctx.artifacts_dir / f"plot_{uuid.uuid4().hex[:8]}.png"
                plt.savefig(figure_path, dpi=150, bbox_inches='tight')
                logger.info(f"Plot saved to: {figure_path}")
            return original_show(*args, **kwargs)
        
        plt.show = patched_show
        return True
    except ImportError:
        return False


def monkey_patch_pil():
    """Monkey patch PIL to save images to artifacts directory."""
    try:
        from PIL import Image
        
        # Get the current ExecutionContext
        ctx = globals().get('ctx')
        if not ctx:
            return False
        
        original_show = Image.Image.show
        original_save = Image.Image.save
        
        def patched_show(self, title=None, command=None):
            if ctx.artifacts_dir:
                image_path = ctx.artifacts_dir / f"image_{uuid.uuid4().hex[:8]}.png"
                self.save(image_path)
                logger.info(f"Image saved to: {image_path}")
            return original_show(self)
        
        def patched_save(self, fp, format=None, **params):
            result = original_save(self, fp, format, **params)
            # If saving to artifacts dir, log it
            if ctx.artifacts_dir and str(fp).startswith(str(ctx.artifacts_dir)):
                logger.info(f"Image saved to artifacts: {fp}")
            return result
        
        Image.Image.show = patched_show
        Image.Image.save = patched_save
        return True
    except ImportError:
        return False


def find_free_port(start_port=8000):
    """Find a free port starting from start_port."""
    for port in range(start_port, start_port + 100):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return port
        except OSError:
            continue
    raise RuntimeError("No free ports available")


def launch_web_app(code: str, app_type: str) -> Optional[str]:
    """Launch a web application and return the URL."""
    try:
        ctx = globals().get('ctx')
        resource_manager = globals().get('resource_manager')
        if not ctx or not resource_manager:
            return None

        if ctx.project_root is None:
            return None

        resource_manager.check_resource_limits()
        port = find_free_port()
        resource_manager.process_manager.cleanup_finished()

        if app_type == 'flask':
            # Modify Flask code to run on specific port
            if 'app.run()' in code:
                modified_code = code.replace('app.run()', f'app.run(host="127.0.0.1", port={port}, debug=False)')
            elif 'app.run(' in code:
                # Already has parameters, might need to override port
                modified_code = code
            else:
                # Add app.run() call
                modified_code = code + f'\nif __name__ == "__main__":\n    app.run(host="127.0.0.1", port={port}, debug=False)'

            # Launch Flask app in subprocess
            process = subprocess.Popen(
                [sys.executable, '-c', modified_code],
                cwd=str(ctx.project_root)
            )
            resource_manager.process_manager.add_process(process)

            if process.poll() is None:  # Still running
                url = f"http://127.0.0.1:{port}"
                ctx.web_servers[url] = process.pid
                return url
            else:
                return None

        return None

    except Exception as e:
        logger.error(f"Failed to launch web app: {e}")
        return None


def collect_artifacts() -> List[Dict[str, Any]]:
    """Collect all artifacts from the artifacts directory."""
    artifacts = []
    ctx = globals().get('ctx')
    if not ctx or ctx.artifacts_dir is None or not ctx.artifacts_dir.exists():
        return artifacts

    for file_path in ctx.artifacts_dir.iterdir():
        if file_path.is_file():
            try:
                # Read file as base64 for embedding
                with open(file_path, 'rb') as f:
                    content = base64.b64encode(f.read()).decode('utf-8')

                artifacts.append({
                    'name': file_path.name,
                    'path': str(file_path),
                    'type': file_path.suffix.lower(),
                    'content_base64': content,
                    'size': file_path.stat().st_size
                })
            except Exception as e:
                logger.error(f"Error reading artifact {file_path}: {e}")

    return artifacts


class UltimateSandboxMCPServer:
    """
    The Ultimate Swiss Army Knife MCP Server for AI Agents.
    
    Combines all functionality from:
    - Intelligent Sandbox System
    - CodeIndexer System
    - Original Sandbox Tools
    """
    
    def __init__(self, server_name: str = "ultimate-sandbox"):
        """Initialize the ultimate MCP server."""
        logger.info("🚀 Initializing Ultimate Swiss Army Knife MCP Server...")

        # Initialize FastMCP server
        self.mcp = FastMCP(server_name)

        # Initialize Intelligent Sandbox components
        self.config_manager = get_config_manager()
        self.workspace_cloner = WorkspaceCloner()
        self.lifecycle_manager = WorkspaceLifecycleManager()
        self.codebase_analyzer = CodebaseAnalyzer()
        self.task_planner = TaskPlanner()
        self.execution_engine = ExecutionEngine()
        self.action_logger = ActionLogger()
        self.cache_manager = CacheManager()

        # Initialize connection manager with rate limiting
        self.connection_manager = initialize_connection_manager(self.config_manager.config)

        # Initialize Original Sandbox components if available
        if ORIGINAL_SANDBOX_AVAILABLE:
            self.sandbox_manager = SandboxManager()
            # Create default config for ArtifactManager
            from sandbox.core.types import ServerConfig
            default_config = ServerConfig()
            # Use proper artifact directory instead of temp
            if default_config.artifacts_base_dir is None:
                import tempfile
                from pathlib import Path
                default_config.artifacts_base_dir = Path.home() / ".swiss_sandbox" / "artifacts"
            self.artifact_manager = ArtifactManager(default_config, default_config.artifacts_base_dir)
            self.manim_executor = ManimExecutor(Path.cwd())
            self.web_app_builder = WebAppBuilder()

        # Initialize CodeIndexer-style components
        self.indexed_projects = {}
        self.search_cache = {}
        self.file_versions = {}

        # Track active resources
        self.active_workspaces = {}
        self.active_sessions = {}
        self.active_plans = {}
        self.active_artifacts = {}

        # Register all MCP tools
        self._register_intelligent_sandbox_tools()
        self._register_codeindexer_tools()
        if ORIGINAL_SANDBOX_AVAILABLE:
            self._register_original_sandbox_tools()
        self._register_execution_tools()

        logger.info("✅ Ultimate MCP Server initialized with all components!")
    
    def _register_intelligent_sandbox_tools(self):
        """Register Intelligent Sandbox MCP tools."""
        
        @self.mcp.tool()
        def create_workspace(source_path: str, workspace_id: Optional[str] = None) -> Dict[str, Any]:
            """Create a new isolated sandbox workspace."""
            try:
                if not workspace_id:
                    workspace_id = f"workspace_{uuid.uuid4().hex[:8]}"
                
                session = self.lifecycle_manager.create_workspace(
                    source_path=source_path,
                    session_id=workspace_id
                )
                
                self.active_sessions[workspace_id] = session
                self.active_workspaces[workspace_id] = session.workspace
                
                return {
                    "success": True,
                    "workspace_id": workspace_id,
                    "sandbox_path": str(session.workspace.sandbox_path),
                    "isolation_enabled": session.workspace.isolation_config.use_docker
                }
            except Exception as e:
                logger.error(f"Failed to create workspace: {e}")
                return {"success": False, "error": str(e)}
        
        @self.mcp.tool()
        def analyze_codebase(workspace_id: str) -> Dict[str, Any]:
            """Analyze codebase structure and dependencies."""
            try:
                if workspace_id not in self.active_workspaces:
                    return {"success": False, "error": "Workspace not found"}
                
                workspace = self.active_workspaces[workspace_id]
                analysis = self.codebase_analyzer.analyze_codebase(workspace)
                
                return {
                    "success": True,
                    "languages": analysis.structure.languages,
                    "frameworks": analysis.structure.frameworks,
                    "dependencies": len(analysis.dependencies.dependencies),
                    "files": len(analysis.structure.file_tree),
                    "loc": analysis.metrics.lines_of_code
                }
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        @self.mcp.tool()
        def create_task_plan(workspace_id: str, description: str) -> Dict[str, Any]:
            """Create an intelligent task plan."""
            try:
                if workspace_id not in self.active_workspaces:
                    return {"success": False, "error": "Workspace not found"}
                
                workspace = self.active_workspaces[workspace_id]
                analysis = self.codebase_analyzer.analyze_codebase(workspace)
                plan = self.task_planner.create_plan(description, analysis)
                
                self.active_plans[plan.id] = plan
                
                return {
                    "success": True,
                    "plan_id": plan.id,
                    "tasks_count": len(plan.tasks),
                    "tasks": [
                        {
                            "id": task.id,
                            "description": task.description,
                            "status": task.status.value
                        }
                        for task in plan.tasks
                    ]
                }
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        @self.mcp.tool()
        def execute_task_plan(plan_id: str) -> Dict[str, Any]:
            """Execute a task plan."""
            try:
                if plan_id not in self.active_plans:
                    return {"success": False, "error": "Plan not found"}
                
                plan = self.active_plans[plan_id]
                result = self.execution_engine.execute_plan(plan)
                
                return {
                    "success": result.success,
                    "tasks_completed": result.tasks_completed,
                    "tasks_failed": result.tasks_failed,
                    "duration": result.total_duration,
                    "summary": result.summary
                }
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        @self.mcp.tool()
        def destroy_workspace(workspace_id: str) -> Dict[str, Any]:
            """Destroy a workspace and clean up resources."""
            try:
                if workspace_id in self.active_sessions:
                    success = self.lifecycle_manager.destroy_workspace(workspace_id)
                    if success:
                        del self.active_sessions[workspace_id]
                        del self.active_workspaces[workspace_id]
                    return {"success": success}
                return {"success": False, "error": "Workspace not found"}
            except Exception as e:
                return {"success": False, "error": str(e)}
    
    def _register_codeindexer_tools(self):
        """Register CodeIndexer-style MCP tools."""
        
        @self.mcp.tool()
        def search_code_advanced(
            pattern: str,
            workspace_id: Optional[str] = None,
            file_pattern: Optional[str] = None,
            case_sensitive: bool = True,
            fuzzy: bool = False
        ) -> Dict[str, Any]:
            """Advanced code search with pattern matching."""
            try:
                # Use workspace or current directory
                search_path = "."
                if workspace_id and workspace_id in self.active_workspaces:
                    workspace = self.active_workspaces[workspace_id]
                    search_path = workspace.sandbox_path
                
                # Simulate advanced search (simplified)
                results = []
                for root, dirs, files in os.walk(search_path):
                    for file in files:
                        if file_pattern and not file.endswith(file_pattern):
                            continue
                        
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                lines = f.readlines()
                                for i, line in enumerate(lines, 1):
                                    if pattern in line:
                                        results.append({
                                            "file": file_path,
                                            "line": i,
                                            "content": line.strip()
                                        })
                        except:
                            continue
                
                return {
                    "success": True,
                    "matches": len(results),
                    "results": results[:20]  # Limit results
                }
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        @self.mcp.tool()
        def find_files(pattern: str, workspace_id: Optional[str] = None) -> Dict[str, Any]:
            """Find files matching a pattern."""
            try:
                search_path = "."
                if workspace_id and workspace_id in self.active_workspaces:
                    workspace = self.active_workspaces[workspace_id]
                    search_path = workspace.sandbox_path
                
                import glob
                files = glob.glob(os.path.join(search_path, "**", pattern), recursive=True)
                
                return {
                    "success": True,
                    "count": len(files),
                    "files": files[:100]  # Limit results
                }
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        @self.mcp.tool()
        def write_to_file(
            path: str,
            content: str,
            workspace_id: Optional[str] = None
        ) -> Dict[str, Any]:
            """Write content to a file."""
            try:
                if workspace_id and workspace_id in self.active_workspaces:
                    workspace = self.active_workspaces[workspace_id]
                    if workspace.sandbox_path is None:
                        return {"success": False, "error": "Workspace sandbox path is None"}
                    path = os.path.join(workspace.sandbox_path, path)

                if path is None:
                    return {"success": False, "error": "Path is None"}

                # Create directory if needed
                os.makedirs(os.path.dirname(path), exist_ok=True)

                # Store version history
                if path in self.file_versions:
                    self.file_versions[path].append({
                        "timestamp": datetime.now().isoformat(),
                        "content": content
                    })
                else:
                    self.file_versions[path] = [{
                        "timestamp": datetime.now().isoformat(),
                        "content": content
                    }]

                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)

                return {"success": True, "path": path}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        @self.mcp.tool()
        def apply_diff(
            diffs: List[Dict[str, Any]],
            workspace_id: Optional[str] = None
        ) -> Dict[str, Any]:
            """Apply diffs to multiple files."""
            try:
                results = []
                for diff in diffs:
                    file_path = diff.get('file_path')
                    search = diff.get('search')
                    replace = diff.get('replace')

                    if not file_path or not search or replace is None:
                        results.append({"file": file_path or "unknown", "success": False, "error": "Missing required fields"})
                        continue

                    if workspace_id and workspace_id in self.active_workspaces:
                        workspace = self.active_workspaces[workspace_id]
                        if workspace.sandbox_path is None:
                            results.append({"file": file_path, "success": False, "error": "Workspace sandbox path is None"})
                            continue
                        file_path = os.path.join(workspace.sandbox_path, file_path)

                    if file_path is None:
                        results.append({"file": "unknown", "success": False, "error": "File path is None"})
                        continue

                    # Read file
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Apply diff
                    new_content = content.replace(search, replace)

                    # Write file
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)

                    results.append({"file": file_path, "success": True})

                return {"success": True, "files_modified": len(results)}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        @self.mcp.tool()
        def get_file_history(path: str) -> Dict[str, Any]:
            """Get version history of a file."""
            try:
                if path in self.file_versions:
                    return {
                        "success": True,
                        "versions": len(self.file_versions[path]),
                        "history": self.file_versions[path][-5:]  # Last 5 versions
                    }
                return {"success": False, "error": "No history for file"}
            except Exception as e:
                return {"success": False, "error": str(e)}
    
    def _register_original_sandbox_tools(self):
        """Register Original Sandbox MCP tools."""
        
        @self.mcp.tool()
        def create_manim_animation(
            code: str,
            workspace_id: Optional[str] = None
        ) -> Dict[str, Any]:
            """Create a Manim animation."""
            try:
                if not ORIGINAL_SANDBOX_AVAILABLE:
                    return {"success": False, "error": "Manim not available"}
                
                # Execute Manim code
                from pathlib import Path
                import tempfile
                artifacts_dir = Path(tempfile.mkdtemp())
                result = self.manim_executor.execute_manim_code(code, artifacts_dir)
                
                # Store artifact
                artifact_id = f"manim_{uuid.uuid4().hex[:8]}"
                self.active_artifacts[artifact_id] = result
                
                return {
                    "success": True,
                    "artifact_id": artifact_id,
                    "output_path": result.get('output_path')
                }
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        @self.mcp.tool()
        def execute_python(
            code: str,
            workspace_id: Optional[str] = None
        ) -> Dict[str, Any]:
            """Execute Python code in sandbox."""
            try:
                # Create temporary file
                with tempfile.NamedTemporaryFile(
                    mode='w',
                    suffix='.py',
                    delete=False
                ) as f:
                    f.write(code)
                    temp_file = f.name
                
                # Execute
                import subprocess
                result = subprocess.run(
                    [sys.executable, temp_file],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                # Clean up
                os.unlink(temp_file)
                
                return {
                    "success": result.returncode == 0,
                    "output": result.stdout,
                    "error": result.stderr
                }
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        @self.mcp.tool()
        def start_web_app(
            app_code: str,
            port: int = 8080,
            workspace_id: Optional[str] = None
        ) -> Dict[str, Any]:
            """Start a web application."""
            try:
                if not ORIGINAL_SANDBOX_AVAILABLE:
                    return {"success": False, "error": "Web app builder not available"}
                
                # Build and start web app
                app_url = self.web_app_builder.build(app_code, port)

                return {
                    "success": True,
                    "url": app_url or f"http://localhost:{port}",
                    "app_id": f"web_app_{uuid.uuid4().hex[:8]}" if app_url else None
                }
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        @self.mcp.tool()
        def list_artifacts(workspace_id: Optional[str] = None) -> Dict[str, Any]:
            """List all artifacts."""
            try:
                artifacts = []
                for artifact_id, artifact in self.active_artifacts.items():
                    artifacts.append({
                        "id": artifact_id,
                        "type": artifact.get('type', 'unknown'),
                        "created": artifact.get('created', 'unknown')
                    })
                
                return {
                    "success": True,
                    "count": len(artifacts),
                    "artifacts": artifacts
                }
            except Exception as e:
                return {"success": False, "error": str(e)}
    
    def _register_execution_tools(self):
        """Register execution tools (execute, debug_execute, etc.)."""
        
        @self.mcp.tool()
        def debug_execute(code: str) -> str:
            """
            Debug version of execute with minimal processing and extensive logging.
            This is for troubleshooting the hanging issue.
            """
            logger.info(f"DEBUG_EXECUTE: Starting with code length {len(code)}")
            
            result = {
                'debug_mode': True,
                'code_length': len(code),
                'steps_completed': [],
                'stdout': '',
                'stderr': '',
                'error': None
            }
            
            try:
                result['steps_completed'].append('function_entry')
                logger.info("DEBUG_EXECUTE: Function entry completed")
                
                # Get global execution context
                ctx = globals().get('ctx')
                if not ctx:
                    ctx = ExecutionContext()
                    globals()['ctx'] = ctx
                
                # Step 1: Capture streams
                old_stdout, old_stderr = sys.stdout, sys.stderr
                stdout_capture = io.StringIO()
                stderr_capture = io.StringIO()
                result['steps_completed'].append('streams_captured')
                logger.info("DEBUG_EXECUTE: Streams captured")
                
                try:
                    # Step 2: Redirect streams
                    sys.stdout = stdout_capture
                    sys.stderr = stderr_capture
                    result['steps_completed'].append('streams_redirected')
                    logger.info("DEBUG_EXECUTE: Streams redirected")
                    
                    # Step 3: Execute code
                    logger.info("DEBUG_EXECUTE: About to exec code")
                    exec(code, ctx.execution_globals)
                    result['steps_completed'].append('code_executed')
                    logger.info("DEBUG_EXECUTE: Code executed successfully")
                    
                finally:
                    # Step 4: Restore streams
                    sys.stdout = old_stdout
                    sys.stderr = old_stderr
                    result['steps_completed'].append('streams_restored')
                    logger.info("DEBUG_EXECUTE: Streams restored")
                    
                    # Step 5: Capture output
                    result['stdout'] = stdout_capture.getvalue()
                    result['stderr'] = stderr_capture.getvalue()
                    result['steps_completed'].append('output_captured')
                    logger.info(f"DEBUG_EXECUTE: Output captured - stdout={len(result['stdout'])}, stderr={len(result['stderr'])}")
                
                # Step 6: Create result
                result['steps_completed'].append('result_created')
                logger.info("DEBUG_EXECUTE: Result created")
                
                # Step 7: JSON dumps
                logger.info("DEBUG_EXECUTE: About to json.dumps")
                json_result = json.dumps(result, indent=2)
                result['steps_completed'].append('json_created')
                logger.info(f"DEBUG_EXECUTE: JSON created, length={len(json_result)}")
                
                return json_result
                
            except Exception as e:
                logger.error(f"DEBUG_EXECUTE: Exception occurred: {e}")
                logger.error(f"DEBUG_EXECUTE: Exception type: {type(e)}")
                logger.error(f"DEBUG_EXECUTE: Traceback: {traceback.format_exc()}")
                
                error_result = {
                    'debug_mode': True,
                    'steps_completed': result.get('steps_completed', []),
                    'error': {
                        'type': type(e).__name__,
                        'message': str(e),
                        'traceback': traceback.format_exc()
                    },
                    'stdout': '',
                    'stderr': f'Error: {e}'
                }
                
                try:
                    return json.dumps(error_result, indent=2)
                except Exception as json_error:
                    logger.error(f"DEBUG_EXECUTE: Failed to create JSON error result: {json_error}")
                    return '{"error": "Failed to create JSON result", "debug_mode": true}'
        
        @self.mcp.tool()
        def execute(code: str, interactive: bool = False, web_app_type: Optional[str] = None) -> str:
            """
            Execute Python code with enhanced features:
            - Robust sys.path and venv activation
            - Module import error handling with full traceback
            - Artifact interception and storage
            - Web app launch support
            - Interactive REPL mode
            - Rate limiting protection

            Args:
                code: Python code to execute
                interactive: If True, drop into interactive REPL after execution
                web_app_type: Type of web app to launch ('flask' or 'streamlit')

            Returns:
                JSON string containing execution results, artifacts, and metadata
            """
            logger.info(f"EXECUTE: Starting with code length {len(code)}")

            # Check rate limiting if enabled
            if self.config_manager.config.enable_rate_limiting:
                # For MCP connections, we need to get the connection ID from the context
                # This is a simplified approach - in a real WebSocket/MCP implementation,
                # the connection ID would be available in the request context
                connection_id = "mcp_default"  # Default for MCP stdio connections

                allowed, retry_after = self.connection_manager.check_rate_limit(connection_id)
                if not allowed:
                    result = {
                        'stdout': '',
                        'stderr': f'Rate limit exceeded. Try again in {retry_after:.1f} seconds.',
                        'error': f'Rate limit exceeded. Retry after {retry_after:.1f} seconds.',
                        'rate_limited': True,
                        'retry_after': retry_after,
                        'execution_info': {
                            'rate_limiting_enabled': True,
                            'connection_id': connection_id
                        }
                    }
                    return json.dumps(result, indent=2)

            # Get global execution context
            ctx = globals().get('ctx')
            if not ctx:
                ctx = ExecutionContext()
                globals()['ctx'] = ctx

            # Get resource and security managers
            resource_manager = globals().get('resource_manager')
            security_manager = globals().get('security_manager')
            if not resource_manager:
                resource_manager = get_resource_manager()
                globals()['resource_manager'] = resource_manager
            if not security_manager:
                security_manager = get_security_manager(SecurityLevel.MEDIUM)
                globals()['security_manager'] = security_manager
            
            # Create artifacts directory for this execution
            artifacts_dir = ctx.create_artifacts_dir()
            logger.info(f"EXECUTE: Created artifacts directory: {artifacts_dir}")
            
            # Set up monkey patches
            matplotlib_patched = monkey_patch_matplotlib()
            pil_patched = monkey_patch_pil()
            logger.info(f"EXECUTE: Monkey patches - matplotlib: {matplotlib_patched}, pil: {pil_patched}")
            
            # Capture stdout and stderr
            logger.info("EXECUTE: About to capture stdout/stderr")
            old_stdout, old_stderr = sys.stdout, sys.stderr
            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()
            logger.info("EXECUTE: Stdout/stderr captured")
            
            result = {
                'stdout': '',
                'stderr': '',
                'error': None,
                'artifacts': [],
                'web_url': None,
                'execution_info': {
                    'sys_executable': sys.executable,
                    'sys_path_first_3': sys.path[:3],
                    'project_root': str(ctx.project_root),
                    'artifacts_dir': artifacts_dir,
                    'matplotlib_patched': matplotlib_patched,
                    'pil_patched': pil_patched
                }
            }
            
            try:
                logger.info("EXECUTE: About to redirect sys.stdout/stderr")
                sys.stdout = stdout_capture
                sys.stderr = stderr_capture
                logger.info("EXECUTE: Redirected sys.stdout/stderr successfully")
                
                # Check if this is a web app
                if web_app_type and web_app_type in ['flask', 'streamlit']:
                    logger.info(f"EXECUTE: Launching {web_app_type} web app")
                    url = launch_web_app(code, web_app_type)
                    if url:
                        result['web_url'] = url
                        result['stdout'] += f"\n🌐 {web_app_type.title()} app launched at: {url}\n"
                    else:
                        result['stderr'] += f"\n❌ Failed to launch {web_app_type} app\n"
                else:
                    # Regular code execution
                    logger.info("EXECUTE: About to exec code")
                    exec(code, ctx.execution_globals)
                    logger.info("EXECUTE: Code executed successfully")
                
                # Interactive REPL mode
                if interactive:
                    result['stdout'] += "\n[Interactive mode enabled - code executed successfully]\n"
                    result['stdout'] += "Note: REPL mode would be available in a real terminal session\n"
            
            except ImportError as e:
                # Enhanced import error handling
                error_trace = traceback.format_exc()
                module_name = str(e).split("'")[1] if "'" in str(e) else "unknown"
                
                error_details = {
                    'type': 'ImportError',
                    'message': str(e),
                    'module': module_name,
                    'traceback': error_trace,
                    'sys_path': sys.path[:5],  # First 5 paths for debugging
                    'attempted_paths': [p for p in sys.path if Path(p).exists()]
                }
                result['error'] = error_details
                result['stderr'] = f"Import Error: {e}\n\nFull traceback:\n{error_trace}"
            
            except Exception as e:
                # General exception handling
                error_trace = traceback.format_exc()
                result['error'] = {
                    'type': type(e).__name__,
                    'message': str(e),
                    'traceback': error_trace
                }
                result['stderr'] = f"Error: {e}\n\nFull traceback:\n{error_trace}"
            
            finally:
                logger.info("EXECUTE: In finally block - restoring stdout/stderr")
                # Restore stdout/stderr
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                logger.info("EXECUTE: Stdout/stderr restored")
                
                # Capture output
                logger.info("EXECUTE: Capturing output from StringIO objects")
                result['stdout'] += stdout_capture.getvalue()
                result['stderr'] += stderr_capture.getvalue()
                logger.info(f"EXECUTE: Output captured - stdout={len(result['stdout'])}, stderr={len(result['stderr'])}")
                
                # Collect artifacts
                logger.info("EXECUTE: About to collect artifacts")
                result['artifacts'] = collect_artifacts()
                logger.info(f"EXECUTE: Collected {len(result['artifacts'])} artifacts")
            
            logger.info("EXECUTE: About to create final JSON result")
            logger.info(f"EXECUTE: Result keys: {list(result.keys())}")
            json_result = json.dumps(result, indent=2)
            logger.info(f"EXECUTE: Final JSON result created, length={len(json_result)}")
            logger.info("EXECUTE: Function completed successfully, returning result")
            return json_result
        
        @self.mcp.tool()
        def list_artifacts() -> str:
            """List all current artifacts."""
            artifacts = collect_artifacts()
            if not artifacts:
                return "No artifacts found."
            
            result = "Current artifacts:\n"
            for artifact in artifacts:
                result += f"- {artifact['name']} ({artifact['size']} bytes) - {artifact['type']}\n"
            
            return result
        
        @self.mcp.tool()
        def cleanup_artifacts() -> str:
            """Clean up all artifacts and temporary files."""
            ctx = globals().get('ctx')
            if ctx:
                ctx.cleanup_artifacts()
                # Also cleanup web servers
                for url, process in ctx.web_servers.items():
                    try:
                        process.terminate()
                    except:
                        pass
                ctx.web_servers.clear()
            return "Artifacts and web servers cleaned up."
        
        @self.mcp.tool()
        def shell_execute(command: str, working_directory: Optional[str] = None, timeout: int = 30) -> str:
            """
            Execute a shell command safely in a controlled environment.
            
            Args:
                command: The shell command to execute
                working_directory: Directory to run the command in (defaults to project root)
                timeout: Maximum execution time in seconds
            
            Returns:
                JSON string containing execution results, stdout, stderr, and metadata
            """
            # Get global context
            ctx = globals().get('ctx')
            security_manager = globals().get('security_manager')
            if not ctx:
                ctx = ExecutionContext()
                globals()['ctx'] = ctx
            if not security_manager:
                security_manager = get_security_manager(SecurityLevel.MEDIUM)
                globals()['security_manager'] = security_manager
            
            # Set working directory
            if working_directory is None:
                if ctx.project_root is None:
                    working_directory = os.getcwd()
                else:
                    working_directory = str(ctx.project_root)
            
            # Enhanced security checks using security manager
            is_safe, violation = security_manager.check_command_security(command)
            if not is_safe and violation:
                return json.dumps({
                    'stdout': '',
                    'stderr': f'Command blocked for security: {violation.message}',
                    'return_code': -1,
                    'error': {
                        'type': 'SecurityError',
                        'message': violation.message,
                        'level': violation.level.value,
                        'command': command
                    },
                    'execution_info': {
                        'working_directory': working_directory,
                        'timeout': timeout,
                        'command_blocked': True,
                        'security_violation': True
                    }
                }, indent=2)
            
            result = {
                'stdout': '',
                'stderr': '',
                'return_code': 0,
                'error': None,
                'execution_info': {
                    'working_directory': working_directory,
                    'timeout': timeout,
                    'command': command,
                    'command_blocked': False
                }
            }
            
            try:
                # Execute the command with timeout
                process = subprocess.run(
                    command,
                    shell=True,
                    cwd=working_directory,
                    timeout=timeout,
                    capture_output=True,
                    text=True,
                    env=os.environ.copy()  # Use current environment including VIRTUAL_ENV
                )
                
                result['stdout'] = process.stdout
                result['stderr'] = process.stderr
                result['return_code'] = process.returncode
                
                if process.returncode != 0:
                    result['error'] = {
                        'type': 'CommandError',
                        'message': f'Command failed with return code {process.returncode}',
                        'return_code': process.returncode
                    }
                    
            except subprocess.TimeoutExpired:
                result['error'] = {
                    'type': 'TimeoutError',
                    'message': f'Command timed out after {timeout} seconds',
                    'timeout': timeout
                }
                result['stderr'] = f'Command timed out after {timeout} seconds'
                result['return_code'] = -2
                
            except Exception as e:
                result['error'] = {
                    'type': type(e).__name__,
                    'message': str(e),
                    'traceback': traceback.format_exc()
                }
                result['stderr'] = f'Error executing command: {e}'
                result['return_code'] = -3
            
            return json.dumps(result, indent=2)
        
        @self.mcp.tool()
        def get_execution_info() -> str:
            """Get information about the current execution environment."""
            ctx = globals().get('ctx')
            if not ctx:
                ctx = ExecutionContext()
                globals()['ctx'] = ctx
            
            info = {
                'project_root': str(ctx.project_root),
                'venv_path': str(ctx.venv_path),
                'venv_active': ctx.venv_path.exists(),
                'sys_executable': sys.executable,
                'sys_path_length': len(sys.path),
                'sys_path_first_5': sys.path[:5],
                'artifacts_dir': str(ctx.artifacts_dir) if ctx.artifacts_dir else None,
                'web_servers': list(ctx.web_servers.keys()),
                'global_variables': list(ctx.execution_globals.keys()),
                'virtual_env': os.environ.get('VIRTUAL_ENV'),
                'path_contains_venv': str(ctx.venv_path / 'bin') in os.environ.get('PATH', ''),
                'current_working_directory': os.getcwd(),
                'shell_available': True
            }
            return json.dumps(info, indent=2)
        
        @self.mcp.tool()
        def start_repl() -> str:
            """Start an interactive REPL session (simulated for MCP)."""
            ctx = globals().get('ctx')
            if not ctx:
                ctx = ExecutionContext()
                globals()['ctx'] = ctx
            
            # In a real implementation, this would stream stdin/stdout over MCP
            # For now, we provide a simulation
            return json.dumps({
                'status': 'repl_started',
                'message': 'Interactive REPL session started (simulated)',
                'note': 'In a full implementation, this would provide streaming I/O over MCP',
                'globals_available': list(ctx.execution_globals.keys()),
                'sys_path_active': sys.path[:3]
            }, indent=2)
        
        @self.mcp.tool()
        def start_web_app(code: str, app_type: str = 'flask') -> str:
            """Launch a web application and return connection details."""
            url = launch_web_app(code, app_type)
            if url:
                return json.dumps({
                    'status': 'success',
                    'url': url,
                    'app_type': app_type,
                    'message': f'{app_type.title()} application launched successfully'
                }, indent=2)
            else:
                return json.dumps({
                    'status': 'error',
                    'app_type': app_type,
                    'message': f'Failed to launch {app_type} application'
                }, indent=2)
        
        @self.mcp.tool()
        def cleanup_temp_artifacts(max_age_hours: int = 24) -> str:
            """Clean up old temporary artifact directories."""
            cleaned = 0
            temp_dir = Path(tempfile.gettempdir())
            
            try:
                for item in temp_dir.glob('sandbox_artifacts_*'):
                    if item.is_dir():
                        # Check age
                        age_hours = (time.time() - item.stat().st_mtime) / 3600
                        if age_hours > max_age_hours:
                            shutil.rmtree(item, ignore_errors=True)
                            cleaned += 1
            except Exception as e:
                logger.error(f"Error during temp cleanup: {e}")
            
            return json.dumps({
                'cleaned_directories': cleaned,
                'max_age_hours': max_age_hours,
                'message': f'Cleaned {cleaned} old artifact directories'
            }, indent=2)
        
        @self.mcp.tool()
        def get_resource_stats() -> str:
            """Get comprehensive resource usage statistics."""
            resource_manager = globals().get('resource_manager')
            if not resource_manager:
                resource_manager = get_resource_manager()
                globals()['resource_manager'] = resource_manager

            stats = resource_manager.get_resource_stats()
            return json.dumps(stats, indent=2)

        @self.mcp.tool()
        def get_connection_stats() -> str:
            """Get connection and rate limiting statistics."""
            stats = self.connection_manager.get_connection_stats()
            return json.dumps(stats, indent=2)

        @self.mcp.tool()
        def configure_rate_limits(max_requests_per_minute: Optional[int] = None,
                                 max_requests_per_hour: Optional[int] = None,
                                 burst_limit: Optional[int] = None) -> str:
            """Configure rate limiting settings dynamically."""
            config = self.config_manager.config

            if max_requests_per_minute is not None:
                config.rate_limits.max_requests_per_minute = max_requests_per_minute
            if max_requests_per_hour is not None:
                config.rate_limits.max_requests_per_hour = max_requests_per_hour
            if burst_limit is not None:
                config.rate_limits.burst_limit = burst_limit

            # Re-initialize connection manager with new settings
            self.connection_manager = initialize_connection_manager(config)
            self.config_manager.save_config()

            return json.dumps({
                'status': 'success',
                'message': 'Rate limiting configuration updated',
                'new_limits': {
                    'max_requests_per_minute': config.rate_limits.max_requests_per_minute,
                    'max_requests_per_hour': config.rate_limits.max_requests_per_hour,
                    'burst_limit': config.rate_limits.burst_limit
                }
            }, indent=2)

        @self.mcp.tool()
        def configure_connection_limits(max_connections: Optional[int] = None,
                                       max_per_ip: Optional[int] = None,
                                       connection_timeout: Optional[int] = None) -> str:
            """Configure connection limits dynamically."""
            config = self.config_manager.config

            if max_connections is not None:
                config.connection_limits.max_concurrent_connections = max_connections
            if max_per_ip is not None:
                config.connection_limits.max_connections_per_ip = max_per_ip
            if connection_timeout is not None:
                config.connection_limits.connection_timeout = connection_timeout

            # Re-initialize connection manager with new settings
            self.connection_manager = initialize_connection_manager(config)
            self.config_manager.save_config()

            return json.dumps({
                'status': 'success',
                'message': 'Connection limits configuration updated',
                'new_limits': {
                    'max_connections': config.connection_limits.max_concurrent_connections,
                    'max_per_ip': config.connection_limits.max_connections_per_ip,
                    'connection_timeout': config.connection_limits.connection_timeout
                }
            }, indent=2)
        
        @self.mcp.tool()
        def emergency_cleanup() -> str:
            """Perform emergency cleanup of all resources."""
            try:
                ctx = globals().get('ctx')
                resource_manager = globals().get('resource_manager')
                if not ctx:
                    ctx = ExecutionContext()
                    globals()['ctx'] = ctx
                if not resource_manager:
                    resource_manager = get_resource_manager()
                    globals()['resource_manager'] = resource_manager
                
                # Clean up finished processes
                finished = resource_manager.process_manager.cleanup_finished()
                
                # Clean up web servers
                for url, process_id in ctx.web_servers.items():
                    resource_manager.process_manager.remove_process(process_id)
                ctx.web_servers.clear()
                
                # Clean up artifacts
                ctx.cleanup_artifacts()
                
                # Force garbage collection
                import gc
                gc.collect()
                
                return json.dumps({
                    'status': 'success',
                    'message': 'Emergency cleanup completed',
                    'finished_processes': finished,
                    'web_servers_cleaned': len(ctx.web_servers)
                }, indent=2)
            except Exception as e:
                return json.dumps({
                    'status': 'error',
                    'message': f'Emergency cleanup failed: {str(e)}'
                }, indent=2)
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive server status."""
        config = self.config_manager.config
        connection_stats = self.connection_manager.get_connection_stats()

        return {
            "server": "Ultimate Swiss Army Knife MCP Server",
            "version": "1.0.0",
            "components": {
                "intelligent_sandbox": True,
                "codeindexer": True,
                "original_sandbox": ORIGINAL_SANDBOX_AVAILABLE,
                "connection_limits": config.enable_connection_limits,
                "rate_limiting": config.enable_rate_limiting
            },
            "active_resources": {
                "workspaces": len(self.active_workspaces),
                "sessions": len(self.active_sessions),
                "plans": len(self.active_plans),
                "artifacts": len(self.active_artifacts),
                "connections": connection_stats.get('total_connections', 0)
            },
            "connection_limits": {
                "max_concurrent_connections": config.connection_limits.max_concurrent_connections,
                "max_connections_per_ip": config.connection_limits.max_connections_per_ip,
                "connection_timeout_seconds": config.connection_limits.connection_timeout,
                "ip_filtering_enabled": config.connection_limits.enable_ip_filtering
            },
            "rate_limits": {
                "max_requests_per_minute": config.rate_limits.max_requests_per_minute,
                "max_requests_per_hour": config.rate_limits.max_requests_per_hour,
                "burst_limit": config.rate_limits.burst_limit,
                "sliding_window_enabled": config.rate_limits.enable_sliding_window,
                "rate_limit_window_seconds": config.rate_limits.rate_limit_window_seconds
            },
            "capabilities": [
                "Workspace isolation",
                "Codebase analysis",
                "Task planning and execution",
                "Advanced code search",
                "File manipulation",
                "Version history",
                "Python execution",
                "Web app hosting",
                "Connection limits",
                "Rate limiting",
                "Manim animations" if ORIGINAL_SANDBOX_AVAILABLE else None
            ]
        }


def main():
    """Main entry point for the Ultimate MCP Server."""
    server = UltimateSandboxMCPServer()
    
    # Print status
    status = server.get_status()
    print("\n" + "="*80)
    print("🚀 ULTIMATE SWISS ARMY KNIFE MCP SERVER")
    print("="*80)
    print(json.dumps(status, indent=2))
    print("\n✅ Server initialized and ready!")
    print("📡 All MCP tools registered and available.")
    print("="*80)
    
    # Run the MCP server
    server.mcp.run()


if __name__ == "__main__":
    main()
