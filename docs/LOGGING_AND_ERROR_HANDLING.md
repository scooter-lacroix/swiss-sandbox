# Comprehensive Logging and Error Handling System

This document describes the comprehensive logging and error handling system implemented for the Swiss Sandbox restoration project - the Swiss army knife of AI toolkits.

## Overview

The logging and error handling system provides:

- **Structured Logging**: JSON-formatted logs with comprehensive metadata
- **Error Recovery**: Automatic error recovery with configurable strategies
- **Performance Monitoring**: Real-time performance metrics and monitoring
- **Health Monitoring**: System health checks and diagnostics
- **Diagnostic Tools**: Comprehensive diagnostic reports and troubleshooting

## Components

### 1. StructuredLogger

The `StructuredLogger` class provides structured logging with JSON output and comprehensive metadata.

**Features:**
- Multiple output formats (console, file, JSON)
- Thread-safe logging with background processing
- Automatic log rotation
- Structured metadata support

**Usage:**
```python
from sandbox.core.logging_system import StructuredLogger

logger = StructuredLogger("component_name")
logger.info("Operation completed", 
           component="execution_engine",
           context_id="workspace_123",
           execution_time=1.5)
```

### 2. ErrorHandler

The `ErrorHandler` class provides comprehensive error handling with automatic recovery strategies.

**Features:**
- Categorized error handling
- Automatic recovery attempts
- Error statistics and tracking
- Configurable recovery strategies

**Error Categories:**
- `EXECUTION`: Code/command execution errors
- `SECURITY`: Security policy violations
- `RESOURCE`: Memory/CPU/disk resource errors
- `SYSTEM`: System-level errors
- `NETWORK`: Network-related errors
- `VALIDATION`: Input validation errors
- `TIMEOUT`: Operation timeout errors
- `PERMISSION`: Permission/access errors

**Usage:**
```python
from sandbox.core.logging_system import ErrorHandler, ErrorCategory

error_handler = ErrorHandler(logger)

try:
    # Some operation that might fail
    risky_operation()
except Exception as e:
    recovered = error_handler.handle_error(
        e, ErrorCategory.EXECUTION, "component_name",
        {'context_id': 'workspace_123', 'operation': 'risky_operation'}
    )
```

### 3. PerformanceMonitor

The `PerformanceMonitor` class provides real-time performance monitoring and metrics collection.

**Features:**
- Operation timing and measurement
- Memory and CPU usage tracking
- Background system monitoring
- Performance statistics and summaries

**Usage:**
```python
from sandbox.core.logging_system import PerformanceMonitor

performance_monitor = PerformanceMonitor(logger)

# Measure operation performance
with performance_monitor.measure_operation("component", "operation", "context_id"):
    # Your operation here
    time.sleep(1)

# Get performance summary
summary = performance_monitor.get_performance_summary()
```

### 4. HealthMonitor

The `HealthMonitor` class provides comprehensive system health monitoring.

**Features:**
- Multi-component health checks
- Continuous background monitoring
- Health history tracking
- Diagnostic report generation

**Health Components:**
- System resources (CPU, memory, disk)
- Error rates and recovery
- Performance metrics
- Component-specific health

**Usage:**
```python
from sandbox.core.health_monitor import HealthMonitor

health_monitor = HealthMonitor(logger, error_handler, performance_monitor)

# Get overall health status
health_report = health_monitor.get_overall_health()

# Get diagnostic report
diagnostic_report = health_monitor.get_diagnostic_report()
```

### 5. DiagnosticTools

The `DiagnosticTools` class provides comprehensive diagnostic capabilities.

**Features:**
- System health checks
- Performance analysis
- Error analysis
- Recommendation generation

## Integration with Unified Server

The logging and error handling system is fully integrated with the `UnifiedSandboxServer`:

### Initialization

```python
# The server automatically initializes all logging components
server = UnifiedSandboxServer(config)

# Components are available as:
server.structured_logger
server.error_handler
server.performance_monitor
server.health_monitor
```

### MCP Tools

The following diagnostic MCP tools are automatically registered:

- `health_check`: Comprehensive health check
- `get_diagnostic_report`: Full diagnostic report
- `get_error_statistics`: Error statistics and recovery info
- `get_performance_metrics`: Performance metrics
- `get_health_history`: Health monitoring history
- `trigger_garbage_collection`: Manual garbage collection

### Usage Examples

```python
# Health check
health_result = server.mcp.call_tool("health_check")

# Get diagnostic report
diagnostic_result = server.mcp.call_tool("get_diagnostic_report")

# Get error statistics
error_stats = server.mcp.call_tool("get_error_statistics")
```

## Decorators

The system provides decorators for automatic error handling and performance monitoring:

### @with_error_handling

Automatically handles errors with recovery attempts:

```python
from sandbox.core.logging_system import with_error_handling, ErrorCategory

@with_error_handling(ErrorCategory.EXECUTION, "component_name")
def risky_function():
    # Function that might fail
    pass
```

### @with_performance_monitoring

Automatically measures function performance:

```python
from sandbox.core.logging_system import with_performance_monitoring

@with_performance_monitoring("component_name", "operation_name")
def measured_function():
    # Function to measure
    pass
```

## Log Files

The system creates several log files in the `logs/` directory:

- `{component}.log`: Standard text logs
- `{component}_structured.jsonl`: Structured JSON logs (one JSON object per line)

### Log File Format

Structured logs are in JSON Lines format:

```json
{
  "timestamp": "2025-08-15T20:41:36.017000",
  "level": "INFO",
  "message": "Operation completed",
  "component": "execution_engine",
  "context_id": "workspace_123",
  "metadata": {
    "execution_time": 1.5,
    "success": true
  }
}
```

## Configuration

The logging system can be configured through the `ServerConfig`:

```python
config = ServerConfig(
    log_level="DEBUG",  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    # Other config options...
)
```

## Error Recovery Strategies

The system includes built-in recovery strategies for different error categories:

### Execution Errors
- Clear corrupted execution globals
- Restart execution context

### Resource Errors
- Trigger garbage collection
- Reduce resource limits

### Timeout Errors
- Extend timeout limits
- Kill hanging processes

### System Errors
- Restart components
- Enable fallback mode

## Health Check Components

The health monitoring system checks:

1. **System Health**: CPU, memory, disk usage
2. **Memory Health**: System and process memory usage
3. **Disk Health**: Disk space and I/O
4. **CPU Health**: CPU usage and load average
5. **Error Health**: Error rates and recovery
6. **Performance Health**: Success rates and response times

## Monitoring and Alerts

The system provides:

- **Continuous Monitoring**: Background health monitoring
- **Threshold Alerts**: Configurable alert thresholds
- **Health History**: Historical health data
- **Performance Trends**: Performance trend analysis

## Best Practices

1. **Use Structured Logging**: Always include relevant metadata
2. **Handle Errors Gracefully**: Use error categories appropriately
3. **Monitor Performance**: Use performance monitoring for critical operations
4. **Regular Health Checks**: Monitor system health regularly
5. **Review Logs**: Regularly review structured logs for insights

## Troubleshooting

### Common Issues

1. **Log Files Not Created**: Check directory permissions
2. **High Memory Usage**: Review log retention settings
3. **Performance Issues**: Check monitoring overhead
4. **Recovery Failures**: Review recovery strategies

### Diagnostic Commands

```python
# Get comprehensive diagnostic report
diagnostic_report = health_monitor.get_diagnostic_report()

# Get error statistics
error_stats = error_handler.get_error_statistics()

# Get performance summary
perf_summary = performance_monitor.get_performance_summary()

# Trigger garbage collection
import gc
collected = gc.collect()
```

## Testing

The system includes comprehensive tests:

- `test_logging_system.py`: Core logging system tests
- `test_server_integration.py`: Server integration tests

Run tests with:
```bash
python test_logging_system.py
python test_server_integration.py
```

## Future Enhancements

Potential future improvements:

1. **Remote Logging**: Send logs to external systems
2. **Advanced Analytics**: Machine learning for error prediction
3. **Custom Recovery**: User-defined recovery strategies
4. **Real-time Dashboards**: Web-based monitoring dashboards
5. **Alert Notifications**: Email/SMS alerts for critical issues