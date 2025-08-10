# Installation Guide

## Prerequisites

### System Requirements

- **Python**: 3.9 or higher
- **Operating System**: Linux, macOS, or Windows
- **Memory**: Minimum 512MB RAM available for sandbox execution
- **Storage**: At least 1GB free space for artifacts and session data

### Required Tools

#### uv (Recommended)

uv is the fastest Python package manager and is recommended for this project.

**Install uv:**

```bash
# macOS and Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Alternative: pip install
pip install uv
```

#### Git

Ensure Git is installed for cloning the repository:

```bash
# Check if Git is installed
git --version

# Install Git if needed:
# Ubuntu/Debian: sudo apt install git
# macOS: brew install git
# Windows: Download from https://git-scm.com/
```

## Installation Methods

### Method 1: Using uv (Recommended)

```bash
# Clone the repository
git clone https://github.com/scooter-lacroix/sandbox-mcp.git
cd sandbox-mcp

# Create virtual environment and install
uv venv
uv pip install -e .

# Verify installation
uv run sandbox-server-stdio --help
```

### Method 2: Using pip

```bash
# Clone the repository
git clone https://github.com/scooter-lacroix/sandbox-mcp.git
cd sandbox-mcp

# Create and activate virtual environment
python -m venv .venv

# Activate virtual environment
# Linux/macOS:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# Install package
pip install -e .

# Verify installation
sandbox-server-stdio --help
```

### Method 3: Direct Installation from Git

```bash
# Using uv
uv pip install git+https://github.com/scooter-lacroix/sandbox-mcp.git

# Using pip
pip install git+https://github.com/scooter-lacroix/sandbox-mcp.git
```

## Development Installation

For development work, install with additional dependencies:

```bash
# Clone repository
git clone https://github.com/scooter-lacroix/sandbox-mcp.git
cd sandbox-mcp

# Install with development dependencies
uv venv
uv pip install -e ".[dev]"

# Or with pip
pip install -e ".[dev]"
```

Development dependencies include:
- pytest for testing
- pytest-asyncio for async testing
- black for code formatting
- flake8 for linting

## Optional Dependencies

### For Matplotlib Support

```bash
# Install matplotlib for plot generation
uv pip install matplotlib
# or
pip install matplotlib
```

### For Image Processing

```bash
# Install Pillow for image handling
uv pip install Pillow
# or
pip install Pillow
```

### For Web Applications

```bash
# Install Flask for web app support
uv pip install Flask
# or
pip install Flask

# Install Streamlit for data apps
uv pip install streamlit
# or
pip install streamlit
```

### For Mathematical Animations

```bash
# Install Manim for mathematical animations
uv pip install manim
# or
pip install manim

# Note: Manim may require additional system dependencies
# See: https://docs.manim.community/en/stable/installation.html
```

### For Enhanced Features

```bash
# Install all optional dependencies at once
uv pip install matplotlib Pillow Flask streamlit manim numpy pandas
```

## Configuration

### Environment Setup

The sandbox automatically detects and configures the environment, but you can customize it:

#### Virtual Environment

The sandbox will automatically use a `.venv` directory if present:

```bash
# Ensure .venv is properly set up
uv venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows
```

#### Environment Variables

Set optional environment variables:

```bash
# Set custom temp directory
export SANDBOX_TEMP_DIR="/custom/temp/path"

# Set logging level
export SANDBOX_LOG_LEVEL="DEBUG"

# Set custom session directory
export SANDBOX_SESSION_DIR="/custom/sessions"
```

### CLI Configuration

Test the CLI tools after installation:

```bash
# Test stdio server
sandbox-server-stdio --help

# Test HTTP server
sandbox-server --help
```

## Verification

### Basic Verification

```bash
# Test basic import
python -c "import sandbox; print('✓ Sandbox imported successfully')"

# Test CLI
sandbox-server-stdio --help

# Run simple test
python -c "
import asyncio
from sandbox import LocalSandbox

async def test():
    sandbox = LocalSandbox(name='test')
    await sandbox.start()
    result = await sandbox.run('print(\"Hello from sandbox!\")')
    print(f'✓ Output: {result.stdout.strip()}')
    await sandbox.stop()

asyncio.run(test())
"
```

### Comprehensive Testing

```bash
# Run the full test suite
uv run pytest tests/ -v

# Or with pip
pytest tests/ -v

# Run specific tests
python -m unittest tests.test_integration.TestBasicIntegration.test_simple_execution
```

### Performance Testing

```bash
# Test execution performance
python -c "
import asyncio
import time
from sandbox import LocalSandbox

async def perf_test():
    sandbox = LocalSandbox(name='perf-test')
    await sandbox.start()
    
    start = time.time()
    for i in range(10):
        await sandbox.run(f'result_{i} = {i} * 2')
    
    stats = sandbox.get_performance_stats()
    print(f'✓ Performance test completed')
    print(f'  - Executions: {stats[\"total_executions\"]}')
    print(f'  - Average time: {stats[\"average_execution_time\"]:.3f}s')
    print(f'  - Cache hit ratio: {stats[\"cache_hit_ratio\"]:.2%}')
    
    await sandbox.stop()

asyncio.run(perf_test())
"
```

## Integration Setup

### LM Studio Integration

1. **Install and start the sandbox server:**

```bash
uv run sandbox-server-stdio
```

2. **Add to LM Studio MCP configuration:**

Add this to your LM Studio `settings.json`:

```json
{
  "mcpServers": {
    "sandbox": {
      "command": "sandbox-server-stdio",
      "args": []
    }
  }
}
```

3. **Alternative with custom path:**

If you need to specify the full path:

```json
{
  "mcpServers": {
    "sandbox": {
      "command": "/path/to/your/.venv/bin/sandbox-server-stdio",
      "args": []
    }
  }
}
```

### Remote Sandbox Integration

For remote execution with microsandbox:

1. **Start the microsandbox server** (see microsandbox documentation)

2. **Configure the sandbox client:**

```python
from sandbox import RemoteSandbox

async with RemoteSandbox.create(
    server_url="http://your-microsandbox-server:5555",
    api_key="your-api-key",
    name="remote-env"
) as sandbox:
    result = await sandbox.run("print('Hello from remote!')")
    print(await result.output())
```

## Troubleshooting

### Common Issues

#### Import Errors

```bash
# If you get import errors, check Python path
python -c "import sys; print('\n'.join(sys.path))"

# Ensure package is installed in development mode
uv pip install -e .
```

#### Virtual Environment Issues

```bash
# Check if virtual environment is activated
python -c "import sys; print(sys.prefix)"

# Check for .venv directory
ls -la .venv/

# Recreate virtual environment if needed
rm -rf .venv
uv venv .venv
uv pip install -e .
```

#### Permission Issues

```bash
# On Linux/macOS, ensure proper permissions
chmod +x .venv/bin/sandbox-server-stdio

# Check if executables are in PATH
which sandbox-server-stdio
```

#### Package Dependencies

```bash
# Check installed packages
uv pip list
# or
pip list

# Update packages
uv pip install --upgrade sandbox-mcp
```

### Platform-Specific Notes

#### Windows

- Use PowerShell or Command Prompt
- Use backslashes for paths: `.venv\Scripts\activate`
- Some features may require Windows Subsystem for Linux (WSL)

#### macOS

- May require Xcode command line tools: `xcode-select --install`
- Use Homebrew for system dependencies: `brew install python`

#### Linux

- Install system dependencies as needed:
  ```bash
  # Ubuntu/Debian
  sudo apt update
  sudo apt install python3-dev python3-venv
  
  # CentOS/RHEL
  sudo yum install python3-devel
  ```

### Getting Help

If you encounter issues:

1. **Check the logs:**
   ```bash
   # Run with debug logging
   SANDBOX_LOG_LEVEL=DEBUG sandbox-server-stdio
   ```

2. **Run diagnostics:**
   ```bash
   python -c "
   from sandbox import LocalSandbox
   import asyncio
   
   async def diagnose():
       sandbox = LocalSandbox(name='diag')
       await sandbox.start()
       info = sandbox.get_execution_info()
       print('Environment Info:')
       for key, value in info.items():
           print(f'  {key}: {value}')
       await sandbox.stop()
   
   asyncio.run(diagnose())
   "
   ```

3. **Check GitHub issues:** [sandbox-mcp issues](https://github.com/scooter-lacroix/sandbox-mcp/issues)

4. **Create a new issue** with:
   - Python version (`python --version`)
   - Operating system
   - Installation method used
   - Full error traceback
   - Minimal reproduction code
