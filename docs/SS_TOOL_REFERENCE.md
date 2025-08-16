# Swiss Sandbox (SS) Tool Reference
**Swiss army knife of AI toolkits - AI-Powered Development Environment with Intelligent Task Automation**

## Overview
Swiss Sandbox (SS) - the Swiss army knife of AI toolkits - is a comprehensive MCP server that combines isolated workspace management, intelligent code analysis, automated task planning, and advanced search capabilities into a single powerful development environment.

---

## 🏗️ Workspace Management Tools

### create_workspace
**Description:** Create an isolated development workspace
**Usage Example:**
```python
result = await create_workspace(
    source_path="/path/to/project",
    use_docker=True,
    resource_limits={"memory_mb": 2048, "cpu_cores": 2}
)
# Returns: {"workspace_id": "ws_123", "sandbox_path": "/tmp/ws_123", "status": "active"}
```

### analyze_codebase
**Description:** Analyze project structure and dependencies
**Usage Example:**
```python
analysis = await analyze_codebase(
    workspace_id="ws_123",
    deep_analysis=True
)
# Returns: {"languages": ["Python", "JavaScript"], "frameworks": ["Flask"], "dependencies": {...}}
```

### destroy_workspace
**Description:** Clean up and remove a workspace
**Usage Example:**
```python
await destroy_workspace(workspace_id="ws_123", force=False)
# Returns: {"success": true, "message": "Workspace removed"}
```

### list_workspaces
**Description:** List all active workspaces
**Usage Example:**
```python
workspaces = await list_workspaces()
# Returns: [{"id": "ws_123", "path": "/tmp/ws_123", "created": "2024-01-01T00:00:00Z"}]
```

---

## 📋 Task Planning & Execution Tools

### create_task_plan
**Description:** Generate an intelligent task plan for your project
**Usage Example:**
```python
plan = await create_task_plan(
    workspace_id="ws_123",
    description="Setup Python project with tests and CI",
    auto_approve=False
)
# Returns: {"plan_id": "plan_456", "tasks": [{"name": "setup", "command": "pip install -r requirements.txt"}]}
```

### execute_task_plan
**Description:** Execute a task plan sequentially or in parallel
**Usage Example:**
```python
execution = await execute_task_plan(
    plan_id="plan_456",
    parallel=False,
    timeout=300
)
# Returns: {"execution_id": "exec_789", "status": "running", "progress": 0}
```

### get_execution_history
**Description:** Get detailed execution history and logs
**Usage Example:**
```python
history = await get_execution_history(workspace_id="ws_123")
# Returns: [{"task": "setup", "status": "completed", "output": "...", "duration": 2.5}]
```

### retry_failed_task
**Description:** Retry a specific failed task
**Usage Example:**
```python
result = await retry_failed_task(
    execution_id="exec_789",
    task_id="task_001"
)
# Returns: {"success": true, "new_status": "completed"}
```

---

## 🔍 Code Search & Indexing Tools

### set_project_path
**Description:** Set project path and initialize search index
**Usage Example:**
```python
await set_project_path(
    path="/home/user/project",
    index_immediately=True,
    watch_changes=True
)
# Returns: {"success": true, "indexed_files": 150}
```

### search_code_advanced
**Description:** Search code using multiple backends (Zoekt, ripgrep, AST)
**Usage Example:**
```python
results = await search_code_advanced(
    pattern="def.*test.*",
    use_regex=True,
    search_type="zoekt",
    file_pattern="*.py",
    max_results=50
)
# Returns: [{"file": "test.py", "line": 10, "content": "def test_function():", "context": [...]}]
```

### find_files
**Description:** Find files by name patterns
**Usage Example:**
```python
files = await find_files(
    patterns=["*.test.js", "*spec.py"],
    exclude_dirs=["node_modules", ".git"]
)
# Returns: ["src/test.spec.py", "tests/unit.test.js"]
```

### force_reindex
**Description:** Force complete reindexing of the project
**Usage Example:**
```python
await force_reindex(clear_cache=True)
# Returns: {"success": true, "files_indexed": 200, "time_taken": 1.5}
```

---

## 📝 File Operations Tools

### write_to_file
**Description:** Write content to file with version tracking
**Usage Example:**
```python
await write_to_file(
    path="src/main.py",
    content="def main():\n    print('Hello')\n",
    line_count=2
)
# Returns: {"success": true, "version": 3, "previous_version": 2}
```

### apply_diff
**Description:** Apply unified diff patches to files
**Usage Example:**
```python
await apply_diff(
    diff_content="--- a/test.py\n+++ b/test.py\n@@ -1 +1 @@\n-old line\n+new line",
    backup=True
)
# Returns: {"success": true, "files_modified": 1, "backup_created": true}
```

### get_file_history
**Description:** Get version history of a file
**Usage Example:**
```python
history = await get_file_history(
    path="src/main.py",
    limit=10
)
# Returns: [{"version": 3, "timestamp": "2024-01-01T00:00:00Z", "size": 45, "diff": "..."}]
```

### revert_file_to_version
**Description:** Revert file to a previous version
**Usage Example:**
```python
await revert_file_to_version(
    path="src/main.py",
    version=2
)
# Returns: {"success": true, "current_version": 4, "reverted_from": 3}
```

---

## 🚀 Code Execution Tools

### execute
**Description:** Execute code in isolated environment
**Usage Example:**
```python
result = await execute(
    code="print('Hello'); import numpy as np; print(np.array([1,2,3]))",
    language="python",
    timeout=30
)
# Returns: {"output": "Hello\n[1 2 3]", "exit_code": 0, "duration": 0.5}
```

### execute_with_artifacts
**Description:** Execute code and collect generated artifacts
**Usage Example:**
```python
result = await execute_with_artifacts(
    code="import matplotlib.pyplot as plt\nplt.plot([1,2,3])\nplt.savefig('plot.png')",
    expected_artifacts=["plot.png"]
)
# Returns: {"output": "", "artifacts": [{"name": "plot.png", "path": "/tmp/artifacts/plot.png"}]}
```

### start_enhanced_repl
**Description:** Start an interactive REPL session
**Usage Example:**
```python
session = await start_enhanced_repl(
    language="python",
    persist_state=True
)
# Returns: {"session_id": "repl_123", "status": "active", "port": 9999}
```

---

## 🎨 Animation & Visualization Tools

### create_manim_animation
**Description:** Create mathematical animations using Manim
**Usage Example:**
```python
animation = await create_manim_animation(
    code="class Square(Scene):\n    def construct(self):\n        self.play(Create(Square()))",
    quality="high",
    format="mp4"
)
# Returns: {"animation_id": "anim_456", "output_path": "/tmp/animations/Square.mp4"}
```

---

## 🌐 Web Application Tools

### start_web_app
**Description:** Deploy and run web applications
**Usage Example:**
```python
app = await start_web_app(
    code="from flask import Flask\napp = Flask(__name__)\n@app.route('/')\ndef home(): return 'Hello'",
    app_type="flask",
    port=5000,
    containerize=True
)
# Returns: {"app_id": "app_789", "url": "http://localhost:5000", "container_id": "c123"}
```

### export_web_app
**Description:** Export web app with Docker configuration
**Usage Example:**
```python
export = await export_web_app(
    app_id="app_789",
    include_dockerfile=True,
    include_compose=True
)
# Returns: {"export_path": "/tmp/exports/app_789.tar.gz", "files": ["Dockerfile", "docker-compose.yml"]}
```

---

## 📦 Artifact Management Tools

### list_artifacts
**Description:** List all generated artifacts
**Usage Example:**
```python
artifacts = await list_artifacts(
    category="plots",
    date_range={"from": "2024-01-01", "to": "2024-01-31"}
)
# Returns: [{"name": "plot.png", "size": 12345, "created": "2024-01-15T10:00:00Z"}]
```

### backup_current_artifacts
**Description:** Create backup of current artifacts
**Usage Example:**
```python
backup = await backup_current_artifacts(
    compress=True,
    categories=["plots", "data"]
)
# Returns: {"backup_id": "backup_123", "path": "/tmp/backups/backup_123.tar.gz", "size": 1048576}
```

---

## 🔧 System & Utility Tools

### get_system_status
**Description:** Get comprehensive system status
**Usage Example:**
```python
status = await get_system_status()
# Returns: {"cpu": "15%", "memory": "2.5GB/8GB", "disk": "100GB/500GB", "active_workspaces": 3}
```

### shell_execute
**Description:** Execute shell commands safely
**Usage Example:**
```python
result = await shell_execute(
    command="ls -la",
    cwd="/home/user/project",
    timeout=10
)
# Returns: {"stdout": "total 24\ndrwxr-xr-x...", "stderr": "", "exit_code": 0}
```

### install_package
**Description:** Install packages in workspace
**Usage Example:**
```python
await install_package(
    packages=["numpy", "pandas"],
    workspace_id="ws_123",
    package_manager="pip"
)
# Returns: {"success": true, "installed": ["numpy==1.24.0", "pandas==2.0.0"]}
```

### cleanup_all_resources
**Description:** Clean up all resources and temporary files
**Usage Example:**
```python
await cleanup_all_resources(
    force=False,
    keep_backups=True
)
# Returns: {"cleaned": {"workspaces": 2, "artifacts": 150, "cache": "500MB"}}
```

---

## 🏆 Best Practices

1. **Always use workspace isolation** for untrusted code
2. **Set appropriate resource limits** to prevent resource exhaustion
3. **Use version tracking** for important file modifications
4. **Enable watch mode** for real-time indexing of active projects
5. **Backup artifacts regularly** before cleanup operations
6. **Use parallel execution** for independent tasks
7. **Specify timeouts** for long-running operations

---

## 📊 Performance Guidelines

- **Small Projects (<1000 files):** Use default settings
- **Medium Projects (1000-10000 files):** Enable lazy loading, use incremental indexing
- **Large Projects (>10000 files):** Use Zoekt search, enable caching, limit parallel operations
- **Memory Constrained (<4GB):** Set memory limits, use SQLite instead of PostgreSQL
- **CPU Constrained (<4 cores):** Disable parallel execution, reduce indexing threads

---

## 🔒 Security Notes

- All workspaces are isolated with configurable resource limits
- Path traversal attacks are prevented through validation
- Command injection is mitigated through proper escaping
- Network access can be restricted per workspace
- Docker containers run with minimal privileges
- All file operations are logged for audit trails

---

## 💡 Tips for Small Language Models (4B-8B parameters)

For optimal tool usage with smaller models:

1. **Use simple, direct commands** - Avoid complex nested parameters
2. **Specify explicit paths** - Don't rely on relative paths
3. **Use default values** - Only override when necessary
4. **Chain simple operations** - Break complex tasks into steps
5. **Check status frequently** - Use status tools to verify operations

Example for small models:
```python
# Simple, step-by-step approach
await set_project_path(path="/home/user/project")
files = await find_files(patterns=["*.py"])
result = await search_code_advanced(pattern="TODO", search_type="simple")
```

---

## 📚 Complete Tool Count: 68 Tools

**Workspace & Analysis:** 19 tools  
**Search & Indexing:** 25 tools  
**Execution & Artifacts:** 18 tools  
**System & Utilities:** 6 tools
