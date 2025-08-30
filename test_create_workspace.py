#!/usr/bin/env python3
"""
Test script for create_workspace tool functionality.

This script tests:
1. Workspace creation in ~/.swiss_sandbox/ directory structure
2. Local directory configuration
3. Health check functionality
"""

import os
import sys
import json
import tempfile
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

def test_create_workspace_tool():
    """Test the create_workspace MCP tool functionality."""
    print("🧪 Testing create_workspace tool functionality...")

    try:
        # Test 1: Test core workspace manager (should use ~/.swiss_sandbox)
        print("\n📁 Test 1: Testing core workspace manager...")
        from sandbox.core.workspace_manager import WorkspaceManager

        # Initialize with default settings (should use ~/.swiss_sandbox/workspaces)
        core_manager = WorkspaceManager()
        print("✅ Core workspace manager initialized successfully")
        print(f"📂 Base workspace directory: {core_manager.base_workspace_dir}")

        # Create workspace using core manager with simple configuration (no isolation)
        test_workspace_id = "core_test_workspace_001"
        from sandbox.core.workspace_manager import WorkspaceConfig

        # Create config with isolation enabled for proper Docker container isolation
        simple_config = WorkspaceConfig(
            workspace_id=test_workspace_id,
            use_isolation=True  # This should use Docker containers for isolation
        )

        core_workspace = core_manager.create_workspace(
            workspace_id=test_workspace_id,
            source_path=str(project_root),
            config=simple_config
        )

        if core_workspace:
            print(f"✅ Core workspace created successfully: {test_workspace_id}")
            print(f"📂 Core workspace path: {core_workspace.workspace_path}")

            # Verify core workspace directory structure
            expected_base = Path.home() / ".swiss_sandbox" / "workspaces"
            print(f"Expected base directory: {expected_base}")

            if expected_base.exists():
                print("✅ Base workspace directory exists")
                # List contents
                workspaces = list(expected_base.iterdir())
                print(f"Workspaces in directory: {[w.name for w in workspaces]}")

                # Check if our test workspace exists
                test_workspace_dir = expected_base / test_workspace_id
                if test_workspace_dir.exists():
                    print(f"✅ Core test workspace directory exists: {test_workspace_dir}")
                    # List contents
                    contents = list(test_workspace_dir.iterdir())
                    print(f"Core workspace contents: {[c.name for c in contents[:5]]}")  # First 5 items
                else:
                    print(f"❌ Core test workspace directory not found: {test_workspace_dir}")
            else:
                print(f"❌ Base workspace directory does not exist: {expected_base}")

            # Cleanup core workspace
            core_manager.cleanup_workspace(test_workspace_id)
            print("✅ Core workspace cleaned up")

        # Test 2: Test intelligent workspace system
        print("\n🤖 Test 2: Testing intelligent workspace system...")
        from sandbox.intelligent.workspace.lifecycle import WorkspaceLifecycleManager

        # Initialize lifecycle manager
        lifecycle_manager = WorkspaceLifecycleManager()
        print("✅ Intelligent workspace lifecycle manager initialized successfully")

        # Create workspace using intelligent system
        intelligent_workspace_id = "intelligent_test_workspace_001"
        session = lifecycle_manager.create_workspace(
            source_path=str(project_root),
            session_id=intelligent_workspace_id
        )

        if session:
            print(f"✅ Intelligent workspace created successfully: {intelligent_workspace_id}")
            print(f"📂 Intelligent workspace path: {session.workspace.sandbox_path}")

            # Check if intelligent workspace uses temp directory
            if session.workspace.sandbox_path.startswith('/tmp'):
                print("ℹ️  Intelligent workspace uses temp directory (/tmp/intelligent_sandbox)")
            else:
                print(f"ℹ️  Intelligent workspace path: {session.workspace.sandbox_path}")

            # Cleanup intelligent workspace
            lifecycle_manager.destroy_workspace(intelligent_workspace_id)
            print("✅ Intelligent workspace cleaned up")

        # Test 3: Health check
        print("\n🏥 Test 3: Running health check...")
        try:
            # Import health monitor
            from sandbox.core.health_monitor import HealthMonitor
            from sandbox.core.logging_system import StructuredLogger, ErrorHandler, PerformanceMonitor

            # Create health monitor components
            logger = StructuredLogger("test")
            error_handler = ErrorHandler(logger)
            performance_monitor = PerformanceMonitor(logger)

            health_monitor = HealthMonitor(logger, error_handler, performance_monitor)
            health_report = health_monitor.get_overall_health()

            print(f"Health check result: {json.dumps(health_report, indent=2)}")

            if health_report.get('overall_status') == 'healthy':
                print("✅ Health check passed")
            else:
                print(f"⚠️  Health check status: {health_report.get('overall_status')}")

            # Check components
            components = health_report.get('components', {})
            for component_name, component_data in components.items():
                status = component_data.get('status')
                if status == 'healthy':
                    print(f"✅ {component_name}: healthy")
                else:
                    print(f"⚠️  {component_name}: {status}")

        except Exception as e:
            print(f"❌ Health check failed: {e}")
            import traceback
            traceback.print_exc()

    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()

    print("\n🏁 Test completed!")


if __name__ == "__main__":
    test_create_workspace_tool()