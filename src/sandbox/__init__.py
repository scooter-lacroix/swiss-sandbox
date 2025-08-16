"""
Swiss Sandbox - The Swiss army knife of AI toolkits

Enhanced Python code execution sandbox with FastMCP server integration,
designed for secure and feature-rich code execution with artifact management
and web application support.
"""

__version__ = "0.3.0"
__author__ = "Sandbox Development Team"
__description__ = "Swiss army knife of AI toolkits - Enhanced Python code execution sandbox with microsandbox integration and FastMCP server support"

# Core modules
from . import server, utils
from . import mcp_sandbox_server

# Enhanced SDK
from . import sdk
from .sdk.python_sandbox import PythonSandbox
from .sdk.node_sandbox import NodeSandbox
from .sdk.local_sandbox import LocalSandbox
from .sdk.remote_sandbox import RemoteSandbox
from .sdk.execution import Execution
from .sdk.command_execution import CommandExecution
from .sdk.config import SandboxConfig, SandboxOptions
from .core.execution_context import PersistentExecutionContext

__all__ = [
    'server',
    'utils', 
    'mcp_sandbox_server',
    'sdk',
    'PythonSandbox',
    'NodeSandbox',
    'LocalSandbox',
    'RemoteSandbox',
    'Execution',
    'CommandExecution',
    'SandboxConfig',
    'SandboxOptions',
    'PersistentExecutionContext',
    '__version__',
    '__author__',
    '__description__'
]
