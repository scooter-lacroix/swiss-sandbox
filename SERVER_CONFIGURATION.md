# Swiss Sandbox Server Configuration

## Server Entry Points

The Swiss Sandbox system - the Swiss army knife of AI toolkits - now provides multiple ways to start the server:

### 1. Primary Entry Points

- **Unified Server**: `python -m sandbox.unified_server`
- **Package Entry**: `python -m sandbox`
- **Direct Script**: `python server.py`
- **Console Commands** (after installation):
  - `swiss-sandbox`
  - `ss-server`

### 2. Legacy Compatibility

- **Legacy MCP Server**: `python -m sandbox.mcp_sandbox_server` (redirects to unified)

### 3. Platform-Specific Scripts

- **Linux/macOS**: `./start_server.sh`
- **Windows**: `start_server.bat`

## MCP Configuration

### Basic Configuration (mcp.json)

```json
{
  "mcpServers": {
    "swiss-sandbox": {
      "command": "python3",
      "args": ["-m", "sandbox.unified_server"],
      "env": {
        "PYTHONPATH": "${PROJECT_DIR}/src"
      },
      "transport": "stdio",
      "disabled": false,
      "autoApprove": [
        "execute",
        "debug_execute",
        "create_artifact",
        "get_artifact",
        "list_artifacts",
        "create_workspace",
        "get_workspace_status",
        "cleanup_workspace"
      ]
    }
  }
}
```

### HTTP Transport Configuration

```json
{
  "mcpServers": {
    "swiss-sandbox-http": {
      "command": "python3",
      "args": [
        "-m",
        "sandbox.unified_server",
        "--transport",
        "http",
        "--port",
        "8765"
      ],
      "transport": "http",
      "disabled": false
    }
  }
}
```

## Command Line Options

The unified server supports the following command line options:

```bash
python -m sandbox.unified_server --help

Options:
  --transport {stdio,http}  Transport protocol (default: stdio)
  --host HOST              Host for HTTP transport (default: 127.0.0.1)
  --port PORT              Port for HTTP transport (default: 8765)
  --config CONFIG          Path to configuration file
  --log-level {DEBUG,INFO,WARNING,ERROR}
                          Logging level (default: INFO)
```

## Installation

### Development Installation

```bash
pip install -e .
```

### Production Installation

```bash
pip install swiss-sandbox
```

## Troubleshooting

### Import Errors

If you encounter import errors, ensure:

1. The `src` directory is in your Python path
2. All dependencies are installed: `pip install -r requirements.txt`
3. The package is properly installed: `pip install -e .`

### Server Won't Start

1. Check Python path: `echo $PYTHONPATH`
2. Verify installation: `python -c "import sandbox.unified_server"`
3. Check for port conflicts (HTTP mode)
4. Review log output for specific errors

### Legacy Compatibility

The system maintains backward compatibility with existing configurations:

- Old `mcp_sandbox_server.py` calls are automatically redirected
- Legacy `mcp.run()` calls work through compatibility wrapper
- Existing MCP configurations continue to work with updated entry points