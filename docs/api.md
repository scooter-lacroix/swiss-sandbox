# API Documentation

## Enhanced Sandbox SDK

The Enhanced Sandbox SDK provides a unified interface for both local and remote code execution with comprehensive artifact management and performance monitoring.

### Core Classes

#### PersistentExecutionContext

```python
from sandbox.core.execution_context import PersistentExecutionContext

context = PersistentExecutionContext(session_id="optional-session-id")
```

**Features:**
- Persistent variable storage across sessions
- Compilation caching for improved performance
- SQLite-based state persistence
- Comprehensive artifact tracking
- Performance metrics collection

**Methods:**

##### `execute_code(code: str, cache_key: Optional[str] = None) -> Dict[str, Any]`

Execute Python code with enhanced performance and caching.

```python
result = context.execute_code("""
import numpy as np
x = np.array([1, 2, 3, 4, 5])
print(f"Mean: {np.mean(x)}")
""", cache_key="numpy_mean_example")

# Returns:
{
    'success': True,
    'error': None,
    'error_type': None,
    'stdout': 'Mean: 3.0\n',
    'stderr': '',
    'execution_time': 0.045,
    'artifacts': [],
    'cache_hit': False
}
```

##### `get_execution_stats() -> Dict[str, Any]`

Get performance statistics.

```python
stats = context.get_execution_stats()
# Returns:
{
    'total_executions': 15,
    'average_execution_time': 0.123,
    'cache_hit_ratio': 0.73,
    'cache_hits': 11,
    'cache_misses': 4,
    'cached_compilations': 8,
    'session_id': 'unique-session-id',
    'artifacts_count': 3
}
```

##### `get_execution_history(limit: int = 100) -> List[Dict[str, Any]]`

Get execution history with metadata.

```python
history = context.get_execution_history(limit=10)
# Returns list of execution records with timestamps
```

#### LocalSandbox

Enhanced local sandbox with persistent execution context.

```python
from sandbox import LocalSandbox

sandbox = LocalSandbox(name="my-sandbox")
await sandbox.start()
```

**Enhanced Methods:**

##### `get_performance_stats() -> Dict[str, Any]`

Get performance statistics from the execution context.

```python
stats = sandbox.get_performance_stats()
```

##### `get_execution_history(limit: int = 50) -> List[Dict[str, Any]]`

Get execution history.

```python
history = sandbox.get_execution_history(limit=20)
```

##### `clear_cache() -> None`

Clear compilation and execution cache.

```python
sandbox.clear_cache()
```

##### `save_session() -> None`

Manually save the current execution session state.

```python
sandbox.save_session()
```

##### `session_id -> str`

Get the current session ID.

```python
session_id = sandbox.session_id
```

##### `cleanup_session() -> None`

Cleanup the current session.

```python
sandbox.cleanup_session()
```

### SDK Classes

#### PythonSandbox

```python
from sandbox import PythonSandbox

# Local execution
async with PythonSandbox.create_local(name="local-py") as sandbox:
    result = await sandbox.run("print('Hello World')")
    print(await result.output())

# Remote execution
async with PythonSandbox.create_remote(
    server_url="http://127.0.0.1:5555",
    api_key="your-key",
    name="remote-py"
) as sandbox:
    result = await sandbox.run("print('Hello from microVM')")
    print(await result.output())
```

#### NodeSandbox

```python
from sandbox import NodeSandbox

async with NodeSandbox.create(
    server_url="http://127.0.0.1:5555",
    api_key="your-key",
    name="node-env"
) as sandbox:
    result = await sandbox.run("console.log('Hello from Node.js')")
    print(await result.output())
```

#### LocalSandbox / RemoteSandbox

```python
from sandbox import LocalSandbox, RemoteSandbox

# Local sandbox
async with LocalSandbox.create(name="local") as sandbox:
    result = await sandbox.run("import sys; print(sys.version)")
    
# Remote sandbox
async with RemoteSandbox.create(
    server_url="http://127.0.0.1:5555",
    api_key="your-key"
) as sandbox:
    result = await sandbox.run("import sys; print(sys.version)")
```

### Configuration

#### SandboxOptions

Builder pattern for sandbox configuration:

```python
from sandbox import SandboxOptions

config = (SandboxOptions.builder()
          .name("configured-sandbox")
          .memory(1024)
          .cpus(2.0)
          .timeout(300.0)
          .env("DEBUG", "true")
          .env("LOG_LEVEL", "info")
          .build())

# Use with any sandbox type
sandbox = LocalSandbox.create(**config.__dict__)
```

**Builder Methods:**
- `name(name: str)` - Set sandbox name
- `memory(mb: int)` - Set memory limit in MB
- `cpus(count: float)` - Set CPU allocation
- `timeout(seconds: float)` - Set execution timeout
- `env(key: str, value: str)` - Set environment variable
- `build()` - Build the configuration

### Execution Results

#### Execution

```python
result = await sandbox.run("print('Hello')")

# Access properties
stdout = result.stdout
stderr = result.stderr
artifacts = result.artifacts
exception = result.exception

# Get combined output
output = await result.output()
```

#### CommandExecution

```python
cmd_result = await sandbox.command.run("ls", ["-la"])

output = await cmd_result.output()
exit_code = cmd_result.exit_code
```

### Metrics and Monitoring

#### Metrics

```python
# Get all metrics
metrics = await sandbox.metrics.all()

# Get specific metric
cpu_usage = await sandbox.metrics.get("cpu_usage")
memory_usage = await sandbox.metrics.get("memory_usage")
```

### Error Handling

All SDK methods use structured error handling:

```python
try:
    result = await sandbox.run("invalid python code")
except SandboxExecutionError as e:
    print(f"Execution failed: {e}")
    print(f"Error type: {e.error_type}")
    print(f"Traceback: {e.traceback}")
except SandboxTimeoutError as e:
    print(f"Execution timed out after {e.timeout} seconds")
except SandboxConnectionError as e:
    print(f"Connection failed: {e}")
```

### MCP Tools

The sandbox provides several MCP tools for integration with AI systems:

#### `execute`

Execute Python code with artifact capture.

```python
execute(code="print('Hello World')")
```

#### `shell_execute`

Execute shell commands safely.

```python
shell_execute("ls -la", working_directory="/tmp", timeout=30)
```

#### `list_artifacts`

List generated artifacts.

```python
list_artifacts()
```

#### `cleanup_artifacts`

Clean up temporary files.

```python
cleanup_artifacts()
```

#### `get_execution_info`

Get environment diagnostics.

```python
get_execution_info()
```

#### `start_web_app`

Launch Flask/Streamlit applications.

```python
start_web_app(code="flask_app_code", app_type="flask", port=5000)
```

#### `create_manim_animation`

Create mathematical animations.

```python
create_manim_animation(
    code="manim_scene_code",
    quality="medium_quality",
    scene_name="MyScene"
)
```

### Advanced Features

#### Session Persistence

Sessions automatically persist execution state:

```python
# First session
sandbox1 = LocalSandbox(name="persistent")
await sandbox1.start()
await sandbox1.run("x = 42")
session_id = sandbox1.session_id

# Later session with same ID
context = PersistentExecutionContext(session_id=session_id)
sandbox2 = LocalSandbox(name="persistent")
sandbox2._execution_context = context
await sandbox2.start()
result = await sandbox2.run("print(x)")  # Prints: 42
```

#### Performance Optimization

- **Compilation Caching**: Code compilation results are cached
- **Memory Management**: Automatic cleanup of large objects
- **Lazy Loading**: Artifacts loaded only when accessed
- **Connection Pooling**: Remote connections are pooled and reused

#### Artifact Management

```python
# Automatic artifact capture
await sandbox.run("""
import matplotlib.pyplot as plt
import numpy as np

x = np.linspace(0, 10, 100)
y = np.sin(x)

plt.plot(x, y)
plt.title('Sine Wave')
plt.show()  # Automatically captured
""")

# List artifacts
artifacts = sandbox.list_artifacts()
print(f"Created {len(artifacts)} artifacts")

# Get artifact directory
artifacts_dir = sandbox.artifacts_dir
```
