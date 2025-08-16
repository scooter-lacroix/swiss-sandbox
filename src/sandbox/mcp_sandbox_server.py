#!/usr/bin/env python3
"""
MCP SANDBOX SERVER - UNIFIED SERVER DELEGATE

This file now properly delegates to the Unified Swiss Sandbox MCP Server,
the Swiss army knife of AI toolkits. All functionality has been consolidated 
into the unified server architecture.
"""

import sys
import warnings
from pathlib import Path


def main():
    """Delegate to the Unified server."""
    warnings.warn(
        "This server has been consolidated into the Unified Swiss Sandbox MCP Server. "
        "Please use 'python -m sandbox.unified_server' or 'swiss-sandbox' instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    print("\n" + "=" * 80)
    print("🔄 SERVER DELEGATION")
    print("=" * 80)
    print("This MCP server now delegates to the Unified Swiss Sandbox server.")
    print("Automatically starting the unified server...")
    print("\n✨ The Unified server includes ALL functionality:")
    print("   • Core execution tools (execute, debug_execute, etc.)")
    print("   • Security management and validation")
    print("   • Artifact management and storage")
    print("   • Workspace isolation and management")
    print("   • Intelligent features and analysis")
    print("=" * 80)
    print()
    
    try:
        # Import and run the unified server
        from sandbox.unified_server import main as unified_main
        print("Starting Unified Swiss Sandbox MCP Server...\n")
        unified_main()
    except ImportError as e:
        print(f"Error importing unified server: {e}")
        print("Falling back to ultimate server...")
        try:
            from sandbox.ultimate.server import main as ultimate_main
            ultimate_main()
        except ImportError as e2:
            print(f"Fallback failed: {e2}")
            print("\nPlease ensure Swiss Sandbox is properly installed:")
            print("  pip install -e .")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\nServer stopped by user.\n")
    except Exception as e:
        print(f"\nError starting server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


# Create an mcp attribute for backward compatibility
class MCPServerCompat:
    """Compatibility wrapper for legacy mcp.run() calls."""
    
    def run(self, transport='stdio'):
        """Run the unified server with specified transport."""
        print(f"Legacy mcp.run() called with transport={transport}")
        print("Delegating to unified server...")
        main()

# Create the mcp instance for backward compatibility
mcp = MCPServerCompat()


if __name__ == "__main__":
    main()