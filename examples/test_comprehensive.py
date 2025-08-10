#!/usr/bin/env python3
"""
Test comprehensive usage example functionality.
"""

import sys
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import the example module
from comprehensive_usage_example import SandboxUsageExamples

def test_comprehensive_usage():
    """Test the comprehensive usage example."""
    print("Testing comprehensive usage example...")
    
    try:
        # Create instance
        examples = SandboxUsageExamples()
        print("✅ SandboxUsageExamples initialized successfully")
        
        # Test basic workspace operations
        print("\nTesting Example 1: Basic Workspace Operations...")
        examples.example_1_basic_workspace_operations()
        print("✅ Example 1 completed successfully")
        
        # Test MCP integration
        print("\nTesting Example 5: MCP Integration...")
        examples.example_5_mcp_integration()
        print("✅ Example 5 completed successfully")
        
        # Test performance monitoring
        print("\nTesting Example 6: Performance Monitoring...")
        examples.example_6_performance_monitoring()
        print("✅ Example 6 completed successfully")
        
        # Test security features
        print("\nTesting Example 9: Security Features...")
        examples.example_9_security_features()
        print("✅ Example 9 completed successfully")
        
        print("\n🎉 All tests passed! Comprehensive usage example is working correctly.")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_comprehensive_usage()
    sys.exit(0 if success else 1)
