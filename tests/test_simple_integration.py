#!/usr/bin/env python3
"""
Simple integration tests for the enhanced MCP sandbox server.
"""

import sys
import json
import tempfile
import shutil
import unittest
from pathlib import Path

# Add the src directory to Python path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

# Import the server module  
from sandbox.mcp_sandbox_server_stdio import (
    ExecutionContext, 
    monkey_patch_matplotlib,
    monkey_patch_pil,
    find_free_port,
    collect_artifacts
)

class TestSandboxBasics(unittest.TestCase):
    """Basic integration tests for sandbox functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = Path(tempfile.mkdtemp())
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_execution_context_creation(self):
        """Test ExecutionContext can be created and configured."""
        ctx = ExecutionContext()
        
        self.assertIsInstance(ctx.project_root, Path)
        self.assertIsInstance(ctx.venv_path, Path) 
        self.assertEqual(str(ctx.project_root), '/home/stan/Prod/sandbox')
        self.assertTrue(ctx.venv_path.exists())
    
    def test_monkey_patching(self):
        """Test monkey patching functionality."""
        matplotlib_result = monkey_patch_matplotlib()
        pil_result = monkey_patch_pil()
        
        # Should return booleans indicating if patches were applied
        self.assertIsInstance(matplotlib_result, bool)
        self.assertIsInstance(pil_result, bool)
    
    def test_find_free_port(self):
        """Test free port finding functionality."""
        port = find_free_port(8000)
        
        self.assertIsInstance(port, int)
        self.assertGreaterEqual(port, 8000)
        self.assertLess(port, 8100)
    
    def test_collect_artifacts_empty(self):
        """Test artifact collection when no artifacts exist.""" 
        # Create a clean context with no artifacts
        ctx = ExecutionContext()
        ctx.artifacts_dir = None
        
        # Import the function and set the global context temporarily
        from sandbox.mcp_sandbox_server_stdio import collect_artifacts
        import sandbox.mcp_sandbox_server_stdio as server_module
        
        # Save original context
        original_ctx = server_module.ctx
        
        try:
            # Set our clean context
            server_module.ctx = ctx
            artifacts = collect_artifacts()
            
            # Should return empty list when no artifacts
            self.assertIsInstance(artifacts, list)
            self.assertEqual(len(artifacts), 0)
        finally:
            # Restore original context
            server_module.ctx = original_ctx
    
    def test_module_imports(self):
        """Test that the enhanced modules can be imported."""
        # Test package imports work
        from sandbox.server import run_server, get_status
        from sandbox.utils import helper_function, process_data
        
        self.assertEqual(run_server(), "Server is running!")
        self.assertEqual(get_status(), "Server status: OK")
        self.assertEqual(helper_function(), "Helper function called!")
        self.assertEqual(process_data("test"), "Processed: test")

if __name__ == '__main__':
    unittest.main(verbosity=2)
