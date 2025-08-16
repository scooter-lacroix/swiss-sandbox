#!/bin/bash
"""
Swiss Sandbox MCP Server Startup Script

This script provides an easy way to start the Swiss Sandbox MCP server
with proper environment setup.
"""

# Get the directory containing this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Set up Python path
export PYTHONPATH="${SCRIPT_DIR}/src:${PYTHONPATH}"
export PYTHONUNBUFFERED=1

echo "Starting Swiss Sandbox MCP Server..."
echo "Script directory: ${SCRIPT_DIR}"
echo "Python path: ${PYTHONPATH}"

# Try to start the unified server
if python3 -m sandbox.unified_server "$@"; then
    echo "Server started successfully"
else
    echo "Failed to start unified server, trying fallback..."
    if python3 "${SCRIPT_DIR}/server.py" "$@"; then
        echo "Fallback server started successfully"
    else
        echo "Failed to start server. Please check your installation."
        exit 1
    fi
fi