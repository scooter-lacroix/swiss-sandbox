# Intelligent Sandbox System

A comprehensive virtual development environment where AI models can perform unrestricted coding actions safely with workspace cloning, intelligent codebase understanding, dynamic task planning, and detailed execution tracking.

## Overview

The Intelligent Sandbox System transforms the basic sandbox into a "virtual computer" environment that provides:

- **Workspace Cloning**: Complete isolation of workspaces with Docker/container support
- **Codebase Analysis**: Intelligent understanding of code structure, patterns, and dependencies
- **Task Planning**: Dynamic breakdown of complex tasks into manageable subtasks
- **Execution Engine**: Sequential task execution with comprehensive error handling
- **Action Logging**: Detailed tracking of all sandbox activities
- **MCP Integration**: FastMCP server for seamless AI model integration

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Host Environment                          │
│  ┌─────────────────┐    ┌─────────────────────────────────┐ │
│  │  User Interface │    │      FastMCP Server             │ │
│  │                 │    │  (IntelligentSandboxMCPServer)  │ │
│  └─────────────────┘    └─────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────┐
│                 Sandbox Environment                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  Workspace  │  │  Codebase   │  │    Task Planner     │  │
│  │   Cloner    │  │  Analyzer   │  │                     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐                          │
│  │ Execution   │  │   Action    │                          │
│  │   Engine    │  │   Logger    │                          │
│  └─────────────┘  └─────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Workspace Management (`workspace/`)
- **WorkspaceCloner**: Creates isolated copies of workspaces
- **SandboxWorkspace**: Represents an isolated workspace
- **IsolationConfig**: Configuration for container isolation

### 2. Codebase Analysis (`analyzer/`)
- **CodebaseAnalyzer**: Analyzes code structure and patterns
- **CodebaseAnalysis**: Complete analysis results
- **DependencyGraph**: Dependency mapping and analysis

### 3. Task Planning (`planner/`)
- **TaskPlanner**: Intelligent task breakdown and planning
- **TaskPlan**: Dynamic task execution plans
- **Task**: Individual tasks with status tracking

### 4. Execution Engine (`executor/`)
- **ExecutionEngine**: Sequential task execution
- **ExecutionResult**: Comprehensive execution results
- **RetryContext**: Error handling and retry logic

### 5. Action Logging (`logger/`)
- **ActionLogger**: Comprehensive activity logging
- **Action**: Individual logged actions
- **LogSummary**: Execution history summaries

### 6. MCP Integration (`mcp/`)
- **IntelligentSandboxMCPServer**: FastMCP server implementation
- **register_sandbox_tools**: Tool registration utilities

## Usage

### As a Standalone MCP Server

```bash
# Run with stdio transport (default for MCP)
python src/sandbox/intelligent_sandbox_server.py

# Run with HTTP transport
python src/sandbox/intelligent_sandbox_server.py http 0.0.0.0 8765
```

### As a Library

```python
from sandbox.intelligent import (
    IntelligentSandboxMCPServer,
    WorkspaceCloner,
    CodebaseAnalyzer,
    TaskPlanner,
    ExecutionEngine
)

# Create and run MCP server
server = IntelligentSandboxMCPServer("my-sandbox")
server.run_stdio()

# Or use components directly
cloner = WorkspaceCloner()
workspace = cloner.clone_workspace("/path/to/source", "my-workspace")

analyzer = CodebaseAnalyzer()
analysis = analyzer.analyze_codebase(workspace)

planner = TaskPlanner()
plan = planner.create_plan("Implement user authentication", analysis)
```

### Integration with Existing FastMCP Server

```python
from fastmcp import FastMCP
from sandbox.intelligent.mcp import register_sandbox_tools

# Add intelligent sandbox tools to existing server
mcp = FastMCP("my-server")
register_sandbox_tools(mcp)
mcp.run()
```

## MCP Tools

The intelligent sandbox provides the following MCP tools:

- `create_sandbox_workspace`: Create isolated workspace
- `analyze_codebase`: Analyze code structure and patterns
- `create_task_plan`: Generate detailed task plans
- `execute_task_plan`: Execute tasks sequentially
- `get_execution_history`: Retrieve activity logs
- `cleanup_workspace`: Clean up sandbox resources
- `get_sandbox_status`: Get system status

## Configuration

The system uses a comprehensive configuration system:

```python
from sandbox.intelligent import get_config, get_config_manager

# Get current configuration
config = get_config()
print(f"Command timeout: {config.default_command_timeout}")

# Update configuration
config_manager = get_config_manager()
config_manager.set_setting("max_concurrent_sandboxes", 10)
```

Configuration options include:
- Isolation settings (Docker, resource limits)
- Execution settings (timeouts, retries)
- Logging settings (retention, detail level)
- Security settings (allowed hosts, command validation)

## Security Features

- **Complete Isolation**: Docker/container-based workspace isolation
- **Resource Limits**: CPU, memory, and disk space constraints
- **Network Isolation**: Controlled external access
- **Command Validation**: Optional command filtering
- **Audit Logging**: Comprehensive activity tracking

## Development Status

This is the initial implementation with core structure and interfaces. The following components have TODO placeholders for future development:

- Actual workspace cloning and Docker integration
- Codebase analysis algorithms
- Task breakdown intelligence
- Command execution within containers
- Advanced error recovery

## Requirements

- Python 3.8+
- FastMCP
- Docker (for workspace isolation)
- Additional dependencies as specified in requirements

## License

[License information]