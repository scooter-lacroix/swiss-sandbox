# Sandbox Improvements Documentation

This document outlines the major improvements made to the sandbox environment to enhance reliability, usability, and user empowerment.

## 1. Artifact Versioning System

### Overview
The artifact versioning system provides comprehensive backup and rollback capabilities for all generated artifacts, safeguarding against accidental data loss.

### Features
- **Timestamped Backups**: Automatic creation of timestamped backups before cleanup
- **Custom Backup Names**: Optional custom naming for backups
- **Version Rollback**: Ability to rollback to any previous artifact version
- **Storage Management**: Automatic cleanup of old backups to prevent storage overflow (configurable limit)
- **Detailed Backup Info**: Comprehensive information about each backup including file counts, sizes, and categories

### MCP Tools
- `backup_current_artifacts(backup_name?)` - Create a backup of current artifacts
- `list_artifact_backups()` - List all available backups with details
- `rollback_to_backup(backup_name)` - Rollback to a specific backup
- `get_backup_details(backup_name)` - Get detailed information about a backup
- `cleanup_old_backups(max_backups=10)` - Clean up old backups

### Implementation Details
- Backups are stored in `artifact_backups/` directory in the project root
- Each backup includes metadata about file counts, sizes, and categories
- Automatic cleanup keeps only the 10 most recent backups by default
- Before rollback, current state is automatically backed up as "pre_rollback"

### Usage Examples
```python
# Create a backup with custom name
backup_current_artifacts("before_major_changes")

# List all backups
list_artifact_backups()

# Rollback to a specific backup
rollback_to_backup("backup_20231214_143022")

# Get detailed information about a backup
get_backup_details("backup_20231214_143022")
```

## 2. Web Application Export System

### Overview
The web application export system enables persistence and sharing of Flask and Streamlit applications beyond the sandbox session through Docker containerization.

### Features
- **Flask App Export**: Export Flask applications as Docker containers
- **Streamlit App Export**: Export Streamlit applications as Docker containers
- **Complete Package**: Includes Dockerfile, docker-compose.yml, requirements.txt, and README.md
- **Automatic Docker Build**: Attempts to build Docker images when Docker is available
- **Export Management**: List, inspect, and manage all exported applications
- **Easy Deployment**: Ready-to-deploy packages with instructions

### MCP Tools
- `export_web_app(code, app_type='flask', export_name?)` - Export a web application
- `list_web_app_exports()` - List all exported web applications
- `get_export_details(export_name)` - Get detailed information about an export
- `build_docker_image(export_name)` - Build Docker image for an export
- `cleanup_web_app_export(export_name)` - Remove an exported application

### File Structure
Each export creates a complete deployment package:
```
exports/
├── app_name/
│   ├── app.py              # Main application code
│   ├── requirements.txt    # Python dependencies
│   ├── Dockerfile         # Docker configuration
│   ├── docker-compose.yml # Docker Compose setup
│   └── README.md          # Deployment instructions
```

### Deployment Options
1. **Docker Compose**: `docker-compose up --build`
2. **Docker**: `docker build -t app-name . && docker run -p 8000:8000 app-name`
3. **Local**: `pip install -r requirements.txt && python app.py`

### Usage Examples
```python
# Export a Flask application
flask_code = """
from flask import Flask
app = Flask(__name__)

@app.route('/')
def hello():
    return 'Hello, World!'
"""
export_web_app(flask_code, 'flask', 'my_flask_app')

# List all exports
list_web_app_exports()

# Get export details
get_export_details('my_flask_app')

# Build Docker image
build_docker_image('my_flask_app')
```

## 3. Enhanced Error Logging and Reporting

### Overview
Comprehensive error handling with detailed tracebacks and contextual information for improved debugging.

### Features
- **Detailed Import Errors**: Full traceback with attempted paths and sys.path information
- **Syntax Error Detection**: Enhanced detection of code truncation issues
- **Contextual Error Messages**: Errors include environment information for debugging
- **JSON Error Responses**: Structured error responses with full details
- **Compilation Cache**: Warnings about potential code transmission issues

### Error Types Handled
- **ImportError**: Enhanced with module paths and environment details
- **SyntaxError**: Detection of truncation with helpful suggestions
- **TruncationError**: Special handling for code transmission issues
- **General Exceptions**: Full traceback with context

### Error Response Format
```json
{
  "error": {
    "type": "ImportError",
    "message": "No module named 'missing_module'",
    "module": "missing_module",
    "traceback": "Full traceback...",
    "sys_path": ["path1", "path2", ...],
    "attempted_paths": ["existing_path1", ...]
  },
  "stderr": "User-friendly error message with suggestions"
}
```

## 4. Dependency Management Documentation

### Installing Dependencies
Use `uv` package manager for fast dependency installation:

```bash
# Add a new dependency
uv add package_name

# Install from requirements
uv pip install -r requirements.txt

# Install development dependencies
uv add --dev pytest black flake8
```

### Common Dependencies
- **Web Frameworks**: `uv add flask streamlit fastapi`
- **Data Science**: `uv add pandas numpy matplotlib scipy`
- **Machine Learning**: `uv add scikit-learn tensorflow pytorch`
- **Animation**: `uv add manim`

### Troubleshooting
1. **Import Errors**: Check if package is installed in virtual environment
2. **Version Conflicts**: Use `uv pip list` to check installed packages
3. **Path Issues**: Verify virtual environment is activated
4. **Cache Issues**: Clear compilation cache with `clear_cache()`

## 5. Performance Improvements

### Caching System
- **Compilation Cache**: Caches compiled code for faster execution
- **Artifact Tracking**: Efficient tracking of new artifacts
- **Memory Management**: Automatic cleanup of old caches

### Resource Management
- **Process Tracking**: Tracks and manages running processes
- **Memory Limits**: Configurable memory limits for execution
- **Cleanup Automation**: Automatic cleanup of temporary files

## 6. Security Enhancements

### Command Security
- **Security Manager**: Blocks dangerous commands
- **Sandboxed Execution**: Execution in isolated sandbox area
- **Resource Limits**: Prevents resource exhaustion

### Safe Defaults
- **Working Directory**: Defaults to safe sandbox area
- **Timeout Limits**: Prevents infinite execution
- **Environment Isolation**: Controlled environment variables

## 7. Monitoring and Diagnostics

### Execution Info
- **Environment Details**: Complete environment information
- **Path Diagnostics**: sys.path and virtual environment status
- **Resource Usage**: Memory and process information

### Artifact Reports
- **Categorized Listing**: Artifacts organized by type
- **Size Information**: File sizes and storage usage
- **Metadata**: Creation time, modification time, and more

## 8. Best Practices

### Artifact Management
1. Create backups before major changes
2. Use descriptive backup names
3. Regular cleanup of old backups
4. Monitor artifact sizes

### Web App Development
1. Export applications for persistence
2. Use Docker for consistent deployment
3. Include proper requirements.txt
4. Test locally before deployment

### Error Handling
1. Check error logs for detailed information
2. Use structured error responses
3. Verify code completeness for truncation issues
4. Check virtual environment status

## 9. API Reference

### Artifact Versioning
```python
# Backup management
backup_current_artifacts(backup_name: str = None) -> str
list_artifact_backups() -> str
rollback_to_backup(backup_name: str) -> str
get_backup_details(backup_name: str) -> str
cleanup_old_backups(max_backups: int = 10) -> str
```

### Web App Export
```python
# Export management
export_web_app(code: str, app_type: str = 'flask', export_name: str = None) -> str
list_web_app_exports() -> str
get_export_details(export_name: str) -> str
build_docker_image(export_name: str) -> str
cleanup_web_app_export(export_name: str) -> str
```

### Enhanced Execution
```python
# Execution with tracking
execute_with_artifacts(code: str, track_artifacts: bool = True) -> str
get_artifact_report() -> str
categorize_artifacts() -> str
cleanup_artifacts_by_type(artifact_type: str) -> str
```

## 10. Migration Guide

### From Previous Version
1. Existing artifacts are automatically compatible
2. New backup system requires no migration
3. Export functionality is additive
4. Error handling is backward compatible

### Configuration
- Backup limits configurable via `max_backups` parameter
- Export directory structure is standardized
- Docker integration is optional but recommended

This comprehensive improvement package delivers enhanced reliability, usability, and user empowerment while maintaining backward compatibility with existing sandbox functionality.
