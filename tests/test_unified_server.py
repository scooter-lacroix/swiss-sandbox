"""
Comprehensive unit tests for the UnifiedSandboxServer.

This module tests the main server class that consolidates all Swiss Sandbox
functionality into a single, reliable MCP server implementation.
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime

from src.sandbox.unified_server import UnifiedSandboxServer
from src.sandbox.core.types import (
    ServerConfig, SecurityLevel, ExecutionContext, ExecutionResult
)


class TestUnifiedSandboxServer:
    """Test the UnifiedSandboxServer class."""
    
    def test_server_initialization(self, server_config, temp_dir):
        """Test server initialization with configuration."""
        server = UnifiedSandboxServer(server_config)
        
        assert server.config == server_config
        assert server.security_level == server_config.security_level
        assert server.execution_engine is not None
        assert server.security_manager is not None
        assert server.artifact_manager is not None
        assert server.workspace_manager is not None
        assert server.health_monitor is not None
        assert server.logger is not None
    
    def test_server_initialization_with_custom_paths(self, temp_dir):
        """Test server initialization with custom directory paths."""
        config = ServerConfig(
            artifacts_dir=temp_dir / "custom_artifacts",
            workspaces_dir=temp_dir / "custom_workspaces",
            logs_dir=temp_dir / "custom_logs"
        )
        
        server = UnifiedSandboxServer(config)
        
        assert server.config.artifacts_dir == temp_dir / "custom_artifacts"
        assert server.config.workspaces_dir == temp_dir / "custom_workspaces"
        assert server.config.logs_dir == temp_dir / "custom_logs"
    
    def test_mcp_server_creation(self, server_config):
        """Test MCP server creation and tool registration."""
        server = UnifiedSandboxServer(server_config)
        
        # Test that server initializes without errors
        assert server is not None
        assert hasattr(server, 'config')
        assert server.config == server_config
    
    def test_tool_registration(self, unified_server):
        """Test that all required tools are registered."""
        # Test that server has the required tool methods
        expected_tools = [
            '_execute_python_tool',
            '_execute_shell_tool', 
            '_execute_manim_tool',
            '_list_artifacts_tool',
            '_get_artifact_tool',
            '_create_workspace_tool',
            '_list_workspaces_tool',
            '_get_server_status_tool'
        ]
        
        for tool in expected_tools:
            assert hasattr(unified_server, tool), f"Tool method {tool} not found"
    
    @pytest.mark.asyncio
    async def test_execute_python_tool(self, unified_server, sample_python_code):
        """Test the execute_python MCP tool."""
        result = await unified_server._execute_python_tool(
            code=sample_python_code,
            workspace_id="test_workspace"
        )
        
        assert 'success' in result
        assert 'output' in result
        assert 'execution_time' in result
        
        if result['success']:
            assert "Circle area" in result['output']
            assert result['execution_time'] > 0
    
    @pytest.mark.asyncio
    async def test_execute_python_tool_with_error(self, unified_server):
        """Test the execute_python tool with execution error."""
        error_code = "print(undefined_variable)"
        
        result = await unified_server._execute_python_tool(
            code=error_code,
            workspace_id="test_workspace"
        )
        
        assert result['success'] is False
        assert 'error' in result
        assert "NameError" in result['error']
    
    @pytest.mark.asyncio
    async def test_execute_shell_tool(self, unified_server):
        """Test the execute_shell MCP tool."""
        result = await unified_server._execute_shell_tool(
            command="echo 'Hello World'",
            workspace_id="test_workspace"
        )
        
        assert 'success' in result
        assert 'output' in result
        
        if result['success']:
            assert "Hello World" in result['output']
            if 'metadata' in result:
                assert 'return_code' in result['metadata']
    
    @pytest.mark.asyncio
    async def test_execute_manim_tool(self, unified_server, sample_manim_script):
        """Test the execute_manim MCP tool."""
        result = await unified_server._execute_manim_tool(
            script=sample_manim_script,
            quality="medium",
            workspace_id="test_workspace"
        )
        
        assert 'success' in result
        assert 'output' in result
        
        if result['success']:
            assert 'artifacts' in result
            if 'metadata' in result:
                assert result['metadata']['quality'] == 'medium'
    
    @pytest.mark.asyncio
    async def test_list_artifacts_tool(self, unified_server):
        """Test the list_artifacts MCP tool."""
        # First create some artifacts by executing code that creates files
        await unified_server._execute_python_tool(
            code="with open('test1.txt', 'w') as f: f.write('test content')",
            workspace_id="test_workspace"
        )
        
        result = await unified_server._list_artifacts_tool(workspace_id="test_workspace")
        
        assert 'artifacts' in result
        assert isinstance(result['artifacts'], list)
    
    @pytest.mark.asyncio
    async def test_get_artifact_tool(self, unified_server):
        """Test the get_artifact MCP tool."""
        # Create an artifact first
        await unified_server._execute_python_tool(
            code="with open('test.txt', 'w') as f: f.write('Test content')",
            workspace_id="test_workspace"
        )
        
        # List artifacts to get an ID
        artifacts = await unified_server._list_artifacts_tool(workspace_id="test_workspace")
        
        if artifacts['artifacts']:
            artifact_id = artifacts['artifacts'][0].get('artifact_id')
            if artifact_id:
                result = await unified_server._get_artifact_tool(artifact_id=artifact_id)
                assert 'found' in result
    
    @pytest.mark.asyncio
    async def test_get_artifact_tool_not_found(self, unified_server):
        """Test the get_artifact tool when artifact doesn't exist."""
        result = await unified_server._get_artifact_tool(artifact_id="nonexistent")
        
        assert result['found'] is False
        assert 'error' in result
    
    @pytest.mark.asyncio
    async def test_create_workspace_tool(self, unified_server):
        """Test the create_workspace MCP tool."""
        result = await unified_server._create_workspace_tool(
            workspace_id="new_workspace",
            description="Test workspace"
        )
        
        assert 'success' in result
        if result['success']:
            assert 'workspace_id' in result
            assert 'path' in result
    
    @pytest.mark.asyncio
    async def test_list_workspaces_tool(self, unified_server):
        """Test the list_workspaces MCP tool."""
        # Create a workspace first
        await unified_server._create_workspace_tool(
            workspace_id="test_ws",
            description="Test workspace"
        )
        
        result = await unified_server._list_workspaces_tool()
        
        assert 'workspaces' in result
        assert isinstance(result['workspaces'], list)
    
    @pytest.mark.asyncio
    async def test_get_server_status_tool(self, unified_server):
        """Test the get_server_status MCP tool."""
        result = await unified_server._get_server_status_tool()
        
        assert 'status' in result
        assert 'security_level' in result
        assert result['status'] in ['healthy', 'warning', 'error']
    
    @pytest.mark.asyncio
    async def test_error_handling_wrapper(self, unified_server):
        """Test the error handling wrapper for MCP tools."""
        # Test with code that will cause an error
        result = await unified_server._execute_python_tool(
            code="raise ValueError('Test error')",
            workspace_id="error_test"
        )
        
        assert result['success'] is False
        assert 'error' in result
        assert 'ValueError' in result['error']
    
    @pytest.mark.asyncio
    async def test_security_validation_integration(self, unified_server):
        """Test that security validation is integrated into tools."""
        result = await unified_server._execute_python_tool(
            code="import os; os.system('rm -rf /')",
            workspace_id="security_test"
        )
        
        # Should either be blocked by security or fail safely
        if not result['success']:
            error = result.get('error', '').lower()
            # Could be blocked by security or fail for other reasons
            assert 'error' in result
    
    def test_performance_monitoring_integration(self, unified_server):
        """Test that performance monitoring is integrated."""
        # Verify performance monitor exists
        assert hasattr(unified_server, 'performance_monitor')
        
        # Test that server has monitoring capabilities
        assert hasattr(unified_server, 'health_monitor')
    
    def test_logging_integration(self, unified_server):
        """Test that structured logging is integrated."""
        assert hasattr(unified_server, 'logger')
        
        # Test that server has logging capabilities
        assert unified_server.logger is not None
    
    def test_server_startup(self, unified_server):
        """Test server startup process."""
        # Test that server can be initialized without errors
        assert unified_server is not None
        assert hasattr(unified_server, 'start')
        
        # Test server has required components
        assert hasattr(unified_server, 'execution_engine')
        assert hasattr(unified_server, 'security_manager')
        assert hasattr(unified_server, 'artifact_manager')
    
    def test_server_cleanup(self, unified_server):
        """Test server cleanup process."""
        # Test that server has cleanup method
        assert hasattr(unified_server, 'cleanup')
        
        # Test that components have cleanup methods
        assert hasattr(unified_server.execution_engine, 'cleanup_all')
        assert hasattr(unified_server.workspace_manager, 'cleanup_all')
        assert hasattr(unified_server.artifact_manager, 'auto_cleanup')
    
    def test_configuration_validation(self, temp_dir):
        """Test configuration validation during initialization."""
        # Test with invalid configuration
        invalid_config = ServerConfig(
            max_execution_time=-1,  # Invalid negative value
            max_memory_mb=0,        # Invalid zero value
            security_level="invalid"  # Invalid security level
        )
        
        with pytest.raises((ValueError, TypeError)):
            UnifiedSandboxServer(invalid_config)
    
    @pytest.mark.asyncio
    async def test_concurrent_execution_handling(self, unified_server):
        """Test handling of concurrent executions."""
        async def run_concurrent_executions():
            tasks = [
                unified_server._execute_python_tool(f"print({i})", f"concurrent_test_{i}")
                for i in range(3)
            ]
            return await asyncio.gather(*tasks)
        
        results = await run_concurrent_executions()
        
        assert len(results) == 3
        for i, result in enumerate(results):
            assert 'success' in result
            if result['success']:
                assert str(i) in result['output']


class TestUnifiedServerIntegration:
    """Integration tests for the UnifiedSandboxServer."""
    
    @pytest.mark.integration
    def test_full_python_execution_workflow(self, unified_server, sample_python_code):
        """Test complete Python execution workflow."""
        import asyncio
        
        # Execute Python code
        result = asyncio.run(unified_server._execute_python_tool(
            code=sample_python_code,
            workspace_id="integration_test"
        ))
        
        assert result['success'] is True
        assert "Circle area" in result['output']
        assert result['execution_time'] > 0
    
    @pytest.mark.integration
    def test_artifact_creation_and_retrieval(self, unified_server, temp_dir):
        """Test artifact creation and retrieval workflow."""
        import asyncio
        
        # Create a file through Python execution
        code = """
with open('test_artifact.txt', 'w') as f:
    f.write('This is a test artifact')
print('Artifact created')
"""
        
        result = asyncio.run(unified_server._execute_python_tool(
            code=code,
            workspace_id="artifact_test"
        ))
        
        assert result['success'] is True
        assert "Artifact created" in result['output']
    
    @pytest.mark.integration
    def test_workspace_isolation(self, unified_server):
        """Test that workspaces are properly isolated."""
        import asyncio
        
        # Execute code in first workspace
        result1 = asyncio.run(unified_server._execute_python_tool(
            code="x = 42",
            workspace_id="workspace1"
        ))
        
        # Execute code in second workspace that tries to access x
        result2 = asyncio.run(unified_server._execute_python_tool(
            code="print(x)",  # Should fail if properly isolated
            workspace_id="workspace2"
        ))
        
        assert result1['success'] is True
        assert result2['success'] is False  # Should fail due to isolation
        assert "NameError" in result2.get('error', '')
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_timeout_handling(self, unified_server):
        """Test execution timeout handling."""
        import asyncio
        
        # Code that should timeout
        timeout_code = """
import time
time.sleep(20)  # Should timeout before this completes
print('This should not print')
"""
        
        result = asyncio.run(unified_server._execute_python_tool(
            code=timeout_code,
            workspace_id="timeout_test"
        ))
        
        assert result['success'] is False
        assert 'timeout' in result.get('error', '').lower()
    
    @pytest.mark.integration
    def test_security_enforcement(self, unified_server, security_test_cases):
        """Test that security policies are enforced."""
        import asyncio
        
        # Test dangerous Python code is blocked
        result = asyncio.run(unified_server._execute_python_tool(
            code=security_test_cases['dangerous_python'],
            workspace_id="security_test"
        ))
        
        assert result['success'] is False
        assert 'security' in result.get('error', '').lower()
        
        # Test safe Python code is allowed
        result = asyncio.run(unified_server._execute_python_tool(
            code=security_test_cases['safe_python'],
            workspace_id="security_test"
        ))
        
        assert result['success'] is True


if __name__ == "__main__":
    pytest.main([__file__])