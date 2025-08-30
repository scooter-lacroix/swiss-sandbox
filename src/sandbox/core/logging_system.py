"""
Comprehensive logging and error handling system for Swiss Sandbox.

This module provides structured logging, error recovery, diagnostics, and performance monitoring.
"""

import logging
import logging.handlers
import json
import time
import traceback
import threading
import psutil
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from contextlib import contextmanager
import functools
import queue
import atexit


class LogLevel(Enum):
    """Log levels for structured logging."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ErrorCategory(Enum):
    """Categories of errors for better classification."""
    EXECUTION = "execution"
    SECURITY = "security"
    RESOURCE = "resource"
    SYSTEM = "system"
    NETWORK = "network"
    VALIDATION = "validation"
    TIMEOUT = "timeout"
    PERMISSION = "permission"


@dataclass
class LogEntry:
    """Structured log entry with comprehensive metadata."""
    timestamp: datetime
    level: LogLevel
    message: str
    category: Optional[str] = None
    component: Optional[str] = None
    context_id: Optional[str] = None
    user_id: Optional[str] = None
    execution_id: Optional[str] = None
    error_type: Optional[str] = None
    stack_trace: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    performance_data: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Handle additional keyword arguments by storing them in metadata."""
        # This allows the LogEntry to accept any additional kwargs
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        result['level'] = self.level.value
        return result


@dataclass
class ErrorRecord:
    """Comprehensive error record for tracking and analysis."""
    error_id: str
    timestamp: datetime
    category: ErrorCategory
    error_type: str
    message: str
    component: str
    context_id: Optional[str] = None
    user_id: Optional[str] = None
    execution_id: Optional[str] = None
    stack_trace: Optional[str] = None
    recovery_attempted: bool = False
    recovery_successful: bool = False
    recovery_method: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        result['category'] = self.category.value
        return result


@dataclass
class PerformanceMetrics:
    """Performance metrics for monitoring system health."""
    timestamp: datetime
    component: str
    operation: str
    duration_ms: float
    memory_usage_mb: float
    cpu_usage_percent: float
    success: bool
    context_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result


class StructuredLogger:
    """Structured logger with JSON output and comprehensive metadata."""
    
    def __init__(self, name: str, log_dir: Optional[Path] = None):
        self.name = name
        self.log_dir = log_dir or Path("logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Remove existing handlers to avoid duplicates
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Setup handlers
        self._setup_handlers()
        
        # Thread-safe log queue
        self.log_queue = queue.Queue()
        self.log_thread = threading.Thread(target=self._log_worker, daemon=True)
        self.log_thread.start()
        
        # Register cleanup
        atexit.register(self.cleanup)
    
    def _setup_handlers(self):
        """Setup logging handlers for different outputs."""
        # Console handler with colored output
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler for all logs
        log_file = self.log_dir / f"{self.name}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # JSON handler for structured logs
        json_log_file = self.log_dir / f"{self.name}_structured.jsonl"
        self.json_handler = logging.handlers.RotatingFileHandler(
            json_log_file, maxBytes=10*1024*1024, backupCount=5
        )
        self.json_handler.setLevel(logging.DEBUG)
    
    def _log_worker(self):
        """Background worker for processing log entries."""
        while True:
            try:
                log_entry = self.log_queue.get(timeout=1)
                if log_entry is None:  # Shutdown signal
                    break
                
                # Write structured log to JSON file
                json_line = json.dumps(log_entry.to_dict())
                self.json_handler.stream.write(json_line + '\n')
                self.json_handler.stream.flush()
                
                self.log_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                # Fallback logging to avoid infinite loops
                print(f"Error in log worker: {e}", file=sys.stderr)
    
    def log(self, level: LogLevel, message: str, **kwargs):
        """Log a structured message."""
        # Extract known fields
        known_fields = {
            'category', 'component', 'context_id', 'user_id', 'execution_id',
            'error_type', 'stack_trace', 'metadata', 'performance_data'
        }
        
        log_entry_kwargs = {}
        extra_metadata = {}
        
        for key, value in kwargs.items():
            if key in known_fields:
                log_entry_kwargs[key] = value
            else:
                extra_metadata[key] = value
        
        # Merge extra metadata with existing metadata
        if 'metadata' in log_entry_kwargs:
            log_entry_kwargs['metadata'].update(extra_metadata)
        elif extra_metadata:
            log_entry_kwargs['metadata'] = extra_metadata
        
        log_entry = LogEntry(
            timestamp=datetime.now(),
            level=level,
            message=message,
            **log_entry_kwargs
        )
        
        # Queue for structured logging
        try:
            self.log_queue.put_nowait(log_entry)
        except queue.Full:
            pass  # Drop log if queue is full to avoid blocking
        
        # Standard logging
        getattr(self.logger, level.value.lower())(message)
    
    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self.log(LogLevel.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message."""
        self.log(LogLevel.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self.log(LogLevel.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message."""
        self.log(LogLevel.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message."""
        self.log(LogLevel.CRITICAL, message, **kwargs)
    
    def cleanup(self):
        """Cleanup resources."""
        try:
            # Signal shutdown to worker thread
            self.log_queue.put(None)
            self.log_thread.join(timeout=5)
        except:
            pass


class ErrorHandler:
    """Comprehensive error handling with recovery strategies."""
    
    def __init__(self, logger: StructuredLogger):
        self.logger = logger
        self.error_records: List[ErrorRecord] = []
        self.recovery_strategies: Dict[ErrorCategory, List[Callable]] = {
            ErrorCategory.EXECUTION: [
                self._recover_execution_error,
                self._restart_execution_context
            ],
            ErrorCategory.RESOURCE: [
                self._cleanup_resources,
                self._reduce_resource_limits
            ],
            ErrorCategory.TIMEOUT: [
                self._extend_timeout,
                self._kill_hanging_process
            ],
            ErrorCategory.SYSTEM: [
                self._restart_component,
                self._fallback_mode
            ]
        }
        self.max_error_records = 1000
    
    def handle_error(self, error: Exception, category: ErrorCategory, 
                    component: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Handle an error with automatic recovery attempts.
        
        Returns:
            bool: True if error was recovered, False otherwise
        """
        error_id = f"{category.value}_{int(time.time() * 1000)}"
        context = context or {}
        
        # Create error record
        error_record = ErrorRecord(
            error_id=error_id,
            timestamp=datetime.now(),
            category=category,
            error_type=type(error).__name__,
            message=str(error),
            component=component,
            context_id=context.get('context_id'),
            user_id=context.get('user_id'),
            execution_id=context.get('execution_id'),
            stack_trace=traceback.format_exc(),
            metadata=context
        )
        
        # Log the error
        self.logger.error(
            f"Error in {component}: {error}",
            category=category.value,
            component=component,
            error_type=type(error).__name__,
            context_id=context.get('context_id'),
            execution_id=context.get('execution_id'),
            stack_trace=traceback.format_exc(),
            metadata=context
        )
        
        # Attempt recovery
        recovery_successful = self._attempt_recovery(error_record, error, context)
        
        # Update error record
        error_record.recovery_attempted = True
        error_record.recovery_successful = recovery_successful
        
        # Store error record
        self.error_records.append(error_record)
        
        # Keep records manageable
        if len(self.error_records) > self.max_error_records:
            self.error_records = self.error_records[-self.max_error_records//2:]
        
        return recovery_successful
    
    def _attempt_recovery(self, error_record: ErrorRecord, error: Exception, 
                         context: Dict[str, Any]) -> bool:
        """Attempt to recover from an error using registered strategies."""
        strategies = self.recovery_strategies.get(error_record.category, [])
        
        for strategy in strategies:
            try:
                self.logger.info(
                    f"Attempting recovery strategy: {strategy.__name__}",
                    category=error_record.category.value,
                    component=error_record.component,
                    error_id=error_record.error_id
                )
                
                if strategy(error, context):
                    error_record.recovery_method = strategy.__name__
                    self.logger.info(
                        f"Recovery successful using: {strategy.__name__}",
                        category=error_record.category.value,
                        component=error_record.component,
                        error_id=error_record.error_id
                    )
                    return True
                    
            except Exception as recovery_error:
                self.logger.warning(
                    f"Recovery strategy {strategy.__name__} failed: {recovery_error}",
                    category=error_record.category.value,
                    component=error_record.component,
                    error_id=error_record.error_id
                )
        
        return False
    
    def _recover_execution_error(self, error: Exception, context: Dict[str, Any]) -> bool:
        """Recover from execution errors."""
        # Clear execution globals that might be corrupted
        if 'execution_context' in context:
            execution_context = context['execution_context']
            if hasattr(execution_context, 'execution_globals'):
                execution_context.execution_globals.clear()
                return True
        return False
    
    def _restart_execution_context(self, error: Exception, context: Dict[str, Any]) -> bool:
        """Restart execution context."""
        # This would be implemented based on the specific execution engine
        return False
    
    def _cleanup_resources(self, error: Exception, context: Dict[str, Any]) -> bool:
        """Clean up resources to recover from resource errors."""
        try:
            import gc
            gc.collect()
            return True
        except:
            return False
    
    def _reduce_resource_limits(self, error: Exception, context: Dict[str, Any]) -> bool:
        """Reduce resource limits to prevent future resource errors."""
        if 'execution_context' in context:
            execution_context = context['execution_context']
            if hasattr(execution_context, 'resource_limits'):
                limits = execution_context.resource_limits
                limits.max_memory_mb = max(128, limits.max_memory_mb // 2)
                limits.max_execution_time = max(10, limits.max_execution_time // 2)
                return True
        return False
    
    def _extend_timeout(self, error: Exception, context: Dict[str, Any]) -> bool:
        """Extend timeout for timeout errors."""
        if 'execution_context' in context:
            execution_context = context['execution_context']
            if hasattr(execution_context, 'resource_limits'):
                limits = execution_context.resource_limits
                limits.max_execution_time = min(300, limits.max_execution_time * 2)
                return True
        return False
    
    def _kill_hanging_process(self, error: Exception, context: Dict[str, Any]) -> bool:
        """Kill hanging processes."""
        # This would require process tracking
        return False
    
    def _restart_component(self, error: Exception, context: Dict[str, Any]) -> bool:
        """Restart a system component."""
        # This would be implemented based on component architecture
        return False
    
    def _fallback_mode(self, error: Exception, context: Dict[str, Any]) -> bool:
        """Enable fallback mode for system errors."""
        # This would enable a degraded but functional mode
        return False
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics for monitoring."""
        if not self.error_records:
            return {
                'total_errors': 0,
                'errors_by_category': {},
                'errors_by_component': {},
                'recovery_rate': 1.0,  # 100% recovery rate when no errors
                'recent_errors': 0
            }
        
        recent_time = datetime.now() - timedelta(hours=1)
        recent_errors = [e for e in self.error_records if e.timestamp >= recent_time]
        
        errors_by_category = {}
        errors_by_component = {}
        recovered_errors = 0
        
        for error in self.error_records:
            category = error.category.value
            errors_by_category[category] = errors_by_category.get(category, 0) + 1
            errors_by_component[error.component] = errors_by_component.get(error.component, 0) + 1
            
            if error.recovery_successful:
                recovered_errors += 1
        
        return {
            'total_errors': len(self.error_records),
            'errors_by_category': errors_by_category,
            'errors_by_component': errors_by_component,
            'recovery_rate': recovered_errors / len(self.error_records),
            'recent_errors': len(recent_errors)
        }


class PerformanceMonitor:
    """Performance monitoring and metrics collection."""
    
    def __init__(self, logger: StructuredLogger):
        self.logger = logger
        self.metrics: List[PerformanceMetrics] = []
        self.max_metrics = 10000
        self.start_time = time.time()
        
        # System monitoring
        self.process = psutil.Process()
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitor_system, daemon=True)
        self.monitor_thread.start()
    
    @contextmanager
    def measure_operation(self, component: str, operation: str, 
                         context_id: Optional[str] = None, **metadata):
        """Context manager to measure operation performance."""
        start_time = time.time()
        start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        start_cpu = self.process.cpu_percent()
        
        success = True
        try:
            yield
        except Exception as e:
            success = False
            raise
        finally:
            end_time = time.time()
            end_memory = self.process.memory_info().rss / 1024 / 1024  # MB
            duration_ms = (end_time - start_time) * 1000
            
            # Calculate CPU usage (approximate)
            cpu_usage = self.process.cpu_percent()
            
            metrics = PerformanceMetrics(
                timestamp=datetime.now(),
                component=component,
                operation=operation,
                duration_ms=duration_ms,
                memory_usage_mb=end_memory,
                cpu_usage_percent=cpu_usage,
                success=success,
                context_id=context_id,
                metadata=metadata
            )
            
            self._record_metrics(metrics)
    
    def _record_metrics(self, metrics: PerformanceMetrics):
        """Record performance metrics."""
        self.metrics.append(metrics)
        
        # Keep metrics manageable
        if len(self.metrics) > self.max_metrics:
            self.metrics = self.metrics[-self.max_metrics//2:]
        
        # Log performance data
        self.logger.debug(
            f"Performance: {metrics.component}.{metrics.operation} "
            f"took {metrics.duration_ms:.2f}ms",
            component=metrics.component,
            performance_data=metrics.to_dict()
        )
    
    def _monitor_system(self):
        """Background system monitoring."""
        while self.monitoring_active:
            try:
                # System metrics
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                # Process metrics
                process_memory = self.process.memory_info().rss / 1024 / 1024  # MB
                process_cpu = self.process.cpu_percent()
                
                system_metrics = PerformanceMetrics(
                    timestamp=datetime.now(),
                    component="system",
                    operation="monitor",
                    duration_ms=0,
                    memory_usage_mb=process_memory,
                    cpu_usage_percent=process_cpu,
                    success=True,
                    metadata={
                        'system_cpu_percent': cpu_percent,
                        'system_memory_percent': memory.percent,
                        'system_disk_percent': disk.percent,
                        'uptime_seconds': time.time() - self.start_time
                    }
                )
                
                self._record_metrics(system_metrics)
                
                time.sleep(60)  # Monitor every minute
                
            except Exception as e:
                self.logger.warning(f"System monitoring error: {e}")
                time.sleep(60)
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary statistics."""
        if not self.metrics:
            return {
                'total_operations': 0,
                'average_duration_ms': 0,
                'success_rate': 0,
                'components': {}
            }
        
        recent_time = datetime.now() - timedelta(hours=1)
        recent_metrics = [m for m in self.metrics if m.timestamp >= recent_time]
        
        total_duration = sum(m.duration_ms for m in self.metrics)
        successful_ops = sum(1 for m in self.metrics if m.success)
        
        components = {}
        for metric in self.metrics:
            comp = metric.component
            if comp not in components:
                components[comp] = {
                    'operations': 0,
                    'total_duration_ms': 0,
                    'success_count': 0,
                    'avg_memory_mb': 0,
                    'avg_cpu_percent': 0
                }
            
            comp_data = components[comp]
            comp_data['operations'] += 1
            comp_data['total_duration_ms'] += metric.duration_ms
            comp_data['avg_memory_mb'] += metric.memory_usage_mb
            comp_data['avg_cpu_percent'] += metric.cpu_usage_percent
            
            if metric.success:
                comp_data['success_count'] += 1
        
        # Calculate averages
        for comp_data in components.values():
            ops = comp_data['operations']
            comp_data['avg_duration_ms'] = comp_data['total_duration_ms'] / ops
            comp_data['avg_memory_mb'] = comp_data['avg_memory_mb'] / ops
            comp_data['avg_cpu_percent'] = comp_data['avg_cpu_percent'] / ops
            comp_data['success_rate'] = comp_data['success_count'] / ops
        
        return {
            'total_operations': len(self.metrics),
            'average_duration_ms': total_duration / len(self.metrics),
            'success_rate': successful_ops / len(self.metrics),
            'recent_operations': len(recent_metrics),
            'uptime_seconds': time.time() - self.start_time,
            'components': components
        }
    
    def cleanup(self):
        """Cleanup monitoring resources."""
        self.monitoring_active = False
        try:
            self.monitor_thread.join(timeout=5)
        except:
            pass


class DiagnosticTools:
    """Diagnostic tools for system health and troubleshooting."""
    
    def __init__(self, logger: StructuredLogger, error_handler: ErrorHandler, 
                 performance_monitor: PerformanceMonitor):
        self.logger = logger
        self.error_handler = error_handler
        self.performance_monitor = performance_monitor
    
    def run_health_check(self) -> Dict[str, Any]:
        """Run comprehensive health check."""
        health_status = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'healthy',
            'checks': {}
        }
        
        # System health
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            health_status['checks']['system'] = {
                'status': 'healthy',
                'cpu_usage': cpu_percent,
                'memory_usage': memory.percent,
                'disk_usage': disk.percent,
                'warnings': []
            }
            
            # Add warnings for high resource usage
            if cpu_percent > 80:
                health_status['checks']['system']['warnings'].append('High CPU usage')
            if memory.percent > 80:
                health_status['checks']['system']['warnings'].append('High memory usage')
            if disk.percent > 90:
                health_status['checks']['system']['warnings'].append('Low disk space')
                
        except Exception as e:
            health_status['checks']['system'] = {
                'status': 'error',
                'error': str(e)
            }
            health_status['overall_status'] = 'degraded'
        
        # Error rate check
        try:
            error_stats = self.error_handler.get_error_statistics()
            recent_errors = error_stats['recent_errors']
            recovery_rate = error_stats['recovery_rate']
            
            error_status = 'healthy'
            if recent_errors > 10:
                error_status = 'warning'
            if recent_errors > 50 or recovery_rate < 0.5:
                error_status = 'critical'
                health_status['overall_status'] = 'unhealthy'
            
            health_status['checks']['errors'] = {
                'status': error_status,
                'recent_errors': recent_errors,
                'recovery_rate': recovery_rate,
                'total_errors': error_stats['total_errors']
            }
            
        except Exception as e:
            health_status['checks']['errors'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # Performance check
        try:
            perf_summary = self.performance_monitor.get_performance_summary()
            success_rate = perf_summary['success_rate']
            avg_duration = perf_summary['average_duration_ms']
            
            perf_status = 'healthy'
            if success_rate < 0.9 or avg_duration > 5000:
                perf_status = 'warning'
            if success_rate < 0.7 or avg_duration > 10000:
                perf_status = 'critical'
                health_status['overall_status'] = 'unhealthy'
            
            health_status['checks']['performance'] = {
                'status': perf_status,
                'success_rate': success_rate,
                'average_duration_ms': avg_duration,
                'total_operations': perf_summary['total_operations']
            }
            
        except Exception as e:
            health_status['checks']['performance'] = {
                'status': 'error',
                'error': str(e)
            }
        
        return health_status
    
    def generate_diagnostic_report(self) -> Dict[str, Any]:
        """Generate comprehensive diagnostic report."""
        report = {
            'timestamp': datetime.now().isoformat(),
            'health_check': self.run_health_check(),
            'error_statistics': self.error_handler.get_error_statistics(),
            'performance_summary': self.performance_monitor.get_performance_summary(),
            'system_info': self._get_system_info(),
            'recommendations': self._generate_recommendations()
        }
        
        return report
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information."""
        try:
            return {
                'platform': sys.platform,
                'python_version': sys.version,
                'cpu_count': psutil.cpu_count(),
                'memory_total_gb': psutil.virtual_memory().total / 1024 / 1024 / 1024,
                'disk_total_gb': psutil.disk_usage('/').total / 1024 / 1024 / 1024,
                'process_id': os.getpid(),
                'working_directory': os.getcwd()
            }
        except Exception as e:
            return {'error': str(e)}
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on current system state."""
        recommendations = []
        
        try:
            # Check system resources
            memory = psutil.virtual_memory()
            if memory.percent > 80:
                recommendations.append("Consider increasing available memory or reducing memory usage")
            
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > 80:
                recommendations.append("High CPU usage detected - consider optimizing operations")
            
            # Check error rates
            error_stats = self.error_handler.get_error_statistics()
            if error_stats['recent_errors'] > 10:
                recommendations.append("High error rate detected - review recent error logs")
            
            if error_stats['recovery_rate'] < 0.5:
                recommendations.append("Low error recovery rate - review recovery strategies")
            
            # Check performance
            perf_summary = self.performance_monitor.get_performance_summary()
            if perf_summary['success_rate'] < 0.9:
                recommendations.append("Low operation success rate - investigate failing operations")
            
            if perf_summary['average_duration_ms'] > 5000:
                recommendations.append("High average operation duration - consider performance optimization")
            
        except Exception as e:
            recommendations.append(f"Error generating recommendations: {e}")
        
        return recommendations


def with_error_handling(category: ErrorCategory, component: str):
    """Decorator for automatic error handling."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get logger and error handler from the first argument (usually self)
            if args and hasattr(args[0], 'error_handler'):
                error_handler = args[0].error_handler
            else:
                # Fallback to global error handler if available
                error_handler = None
            
            try:
                return func(*args, **kwargs)
            except Exception as e:
                context = {
                    'function': func.__name__,
                    'args_count': len(args),
                    'kwargs_keys': list(kwargs.keys())
                }
                
                if error_handler:
                    recovered = error_handler.handle_error(e, category, component, context)
                    if not recovered:
                        raise
                else:
                    raise
        
        return wrapper
    return decorator


def with_performance_monitoring(component: str, operation: str):
    """Decorator for automatic performance monitoring."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get performance monitor from the first argument (usually self)
            if args and hasattr(args[0], 'performance_monitor'):
                performance_monitor = args[0].performance_monitor
                
                with performance_monitor.measure_operation(component, operation):
                    return func(*args, **kwargs)
            else:
                # No monitoring available, just execute
                return func(*args, **kwargs)
        
        return wrapper
    return decorator