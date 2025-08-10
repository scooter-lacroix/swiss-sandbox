#!/usr/bin/env python3
"""
Simplified MCP server for the intelligent sandbox system.
"""

from fastmcp import FastMCP
import sys
import json
import logging
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

# Add the src directory to Python path
project_root = Path(__file__).parent.parent.parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from sandbox.intelligent.workspace.cloner import WorkspaceCloner
from sandbox.intelligent.analyzer.analyzer import CodebaseAnalyzer
from sandbox.intelligent.planner.planner import TaskPlanner
from sandbox.intelligent.executor.engine import ExecutionEngine
from sandbox.intelligent.logger.logger import ActionLogger
from sandbox.intelligent.config import get_config_manager
from sandbox.intelligent.workspace.lifecycle import WorkspaceLifecycleManager
from sandbox.intelligent.cache.cache_manager import CacheManager

logger = logging.getLogger(__name__)

# Initialize the MCP server
mcp = FastMCP("intelligent-sandbox")

# Initialize components with full intelligent sandbox functionality
config_manager = get_config_manager()
lifecycle_manager = WorkspaceLifecycleManager()
workspace_cloner = WorkspaceCloner()
codebase_analyzer = CodebaseAnalyzer()
task_planner = TaskPlanner()
execution_engine = ExecutionEngine()
action_logger = ActionLogger()
cache_manager = CacheManager()

# Track active workspaces
active_workspaces = {}
active_plans = {}

@mcp.tool()
def create_sandbox_workspace(source_path: str, workspace_id: str = None) -> Dict[str, Any]:
    """Create a new isolated sandbox workspace from a source directory."""
    try:
        logger.info(f"Creating sandbox workspace from: {source_path}")
        
        # Generate workspace ID if not provided
        if not workspace_id:
            import uuid
            workspace_id = f"sandbox_{uuid.uuid4().hex[:8]}"
        
        # Create workspace directly using workspace cloner
        workspace = workspace_cloner.clone_workspace(source_path, workspace_id)
        
        # Store the workspace
        active_workspaces[workspace_id] = workspace
        
        logger.info(f"Sandbox workspace created: {workspace_id}")
        
        return {
            "success": True,
            "workspace_id": workspace_id,
            "sandbox_path": str(workspace.sandbox_path),
            "isolation_enabled": workspace.isolation_config.use_docker,
            "message": f"Sandbox workspace '{workspace_id}' created successfully"
        }
        
    except Exception as e:
        import traceback
        logger.error(f"Failed to create sandbox workspace: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to create sandbox workspace"
        }

@mcp.tool()
def analyze_codebase(workspace_id: str) -> Dict[str, Any]:
    """Analyze the codebase structure and context in a sandbox workspace."""
    try:
        if workspace_id not in active_workspaces:
            return {
                "success": False,
                "error": f"Workspace '{workspace_id}' not found",
                "message": "Please create the workspace first"
            }
        
        workspace = active_workspaces[workspace_id]
        logger.info(f"Analyzing codebase in workspace: {workspace_id}")
        
        # Perform analysis
        analysis = codebase_analyzer.analyze_codebase(workspace)
        
        return {
            "success": True,
            "workspace_id": workspace_id,
            "analysis": {
                "languages": analysis.structure.languages,
                "frameworks": analysis.structure.frameworks,
                "dependencies_count": len(analysis.dependencies.dependencies),
                "files_count": len(analysis.structure.file_tree),
                "lines_of_code": analysis.metrics.lines_of_code,
                "complexity_score": analysis.metrics.complexity_score
            },
            "message": f"Codebase analysis completed for workspace '{workspace_id}'"
        }
        
    except Exception as e:
        logger.error(f"Failed to analyze codebase: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to analyze codebase"
        }

@mcp.tool()
def create_task_plan(workspace_id: str, task_description: str) -> Dict[str, Any]:
    """Create a detailed task plan for a given task description."""
    try:
        if workspace_id not in active_workspaces:
            return {
                "success": False,
                "error": f"Workspace '{workspace_id}' not found",
                "message": "Please create the workspace first"
            }
        
        workspace = active_workspaces[workspace_id]
        logger.info(f"Creating task plan for workspace: {workspace_id}")
        
        # Analyze codebase first
        analysis = codebase_analyzer.analyze_codebase(workspace)
        
        # Create task plan
        task_plan = task_planner.create_plan(task_description, analysis)
        
        # Store the plan
        active_plans[task_plan.id] = task_plan
        
        return {
            "success": True,
            "workspace_id": workspace_id,
            "plan_id": task_plan.id,
            "tasks_count": len(task_plan.tasks),
            "description": task_plan.description,
            "tasks": [
                {
                    "id": task.id,
                    "description": task.description,
                    "status": task.status.value,
                    "dependencies": task.dependencies
                }
                for task in task_plan.tasks
            ],
            "message": f"Task plan created with {len(task_plan.tasks)} tasks"
        }
        
    except Exception as e:
        logger.error(f"Failed to create task plan: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to create task plan"
        }

@mcp.tool()
def execute_task_plan(plan_id: str) -> Dict[str, Any]:
    """Execute a task plan in the sandbox environment."""
    try:
        if plan_id not in active_plans:
            return {
                "success": False,
                "error": f"Task plan '{plan_id}' not found",
                "message": "Please create the task plan first"
            }
        
        task_plan = active_plans[plan_id]
        logger.info(f"Executing task plan: {plan_id}")
        
        # Execute the plan
        execution_result = execution_engine.execute_plan(task_plan)
        
        return {
            "success": True,
            "plan_id": plan_id,
            "tasks_completed": execution_result.tasks_completed,
            "tasks_failed": execution_result.tasks_failed,
            "execution_time": execution_result.execution_time,
            "summary": execution_result.summary,
            "message": f"Task plan executed: {execution_result.tasks_completed} completed, {execution_result.tasks_failed} failed"
        }
        
    except Exception as e:
        logger.error(f"Failed to execute task plan: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to execute task plan"
        }

@mcp.tool()
def get_execution_history(workspace_id: str) -> Dict[str, Any]:
    """Get the execution history for a sandbox workspace."""
    try:
        logger.info(f"Getting execution history for workspace: {workspace_id}")
        
        # Get history from action logger
        history = action_logger.get_execution_history(workspace_id)
        
        return {
            "success": True,
            "workspace_id": workspace_id,
            "total_actions": len(history),
            "recent_actions": [
                {
                    "action_type": action.action_type.value,
                    "description": action.description,
                    "timestamp": action.timestamp.isoformat(),
                    "success": action.success
                }
                for action in history[-10:]  # Last 10 actions
            ],
            "message": f"Retrieved {len(history)} actions from execution history"
        }
        
    except Exception as e:
        logger.error(f"Failed to get execution history: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to get execution history"
        }

@mcp.tool()
def cleanup_workspace(workspace_id: str) -> Dict[str, Any]:
    """Clean up and destroy a sandbox workspace."""
    try:
        if workspace_id not in active_workspaces:
            return {
                "success": False,
                "error": f"Workspace '{workspace_id}' not found",
                "message": "Workspace may already be cleaned up"
            }
        
        workspace = active_workspaces[workspace_id]
        logger.info(f"Cleaning up workspace: {workspace_id}")
        
        # Clean up workspace files
        if workspace.sandbox_path.exists():
            shutil.rmtree(workspace.sandbox_path, ignore_errors=True)
        
        # Remove from active workspaces
        del active_workspaces[workspace_id]
        
        # Clean up related plans
        plans_to_remove = [plan_id for plan_id, plan in active_plans.items() 
                          if hasattr(plan, 'workspace_id') and plan.workspace_id == workspace_id]
        for plan_id in plans_to_remove:
            del active_plans[plan_id]
        
        return {
            "success": True,
            "workspace_id": workspace_id,
            "message": f"Workspace '{workspace_id}' cleaned up successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to cleanup workspace: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to cleanup workspace"
        }

@mcp.tool()
def get_sandbox_status() -> Dict[str, Any]:
    """Get the current status of the intelligent sandbox system."""
    try:
        return {
            "success": True,
            "status": "active",
            "active_workspaces": len(active_workspaces),
            "active_plans": len(active_plans),
            "docker_available": config_manager.config.isolation.use_docker,
            "system_info": {
                "python_version": sys.version,
                "platform": sys.platform
            },
            "message": "Sandbox system is running normally"
        }
        
    except Exception as e:
        logger.error(f"Failed to get sandbox status: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to get sandbox status"
        }

def main():
    """Main entry point for the simplified MCP server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Intelligent Sandbox MCP Server (Simplified)")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio",
                       help="Transport method (default: stdio)")
    parser.add_argument("--host", default="localhost", help="Host for SSE transport")
    parser.add_argument("--port", type=int, default=8765, help="Port for SSE transport")
    
    args = parser.parse_args()
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        logger.info(f"Starting Intelligent Sandbox MCP Server with {args.transport} transport")
        
        if args.transport == "stdio":
            mcp.run()
        else:
            mcp.run(transport="sse", host=args.host, port=args.port)
            
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()