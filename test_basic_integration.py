#!/usr/bin/env python3
"""
Basic System Integration Test

A focused test to validate core system functionality of the Swiss Sandbox - 
the Swiss army knife of AI toolkits.
"""

import json
import sys
import time
from pathlib import Path

def test_basic_integration():
    """Test basic system integration."""
    print("🔍 Testing basic system integration...")
    
    try:
        # Test server import and initialization
        print("  ✓ Testing server import...")
        from src.sandbox.unified_server import UnifiedSandboxServer
        from src.sandbox.core.types import ServerConfig
        
        print("  ✓ Testing server initialization...")
        config = ServerConfig()
        server = UnifiedSandboxServer(config)
        
        print("  ✓ Testing core components...")
        assert server.execution_engine is not None
        assert server.artifact_manager is not None
        assert server.mcp is not None
        
        print("  ✓ Testing Python execution...")
        context = server.get_or_create_context("test_workspace")
        result = server.execution_engine.execute_python(
            "print('Hello from integrated system!')\nresult = 2 + 2\nprint(f'2 + 2 = {result}')",
            context
        )
        
        assert result.success, f"Python execution failed: {result.error}"
        assert "Hello from integrated system!" in result.output
        assert "2 + 2 = 4" in result.output
        
        print("  ✓ Testing shell execution...")
        shell_result = server.execution_engine.execute_shell("echo 'Shell test successful'", context)
        assert shell_result.success, f"Shell execution failed: {shell_result.error}"
        assert "Shell test successful" in shell_result.output
        
        print("  ✓ Testing artifact management...")
        # Create a test file
        test_file = Path("test_artifact.txt")
        test_file.write_text("Test artifact content")
        
        try:
            artifact_id = server.artifact_manager.store_file(
                test_file,
                workspace_id="test_workspace",
                description="Test artifact"
            )
            assert artifact_id is not None
            
            # Retrieve artifact
            artifact = server.artifact_manager.retrieve_artifact(artifact_id)
            assert artifact is not None
            assert artifact.exists()
            
        finally:
            test_file.unlink(missing_ok=True)
        
        print("  ✓ Testing execution history...")
        history = server.execution_engine.get_execution_history(limit=5)
        assert len(history) > 0
        
        print("  ✓ Testing health check...")
        health_report = server.health_monitor.get_overall_health()
        assert 'overall_status' in health_report
        assert 'components' in health_report
        assert 'timestamp' in health_report
        
        print("\n✅ Basic integration test PASSED!")
        return True
        
    except Exception as e:
        print(f"\n❌ Basic integration test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_mcp_server_entry_point():
    """Test MCP server entry point."""
    print("\n🔍 Testing MCP server entry point...")
    
    try:
        # Test that the MCP server can be imported
        from src.sandbox import mcp_sandbox_server
        
        # Test that it has the expected attributes
        assert hasattr(mcp_sandbox_server, 'main')
        assert hasattr(mcp_sandbox_server, 'mcp')
        
        print("  ✓ MCP server entry point accessible")
        return True
        
    except Exception as e:
        print(f"  ❌ MCP server entry point test failed: {e}")
        return False

def test_server_configuration():
    """Test server configuration."""
    print("\n🔍 Testing server configuration...")
    
    try:
        from src.sandbox.core.types import ServerConfig, SecurityLevel
        
        # Test default configuration
        config = ServerConfig()
        assert config.max_execution_time > 0
        assert config.max_memory_mb > 0
        assert isinstance(config.security_level, SecurityLevel)
        
        # Test configuration serialization
        config_dict = config.to_dict()
        assert isinstance(config_dict, dict)
        assert 'max_execution_time' in config_dict
        
        print("  ✓ Server configuration working")
        return True
        
    except Exception as e:
        print(f"  ❌ Server configuration test failed: {e}")
        return False

def main():
    """Run basic integration tests."""
    print("=" * 60)
    print("🚀 SWISS SANDBOX BASIC INTEGRATION TEST")
    print("=" * 60)
    
    tests = [
        ("Basic Integration", test_basic_integration),
        ("MCP Entry Point", test_mcp_server_entry_point),
        ("Server Configuration", test_server_configuration)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results[test_name] = False
    
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS")
    print("=" * 60)
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All basic integration tests PASSED!")
        print("✅ System is ready for production use")
        return 0
    else:
        print(f"\n⚠️ {total - passed} test(s) failed")
        print("❌ System needs attention before production use")
        return 1

if __name__ == "__main__":
    sys.exit(main())