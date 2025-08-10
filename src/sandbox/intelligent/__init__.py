"""
Intelligent Sandbox System

A comprehensive virtual development environment where AI models can perform
unrestricted coding actions safely with workspace cloning, intelligent codebase
understanding, dynamic task planning, and detailed execution tracking.
"""

from .workspace import SandboxWorkspace, WorkspaceCloner, IsolationConfig
from .analyzer import CodebaseAnalyzer, CodebaseAnalysis, CodebaseStructure, DependencyGraph
from .planner import TaskPlanner, TaskPlan, Task, TaskStatus
from .executor import ExecutionEngine, ExecutionResult, TaskResult
from .logger import ActionLogger, Action
from .types import ActionType
from .config import ConfigManager, SandboxConfig, get_config, get_config_manager
from .types import WorkspaceStatus, PlanStatus, ApprovalStatus, ErrorInfo
from .mcp import IntelligentSandboxMCPServer, register_sandbox_tools

__all__ = [
    # Workspace components
    'SandboxWorkspace',
    'WorkspaceCloner',
    'IsolationConfig',
    'WorkspaceStatus',
    
    # Analyzer components
    'CodebaseAnalyzer',
    'CodebaseAnalysis',
    'CodebaseStructure',
    'DependencyGraph',
    
    # Planner components
    'TaskPlanner',
    'TaskPlan',
    'Task',
    'TaskStatus',
    'PlanStatus',
    'ApprovalStatus',
    
    # Executor components
    'ExecutionEngine',
    'ExecutionResult',
    'TaskResult',
    
    # Logger components
    'ActionLogger',
    'Action',
    'ActionType',
    
    # Configuration
    'ConfigManager',
    'SandboxConfig',
    'get_config',
    'get_config_manager',
    
    # MCP Integration
    'IntelligentSandboxMCPServer',
    'register_sandbox_tools',
    
    # Common types
    'ErrorInfo'
]