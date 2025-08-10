"""
Intelligent Sandbox MCP Server

A comprehensive FastMCP server for the intelligent sandbox system that provides
workspace cloning, codebase analysis, task planning, and execution capabilities.
"""

import sys
import logging
from pathlib import Path

# Add the src directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent))

from sandbox.intelligent.mcp.server import IntelligentSandboxMCPServer

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for the intelligent sandbox MCP server."""
    logger.info("Starting Intelligent Sandbox MCP Server...")
    
    try:
        # Create the server instance
        server = IntelligentSandboxMCPServer("intelligent-sandbox")
        
        # Determine transport method from command line args
        if len(sys.argv) > 1 and sys.argv[1] == "http":
            # Run HTTP server
            host = sys.argv[2] if len(sys.argv) > 2 else "0.0.0.0"
            port = int(sys.argv[3]) if len(sys.argv) > 3 else 8765
            
            logger.info(f"Running Intelligent Sandbox MCP Server on HTTP at {host}:{port}")
            server.run_http(host=host, port=port)
        else:
            # Run stdio server (default for MCP)
            logger.info("Running Intelligent Sandbox MCP Server on stdio")
            server.run_stdio()
            
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()