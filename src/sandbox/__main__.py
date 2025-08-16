"""
Main entry point for Swiss Sandbox MCP server.
This allows running the server with: python -m sandbox
"""

try:
    from .unified_server import main
    print("Using Unified Swiss Sandbox MCP Server")
except ImportError:
    try:
        from .ultimate.server import main
        print("Falling back to Ultimate Swiss Sandbox MCP Server")
    except ImportError:
        from .mcp_sandbox_server_stdio import main
        print("Falling back to legacy stdio server")

if __name__ == "__main__":
    main()
