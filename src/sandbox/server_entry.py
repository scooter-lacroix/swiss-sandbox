#!/usr/bin/env python3
"""
Entry point for the Unified Swiss Sandbox MCP Server.

This provides a simple way to start the server with different configurations.
Usage:
    python server_entry.py [--transport stdio|http] [--host HOST] [--port PORT]
"""

import sys
import os
from pathlib import Path

def main():
    """Main entry point with proper path setup."""
    # Get the directory containing this script
    script_dir = Path(__file__).parent.resolve()
    
    # Add src directory to Python path if we're in src/sandbox
    if script_dir.name == 'sandbox':
        src_dir = script_dir.parent
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))
    
    # Set up environment variables
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    
    try:
        from sandbox.unified_server import main as unified_main
        print("Starting Unified Swiss Sandbox MCP Server...")
        unified_main()
    except ImportError as e:
        print(f"Failed to import unified server: {e}")
        print("Trying fallback to ultimate server...")
        try:
            from sandbox.ultimate.server import main as ultimate_main
            ultimate_main()
        except ImportError as e2:
            print(f"Fallback failed: {e2}")
            print("Please ensure Swiss Sandbox is properly installed.")
            sys.exit(1)

if __name__ == "__main__":
    main()