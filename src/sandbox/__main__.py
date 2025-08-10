"""
Main entry point for Swiss Sandbox MCP server.
This allows running the server with: python -m sandbox
"""

from .mcp_sandbox_server_stdio import main

if __name__ == "__main__":
    main()
