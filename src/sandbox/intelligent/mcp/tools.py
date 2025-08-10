"""
MCP tool registration utilities for the intelligent sandbox system.
"""

from fastmcp import FastMCP
from typing import Dict, Any
from ..workspace import WorkspaceCloner
from ..analyzer import CodebaseAnalyzer
from ..planner import TaskPlanner
from ..executor import ExecutionEngine
from ..logger import ActionLogger


def register_sandbox_tools(mcp: FastMCP) -> None:
    """
    Register all intelligent sandbox tools with a FastMCP server instance.
    
    This function can be used to add intelligent sandbox capabilities
    to an existing FastMCP server.
    
    Args:
        mcp: FastMCP server instance to register tools with
    """
    
    # Initialize components
    workspace_cloner = WorkspaceCloner()
    codebase_analyzer = CodebaseAnalyzer()
    task_planner = TaskPlanner()
    execution_engine = ExecutionEngine()
    action_logger = ActionLogger()
    
    # Track active workspaces
    active_workspaces = {}
    
    @mcp.tool()
    def intelligent_sandbox_create_workspace(source_path: str, workspace_id: str = None) -> Dict[str, Any]:
        """Create a new intelligent sandbox workspace."""
        try:
            workspace = workspace_cloner.clone_workspace(source_path, workspace_id)
            workspace_cloner.setup_isolation(workspace)
            active_workspaces[workspace.id] = workspace
            
            return {
                "success": True,
                "workspace_id": workspace.id,
                "sandbox_path": workspace.sandbox_path
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @mcp.tool()
    def intelligent_sandbox_analyze_codebase(workspace_id: str) -> Dict[str, Any]:
        """Analyze codebase in an intelligent sandbox workspace."""
        try:
            workspace = active_workspaces.get(workspace_id)
            if not workspace:
                return {"success": False, "error": "Workspace not found"}
            
            analysis = codebase_analyzer.analyze_codebase(workspace)
            return {
                "success": True,
                "summary": analysis.summary,
                "languages": analysis.structure.languages,
                "frameworks": analysis.structure.frameworks
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @mcp.tool()
    def intelligent_sandbox_create_plan(workspace_id: str, task_description: str) -> Dict[str, Any]:
        """Create a task plan for the intelligent sandbox."""
        try:
            workspace = active_workspaces.get(workspace_id)
            if not workspace:
                return {"success": False, "error": "Workspace not found"}
            
            analysis = codebase_analyzer.analyze_codebase(workspace)
            plan = task_planner.create_plan(task_description, analysis)
            
            return {
                "success": True,
                "plan_id": plan.id,
                "tasks_count": len(plan.tasks)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @mcp.tool()
    def intelligent_sandbox_execute_plan(plan_id: str) -> Dict[str, Any]:
        """Execute a task plan in the intelligent sandbox."""
        try:
            plan = task_planner.get_plan(plan_id)
            if not plan:
                return {"success": False, "error": "Plan not found"}
            
            result = execution_engine.execute_plan(plan)
            return {
                "success": result.success,
                "tasks_completed": result.tasks_completed,
                "tasks_failed": result.tasks_failed,
                "summary": result.summary
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @mcp.tool()
    def intelligent_sandbox_get_history(workspace_id: str) -> Dict[str, Any]:
        """Get execution history for an intelligent sandbox workspace."""
        try:
            actions = action_logger.get_execution_history(workspace_id)
            return {
                "success": True,
                "actions_count": len(actions),
                "recent_actions": [
                    {
                        "type": action.action_type.value,
                        "description": action.description,
                        "timestamp": action.timestamp.isoformat()
                    }
                    for action in actions[-5:]  # Last 5 actions
                ]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}