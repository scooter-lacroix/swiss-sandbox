# Enhanced Sandbox System - Complete Feature Documentation

## Overview

The enhanced sandbox system provides comprehensive Python code execution with advanced artifact management, Manim animation support, performance monitoring, and intelligent error handling. This document describes all the new features and improvements.

## 🎨 Enhanced Artifact Management System

### Features

1. **Automatic Categorization**: Files are automatically categorized by type and location
2. **Comprehensive Metadata**: Each artifact includes size, timestamps, and detailed information
3. **Smart Detection**: Manim files and other special types are intelligently detected
4. **Cleanup by Type**: Selective cleanup of specific artifact categories

### Categories

- **images**: PNG, JPG, JPEG, GIF, BMP, TIFF, SVG, WebP files
- **videos**: MP4, AVI, MOV, WMV, FLV, WebM, MKV files
- **plots**: Charts and graphs from matplotlib and similar libraries
- **data**: CSV, JSON, XML, YAML, Pickle, HDF5 files
- **code**: Python, JavaScript, HTML, CSS, SQL, Shell scripts
- **documents**: PDF, DOCX, DOC, TXT, Markdown files
- **audio**: MP3, WAV, FLAC, AAC, OGG, M4A files
- **manim**: Animation files from Manim library
- **other**: Uncategorized files

### Usage Examples

```python
# Get comprehensive artifact report
report = sandbox.get_artifact_report()
print(f"Total artifacts: {report['total_artifacts']}")
print(f"Total size: {report['total_size']} bytes")

# Get categorized artifacts with metadata
categorized = sandbox.categorize_artifacts()
for category, files in categorized.items():
    if files:
        print(f"{category}: {len(files)} files")

# Get human-readable summary
summary = sandbox.get_artifact_summary()
print(summary)

# Cleanup specific types
cleaned_count = sandbox.cleanup_artifacts_by_type('plots')
print(f"Cleaned {cleaned_count} plot files")
```

## 🎬 Enhanced Manim Support

### Features

1. **Virtual Environment Integration**: Automatically uses virtual environment Manim installation
2. **Fallback Support**: Falls back to system Manim if venv not available
3. **Enhanced Code Processing**: Automatically adds imports if missing
4. **Comprehensive Output**: Tracks scenes, execution time, and generated files
5. **Error Handling**: Detailed error messages for Manim-specific issues

### Quality Options

- `low_quality`: Fast rendering for testing
- `medium_quality`: Balanced quality and speed (default)
- `high_quality`: High resolution output
- `production_quality`: Maximum quality for final output

### Usage Examples

```python
# Create Manim animation
manim_code = """
from manim import *

class SimpleCircle(Scene):
    def construct(self):
        circle = Circle()
        circle.set_fill(PINK, opacity=0.5)
        self.play(Create(circle))
        self.wait(1)
"""

result = await sandbox.run(manim_code)

# Get Manim-specific artifacts
manim_artifacts = sandbox.get_manim_artifacts()
for artifact in manim_artifacts:
    print(f"Animation: {artifact['name']}")
```

### MCP Tools

- `create_manim_animation(code, quality)`: Create animations
- `list_manim_animations()`: List all animations
- `cleanup_manim_animation(animation_id)`: Remove specific animation
- `get_manim_examples()`: Get code examples

## ⚡ Performance Monitoring and Caching

### Features

1. **Compilation Caching**: Compiled code is cached for repeated execution
2. **Execution Statistics**: Track execution times and performance metrics
3. **Cache Hit Tracking**: Monitor cache effectiveness
4. **Execution History**: Complete history of all executed code
5. **Performance Profiling**: Detailed performance analysis

### Usage Examples

```python
# Get performance statistics
stats = sandbox.get_performance_stats()
print(f"Cache hit ratio: {stats['cache_hit_ratio']:.2%}")
print(f"Average execution time: {stats['average_execution_time']:.3f}s")

# Get execution history
history = sandbox.get_execution_history(limit=10)
for entry in history:
    print(f"Code: {entry['code'][:50]}...")
    print(f"Success: {entry['result']['success']}")
    print(f"Time: {entry['execution_time']:.3f}s")

# Clear cache when needed
sandbox.clear_cache()
```

## 🚨 Enhanced Error Handling

### Features

1. **Categorized Errors**: Different handling for import, syntax, and runtime errors
2. **Detailed Tracebacks**: Complete stack traces with context
3. **Import Error Analysis**: Specific analysis for missing modules
4. **Recovery Suggestions**: Helpful suggestions for common errors
5. **Non-Breaking Execution**: Errors don't crash the session

### Error Types

- **ImportError**: Missing modules with path analysis
- **SyntaxError**: Code syntax issues with line numbers
- **RuntimeError**: Execution-time errors with full context
- **SecurityError**: Blocked operations for safety

### Usage Examples

```python
# Error handling is automatic
result = await sandbox.run("import nonexistent_module")
if result.exception:
    print(f"Error type: {type(result.exception).__name__}")
    print(f"Error message: {result.exception}")
    # Full traceback available in result.stderr
```

## 💾 Session Management and Persistence

### Features

1. **Persistent State**: Variables persist across executions
2. **Session Saving**: Manual and automatic session state saving
3. **Session Recovery**: Reload previous sessions
4. **Variable Tracking**: Monitor all session variables
5. **Database Storage**: SQLite backend for persistence

### Usage Examples

```python
# Session variables persist automatically
await sandbox.run("x = 42")
await sandbox.run("y = x * 2")  # x is still available

# Manual session saving
sandbox.save_session()
session_id = sandbox.session_id

# Get session info
info = sandbox.get_execution_info()
print(f"Session ID: {session_id}")
print(f"Variables: {info['global_variables']}")
```

## 🧹 Cleanup and Management

### Features

1. **Selective Cleanup**: Clean specific artifact types
2. **Bulk Operations**: Clean all artifacts at once
3. **Size Management**: Monitor and control storage usage
4. **Automatic Cleanup**: Scheduled cleanup of old artifacts
5. **Session Cleanup**: Clean up session-specific data

### Usage Examples

```python
# Clean specific types
cleaned = sandbox.cleanup_artifacts_by_type('images')
print(f"Cleaned {cleaned} image files")

# Clean all artifacts
sandbox.cleanup_artifacts()

# Clean session data
sandbox.cleanup_session()
```

## 🔧 Enhanced REPL Features

### Features

1. **IPython Integration**: Full IPython support when available
2. **Tab Completion**: Intelligent code completion
3. **Magic Commands**: Custom magic commands for sandbox features
4. **History Support**: Command history with search
5. **Syntax Highlighting**: Enhanced code display

### Magic Commands

- `%artifacts`: List and manage artifacts
- `%manim`: Execute Manim animations
- `%save_session`: Save current session
- `%load_session`: Load saved session
- `%clear_cache`: Clear compilation cache
- `%env_info`: Show environment information

### Usage Examples

```python
# Start enhanced REPL
repl_info = sandbox.start_enhanced_repl()
print(f"IPython available: {repl_info['ipython_available']}")
print(f"Features: {repl_info['features']}")
```

## 📊 MCP Tools Reference

### Core Execution

- `execute(code, interactive, web_app_type)`: Execute Python code
- `execute_with_artifacts(code, track_artifacts)`: Execute with artifact tracking
- `shell_execute(command, working_directory, timeout)`: Execute shell commands

### Artifact Management

- `get_artifact_report()`: Get comprehensive artifact report
- `categorize_artifacts()`: Get categorized artifact list
- `cleanup_artifacts_by_type(type)`: Clean specific artifact types
- `list_artifacts()`: List all current artifacts
- `cleanup_artifacts()`: Clean all artifacts

### Manim Support

- `create_manim_animation(code, quality)`: Create Manim animations
- `list_manim_animations()`: List all animations
- `cleanup_manim_animation(animation_id)`: Remove specific animation
- `get_manim_examples()`: Get example code snippets

### Performance and Monitoring

- `get_execution_info()`: Get environment information
- `clear_cache(important_only)`: Clear compilation cache
- `cleanup_temp_artifacts(max_age_hours)`: Clean old temporary files

### REPL and Session

- `start_enhanced_repl()`: Start enhanced REPL session
- `start_repl()`: Start basic REPL session
- `start_web_app(code, app_type)`: Launch web applications

## 🛠️ Installation and Setup

### Prerequisites

- Python 3.9+
- Virtual environment (recommended)
- FFmpeg (for Manim video rendering)
- Cairo and Pango (for Manim text rendering)

### Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install manim jupyter matplotlib pandas numpy ipython

# Install the sandbox system
pip install -e .
```

### Configuration

The system automatically detects and configures:
- Virtual environment paths
- Manim installation
- FFmpeg availability
- IPython support

## 🔍 Troubleshooting

### Common Issues

1. **Manim not found**: Ensure Manim is installed in virtual environment
2. **FFmpeg missing**: Install FFmpeg for video rendering
3. **Import errors**: Check virtual environment activation
4. **Permission issues**: Ensure write access to artifacts directory

### Debug Mode

Enable debug mode for detailed logging:

```bash
export SANDBOX_MCP_DEBUG=1
```

### Log Files

Check log files for detailed error information:
- MCP Server: `/tmp/sandbox_mcp_server.log`
- Execution Context: Session-specific logs in artifacts directory

## 🚀 Performance Tips

1. **Use Caching**: Repeated code execution benefits from compilation caching
2. **Monitor Artifacts**: Regular cleanup prevents excessive disk usage
3. **Virtual Environment**: Use virtual environment for better dependency management
4. **Quality Settings**: Use appropriate Manim quality for your needs
5. **Selective Cleanup**: Clean specific artifact types instead of all artifacts

## 📈 Advanced Usage

### Custom Artifact Processing

```python
# Process artifacts with custom logic
categorized = sandbox.categorize_artifacts()
for category, files in categorized.items():
    if category == 'images':
        # Process images
        for file_info in files:
            print(f"Processing: {file_info['name']}")
```

### Performance Optimization

```python
# Monitor and optimize performance
stats = sandbox.get_performance_stats()
if stats['cache_hit_ratio'] < 0.5:
    print("Consider optimizing code for better caching")

# Use execution history for analysis
history = sandbox.get_execution_history(limit=50)
avg_time = sum(h['execution_time'] for h in history) / len(history)
print(f"Average execution time: {avg_time:.3f}s")
```

### Advanced Manim Integration

```python
# Create complex Manim scenes with error handling
manim_code = """
from manim import *

class ComplexScene(Scene):
    def construct(self):
        # Complex animation logic
        equations = [
            MathTex("E = mc^2"),
            MathTex("F = ma"),
            MathTex("\\\\nabla \\\\cdot E = \\\\frac{\\\\rho}{\\\\epsilon_0}")
        ]
        
        for eq in equations:
            self.play(Write(eq))
            self.wait(1)
            self.play(FadeOut(eq))
"""

result = await sandbox.run(manim_code)
if result.exception:
    print(f"Manim error: {result.exception}")
else:
    artifacts = sandbox.get_manim_artifacts()
    print(f"Created {len(artifacts)} Manim artifacts")
```

## 🎯 Best Practices

1. **Regular Cleanup**: Clean artifacts periodically to manage disk space
2. **Error Handling**: Always check execution results for errors
3. **Session Management**: Save important sessions for later use
4. **Performance Monitoring**: Monitor cache hit rates and execution times
5. **Virtual Environment**: Use virtual environment for dependency isolation
6. **Quality Settings**: Choose appropriate Manim quality for your use case
7. **Artifact Organization**: Use the categorization system for better organization

## 🔧 Configuration Options

### Environment Variables

- `SANDBOX_MCP_DEBUG`: Enable debug logging
- `VIRTUAL_ENV`: Virtual environment path (auto-detected)
- `MANIM_QUALITY`: Default Manim quality setting

### File Locations

- **Artifacts**: `{project_root}/artifacts/`
- **Sessions**: `{project_root}/sessions/`
- **Logs**: `/tmp/sandbox_mcp_server.log`
- **Cache**: In-memory compilation cache

This enhanced sandbox system provides a comprehensive platform for Python development with advanced artifact management, Manim animation support, and intelligent monitoring capabilities.
