"""
MCP client interface for the intelligent sandbox system.

This module provides:
- User-friendly client interface for sandbox operations
- Real-time progress monitoring and status updates
- Error reporting and retry mechanisms
- Task submission and workflow management
"""

import json
import time
import logging
import asyncio
import threading
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import subprocess
import sys

logger = logging.getLogger(__name__)


class ClientStatus(Enum):
    """Client connection status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class OperationStatus(Enum):
    """Operation execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProgressUpdate:
    """Progress update information."""
    operation_id: str
    status: OperationStatus
    progress_percent: float
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class OperationResult:
    """Operation execution result."""
    operation_id: str
    success: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration: float = 0.0
    timestamp: float = field(default_factory=time.time)


class SandboxMCPClient:
    """
    User-friendly MCP client for the intelligent sandbox system.
    
    Provides high-level interfaces for:
    - Workspace management
    - Task planning and execution
    - Progress monitoring
    - Error handling and recovery
    """
    
    def __init__(self, server_command: Optional[List[str]] = None, api_key: Optional[str] = None):
        """
        Initialize the sandbox MCP client.
        
        Args:
            server_command: Command to start the MCP server (for stdio transport)
            api_key: API key for authentication
        """
        self.server_command = server_command or [
            sys.executable, "-m", "src.sandbox.intelligent_sandbox_server"
        ]
        self.api_key = api_key
        self.status = ClientStatus.DISCONNECTED
        self.server_process: Optional[subprocess.Popen] = None
        self.request_id = 0
        self.pending_requests: Dict[int, asyncio.Future] = {}
        self.progress_callbacks: List[Callable[[ProgressUpdate], None]] = []
        self.error_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []
        
        # Operation tracking
        self.active_operations: Dict[str, Dict[str, Any]] = {}
        self.operation_history: List[OperationResult] = []
        
        # Server capabilities
        self.server_capabilities: Dict[str, Any] = {}
        self.available_tools: List[Dict[str, Any]] = []
        
        # Background tasks
        self._monitor_task: Optional[asyncio.Task] = None
        self._reader_task: Optional[asyncio.Task] = None
    
    async def connect(self) -> bool:
        """
        Connect to the MCP server.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.status = ClientStatus.CONNECTING
            logger.info("Connecting to intelligent sandbox MCP server...")
            
            # Start the server process
            self.server_process = subprocess.Popen(
                self.server_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0
            )
            
            # Initialize the connection
            init_response = await self._send_request("initialize", {
                "protocolVersion": "2.0",
                "capabilities": {
                    "tools": {},
                    "resources": {},
                    "logging": {}
                },
                "clientInfo": {
                    "name": "Intelligent Sandbox Client",
                    "version": "1.0.0"
                }
            })
            
            if not init_response.get("result"):
                raise Exception("Server initialization failed")
            
            # Store server capabilities
            result = init_response["result"]
            self.server_capabilities = result.get("capabilities", {})
            
            # Send initialized notification
            await self._send_notification("initialized", {})
            
            # Get available tools
            tools_response = await self._send_request("tools/list", {})
            if tools_response.get("result"):
                self.available_tools = tools_response["result"].get("tools", [])
            
            self.status = ClientStatus.CONNECTED
            logger.info("Successfully connected to MCP server")
            
            # Start background monitoring
            self._reader_task = asyncio.create_task(self._read_responses())
            self._monitor_task = asyncio.create_task(self._monitor_operations())
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            self.status = ClientStatus.ERROR
            await self.disconnect()
            return False
    
    async def disconnect(self):
        """Disconnect from the MCP server."""
        try:
            self.status = ClientStatus.DISCONNECTED
            
            # Cancel background tasks
            if self._monitor_task:
                self._monitor_task.cancel()
            if self._reader_task:
                self._reader_task.cancel()
            
            # Close server process
            if self.server_process:
                self.server_process.terminate()
                try:
                    self.server_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.server_process.kill()
                    self.server_process.wait()
                self.server_process = None
            
            # Clear pending requests
            for future in self.pending_requests.values():
                if not future.done():
                    future.cancel()
            self.pending_requests.clear()
            
            logger.info("Disconnected from MCP server")
            
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
    
    async def create_workspace(self, source_path: str, workspace_id: Optional[str] = None) -> OperationResult:
        """
        Create a new sandbox workspace.
        
        Args:
            source_path: Path to the source workspace to clone
            workspace_id: Optional custom workspace ID
            
        Returns:
            OperationResult with workspace creation details
        """
        operation_id = f"create_workspace_{int(time.time())}"
        
        try:
            self._start_operation(operation_id, "Creating sandbox workspace", {
                "source_path": source_path,
                "workspace_id": workspace_id
            })
            
            result = await self._call_tool("create_sandbox_workspace", {
                "source_path": source_path,
                "workspace_id": workspace_id,
                "api_key": self.api_key
            })
            
            if result.get("success"):
                self._complete_operation(operation_id, result)
                return OperationResult(
                    operation_id=operation_id,
                    success=True,
                    result=result
                )
            else:
                error_msg = result.get("error", "Unknown error")
                self._fail_operation(operation_id, error_msg)
                return OperationResult(
                    operation_id=operation_id,
                    success=False,
                    error=error_msg
                )
                
        except Exception as e:
            error_msg = str(e)
            self._fail_operation(operation_id, error_msg)
            return OperationResult(
                operation_id=operation_id,
                success=False,
                error=error_msg
            )
    
    async def analyze_codebase(self, workspace_id: str) -> OperationResult:
        """
        Analyze the codebase in a workspace.
        
        Args:
            workspace_id: ID of the workspace to analyze
            
        Returns:
            OperationResult with analysis details
        """
        operation_id = f"analyze_codebase_{int(time.time())}"
        
        try:
            self._start_operation(operation_id, "Analyzing codebase", {
                "workspace_id": workspace_id
            })
            
            result = await self._call_tool("analyze_codebase", {
                "workspace_id": workspace_id,
                "api_key": self.api_key
            })
            
            if result.get("success"):
                self._complete_operation(operation_id, result)
                return OperationResult(
                    operation_id=operation_id,
                    success=True,
                    result=result
                )
            else:
                error_msg = result.get("error", "Unknown error")
                self._fail_operation(operation_id, error_msg)
                return OperationResult(
                    operation_id=operation_id,
                    success=False,
                    error=error_msg
                )
                
        except Exception as e:
            error_msg = str(e)
            self._fail_operation(operation_id, error_msg)
            return OperationResult(
                operation_id=operation_id,
                success=False,
                error=error_msg
            )
    
    async def create_task_plan(self, workspace_id: str, task_description: str) -> OperationResult:
        """
        Create a task plan for a workspace.
        
        Args:
            workspace_id: ID of the workspace
            task_description: Description of the task to plan
            
        Returns:
            OperationResult with task plan details
        """
        operation_id = f"create_task_plan_{int(time.time())}"
        
        try:
            self._start_operation(operation_id, "Creating task plan", {
                "workspace_id": workspace_id,
                "task_description": task_description
            })
            
            result = await self._call_tool("create_task_plan", {
                "workspace_id": workspace_id,
                "task_description": task_description,
                "api_key": self.api_key
            })
            
            if result.get("success"):
                self._complete_operation(operation_id, result)
                return OperationResult(
                    operation_id=operation_id,
                    success=True,
                    result=result
                )
            else:
                error_msg = result.get("error", "Unknown error")
                self._fail_operation(operation_id, error_msg)
                return OperationResult(
                    operation_id=operation_id,
                    success=False,
                    error=error_msg
                )
                
        except Exception as e:
            error_msg = str(e)
            self._fail_operation(operation_id, error_msg)
            return OperationResult(
                operation_id=operation_id,
                success=False,
                error=error_msg
            )
    
    async def execute_task_plan(self, plan_id: str) -> OperationResult:
        """
        Execute a task plan.
        
        Args:
            plan_id: ID of the task plan to execute
            
        Returns:
            OperationResult with execution details
        """
        operation_id = f"execute_task_plan_{int(time.time())}"
        
        try:
            self._start_operation(operation_id, "Executing task plan", {
                "plan_id": plan_id
            })
            
            result = await self._call_tool("execute_task_plan", {
                "plan_id": plan_id,
                "api_key": self.api_key
            })
            
            if result.get("success"):
                self._complete_operation(operation_id, result)
                return OperationResult(
                    operation_id=operation_id,
                    success=True,
                    result=result
                )
            else:
                error_msg = result.get("error", "Unknown error")
                self._fail_operation(operation_id, error_msg)
                return OperationResult(
                    operation_id=operation_id,
                    success=False,
                    error=error_msg
                )
                
        except Exception as e:
            error_msg = str(e)
            self._fail_operation(operation_id, error_msg)
            return OperationResult(
                operation_id=operation_id,
                success=False,
                error=error_msg
            )
    
    async def get_execution_history(self, workspace_id: str) -> OperationResult:
        """
        Get execution history for a workspace.
        
        Args:
            workspace_id: ID of the workspace
            
        Returns:
            OperationResult with execution history
        """
        operation_id = f"get_history_{int(time.time())}"
        
        try:
            self._start_operation(operation_id, "Getting execution history", {
                "workspace_id": workspace_id
            })
            
            result = await self._call_tool("get_execution_history", {
                "workspace_id": workspace_id,
                "api_key": self.api_key
            })
            
            if result.get("success"):
                self._complete_operation(operation_id, result)
                return OperationResult(
                    operation_id=operation_id,
                    success=True,
                    result=result
                )
            else:
                error_msg = result.get("error", "Unknown error")
                self._fail_operation(operation_id, error_msg)
                return OperationResult(
                    operation_id=operation_id,
                    success=False,
                    error=error_msg
                )
                
        except Exception as e:
            error_msg = str(e)
            self._fail_operation(operation_id, error_msg)
            return OperationResult(
                operation_id=operation_id,
                success=False,
                error=error_msg
            )
    
    async def cleanup_workspace(self, workspace_id: str) -> OperationResult:
        """
        Clean up a workspace.
        
        Args:
            workspace_id: ID of the workspace to clean up
            
        Returns:
            OperationResult with cleanup details
        """
        operation_id = f"cleanup_workspace_{int(time.time())}"
        
        try:
            self._start_operation(operation_id, "Cleaning up workspace", {
                "workspace_id": workspace_id
            })
            
            result = await self._call_tool("cleanup_workspace", {
                "workspace_id": workspace_id,
                "api_key": self.api_key
            })
            
            if result.get("success"):
                self._complete_operation(operation_id, result)
                return OperationResult(
                    operation_id=operation_id,
                    success=True,
                    result=result
                )
            else:
                error_msg = result.get("error", "Unknown error")
                self._fail_operation(operation_id, error_msg)
                return OperationResult(
                    operation_id=operation_id,
                    success=False,
                    error=error_msg
                )
                
        except Exception as e:
            error_msg = str(e)
            self._fail_operation(operation_id, error_msg)
            return OperationResult(
                operation_id=operation_id,
                success=False,
                error=error_msg
            )
    
    async def get_sandbox_status(self) -> OperationResult:
        """
        Get sandbox system status.
        
        Returns:
            OperationResult with system status
        """
        operation_id = f"get_status_{int(time.time())}"
        
        try:
            self._start_operation(operation_id, "Getting sandbox status", {})
            
            result = await self._call_tool("get_sandbox_status", {
                "api_key": self.api_key
            })
            
            if result.get("success"):
                self._complete_operation(operation_id, result)
                return OperationResult(
                    operation_id=operation_id,
                    success=True,
                    result=result
                )
            else:
                error_msg = result.get("error", "Unknown error")
                self._fail_operation(operation_id, error_msg)
                return OperationResult(
                    operation_id=operation_id,
                    success=False,
                    error=error_msg
                )
                
        except Exception as e:
            error_msg = str(e)
            self._fail_operation(operation_id, error_msg)
            return OperationResult(
                operation_id=operation_id,
                success=False,
                error=error_msg
            )
    
    def add_progress_callback(self, callback: Callable[[ProgressUpdate], None]):
        """Add a progress update callback."""
        self.progress_callbacks.append(callback)
    
    def add_error_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """Add an error callback."""
        self.error_callbacks.append(callback)
    
    def get_active_operations(self) -> List[Dict[str, Any]]:
        """Get list of active operations."""
        return list(self.active_operations.values())
    
    def get_operation_history(self) -> List[OperationResult]:
        """Get operation history."""
        return self.operation_history.copy()
    
    def get_server_info(self) -> Dict[str, Any]:
        """Get server information and capabilities."""
        return {
            "status": self.status.value,
            "capabilities": self.server_capabilities,
            "available_tools": self.available_tools,
            "active_operations": len(self.active_operations),
            "total_operations": len(self.operation_history)
        }
    
    # Internal methods
    
    async def _send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send a request to the MCP server."""
        if self.status != ClientStatus.CONNECTED and method != "initialize":
            raise Exception("Client not connected to server")
        
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params
        }
        
        # Create future for response
        future = asyncio.Future()
        self.pending_requests[self.request_id] = future
        
        # Send request
        request_json = json.dumps(request) + "\n"
        if self.server_process and self.server_process.stdin:
            self.server_process.stdin.write(request_json)
            self.server_process.stdin.flush()
        else:
            raise Exception("Server process not available")
        
        # Wait for response
        try:
            response = await asyncio.wait_for(future, timeout=30.0)
            return response
        except asyncio.TimeoutError:
            self.pending_requests.pop(self.request_id, None)
            raise Exception(f"Request timeout for method: {method}")
    
    async def _send_notification(self, method: str, params: Dict[str, Any]):
        """Send a notification to the MCP server."""
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }
        
        notification_json = json.dumps(notification) + "\n"
        if self.server_process and self.server_process.stdin:
            self.server_process.stdin.write(notification_json)
            self.server_process.stdin.flush()
    
    async def _call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the MCP server."""
        response = await self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        
        if "error" in response:
            raise Exception(f"Tool call error: {response['error']}")
        
        result = response.get("result", {})
        content = result.get("content", [])
        
        if content and len(content) > 0:
            text_content = content[0].get("text", "{}")
            try:
                return json.loads(text_content)
            except json.JSONDecodeError:
                return {"success": False, "error": "Invalid response format"}
        
        return {"success": False, "error": "No content in response"}
    
    async def _read_responses(self):
        """Background task to read responses from the server."""
        try:
            while self.status == ClientStatus.CONNECTED and self.server_process:
                if self.server_process.stdout:
                    line = await asyncio.get_event_loop().run_in_executor(
                        None, self.server_process.stdout.readline
                    )
                    
                    if not line:
                        break
                    
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        response = json.loads(line)
                        await self._handle_response(response)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse server response: {e}")
                        
        except Exception as e:
            logger.error(f"Error reading server responses: {e}")
            self.status = ClientStatus.ERROR
    
    async def _handle_response(self, response: Dict[str, Any]):
        """Handle a response from the server."""
        response_id = response.get("id")
        
        if response_id and response_id in self.pending_requests:
            future = self.pending_requests.pop(response_id)
            if not future.done():
                future.set_result(response)
        else:
            # Handle notifications or other messages
            logger.debug(f"Received server message: {response}")
    
    async def _monitor_operations(self):
        """Background task to monitor operation progress."""
        try:
            while self.status == ClientStatus.CONNECTED:
                # Update progress for active operations
                for operation_id, operation in list(self.active_operations.items()):
                    if operation["status"] == OperationStatus.RUNNING:
                        # Simulate progress updates (in a real implementation, 
                        # this would get actual progress from the server)
                        elapsed = time.time() - operation["start_time"]
                        if elapsed > 1.0:  # Update every second
                            progress = min(90.0, elapsed * 10)  # Simulate progress
                            self._update_progress(operation_id, progress, "Processing...")
                
                await asyncio.sleep(1.0)
                
        except Exception as e:
            logger.error(f"Error monitoring operations: {e}")
    
    def _start_operation(self, operation_id: str, description: str, details: Dict[str, Any]):
        """Start tracking an operation."""
        operation = {
            "id": operation_id,
            "description": description,
            "status": OperationStatus.RUNNING,
            "progress": 0.0,
            "details": details,
            "start_time": time.time()
        }
        
        self.active_operations[operation_id] = operation
        
        # Notify callbacks
        update = ProgressUpdate(
            operation_id=operation_id,
            status=OperationStatus.RUNNING,
            progress_percent=0.0,
            message=f"Started: {description}",
            details=details
        )
        
        for callback in self.progress_callbacks:
            try:
                callback(update)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")
    
    def _update_progress(self, operation_id: str, progress: float, message: str):
        """Update operation progress."""
        if operation_id in self.active_operations:
            operation = self.active_operations[operation_id]
            operation["progress"] = progress
            
            # Notify callbacks
            update = ProgressUpdate(
                operation_id=operation_id,
                status=OperationStatus.RUNNING,
                progress_percent=progress,
                message=message,
                details=operation["details"]
            )
            
            for callback in self.progress_callbacks:
                try:
                    callback(update)
                except Exception as e:
                    logger.error(f"Error in progress callback: {e}")
    
    def _complete_operation(self, operation_id: str, result: Dict[str, Any]):
        """Complete an operation successfully."""
        if operation_id in self.active_operations:
            operation = self.active_operations.pop(operation_id)
            duration = time.time() - operation["start_time"]
            
            # Add to history
            operation_result = OperationResult(
                operation_id=operation_id,
                success=True,
                result=result,
                duration=duration
            )
            self.operation_history.append(operation_result)
            
            # Notify callbacks
            update = ProgressUpdate(
                operation_id=operation_id,
                status=OperationStatus.COMPLETED,
                progress_percent=100.0,
                message=f"Completed: {operation['description']}",
                details=operation["details"]
            )
            
            for callback in self.progress_callbacks:
                try:
                    callback(update)
                except Exception as e:
                    logger.error(f"Error in progress callback: {e}")
    
    def _fail_operation(self, operation_id: str, error: str):
        """Fail an operation with an error."""
        if operation_id in self.active_operations:
            operation = self.active_operations.pop(operation_id)
            duration = time.time() - operation["start_time"]
            
            # Add to history
            operation_result = OperationResult(
                operation_id=operation_id,
                success=False,
                error=error,
                duration=duration
            )
            self.operation_history.append(operation_result)
            
            # Notify callbacks
            update = ProgressUpdate(
                operation_id=operation_id,
                status=OperationStatus.FAILED,
                progress_percent=0.0,
                message=f"Failed: {operation['description']} - {error}",
                details=operation["details"]
            )
            
            for callback in self.progress_callbacks:
                try:
                    callback(update)
                except Exception as e:
                    logger.error(f"Error in progress callback: {e}")
            
            # Notify error callbacks
            for callback in self.error_callbacks:
                try:
                    callback(error, operation["details"])
                except Exception as e:
                    logger.error(f"Error in error callback: {e}")


async def create_sandbox_client(server_command: Optional[List[str]] = None, 
                              api_key: Optional[str] = None) -> SandboxMCPClient:
    """
    Create and connect a sandbox MCP client.
    
    Args:
        server_command: Command to start the MCP server
        api_key: API key for authentication
        
    Returns:
        Connected SandboxMCPClient instance
    """
    client = SandboxMCPClient(server_command, api_key)
    
    if await client.connect():
        return client
    else:
        raise Exception("Failed to connect to sandbox MCP server")