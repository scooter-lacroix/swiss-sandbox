# Swiss Sandbox (SS) 🛠️

[![Add to LM Studio](https://files.lmstudio.ai/deeplink/mcp-install-light.svg)](https://lmstudio.ai/install-mcp?name=swiss-sandbox&config=eyJ1cmwiOiJodHRwczovL2dpdGh1Yi5jb20vc2Nvb3Rlci1sYWNyb2l4L3N3aXNzLXNhbmRib3giLCJoZWFkZXJzIjp7fX0%3D)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io)

**The Swiss Army Knife of AI Development Environments** - A comprehensive MCP server that combines isolated workspace management, intelligent code analysis, automated task planning, and lightning-fast code search into one powerful, versatile tool.

Just like a Swiss Army Knife 🔪 provides multiple tools in one compact package, Swiss Sandbox delivers everything you need for AI-powered development in a single, unified interface.

## 🎯 Why Swiss Sandbox?

Swiss Sandbox is designed to be the ultimate multi-tool for AI-assisted development:

- **🔧 All-in-One**: 68 integrated tools covering every aspect of development
- **🛡️ Secure**: Isolated workspaces with Docker containerization
- **🚀 Fast**: Zoekt-powered search indexing at 1000+ files/second
- **🤖 AI-Ready**: Optimized for both large (100B+) and small (4B) language models
- **📦 Modular**: Use what you need, when you need it

## ✨ Key Features

### 🏗️ **Workspace Management**
Create isolated, secure development environments with resource limits and Git integration.

### 🔍 **Advanced Code Search**
Lightning-fast code search powered by Zoekt, with support for regex, AST, and semantic search.

### 📋 **Intelligent Task Planning**
Automatically generate and execute task plans based on project analysis.

### 🚀 **Code Execution & Artifacts**
Execute code safely with automatic artifact collection and web app deployment.

### 🎨 **Visualization & Animation**
Create Manim animations and interactive Canvas displays for code visualization.

## 🚄 Quick Start

### One-Click Installation for LM Studio

[![Add to LM Studio](https://files.lmstudio.ai/deeplink/mcp-install-light.svg)](https://lmstudio.ai/install-mcp?name=swiss-sandbox&config=eyJ1cmwiOiJodHRwczovL2dpdGh1Yi5jb20vc2Nvb3Rlci1sYWNyb2l4L3N3aXNzLXNhbmRib3giLCJoZWFkZXJzIjp7fX0%3D)

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/scooter-lacroix/swiss-sandbox.git
cd swiss-sandbox

# Install system dependencies
chmod +x install_deps.sh
./install_deps.sh

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install Python packages
pip install -e .

# Run tests to verify installation
./run_tests.sh

# Start the server
swiss-sandbox
```

## 📚 Documentation

- [📖 Tool Reference](docs/SS_TOOL_REFERENCE.md) - Complete guide to all 68 tools with examples
- [🚀 Deployment Guide](docs/DEPLOYMENT.md) - Production deployment instructions
- [🔧 API Documentation](docs/API.md) - Detailed API reference
- [🛡️ Security Guide](docs/SECURITY.md) - Security best practices
- [🌍 中文文档](docs/README_zh.md) - Chinese documentation

## 🛠️ Core Capabilities

### Workspace Tools (19 tools)
```python
# Create isolated workspace
workspace = await create_workspace(
    source_path="/path/to/project",
    use_docker=True,
    resource_limits={"memory_mb": 2048}
)

# Analyze codebase
analysis = await analyze_codebase(
    workspace_id=workspace["workspace_id"],
    deep_analysis=True
)
```

### Search & Indexing (25 tools)
```python
# Initialize project search
await set_project_path(
    path="/home/user/project",
    index_immediately=True
)

# Search with Zoekt
results = await search_code_advanced(
    pattern="def.*test",
    search_type="zoekt",
    use_regex=True
)
```

### Execution & Artifacts (18 tools)
```python
# Execute code with artifacts
result = await execute_with_artifacts(
    code="import matplotlib.pyplot as plt\nplt.plot([1,2,3])",
    expected_artifacts=["plot.png"]
)

# Deploy web app
app = await start_web_app(
    code=flask_app_code,
    app_type="flask",
    containerize=True
)
```

## 🏆 Performance

- **Workspace Creation**: < 1 second
- **File Indexing**: 1000+ files/second
- **Search Latency**: < 50ms
- **Memory Usage**: < 500MB baseline
- **Concurrent Operations**: 50+ supported

## 🔒 Security

Swiss Sandbox implements multiple layers of security:

- **Container Isolation**: Docker-based workspace isolation
- **Resource Limits**: CPU, memory, and disk quotas
- **Path Validation**: Prevention of directory traversal attacks
- **Command Sanitization**: Protection against injection attacks
- **Network Control**: Configurable network access restrictions

## 📋 Requirements

### System Requirements
- Python 3.10+ (tested with 3.11)
- Docker (optional but recommended)
- Go 1.19+ (for Zoekt installation)
- 4GB RAM minimum
- Linux/macOS (Windows via WSL2)

### Optional Components
- PostgreSQL (for persistent storage)
- Redis (for distributed caching)
- Elasticsearch (for advanced search features)

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](docs/CONTRIBUTING.md) for details.

### Development Setup
```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Format code
black src/
ruff check src/

# Type checking
mypy src/
```

## 📄 License

Swiss Sandbox is licensed under the Apache License 2.0. See [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

Swiss Sandbox integrates best-in-class open source technologies:

- [Zoekt](https://github.com/sourcegraph/zoekt) - Lightning-fast code search
- [Docker](https://www.docker.com/) - Container runtime
- [FastMCP](https://github.com/modelcontextprotocol/fastmcp) - MCP framework
- [Manim](https://www.manim.community/) - Mathematical animations

## 📊 Project Status

- **Version**: 3.0.0
- **Status**: Production Ready
- **Tests**: 12/12 Passing (100%)
- **Tools**: 68 Fully Implemented
- **Coverage**: 95%+

## 💬 Support

- [GitHub Issues](https://github.com/scooter-lacroix/swiss-sandbox/issues)
- [Discussions](https://github.com/scooter-lacroix/swiss-sandbox/discussions)
- [Wiki](https://github.com/scooter-lacroix/swiss-sandbox/wiki)

---

**Swiss Sandbox** - Your AI Development Swiss Army Knife 🛠️

*Precision. Versatility. Reliability.*
