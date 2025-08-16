#!/usr/bin/env python3
"""
Server Setup Validation Script

This script validates that all server entry points are properly configured
and can be imported without errors.
"""

import sys
import os
from pathlib import Path

def setup_path():
    """Set up Python path for testing."""
    script_dir = Path(__file__).parent.resolve()
    src_dir = script_dir / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    os.environ["PYTHONPATH"] = str(src_dir)

def test_import(module_name, description):
    """Test importing a module."""
    try:
        __import__(module_name)
        print(f"✅ {description}: SUCCESS")
        return True
    except ImportError as e:
        print(f"❌ {description}: FAILED - {e}")
        return False
    except Exception as e:
        print(f"⚠️  {description}: ERROR - {e}")
        return False

def test_attribute(module_name, attr_name, description):
    """Test that a module has a specific attribute."""
    try:
        module = __import__(module_name, fromlist=[attr_name])
        if hasattr(module, attr_name):
            print(f"✅ {description}: SUCCESS")
            return True
        else:
            print(f"❌ {description}: FAILED - Missing attribute '{attr_name}'")
            return False
    except ImportError as e:
        print(f"❌ {description}: FAILED - {e}")
        return False

def main():
    """Run all validation tests."""
    print("Swiss Sandbox Server Setup Validation - Swiss army knife of AI toolkits")
    print("=" * 50)
    
    setup_path()
    
    tests_passed = 0
    total_tests = 0
    
    # Test core server imports
    tests = [
        ("sandbox.unified_server", "Unified Server Import"),
        ("sandbox.mcp_sandbox_server", "Legacy Server Import"),
        ("sandbox.ultimate.server", "Ultimate Server Import"),
        ("sandbox", "Package Import"),
    ]
    
    for module, description in tests:
        total_tests += 1
        if test_import(module, description):
            tests_passed += 1
    
    # Test specific attributes
    attribute_tests = [
        ("sandbox.unified_server", "main", "Unified Server Main Function"),
        ("sandbox.mcp_sandbox_server", "mcp", "Legacy MCP Compatibility Object"),
        ("sandbox.mcp_sandbox_server", "main", "Legacy Server Main Function"),
    ]
    
    for module, attr, description in attribute_tests:
        total_tests += 1
        if test_attribute(module, attr, description):
            tests_passed += 1
    
    # Test MCP compatibility
    try:
        from sandbox.mcp_sandbox_server import mcp
        if hasattr(mcp, 'run') and callable(mcp.run):
            print("✅ MCP Compatibility Object: SUCCESS")
            tests_passed += 1
        else:
            print("❌ MCP Compatibility Object: FAILED - run method not callable")
        total_tests += 1
    except Exception as e:
        print(f"❌ MCP Compatibility Object: FAILED - {e}")
        total_tests += 1
    
    print("\n" + "=" * 50)
    print(f"Validation Results: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("🎉 All server entry points are properly configured!")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the configuration.")
        return 1

if __name__ == "__main__":
    sys.exit(main())