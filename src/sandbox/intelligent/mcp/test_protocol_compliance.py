"""
Unit tests for MCP protocol compliance in the intelligent sandbox system.

Tests cover:
- MCP protocol parsing and validation
- Authentication and authorization
- Request/response handling
- Error handling and recovery
"""

import json
import unittest
import tempfile
import time
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from .protocol import (
    MCPProtocolHandler, MCPCapabilities, MCPServerInfo, MCPRequest, MCPResponse,
    MCPError, MCPErrorCodes, create_protocol_handler
)
from .auth import (
    AuthenticationManager, AuthorizationManager, MCPAuthenticationMiddleware,
    User, Role, Permission, create_auth_managers
)
from .server import IntelligentSandboxMCPServer


class TestMCPProtocolHandler(unittest.TestCase):
    """Test MCP protocol handler functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.capabilities = MCPCapabilities(
            tools=True,
            resources=True,
            prompts=False,
            completion=False,
            logging=True
        )
        
        self.server_info = MCPServerInfo(
            name="Test Sandbox Server",
            version="1.0.0"
        )
        
        self.handler = MCPProtocolHandler(self.capabilities, self.server_info)
    
    def test_parse_valid_request(self):
        """Test parsing of valid MCP requests."""
        request_json = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2.0",
                "capabilities": {}
            }
        })
        
        request = self.handler.parse_request(request_json)
        
        self.assertEqual(request.jsonrpc, "2.0")
        self.assertEqual(request.id, 1)
        self.assertEqual(request.method, "initialize")
        self.assertIn("protocolVersion", request.params)
    
    def test_parse_invalid_json(self):
        """Test parsing of invalid JSON."""
        with self.assertRaises(ValueError) as context:
            self.handler.parse_request("invalid json")
        
        self.assertIn("Invalid JSON", str(context.exception))
    
    def test_parse_missing_required_fields(self):
        """Test parsing requests with missing required fields."""
        # Missing jsonrpc
        with self.assertRaises(ValueError) as context:
            self.handler.parse_request('{"id": 1, "method": "test"}')
        self.assertIn("Missing 'jsonrpc' field", str(context.exception))
        
        # Missing method
        with self.assertRaises(ValueError) as context:
            self.handler.parse_request('{"jsonrpc": "2.0", "id": 1}')
        self.assertIn("Missing 'method' field", str(context.exception))
    
    def test_validate_request_before_initialization(self):
        """Test request validation before server initialization."""
        request = MCPRequest(
            jsonrpc="2.0",
            id=1,
            method="tools/list"
        )
        
        error = self.handler.validate_request(request)
        
        self.assertIsNotNone(error)
        self.assertEqual(error.code, MCPErrorCodes.INVALID_REQUEST)
        self.assertIn("not initialized", error.message)
    
    def test_validate_unknown_method(self):
        """Test validation of unknown methods."""
        # Initialize the handler first
        self.handler.initialized = True
        
        request = MCPRequest(
            jsonrpc="2.0",
            id=1,
            method="unknown/method"
        )
        
        error = self.handler.validate_request(request)
        
        self.assertIsNotNone(error)
        self.assertEqual(error.code, MCPErrorCodes.METHOD_NOT_FOUND)
    
    def test_handle_initialize_request(self):
        """Test initialization request handling."""
        request = MCPRequest(
            jsonrpc="2.0",
            id=1,
            method="initialize",
            params={
                "protocolVersion": "2.0",
                "capabilities": {}
            }
        )
        
        response = self.handler.process_request(request)
        
        self.assertEqual(response.jsonrpc, "2.0")
        self.assertEqual(response.id, 1)
        self.assertIsNone(response.error)
        self.assertIn("protocolVersion", response.result)
        self.assertIn("capabilities", response.result)
        self.assertIn("serverInfo", response.result)
    
    def test_handle_initialized_notification(self):
        """Test initialized notification handling."""
        request = MCPRequest(
            jsonrpc="2.0",
            id=2,
            method="initialized"
        )
        
        response = self.handler.process_request(request)
        
        self.assertTrue(self.handler.initialized)
        self.assertEqual(response.result, {})
    
    def test_create_error_response(self):
        """Test error response creation."""
        error_response = self.handler.create_error_response(
            request_id=1,
            error_code=MCPErrorCodes.INVALID_PARAMS,
            error_message="Invalid parameters",
            error_data={"param": "test"}
        )
        
        self.assertEqual(error_response.id, 1)
        self.assertIsNotNone(error_response.error)
        self.assertEqual(error_response.error["code"], MCPErrorCodes.INVALID_PARAMS)
        self.assertEqual(error_response.error["message"], "Invalid parameters")
        self.assertIn("data", error_response.error)
    
    def test_serialize_response(self):
        """Test response serialization."""
        response = MCPResponse(
            jsonrpc="2.0",
            id=1,
            result={"success": True}
        )
        
        serialized = self.handler.serialize_response(response)
        data = json.loads(serialized)
        
        self.assertEqual(data["jsonrpc"], "2.0")
        self.assertEqual(data["id"], 1)
        self.assertEqual(data["result"]["success"], True)


class TestAuthentication(unittest.TestCase):
    """Test authentication functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.auth_config_path = Path(self.temp_dir) / "test_auth.json"
        self.auth_manager = AuthenticationManager(str(self.auth_config_path))
    
    def test_create_default_admin(self):
        """Test creation of default admin user."""
        # Should have created a default admin user
        self.assertEqual(len(self.auth_manager.users), 1)
        
        admin_user = list(self.auth_manager.users.values())[0]
        self.assertEqual(admin_user.username, "admin")
        self.assertEqual(admin_user.role, Role.ADMIN)
        self.assertEqual(admin_user.permissions, set(Permission))
    
    def test_authenticate_valid_api_key(self):
        """Test authentication with valid API key."""
        admin_user = list(self.auth_manager.users.values())[0]
        api_key = admin_user.api_key
        
        authenticated_user = self.auth_manager.authenticate(api_key)
        
        self.assertIsNotNone(authenticated_user)
        self.assertEqual(authenticated_user.id, admin_user.id)
        self.assertEqual(authenticated_user.username, "admin")
    
    def test_authenticate_invalid_api_key(self):
        """Test authentication with invalid API key."""
        authenticated_user = self.auth_manager.authenticate("invalid_key")
        
        self.assertIsNone(authenticated_user)
    
    def test_rate_limiting(self):
        """Test rate limiting functionality."""
        admin_user = list(self.auth_manager.users.values())[0]
        admin_user.rate_limit = 2  # Set low limit for testing
        api_key = admin_user.api_key
        
        # First two requests should succeed
        self.assertIsNotNone(self.auth_manager.authenticate(api_key))
        self.assertIsNotNone(self.auth_manager.authenticate(api_key))
        
        # Third request should fail due to rate limiting
        self.assertIsNone(self.auth_manager.authenticate(api_key))
    
    def test_session_creation(self):
        """Test session creation and management."""
        admin_user = list(self.auth_manager.users.values())[0]
        
        session = self.auth_manager.create_session(admin_user)
        
        self.assertIsNotNone(session)
        self.assertEqual(session.user_id, admin_user.id)
        self.assertTrue(session.active)
        self.assertIn(session.id, self.auth_manager.sessions)
    
    def test_session_expiration(self):
        """Test session expiration."""
        admin_user = list(self.auth_manager.users.values())[0]
        
        session = self.auth_manager.create_session(admin_user)
        session.expires_at = time.time() - 1  # Expired 1 second ago
        
        retrieved_session = self.auth_manager.get_session(session.id)
        
        self.assertIsNone(retrieved_session)
        self.assertFalse(session.active)


class TestAuthorization(unittest.TestCase):
    """Test authorization functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.authz_manager = AuthorizationManager()
        
        # Create test users with different roles
        self.admin_user = User(
            id="admin_id",
            username="admin",
            api_key="admin_key",
            role=Role.ADMIN,
            permissions=set(Permission)
        )
        
        self.developer_user = User(
            id="dev_id",
            username="developer",
            api_key="dev_key",
            role=Role.DEVELOPER,
            permissions={
                Permission.CREATE_WORKSPACE,
                Permission.ANALYZE_CODEBASE,
                Permission.CREATE_TASK_PLAN,
                Permission.EXECUTE_TASK_PLAN,
                Permission.VIEW_HISTORY,
                Permission.VIEW_STATUS
            }
        )
        
        self.viewer_user = User(
            id="viewer_id",
            username="viewer",
            api_key="viewer_key",
            role=Role.VIEWER,
            permissions={
                Permission.VIEW_HISTORY,
                Permission.VIEW_STATUS
            }
        )
    
    def test_admin_authorization(self):
        """Test admin user authorization."""
        # Admin should be authorized for all operations
        operations = [
            'create_sandbox_workspace',
            'analyze_codebase',
            'create_task_plan',
            'execute_task_plan',
            'get_execution_history',
            'cleanup_workspace',
            'get_sandbox_status',
            'manage_users'
        ]
        
        for operation in operations:
            with self.subTest(operation=operation):
                self.assertTrue(
                    self.authz_manager.authorize(self.admin_user, operation)
                )
    
    def test_developer_authorization(self):
        """Test developer user authorization."""
        # Developer should be authorized for most operations
        allowed_operations = [
            'create_sandbox_workspace',
            'analyze_codebase',
            'create_task_plan',
            'execute_task_plan',
            'get_execution_history',
            'cleanup_workspace',
            'get_sandbox_status'
        ]
        
        denied_operations = [
            'manage_users'
        ]
        
        for operation in allowed_operations:
            with self.subTest(operation=operation):
                self.assertTrue(
                    self.authz_manager.authorize(self.developer_user, operation)
                )
        
        for operation in denied_operations:
            with self.subTest(operation=operation):
                self.assertFalse(
                    self.authz_manager.authorize(self.developer_user, operation)
                )
    
    def test_viewer_authorization(self):
        """Test viewer user authorization."""
        # Viewer should only be authorized for read operations
        allowed_operations = [
            'get_execution_history',
            'get_sandbox_status'
        ]
        
        denied_operations = [
            'create_sandbox_workspace',
            'analyze_codebase',
            'create_task_plan',
            'execute_task_plan',
            'cleanup_workspace',
            'manage_users'
        ]
        
        for operation in allowed_operations:
            with self.subTest(operation=operation):
                self.assertTrue(
                    self.authz_manager.authorize(self.viewer_user, operation)
                )
        
        for operation in denied_operations:
            with self.subTest(operation=operation):
                self.assertFalse(
                    self.authz_manager.authorize(self.viewer_user, operation)
                )
    
    def test_inactive_user_authorization(self):
        """Test authorization for inactive users."""
        self.admin_user.active = False
        
        self.assertFalse(
            self.authz_manager.authorize(self.admin_user, 'get_sandbox_status')
        )


class TestMCPAuthenticationMiddleware(unittest.TestCase):
    """Test MCP authentication middleware."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.auth_config_path = Path(self.temp_dir) / "test_auth.json"
        
        self.auth_manager, self.authz_manager, self.middleware = create_auth_managers(
            str(self.auth_config_path)
        )
        
        # Get the default admin user
        self.admin_user = list(self.auth_manager.users.values())[0]
    
    def test_authenticate_request_with_api_key(self):
        """Test request authentication with API key."""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "get_sandbox_status",
                "arguments": {
                    "api_key": self.admin_user.api_key
                }
            }
        }
        
        auth_context = self.middleware.authenticate_request(request)
        
        self.assertIsNotNone(auth_context)
        self.assertTrue(auth_context['authenticated'])
        self.assertEqual(auth_context['user'].username, "admin")
    
    def test_authenticate_request_without_api_key(self):
        """Test request authentication without API key."""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "get_sandbox_status",
                "arguments": {}
            }
        }
        
        auth_context = self.middleware.authenticate_request(request)
        
        self.assertIsNone(auth_context)
    
    def test_authorize_request(self):
        """Test request authorization."""
        auth_context = {
            'user': self.admin_user,
            'session': Mock(),
            'authenticated': True
        }
        
        # Admin should be authorized for all operations
        self.assertTrue(
            self.middleware.authorize_request(
                auth_context, 'create_sandbox_workspace', {}
            )
        )
    
    def test_create_auth_error_response(self):
        """Test authentication error response creation."""
        response = self.middleware.create_auth_error_response(1, "Invalid API key")
        
        self.assertEqual(response["jsonrpc"], "2.0")
        self.assertEqual(response["id"], 1)
        self.assertIn("error", response)
        self.assertEqual(response["error"]["code"], -32001)
    
    def test_create_authz_error_response(self):
        """Test authorization error response creation."""
        response = self.middleware.create_authz_error_response(1, "create_workspace")
        
        self.assertEqual(response["jsonrpc"], "2.0")
        self.assertEqual(response["id"], 1)
        self.assertIn("error", response)
        self.assertEqual(response["error"]["code"], -32002)


class TestIntelligentSandboxMCPServer(unittest.TestCase):
    """Test the complete MCP server integration."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.auth_config_path = Path(self.temp_dir) / "test_auth.json"
        
        # Mock the core components to avoid complex setup
        with patch('src.sandbox.intelligent.mcp.server.WorkspaceCloner'), \
             patch('src.sandbox.intelligent.mcp.server.CodebaseAnalyzer'), \
             patch('src.sandbox.intelligent.mcp.server.TaskPlanner'), \
             patch('src.sandbox.intelligent.mcp.server.ExecutionEngine'), \
             patch('src.sandbox.intelligent.mcp.server.ActionLogger'), \
             patch('src.sandbox.intelligent.mcp.server.get_config_manager'):
            
            self.server = IntelligentSandboxMCPServer(
                server_name="test-server",
                auth_config_path=str(self.auth_config_path)
            )
    
    def test_server_initialization(self):
        """Test server initialization."""
        self.assertIsNotNone(self.server.auth_manager)
        self.assertIsNotNone(self.server.authz_manager)
        self.assertIsNotNone(self.server.auth_middleware)
        self.assertIsNotNone(self.server.protocol_handler)
        
        # Should have created default admin user
        self.assertEqual(len(self.server.auth_manager.users), 1)
    
    def test_get_server_stats(self):
        """Test server statistics retrieval."""
        stats = self.server.get_server_stats()
        
        self.assertIn("request_stats", stats)
        self.assertIn("active_workspaces", stats)
        self.assertIn("active_sessions", stats)
        self.assertIn("total_users", stats)
        self.assertIn("capabilities", stats)
    
    @patch('sys.stdin')
    @patch('builtins.print')
    def test_stdio_request_processing(self, mock_print, mock_stdin):
        """Test stdio request processing."""
        # Mock stdin to provide a test request
        test_request = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2.0",
                "capabilities": {}
            }
        })
        
        mock_stdin.readline.side_effect = [test_request + '\n', '']  # Empty string to end loop
        
        # This would normally run indefinitely, so we'll just test that it doesn't crash
        try:
            self.server.run_stdio()
        except SystemExit:
            pass  # Expected when stdin ends
        
        # Verify that a response was printed
        self.assertTrue(mock_print.called)


if __name__ == '__main__':
    unittest.main()