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
    from sandbox.core.sandbox_manager import SandboxManager
    from sandbox.core.artifact_manager import ArtifactManager
    from sandbox.animation.manim_executor import ManimExecutor
    from sandbox.web.app_builder import WebAppBuilder
    ORIGINAL_SANDBOX_AVAILABLE = True
except ImportError:
    ORIGINAL_SANDBOX_AVAILABLE = False

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
        
        # Initialize Original Sandbox components if available
        if ORIGINAL_SANDBOX_AVAILABLE:
            self.sandbox_manager = SandboxManager()
            self.artifact_manager = ArtifactManager()
            self.manim_executor = ManimExecutor()
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
        
        logger.info("✅ Ultimate MCP Server initialized with all components!")
    
    def _register_intelligent_sandbox_tools(self):
        """Register Intelligent Sandbox MCP tools."""
        
        @self.mcp.tool()
        def create_workspace(source_path: str, workspace_id: str = None) -> Dict[str, Any]:
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
            workspace_id: str = None,
            file_pattern: str = None,
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
        def find_files(pattern: str, workspace_id: str = None) -> Dict[str, Any]:
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
            workspace_id: str = None
        ) -> Dict[str, Any]:
            """Write content to a file."""
            try:
                if workspace_id and workspace_id in self.active_workspaces:
                    workspace = self.active_workspaces[workspace_id]
                    path = os.path.join(workspace.sandbox_path, path)
                
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
            workspace_id: str = None
        ) -> Dict[str, Any]:
            """Apply diffs to multiple files."""
            try:
                results = []
                for diff in diffs:
                    file_path = diff.get('file_path')
                    search = diff.get('search')
                    replace = diff.get('replace')
                    
                    if workspace_id and workspace_id in self.active_workspaces:
                        workspace = self.active_workspaces[workspace_id]
                        file_path = os.path.join(workspace.sandbox_path, file_path)
                    
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
            workspace_id: str = None
        ) -> Dict[str, Any]:
            """Create a Manim animation."""
            try:
                if not ORIGINAL_SANDBOX_AVAILABLE:
                    return {"success": False, "error": "Manim not available"}
                
                # Execute Manim code
                result = self.manim_executor.execute(code)
                
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
            workspace_id: str = None
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
            workspace_id: str = None
        ) -> Dict[str, Any]:
            """Start a web application."""
            try:
                if not ORIGINAL_SANDBOX_AVAILABLE:
                    return {"success": False, "error": "Web app builder not available"}
                
                # Build and start web app
                app_info = self.web_app_builder.build(app_code, port)
                
                return {
                    "success": True,
                    "url": f"http://localhost:{port}",
                    "app_id": app_info.get('app_id')
                }
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        @self.mcp.tool()
        def list_artifacts(workspace_id: str = None) -> Dict[str, Any]:
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
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive server status."""
        return {
            "server": "Ultimate Swiss Army Knife MCP Server",
            "version": "1.0.0",
            "components": {
                "intelligent_sandbox": True,
                "codeindexer": True,
                "original_sandbox": ORIGINAL_SANDBOX_AVAILABLE
            },
            "active_resources": {
                "workspaces": len(self.active_workspaces),
                "sessions": len(self.active_sessions),
                "plans": len(self.active_plans),
                "artifacts": len(self.active_artifacts)
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
