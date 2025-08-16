#!/usr/bin/env python3
"""
Test script to validate debug_execute function and logging setup
"""

import sys
import os
import logging
import tempfile
from pathlib import Path

# Add the source directory to Python path
sandbox_src = Path(__file__).parent / "src" / "sandbox"
sys.path.insert(0, str(sandbox_src))

# Set up logging same as the server
log_file = Path(tempfile.gettempdir()) / "test_debug.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def test_logging():
    """Test if logging is working"""
    logger.info("Test logging message")
    print(f"Log file location: {log_file}")
    
    # Check if log file was created and written to
    if log_file.exists():
        content = log_file.read_text()
        print(f"Log file content:\n{content}")
        return True
    else:
        print("Log file was not created!")
        return False

def test_import():
    """Test importing the server module"""
    try:
        # Import the server module
        import mcp_sandbox_server_stdio
        print("Successfully imported mcp_sandbox_server_stdio")
        
        # Check if debug_execute exists
        if hasattr(mcp_sandbox_server_stdio, 'debug_execute'):
            print("debug_execute function found in module")
            
            # Try to call it
            result = mcp_sandbox_server_stdio.debug_execute("print('Hello from debug_execute')")
            print(f"debug_execute result: {result}")
            return True
        else:
            print("debug_execute function NOT found in module")
            print(f"Available functions: {[name for name in dir(mcp_sandbox_server_stdio) if not name.startswith('_')]}")
            return False
            
    except ImportError as e:
        print(f"Failed to import mcp_sandbox_server_stdio: {e}")
        return False
    except Exception as e:
        print(f"Error during import test: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Testing debug_execute setup")
    print("=" * 60)
    
    print("\n1. Testing logging...")
    log_works = test_logging()
    
    print("\n2. Testing module import...")
    import_works = test_import()
    
    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Logging working: {log_works}")
    print(f"  Import working: {import_works}")
    print("=" * 60)
