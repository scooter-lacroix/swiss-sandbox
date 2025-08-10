"""
Simple test to verify the intelligent sandbox structure is working correctly.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

def test_imports():
    """Test that all main components can be imported successfully."""
    try:
        # Test workspace imports
        from src.sandbox.intelligent.workspace import WorkspaceCloner, SandboxWorkspace, IsolationConfig
        from src.sandbox.intelligent.workspace.interfaces import WorkspaceClonerInterface
        
        # Test analyzer imports
        from src.sandbox.intelligent.analyzer import CodebaseAnalyzer, CodebaseAnalysis
        from src.sandbox.intelligent.analyzer.interfaces import CodebaseAnalyzerInterface
        
        # Test planner imports
        from src.sandbox.intelligent.planner import TaskPlanner, TaskPlan, Task
        from src.sandbox.intelligent.planner.interfaces import TaskPlannerInterface
        
        # Test executor imports
        from src.sandbox.intelligent.executor import ExecutionEngine, ExecutionResult
        from src.sandbox.intelligent.executor.interfaces import ExecutionEngineInterface
        
        # Test logger imports
        from src.sandbox.intelligent.logger import ActionLogger, Action
        from src.sandbox.intelligent.logger.interfaces import ActionLoggerInterface
        
        # Test config imports
        from src.sandbox.intelligent.config import ConfigManager, SandboxConfig, get_config
        
        # Test types imports
        from src.sandbox.intelligent.types import WorkspaceStatus, TaskStatus, ActionType
        
        print("✓ All imports successful")
        return True
        
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False


def test_basic_instantiation():
    """Test that basic components can be instantiated."""
    try:
        from src.sandbox.intelligent.workspace import WorkspaceCloner, IsolationConfig
        from src.sandbox.intelligent.analyzer import CodebaseAnalyzer
        from src.sandbox.intelligent.planner import TaskPlanner
        from src.sandbox.intelligent.executor import ExecutionEngine
        from src.sandbox.intelligent.logger import ActionLogger
        from src.sandbox.intelligent.config import ConfigManager
        
        # Test instantiation
        cloner = WorkspaceCloner()
        analyzer = CodebaseAnalyzer()
        planner = TaskPlanner()
        engine = ExecutionEngine()
        logger = ActionLogger()
        config_manager = ConfigManager()
        
        print("✓ All components instantiated successfully")
        return True
        
    except Exception as e:
        print(f"✗ Instantiation failed: {e}")
        return False


def test_config_system():
    """Test the configuration system."""
    try:
        from src.sandbox.intelligent.config import get_config, get_config_manager
        
        config = get_config()
        config_manager = get_config_manager()
        
        # Test getting a setting
        timeout = config.default_command_timeout
        assert isinstance(timeout, int)
        
        # Test setting a custom setting
        config_manager.set_setting("test_setting", "test_value")
        value = config_manager.get_setting("test_setting")
        assert value == "test_value"
        
        print("✓ Configuration system working correctly")
        return True
        
    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        return False


if __name__ == "__main__":
    print("Testing intelligent sandbox structure...")
    
    tests = [
        test_imports,
        test_basic_instantiation,
        test_config_system
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
    
    print(f"\nResults: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All tests passed! Structure is working correctly.")
    else:
        print("❌ Some tests failed. Check the implementation.")