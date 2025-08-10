"""
Integration tests for the intelligent sandbox MCP system.

Tests cover:
- Complete user workflows from task submission to completion
- Real-time progress updates and status notifications
- Error reporting and retry interfaces
- Client-server communication and protocol compliance
"""

import asyncio
import unittest
import tempfile
import time
import json
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path
from typing import Dict, Any, List

from .client import SandboxMCPClient, ProgressUpdate, OperationResult, OperationStatus, ClientStatus
from .ui import InteractiveCLI, StatusDisplay, ProgressBar
from .server import IntelligentSandboxMCPServer


class TestSandboxMCPClient(unittest.IsolatedAsyncioTestCase):
    """Test the sandbox MCP client functionality."""
    
    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.api_key = "test_api_key"
        
        # Mock server process
        self.mock_process = Mock()
        self.mock_process.stdin = Mock()
        self.mock_process.stdout = Mock()
        self.mock_process.stderr = Mock()
        self.mock_process.terminate = Mock()
        self.mock_process.wait = Mock()
        self.mock_process.kill = Mock()
        
        # Create client with mocked server
        self.client = SandboxMCPClient(api_key=self.api_key)
        
        # Track progress updates and errors
        self.progress_updates: List[ProgressUpdate] = []
        self.errors: List[tuple] = []
        
        self.client.add_progress_callback(self._on_progress)
        self.client.add_error_callback(self._on_error)
    
    def _on_progress(self, update: ProgressUpdate):
        """Track progress updates."""
        self.progress_updates.append(update)
    
    def _on_error(self, error: str, details: Dict[str, Any]):
        """Track errors."""
        self.errors.append((error, details))
    
    @patch('subprocess.Popen')
    async def test_client_connection(self, mock_popen):
        """Test client connection to server."""
        # Mock server responses
        mock_popen.return_value = self.mock_process
        
        # Mock initialization response
        init_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": "2.0",
                "capabilities": {
                    "tools": {"listChanged": True},
                    "resources": {"subscribe": True}
                },
                "serverInfo": {
                    "name": "Test Server",
                    "version": "1.0.0"
                }
            }
        }
        
        tools_response = {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {
                "tools": [
                    {
                        "name": "create_sandbox_workspace",
                        "description": "Create workspace"
                    }
                ]
            }
        }
        
        # Mock readline to return responses
        self.mock_process.stdout.readline.side_effect = [
            json.dumps(init_response) + "\n",
            json.dumps(tools_response) + "\n"
        ]
        
        # Test connection
        connected = await self.client.connect()
        
        self.assertTrue(connected)
        self.assertEqual(self.client.status, ClientStatus.CONNECTED)
        self.assertIn("tools", self.client.server_capabilities)
        self.assertEqual(len(self.client.available_tools), 1)
    
    @patch('subprocess.Popen')
    async def test_create_workspace_workflow(self, mock_popen):
        """Test complete workspace creation workflow."""
        mock_popen.return_value = self.mock_process
        
        # Mock server responses for connection
        self._setup_connection_mocks()
        
        # Connect client
        await self.client.connect()
        
        # Mock workspace creation response
        workspace_response = {
            "jsonrpc": "2.0",
            "id": 3,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "success": True,
                            "workspace_id": "test_workspace_123",
                            "sandbox_path": "/tmp/sandbox/test_workspace_123",
                            "status": "active"
                        })
                    }
                ]
            }
        }
        
        self.mock_process.stdout.readline.side_effect.append(
            json.dumps(workspace_response) + "\n"
        )
        
        # Test workspace creation
        result = await self.client.create_workspace("/test/source/path")
        
        self.assertTrue(result.success)
        self.assertIn("workspace_id", result.result)
        self.assertEqual(result.result["workspace_id"], "test_workspace_123")
        
        # Verify progress updates were sent
        self.assertGreater(len(self.progress_updates), 0)
        self.assertEqual(self.progress_updates[0].status, OperationStatus.RUNNING)
        self.assertEqual(self.progress_updates[-1].status, OperationStatus.COMPLETED)
    
    @patch('subprocess.Popen')
    async def test_error_handling_workflow(self, mock_popen):
        """Test error handling and reporting."""
        mock_popen.return_value = self.mock_process
        
        # Mock server responses for connection
        self._setup_connection_mocks()
        
        # Connect client
        await self.client.connect()
        
        # Mock error response
        error_response = {
            "jsonrpc": "2.0",
            "id": 3,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "success": False,
                            "error": "Source path not found"
                        })
                    }
                ]
            }
        }
        
        self.mock_process.stdout.readline.side_effect.append(
            json.dumps(error_response) + "\n"
        )
        
        # Test error handling
        result = await self.client.create_workspace("/nonexistent/path")
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Source path not found")
        
        # Verify error callbacks were called
        self.assertGreater(len(self.errors), 0)
        self.assertIn("Source path not found", self.errors[0][0])
        
        # Verify progress updates show failure
        failed_updates = [u for u in self.progress_updates if u.status == OperationStatus.FAILED]
        self.assertGreater(len(failed_updates), 0)
    
    @patch('subprocess.Popen')
    async def test_multiple_operations_workflow(self, mock_popen):
        """Test handling multiple concurrent operations."""
        mock_popen.return_value = self.mock_process
        
        # Mock server responses for connection
        self._setup_connection_mocks()
        
        # Connect client
        await self.client.connect()
        
        # Mock responses for multiple operations
        responses = [
            {
                "jsonrpc": "2.0",
                "id": 3,
                "result": {
                    "content": [{"type": "text", "text": json.dumps({"success": True, "workspace_id": "ws1"})}]
                }
            },
            {
                "jsonrpc": "2.0",
                "id": 4,
                "result": {
                    "content": [{"type": "text", "text": json.dumps({"success": True, "workspace_id": "ws2"})}]
                }
            }
        ]
        
        for response in responses:
            self.mock_process.stdout.readline.side_effect.append(
                json.dumps(response) + "\n"
            )
        
        # Start multiple operations
        task1 = asyncio.create_task(self.client.create_workspace("/path1"))
        task2 = asyncio.create_task(self.client.create_workspace("/path2"))
        
        # Wait for completion
        results = await asyncio.gather(task1, task2)
        
        # Verify both operations completed successfully
        self.assertTrue(all(r.success for r in results))
        self.assertEqual(results[0].result["workspace_id"], "ws1")
        self.assertEqual(results[1].result["workspace_id"], "ws2")
        
        # Verify operation tracking
        history = self.client.get_operation_history()
        self.assertEqual(len(history), 2)
    
    def _setup_connection_mocks(self):
        """Set up mock responses for client connection."""
        init_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": "2.0",
                "capabilities": {"tools": {"listChanged": True}},
                "serverInfo": {"name": "Test Server", "version": "1.0.0"}
            }
        }
        
        tools_response = {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {"tools": [{"name": "create_sandbox_workspace"}]}
        }
        
        self.mock_process.stdout.readline.side_effect = [
            json.dumps(init_response) + "\n",
            json.dumps(tools_response) + "\n"
        ]
    
    async def asyncTearDown(self):
        """Clean up test fixtures."""
        if self.client.status == ClientStatus.CONNECTED:
            await self.client.disconnect()


class TestProgressAndStatusUpdates(unittest.TestCase):
    """Test progress tracking and status updates."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.status_display = StatusDisplay()
        self.progress_bar = ProgressBar()
    
    def test_progress_bar_rendering(self):
        """Test progress bar rendering."""
        # Test 0% progress
        bar = self.progress_bar.render(0.0, "Starting...")
        self.assertIn("0.0%", bar)
        self.assertIn("Starting...", bar)
        
        # Test 50% progress
        bar = self.progress_bar.render(50.0, "Processing...")
        self.assertIn("50.0%", bar)
        self.assertIn("Processing...", bar)
        
        # Test 100% progress
        bar = self.progress_bar.render(100.0, "Complete!")
        self.assertIn("100.0%", bar)
        self.assertIn("Complete!", bar)
    
    def test_status_display_updates(self):
        """Test status display operation tracking."""
        # Create test progress update
        update = ProgressUpdate(
            operation_id="test_op_1",
            status=OperationStatus.RUNNING,
            progress_percent=25.0,
            message="Processing files...",
            details={"file_count": 10}
        )
        
        # Update status display
        self.status_display.update_operation(update)
        
        # Verify operation is tracked
        self.assertIn("test_op_1", self.status_display.active_operations)
        
        operation = self.status_display.active_operations["test_op_1"]
        self.assertEqual(operation["status"], OperationStatus.RUNNING)
        self.assertEqual(operation["progress"], 25.0)
        self.assertEqual(operation["message"], "Processing files...")
    
    def test_operation_completion_tracking(self):
        """Test operation completion and removal."""
        # Add operation
        update = ProgressUpdate(
            operation_id="test_op_2",
            status=OperationStatus.RUNNING,
            progress_percent=50.0,
            message="In progress..."
        )
        self.status_display.update_operation(update)
        
        # Complete operation
        completion_update = ProgressUpdate(
            operation_id="test_op_2",
            status=OperationStatus.COMPLETED,
            progress_percent=100.0,
            message="Completed successfully!"
        )
        self.status_display.update_operation(completion_update)
        
        # Verify status updated
        operation = self.status_display.active_operations["test_op_2"]
        self.assertEqual(operation["status"], OperationStatus.COMPLETED)
        self.assertEqual(operation["progress"], 100.0)
        
        # Remove completed operation
        self.status_display.remove_operation("test_op_2")
        self.assertNotIn("test_op_2", self.status_display.active_operations)


class TestInteractiveCLI(unittest.IsolatedAsyncioTestCase):
    """Test interactive CLI functionality."""
    
    async def asyncSetUp(self):
        """Set up test fixtures."""
        # Create mock client
        self.mock_client = Mock(spec=SandboxMCPClient)
        self.mock_client.status = ClientStatus.CONNECTED
        self.mock_client.get_active_operations.return_value = []
        self.mock_client.get_operation_history.return_value = []
        self.mock_client.add_progress_callback = Mock()
        self.mock_client.add_error_callback = Mock()
        
        # Create CLI
        self.cli = InteractiveCLI(self.mock_client)
    
    def test_cli_initialization(self):
        """Test CLI initialization."""
        self.assertEqual(self.cli.client, self.mock_client)
        self.assertIsNotNone(self.cli.status_display)
        self.assertFalse(self.cli.running)
        
        # Verify callbacks were registered
        self.mock_client.add_progress_callback.assert_called_once()
        self.mock_client.add_error_callback.assert_called_once()
    
    async def test_command_parsing(self):
        """Test command parsing and execution."""
        # Mock successful operations
        self.mock_client.get_sandbox_status.return_value = OperationResult(
            operation_id="status_op",
            success=True,
            result={"system_status": {"active_workspaces": 2}}
        )
        
        # Test status command
        await self.cli._execute_command("status")
        self.mock_client.get_sandbox_status.assert_called_once()
        
        # Test create command
        self.mock_client.create_workspace.return_value = OperationResult(
            operation_id="create_op",
            success=True,
            result={"workspace_id": "test_ws"}
        )
        
        await self.cli._execute_command("create /test/path")
        self.mock_client.create_workspace.assert_called_once_with("/test/path", None)
    
    def test_progress_callback_handling(self):
        """Test progress update handling in CLI."""
        # Create test progress update
        update = ProgressUpdate(
            operation_id="test_op",
            status=OperationStatus.RUNNING,
            progress_percent=75.0,
            message="Almost done..."
        )
        
        # Call progress callback
        self.cli._on_progress_update(update)
        
        # Verify status display was updated
        self.assertIn("test_op", self.cli.status_display.active_operations)
    
    def test_error_callback_handling(self):
        """Test error handling in CLI."""
        # Test error callback
        error_message = "Test error occurred"
        error_details = {"code": 500, "context": "test"}
        
        # This should not raise an exception
        self.cli._on_error(error_message, error_details)


class TestEndToEndWorkflows(unittest.IsolatedAsyncioTestCase):
    """Test complete end-to-end workflows."""
    
    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test workspace structure
        self.test_workspace = Path(self.temp_dir) / "test_workspace"
        self.test_workspace.mkdir()
        (self.test_workspace / "main.py").write_text("print('Hello, World!')")
        (self.test_workspace / "requirements.txt").write_text("requests==2.25.1")
    
    @patch('src.sandbox.intelligent.mcp.server.WorkspaceCloner')
    @patch('src.sandbox.intelligent.mcp.server.CodebaseAnalyzer')
    @patch('src.sandbox.intelligent.mcp.server.TaskPlanner')
    @patch('src.sandbox.intelligent.mcp.server.ExecutionEngine')
    @patch('src.sandbox.intelligent.mcp.server.ActionLogger')
    @patch('src.sandbox.intelligent.mcp.server.get_config_manager')
    async def test_complete_development_workflow(self, mock_config, mock_logger, 
                                               mock_engine, mock_planner, 
                                               mock_analyzer, mock_cloner):
        """Test a complete development workflow from start to finish."""
        # Mock the core components
        mock_config.return_value.config = Mock()
        mock_config.return_value.config.default_isolation_enabled = True
        mock_config.return_value.config.default_container_image = "python:3.11"
        mock_config.return_value.config.max_concurrent_sandboxes = 10
        mock_config.return_value.config.default_command_timeout = 300
        
        # Mock workspace cloner
        mock_workspace = Mock()
        mock_workspace.id = "test_workspace_123"
        mock_workspace.sandbox_path = str(self.test_workspace)
        mock_workspace.status = Mock()
        mock_workspace.status.value = "active"
        mock_workspace.isolation_config = Mock()
        mock_workspace.isolation_config.use_docker = True
        mock_workspace.created_at = Mock()
        mock_workspace.created_at.isoformat.return_value = "2023-01-01T00:00:00"
        
        mock_cloner.return_value.clone_workspace.return_value = mock_workspace
        mock_cloner.return_value.setup_isolation.return_value = True
        mock_cloner.return_value.cleanup_workspace.return_value = True
        
        # Mock codebase analyzer
        mock_analysis = Mock()
        mock_analysis.structure.languages = ["Python"]
        mock_analysis.structure.frameworks = ["Flask"]
        mock_analysis.dependencies.dependencies = ["requests"]
        mock_analysis.patterns = []
        mock_analysis.metrics.lines_of_code = 100
        mock_analysis.metrics.complexity_score = 5.2
        mock_analysis.metrics.test_coverage = 85.0
        mock_analysis.summary = "Simple Python web application"
        mock_analysis.analysis_timestamp = Mock()
        mock_analysis.analysis_timestamp.isoformat.return_value = "2023-01-01T00:01:00"
        
        mock_analyzer.return_value.analyze_codebase.return_value = mock_analysis
        
        # Mock task planner
        mock_plan = Mock()
        mock_plan.id = "plan_123"
        mock_plan.description = "Add new feature"
        mock_plan.tasks = [Mock(), Mock(), Mock()]  # 3 tasks
        mock_plan.status = Mock()
        mock_plan.status.value = "created"
        mock_plan.approval_status = Mock()
        mock_plan.approval_status.value = "pending"
        mock_plan.created_at = Mock()
        mock_plan.created_at.isoformat.return_value = "2023-01-01T00:02:00"
        
        for i, task in enumerate(mock_plan.tasks):
            task.id = f"task_{i+1}"
            task.description = f"Task {i+1} description"
            task.status = Mock()
            task.status.value = "not_started"
        
        mock_planner.return_value.create_plan.return_value = mock_plan
        mock_planner.return_value.get_plan.return_value = mock_plan
        
        # Mock execution engine
        mock_result = Mock()
        mock_result.success = True
        mock_result.plan_id = "plan_123"
        mock_result.tasks_completed = 3
        mock_result.tasks_failed = 0
        mock_result.total_duration = 45.5
        mock_result.summary = "All tasks completed successfully"
        
        mock_engine.return_value.execute_plan.return_value = mock_result
        
        # Mock action logger
        mock_logger.return_value.log_action = Mock()
        mock_logger.return_value.get_execution_history.return_value = []
        mock_logger.return_value.get_log_summary.return_value = Mock(
            total_actions=10,
            files_modified=3,
            commands_executed=5,
            errors_encountered=0
        )
        
        # Create server with mocked components
        auth_config_path = Path(self.temp_dir) / "auth.json"
        server = IntelligentSandboxMCPServer(
            server_name="test-server",
            auth_config_path=str(auth_config_path)
        )
        
        # Get admin API key
        admin_user = list(server.auth_manager.users.values())[0]
        api_key = admin_user.api_key
        
        # Test complete workflow
        
        # 1. Create workspace
        create_result = server._tool_create_sandbox_workspace({
            'source_path': str(self.test_workspace),
            'workspace_id': None,
            'api_key': api_key
        }, {'user': admin_user, 'session': Mock()})
        
        self.assertTrue(create_result['success'])
        workspace_id = create_result['workspace_id']
        
        # 2. Analyze codebase
        analyze_result = server._tool_analyze_codebase({
            'workspace_id': workspace_id,
            'api_key': api_key
        }, {'user': admin_user, 'session': Mock()})
        
        self.assertTrue(analyze_result['success'])
        self.assertIn('analysis', analyze_result)
        self.assertEqual(analyze_result['analysis']['languages'], ["Python"])
        
        # 3. Create task plan
        plan_result = server._tool_create_task_plan({
            'workspace_id': workspace_id,
            'task_description': 'Add new feature to the application',
            'api_key': api_key
        }, {'user': admin_user, 'session': Mock()})
        
        self.assertTrue(plan_result['success'])
        plan_id = plan_result['plan_id']
        self.assertEqual(plan_result['tasks_count'], 3)
        
        # 4. Execute task plan
        execute_result = server._tool_execute_task_plan({
            'plan_id': plan_id,
            'api_key': api_key
        }, {'user': admin_user, 'session': Mock()})
        
        self.assertTrue(execute_result['success'])
        self.assertEqual(execute_result['tasks_completed'], 3)
        self.assertEqual(execute_result['tasks_failed'], 0)
        
        # 5. Get execution history
        history_result = server._tool_get_execution_history({
            'workspace_id': workspace_id,
            'api_key': api_key
        }, {'user': admin_user, 'session': Mock()})
        
        self.assertTrue(history_result['success'])
        self.assertEqual(history_result['total_actions'], 10)
        
        # 6. Get system status
        status_result = server._tool_get_sandbox_status({
            'api_key': api_key
        }, {'user': admin_user, 'session': Mock()})
        
        self.assertTrue(status_result['success'])
        self.assertIn('system_status', status_result)
        
        # 7. Cleanup workspace
        cleanup_result = server._tool_cleanup_workspace({
            'workspace_id': workspace_id,
            'api_key': api_key
        }, {'user': admin_user, 'session': Mock()})
        
        self.assertTrue(cleanup_result['success'])
        
        # Verify all components were called appropriately
        mock_cloner.return_value.clone_workspace.assert_called_once()
        mock_analyzer.return_value.analyze_codebase.assert_called_once()
        mock_planner.return_value.create_plan.assert_called_once()
        mock_engine.return_value.execute_plan.assert_called_once()
        mock_cloner.return_value.cleanup_workspace.assert_called_once()


if __name__ == '__main__':
    unittest.main()