#!/bin/bash

# Swiss Sandbox Installation Script
# This script sets up the Swiss Sandbox MCP server

set -e

echo "🛠️ Swiss Sandbox Installation"
echo "============================="
echo ""

# Check Python version
echo "📍 Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | grep -oE '[0-9]+\.[0-9]+')
    MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    
    if [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 10 ]; then
        echo "✅ Python $PYTHON_VERSION found"
    else
        echo "⚠️  Python $PYTHON_VERSION found, but 3.10+ is recommended"
    fi
else
    echo "❌ Python 3 not found. Please install Python 3.10+"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip --quiet

# Install dependencies
echo "📚 Installing dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt --quiet
else
    # Install core dependencies directly
    pip install fastmcp>=0.1.0 aiofiles>=23.0.0 psutil>=5.9.0 --quiet
fi

# Install package in editable mode
echo "🔗 Installing Swiss Sandbox..."
pip install -e . --quiet

# Optional: Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo ""
    echo "⚠️  Docker not found. Docker is optional but recommended for full isolation."
    echo "   To install Docker, visit: https://docs.docker.com/get-docker/"
fi

# Optional: Install Go for Zoekt
if ! command -v go &> /dev/null; then
    echo ""
    echo "⚠️  Go not found. Go is optional but needed for Zoekt search functionality."
    echo "   To install Go, visit: https://golang.org/dl/"
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "🚀 To start the MCP server:"
echo "   source venv/bin/activate"
echo "   python -m sandbox.mcp_sandbox_server_stdio"
echo ""
echo "📚 For documentation, see: docs/README.md"
echo "🔧 For tool reference, see: docs/SS_TOOL_REFERENCE.md"
