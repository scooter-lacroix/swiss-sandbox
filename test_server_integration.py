#!/usr/bin/env python3
"""
Test script to verify the unified server works with the new logging and error handling system.
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from sandbox.unified_server import UnifiedSandboxServer
from sandbox.core.types import ServerConfig


def test_server_initialization():
    """Test that the server initializes with logging and error handling."""
    print("Testing server initialization...")
    
    try:
        # Create server config
        config = ServerConfig(
            log_level="DEBUG",
            max_execution_time=10,
            security_level="moderate"
        )
        
        # Initialize server
        server = UnifiedSandboxServer(config)
        
        print("✓ Server initialized successfully")
        print(f"✓ Structured logger: {server.structured_logger is not None}")
        print(f"✓ Error handler: {server.error_handler is not None}")
        print(f"✓ Performance monitor: {server.performance_monitor is not None}")
        print(f"✓ Health monitor: {server.health_monitor is not None}")
        
        # Test health check
        health_report = server.health_monitor.get_overall_health()
        print(f"✓ Health check status: {health_report['overall_status']}")
        
        # Test diagnostic report
        diagnostic_report = server.health_monitor.get_diagnostic_report()
        print(f"✓ Diagnostic report generated with {len(diagnostic_report)} sections")
        
        # Cleanup
        server._cleanup()
        print("✓ Server cleanup completed")
        
        return True
        
    except Exception as e:
        print(f"❌ Server initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_mcp_tools():
    """Test that MCP server is properly configured."""
    print("\nTesting MCP server configuration...")
    
    try:
        config = ServerConfig(log_level="INFO")
        server = UnifiedSandboxServer(config)
        
        # Check that MCP server is initialized
        print(f"✓ MCP server initialized: {server.mcp is not None}")
        print(f"✓ MCP server name: {server.mcp.name}")
        
        # Check that diagnostic methods are available on the server
        diagnostic_methods = [
            '_register_diagnostic_tools',
            'health_monitor',
            'error_handler',
            'performance_monitor'
        ]
        
        for method_name in diagnostic_methods:
            if hasattr(server, method_name):
                print(f"✓ Server has {method_name}")
            else:
                print(f"⚠ Server missing {method_name}")
        
        server._cleanup()
        return True
        
    except Exception as e:
        print(f"❌ MCP server test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run integration tests."""
    print("Starting server integration tests...\n")
    
    success = True
    
    # Test server initialization
    if not test_server_initialization():
        success = False
    
    # Test MCP tools
    if not test_mcp_tools():
        success = False
    
    if success:
        print("\n✅ All integration tests passed!")
        return 0
    else:
        print("\n❌ Some integration tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())