"""
Enhanced MCP protocol handlers for the intelligent sandbox system.

This module provides:
- Complete MCP protocol compliance
- Request/response validation
- Error handling and recovery
- Protocol versioning support
"""

import json
import logging
import time
import uuid
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class MCPVersion(Enum):
    """Supported MCP protocol versions."""
    V1_0 = "1.0"
    V2_0 = "2.0"


class RequestType(Enum):
    """MCP request types."""
    INITIALIZE = "initialize"
    INITIALIZED = "initialized"
    TOOLS_LIST = "tools/list"
    TOOLS_CALL = "tools/call"
    RESOURCES_LIST = "resources/list"
    RESOURCES_READ = "resources/read"
    PROMPTS_LIST = "prompts/list"
    PROMPTS_GET = "prompts/get"
    COMPLETION = "completion/complete"
    LOGGING = "logging/setLevel"
    PING = "ping"


@dataclass
class MCPCapabilities:
    """MCP server capabilities."""
    tools: bool = True
    resources: bool = True
    prompts: bool = False
    completion: bool = False
    logging: bool = True
    experimental: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPServerInfo:
    """MCP server information."""
    name: str = "Intelligent Sandbox MCP Server"
    version: str = "1.0.0"
    description: str = "Comprehensive sandbox environment for AI-assisted development"
    author: str = "Sandbox Team"
    license: str = "MIT"
    homepage: str = "https://github.com/sandbox/intelligent-sandbox"


@dataclass
class MCPRequest:
    """Parsed MCP request."""
    jsonrpc: str
    id: Optional[Any]
    method: str
    params: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class MCPResponse:
    """MCP response structure."""
    jsonrpc: str
    id: Optional[Any]
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class MCPError:
    """MCP error structure."""
    code: int
    message: str
    data: Optional[Dict[str, Any]] = None


class MCPErrorCodes:
    """Standard MCP error codes."""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    
    # Custom error codes
    AUTHENTICATION_ERROR = -32001
    AUTHORIZATION_ERROR = -32002
    RESOURCE_NOT_FOUND = -32003
    RESOURCE_BUSY = -32004
    RATE_LIMIT_EXCEEDED = -32005
    VALIDATION_ERROR = -32006


class MCPProtocolHandler:
    """Handles MCP protocol parsing, validation, and response generation."""
    
    def __init__(self, capabilities: Optional[MCPCapabilities] = None, 
                 server_info: Optional[MCPServerInfo] = None):
        self.capabilities = capabilities or MCPCapabilities()
        self.server_info = server_info or MCPServerInfo()
        self.supported_versions = [MCPVersion.V2_0, MCPVersion.V1_0]
        self.initialized = False
        self.client_capabilities = {}
        self.protocol_version = MCPVersion.V2_0
        
        # Request handlers
        self.request_handlers: Dict[str, Callable] = {}
        self._register_core_handlers()
    
    def _register_core_handlers(self):
        """Register core MCP protocol handlers."""
        self.request_handlers.update({
            RequestType.INITIALIZE.value: self._handle_initialize,
            RequestType.INITIALIZED.value: self._handle_initialized,
            RequestType.TOOLS_LIST.value: self._handle_tools_list,
            RequestType.TOOLS_CALL.value: self._handle_tools_call,
            RequestType.RESOURCES_LIST.value: self._handle_resources_list,
            RequestType.RESOURCES_READ.value: self._handle_resources_read,
            RequestType.PROMPTS_LIST.value: self._handle_prompts_list,
            RequestType.PROMPTS_GET.value: self._handle_prompts_get,
            RequestType.COMPLETION.value: self._handle_completion,
            RequestType.LOGGING.value: self._handle_logging,
            RequestType.PING.value: self._handle_ping
        })
    
    def register_handler(self, method: str, handler: Callable):
        """Register a custom request handler."""
        self.request_handlers[method] = handler
    
    def parse_request(self, raw_request: str) -> MCPRequest:
        """
        Parse a raw MCP request.
        
        Args:
            raw_request: Raw JSON-RPC request string
            
        Returns:
            Parsed MCPRequest object
            
        Raises:
            ValueError: If request is invalid
        """
        try:
            data = json.loads(raw_request)
            
            # Validate required fields
            if not isinstance(data, dict):
                raise ValueError("Request must be a JSON object")
            
            if "jsonrpc" not in data:
                raise ValueError("Missing 'jsonrpc' field")
            
            if data["jsonrpc"] not in ["1.0", "2.0"]:
                raise ValueError(f"Unsupported JSON-RPC version: {data['jsonrpc']}")
            
            if "method" not in data:
                raise ValueError("Missing 'method' field")
            
            return MCPRequest(
                jsonrpc=data["jsonrpc"],
                id=data.get("id"),
                method=data["method"],
                params=data.get("params", {}),
                meta=data.get("meta", {})
            )
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
        except Exception as e:
            raise ValueError(f"Request parsing error: {e}")
    
    def create_response(self, request: MCPRequest, result: Optional[Dict[str, Any]] = None,
                       error: Optional[MCPError] = None) -> MCPResponse:
        """
        Create an MCP response.
        
        Args:
            request: The original request
            result: Success result data
            error: Error information
            
        Returns:
            MCPResponse object
        """
        response = MCPResponse(
            jsonrpc=request.jsonrpc,
            id=request.id
        )
        
        if error:
            response.error = {
                "code": error.code,
                "message": error.message
            }
            if error.data:
                response.error["data"] = error.data
        else:
            response.result = result or {}
        
        return response
    
    def create_error_response(self, request_id: Optional[Any], error_code: int, 
                            error_message: str, error_data: Optional[Dict[str, Any]] = None,
                            jsonrpc: str = "1.0") -> MCPResponse:
        """Create an error response."""
        error = MCPError(
            code=error_code,
            message=error_message,
            data=error_data
        )
        
        # Create a minimal request for response generation
        dummy_request = MCPRequest(
            jsonrpc=jsonrpc,
            id=request_id,
            method="error"
        )
        
        return self.create_response(dummy_request, error=error)
    
    def serialize_response(self, response: MCPResponse) -> str:
        """Serialize an MCP response to JSON."""
        data = {
            "jsonrpc": response.jsonrpc,
            "id": response.id
        }
        
        if response.error:
            data["error"] = response.error
        else:
            data["result"] = response.result
        
        return json.dumps(data)
    
    def validate_request(self, request: MCPRequest) -> Optional[MCPError]:
        """
        Validate an MCP request.
        
        Args:
            request: The request to validate
            
        Returns:
            MCPError if validation fails, None if valid
        """
        # Check if server is initialized for non-initialization requests
        if request.method != RequestType.INITIALIZE.value and not self.initialized:
            return MCPError(
                code=MCPErrorCodes.INVALID_REQUEST,
                message="Server not initialized",
                data={"method": request.method}
            )
        
        # Check if method is supported
        if request.method not in self.request_handlers:
            return MCPError(
                code=MCPErrorCodes.METHOD_NOT_FOUND,
                message=f"Method not found: {request.method}",
                data={"method": request.method}
            )
        
        # Validate parameters based on method
        validation_error = self._validate_method_params(request)
        if validation_error:
            return validation_error
        
        return None
    
    def _validate_method_params(self, request: MCPRequest) -> Optional[MCPError]:
        """Validate method-specific parameters."""
        method = request.method
        params = request.params
        
        # Define required parameters for each method
        required_params = {
            RequestType.TOOLS_CALL.value: ["name"],
            RequestType.RESOURCES_READ.value: ["uri"],
            RequestType.PROMPTS_GET.value: ["name"]
        }
        
        if method in required_params:
            for param in required_params[method]:
                if param not in params:
                    return MCPError(
                        code=MCPErrorCodes.INVALID_PARAMS,
                        message=f"Missing required parameter: {param}",
                        data={"method": method, "missing_param": param}
                    )
        
        return None
    
    def process_request(self, request: MCPRequest) -> MCPResponse:
        """
        Process an MCP request and generate a response.
        
        Args:
            request: The parsed request
            
        Returns:
            MCPResponse object
        """
        try:
            # Validate request
            validation_error = self.validate_request(request)
            if validation_error:
                return self.create_response(request, error=validation_error)
            
            # Get handler for the method
            handler = self.request_handlers.get(request.method)
            if not handler:
                error = MCPError(
                    code=MCPErrorCodes.METHOD_NOT_FOUND,
                    message=f"No handler for method: {request.method}"
                )
                return self.create_response(request, error=error)
            
            # Call the handler
            result = handler(request)
            return self.create_response(request, result=result)
            
        except Exception as e:
            logger.error(f"Error processing request {request.method}: {e}")
            error = MCPError(
                code=MCPErrorCodes.INTERNAL_ERROR,
                message="Internal server error",
                data={"details": str(e)}
            )
            return self.create_response(request, error=error)
    
    # Core protocol handlers
    
    def _handle_initialize(self, request: MCPRequest) -> Dict[str, Any]:
        """Handle initialization request."""
        params = request.params
        
        # Extract client capabilities
        self.client_capabilities = params.get("capabilities", {})
        
        # Determine protocol version
        client_version = params.get("protocolVersion", "2.0")
        if client_version in [v.value for v in self.supported_versions]:
            self.protocol_version = MCPVersion(client_version)
        else:
            # Default to v2.0 for compatibility
            self.protocol_version = MCPVersion.V2_0
        
        # Build capabilities object, only including enabled capabilities
        capabilities_obj = {}
        
        if self.capabilities.tools:
            capabilities_obj["tools"] = {"listChanged": True}
        
        if self.capabilities.resources:
            capabilities_obj["resources"] = {
                "subscribe": True,
                "listChanged": True
            }
        
        if self.capabilities.prompts:
            capabilities_obj["prompts"] = {"listChanged": True}
        
        if self.capabilities.completion:
            capabilities_obj["completion"] = {"argument": True}
        
        if self.capabilities.logging:
            capabilities_obj["logging"] = {}
        
        if hasattr(self.capabilities, 'experimental') and self.capabilities.experimental:
            capabilities_obj["experimental"] = self.capabilities.experimental
        
        return {
            "protocolVersion": self.protocol_version.value,
            "capabilities": capabilities_obj,
            "serverInfo": {
                "name": self.server_info.name,
                "version": self.server_info.version,
                "description": self.server_info.description,
                "author": self.server_info.author,
                "license": self.server_info.license,
                "homepage": self.server_info.homepage
            }
        }
    
    def _handle_initialized(self, request: MCPRequest) -> Dict[str, Any]:
        """Handle initialized notification."""
        self.initialized = True
        logger.info("MCP server initialized successfully")
        return {}
    
    def _handle_tools_list(self, request: MCPRequest) -> Dict[str, Any]:
        """Handle tools list request."""
        # This will be overridden by the actual server implementation
        return {
            "tools": []
        }
    
    def _handle_tools_call(self, request: MCPRequest) -> Dict[str, Any]:
        """Handle tool call request."""
        # This will be overridden by the actual server implementation
        tool_name = request.params.get("name")
        arguments = request.params.get("arguments", {})
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Tool {tool_name} called with arguments: {arguments}"
                }
            ]
        }
    
    def _handle_resources_list(self, request: MCPRequest) -> Dict[str, Any]:
        """Handle resources list request."""
        return {
            "resources": []
        }
    
    def _handle_resources_read(self, request: MCPRequest) -> Dict[str, Any]:
        """Handle resource read request."""
        uri = request.params.get("uri")
        
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "text/plain",
                    "text": f"Resource content for {uri}"
                }
            ]
        }
    
    def _handle_prompts_list(self, request: MCPRequest) -> Dict[str, Any]:
        """Handle prompts list request."""
        return {
            "prompts": []
        }
    
    def _handle_prompts_get(self, request: MCPRequest) -> Dict[str, Any]:
        """Handle prompt get request."""
        name = request.params.get("name")
        arguments = request.params.get("arguments", {})
        
        return {
            "description": f"Prompt {name}",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": f"Prompt {name} with arguments: {arguments}"
                    }
                }
            ]
        }
    
    def _handle_completion(self, request: MCPRequest) -> Dict[str, Any]:
        """Handle completion request."""
        return {
            "completion": {
                "values": [],
                "total": 0,
                "hasMore": False
            }
        }
    
    def _handle_logging(self, request: MCPRequest) -> Dict[str, Any]:
        """Handle logging level set request."""
        level = request.params.get("level", "info")
        logger.info(f"Logging level set to: {level}")
        return {}
    
    def _handle_ping(self, request: MCPRequest) -> Dict[str, Any]:
        """Handle ping request."""
        return {
            "pong": True,
            "timestamp": time.time(),
            "server": self.server_info.name
        }


class MCPRequestValidator:
    """Validates MCP requests for security and correctness."""
    
    def __init__(self):
        self.max_request_size = 10 * 1024 * 1024  # 10MB
        self.max_params_depth = 10
        self.blocked_methods = set()
    
    def validate_request_size(self, raw_request: str) -> bool:
        """Validate request size limits."""
        return len(raw_request.encode('utf-8')) <= self.max_request_size
    
    def validate_params_depth(self, params: Dict[str, Any], current_depth: int = 0) -> bool:
        """Validate parameter nesting depth."""
        if current_depth > self.max_params_depth:
            return False
        
        for value in params.values():
            if isinstance(value, dict):
                if not self.validate_params_depth(value, current_depth + 1):
                    return False
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        if not self.validate_params_depth(item, current_depth + 1):
                            return False
        
        return True
    
    def validate_method_security(self, method: str) -> bool:
        """Validate method against security restrictions."""
        return method not in self.blocked_methods
    
    def sanitize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize request parameters."""
        # Remove potentially dangerous parameters
        dangerous_keys = ['__proto__', 'constructor', 'prototype']
        
        def clean_dict(d):
            if isinstance(d, dict):
                return {
                    k: clean_dict(v) for k, v in d.items()
                    if k not in dangerous_keys
                }
            elif isinstance(d, list):
                return [clean_dict(item) for item in d]
            else:
                return d
        
        return clean_dict(params)


def create_protocol_handler(capabilities: Optional[MCPCapabilities] = None,
                          server_info: Optional[MCPServerInfo] = None) -> MCPProtocolHandler:
    """
    Create a configured MCP protocol handler.
    
    Args:
        capabilities: Server capabilities
        server_info: Server information
        
    Returns:
        Configured MCPProtocolHandler instance
    """
    return MCPProtocolHandler(capabilities, server_info)