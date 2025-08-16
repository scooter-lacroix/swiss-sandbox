#!/usr/bin/env python3
"""
Swiss Sandbox MCP Server Entry Point

This script provides the main entry point for the unified Swiss Sandbox MCP server.
It handles importing and running the unified server with proper configuration.
"""

import sys
import os
from pathlib import Path

def main():
    """Main entry point for the Swiss Sandbox MCP server."""
    
    # Get the directory containing this script
    script_dir = Path(__file__).parent.resolve()
    
    # Add src directory to Python path for module imports
    src_dir = script_dir / "src"
    if src_dir.exists() and str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    
    # Set up environment variables if needed
    os.environ.setdefault("PYTHONPATH", str(src_dir))
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    
    try:
        # Import and run the unified Swiss Sandbox server
        from sandbox.unified_server import main as unified_main
        print(f"Starting Swiss Sandbox Unified MCP Server...")
        print(f"Script directory: {script_dir}")
        print(f"Source directory: {src_dir}")
        print(f"Python path includes: {src_dir in sys.path}")
        
        # Run the unified server
        unified_main()
        
    except ImportError as e:
        print(f"Failed to import unified sandbox server: {e}")
        print(f"Current sys.path: {sys.path[:3]}...")
        
        # Try fallback to ultimate server
        try:
            from sandbox.ultimate.server import main as ultimate_main
            print("Falling back to ultimate server...")
            ultimate_main()
        except ImportError as e2:
            print(f"Fallback import also failed: {e2}")
            print("\nPlease ensure the Swiss Sandbox is properly installed:")
            print("  pip install -e .")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error starting Swiss Sandbox MCP server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
