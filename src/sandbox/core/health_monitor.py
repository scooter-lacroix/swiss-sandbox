"""
Health monitoring and diagnostic endpoints for Swiss Sandbox.

This module provides health check endpoints, system diagnostics, and monitoring tools.
"""

import json
import time
import threading
import psutil
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum

from .logging_system import StructuredLogger, ErrorHandler, PerformanceMonitor, DiagnosticTools


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNHEALTHY = "unhealthy"


@dataclass
class ComponentHealth:
    """Health status of a system component."""
    name: str
    status: HealthStatus
    message: str
    last_check: datetime
    metrics: Dict[str, Any]
    warnings: List[str]
    errors: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['status'] = self.status.value
        result['last_check'] = self.last_check.isoformat()
        return result


class HealthMonitor:
    """Comprehensive health monitoring system."""
    
    def __init__(self, logger: StructuredLogger, error_handler: ErrorHandler, 
                 performance_monitor: PerformanceMonitor):
        self.logger = logger
        self.error_handler = error_handler
        self.performance_monitor = performance_monitor
        self.diagnostic_tools = DiagnosticTools(logger, error_handler, performance_monitor)
        
        # Component health checkers
        self.health_checkers: Dict[str, Callable[[], ComponentHealth]] = {
            'system': self._check_system_health,
            'memory': self._check_memory_health,
            'disk': self._check_disk_health,
            'cpu': self._check_cpu_health,
            'errors': self._check_error_health,
            'performance': self._check_performance_health
        }
        
        # Health history
        self.health_history: List[Dict[str, Any]] = []
        self.max_history = 1000
        
        # Monitoring configuration
        self.monitoring_interval = 60  # seconds
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._continuous_monitoring, daemon=True)
        self.monitor_thread.start()
        
        # Alert thresholds
        self.alert_thresholds = {
            'cpu_usage': 80.0,
            'memory_usage': 80.0,
            'disk_usage': 90.0,
            'error_rate': 0.1,
            'response_time_ms': 5000
        }
        
        self.logger.info("Health monitor initialized")
    
    def get_overall_health(self) -> Dict[str, Any]:
        """Get overall system health status."""
        component_healths = {}
        overall_status = HealthStatus.HEALTHY
        
        # Check all components
        for component_name, checker in self.health_checkers.items():
            try:
                health = checker()
                component_healths[component_name] = health.to_dict()
                
                # Determine overall status
                if health.status == HealthStatus.CRITICAL or health.status == HealthStatus.UNHEALTHY:
                    overall_status = HealthStatus.UNHEALTHY
                elif health.status == HealthStatus.WARNING and overall_status == HealthStatus.HEALTHY:
                    overall_status = HealthStatus.WARNING
                    
            except Exception as e:
                self.logger.error(f"Health check failed for {component_name}: {e}")
                component_healths[component_name] = {
                    'name': component_name,
                    'status': HealthStatus.CRITICAL.value,
                    'message': f"Health check failed: {e}",
                    'last_check': datetime.now().isoformat(),
                    'metrics': {},
                    'warnings': [],
                    'errors': [str(e)]
                }
                overall_status = HealthStatus.UNHEALTHY
        
        health_report = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': overall_status.value,
            'components': component_healths,
            'uptime_seconds': time.time() - self.performance_monitor.start_time,
            'summary': self._generate_health_summary(component_healths)
        }
        
        # Store in history
        self.health_history.append(health_report)
        if len(self.health_history) > self.max_history:
            self.health_history = self.health_history[-self.max_history//2:]
        
        return health_report
    
    def _check_system_health(self) -> ComponentHealth:
        """Check overall system health."""
        try:
            # Get system metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            boot_time = psutil.boot_time()
            uptime = time.time() - boot_time
            
            warnings = []
            errors = []
            status = HealthStatus.HEALTHY
            
            # Check thresholds
            if cpu_percent > self.alert_thresholds['cpu_usage']:
                warnings.append(f"High CPU usage: {cpu_percent:.1f}%")
                status = HealthStatus.WARNING
            
            if memory.percent > self.alert_thresholds['memory_usage']:
                warnings.append(f"High memory usage: {memory.percent:.1f}%")
                status = HealthStatus.WARNING
            
            if disk.percent > self.alert_thresholds['disk_usage']:
                warnings.append(f"Low disk space: {disk.percent:.1f}% used")
                status = HealthStatus.CRITICAL
            
            # Critical thresholds
            if cpu_percent > 95:
                errors.append("Critical CPU usage")
                status = HealthStatus.CRITICAL
            
            if memory.percent > 95:
                errors.append("Critical memory usage")
                status = HealthStatus.CRITICAL
            
            if disk.percent > 98:
                errors.append("Critical disk space")
                status = HealthStatus.UNHEALTHY
            
            metrics = {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_available_gb': memory.available / 1024 / 1024 / 1024,
                'disk_percent': disk.percent,
                'disk_free_gb': disk.free / 1024 / 1024 / 1024,
                'uptime_hours': uptime / 3600,
                'load_average': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
            }
            
            message = f"System running normally (CPU: {cpu_percent:.1f}%, Memory: {memory.percent:.1f}%, Disk: {disk.percent:.1f}%)"
            if warnings:
                message = f"System warnings detected: {', '.join(warnings)}"
            if errors:
                message = f"System errors detected: {', '.join(errors)}"
            
            return ComponentHealth(
                name="system",
                status=status,
                message=message,
                last_check=datetime.now(),
                metrics=metrics,
                warnings=warnings,
                errors=errors
            )
            
        except Exception as e:
            return ComponentHealth(
                name="system",
                status=HealthStatus.CRITICAL,
                message=f"System health check failed: {e}",
                last_check=datetime.now(),
                metrics={},
                warnings=[],
                errors=[str(e)]
            )
    
    def _check_memory_health(self) -> ComponentHealth:
        """Check memory health."""
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            process = psutil.Process()
            process_memory = process.memory_info()
            
            warnings = []
            errors = []
            status = HealthStatus.HEALTHY
            
            # Check system memory
            if memory.percent > 80:
                warnings.append(f"High system memory usage: {memory.percent:.1f}%")
                status = HealthStatus.WARNING
            
            if memory.percent > 95:
                errors.append("Critical system memory usage")
                status = HealthStatus.CRITICAL
            
            # Check swap usage
            if swap.percent > 50:
                warnings.append(f"High swap usage: {swap.percent:.1f}%")
                status = HealthStatus.WARNING
            
            # Check process memory
            process_memory_mb = process_memory.rss / 1024 / 1024
            if process_memory_mb > 1024:  # 1GB
                warnings.append(f"High process memory usage: {process_memory_mb:.1f}MB")
                status = HealthStatus.WARNING
            
            metrics = {
                'system_memory_percent': memory.percent,
                'system_memory_available_gb': memory.available / 1024 / 1024 / 1024,
                'swap_percent': swap.percent,
                'process_memory_mb': process_memory_mb,
                'process_memory_percent': process.memory_percent()
            }
            
            message = f"Memory usage normal (System: {memory.percent:.1f}%, Process: {process_memory_mb:.1f}MB)"
            if warnings:
                message = f"Memory warnings: {', '.join(warnings)}"
            if errors:
                message = f"Memory errors: {', '.join(errors)}"
            
            return ComponentHealth(
                name="memory",
                status=status,
                message=message,
                last_check=datetime.now(),
                metrics=metrics,
                warnings=warnings,
                errors=errors
            )
            
        except Exception as e:
            return ComponentHealth(
                name="memory",
                status=HealthStatus.CRITICAL,
                message=f"Memory health check failed: {e}",
                last_check=datetime.now(),
                metrics={},
                warnings=[],
                errors=[str(e)]
            )
    
    def _check_disk_health(self) -> ComponentHealth:
        """Check disk health."""
        try:
            disk = psutil.disk_usage('/')
            disk_io = psutil.disk_io_counters()
            
            warnings = []
            errors = []
            status = HealthStatus.HEALTHY
            
            # Check disk space
            if disk.percent > 85:
                warnings.append(f"High disk usage: {disk.percent:.1f}%")
                status = HealthStatus.WARNING
            
            if disk.percent > 95:
                errors.append("Critical disk space")
                status = HealthStatus.CRITICAL
            
            if disk.percent > 98:
                errors.append("Disk almost full")
                status = HealthStatus.UNHEALTHY
            
            metrics = {
                'disk_percent': disk.percent,
                'disk_free_gb': disk.free / 1024 / 1024 / 1024,
                'disk_total_gb': disk.total / 1024 / 1024 / 1024,
                'disk_read_count': disk_io.read_count if disk_io else None,
                'disk_write_count': disk_io.write_count if disk_io else None
            }
            
            message = f"Disk usage normal ({disk.percent:.1f}% used, {disk.free / 1024 / 1024 / 1024:.1f}GB free)"
            if warnings:
                message = f"Disk warnings: {', '.join(warnings)}"
            if errors:
                message = f"Disk errors: {', '.join(errors)}"
            
            return ComponentHealth(
                name="disk",
                status=status,
                message=message,
                last_check=datetime.now(),
                metrics=metrics,
                warnings=warnings,
                errors=errors
            )
            
        except Exception as e:
            return ComponentHealth(
                name="disk",
                status=HealthStatus.CRITICAL,
                message=f"Disk health check failed: {e}",
                last_check=datetime.now(),
                metrics={},
                warnings=[],
                errors=[str(e)]
            )
    
    def _check_cpu_health(self) -> ComponentHealth:
        """Check CPU health."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
            
            warnings = []
            errors = []
            status = HealthStatus.HEALTHY
            
            # Check CPU usage
            if cpu_percent > 80:
                warnings.append(f"High CPU usage: {cpu_percent:.1f}%")
                status = HealthStatus.WARNING
            
            if cpu_percent > 95:
                errors.append("Critical CPU usage")
                status = HealthStatus.CRITICAL
            
            # Check load average (Unix only)
            if load_avg and load_avg[0] > cpu_count * 2:
                warnings.append(f"High load average: {load_avg[0]:.2f}")
                status = HealthStatus.WARNING
            
            metrics = {
                'cpu_percent': cpu_percent,
                'cpu_count': cpu_count,
                'cpu_freq_current': cpu_freq.current if cpu_freq else None,
                'load_average_1min': load_avg[0] if load_avg else None,
                'load_average_5min': load_avg[1] if load_avg else None,
                'load_average_15min': load_avg[2] if load_avg else None
            }
            
            message = f"CPU usage normal ({cpu_percent:.1f}%)"
            if warnings:
                message = f"CPU warnings: {', '.join(warnings)}"
            if errors:
                message = f"CPU errors: {', '.join(errors)}"
            
            return ComponentHealth(
                name="cpu",
                status=status,
                message=message,
                last_check=datetime.now(),
                metrics=metrics,
                warnings=warnings,
                errors=errors
            )
            
        except Exception as e:
            return ComponentHealth(
                name="cpu",
                status=HealthStatus.CRITICAL,
                message=f"CPU health check failed: {e}",
                last_check=datetime.now(),
                metrics={},
                warnings=[],
                errors=[str(e)]
            )
    
    def _check_error_health(self) -> ComponentHealth:
        """Check error rates and recovery."""
        try:
            error_stats = self.error_handler.get_error_statistics()
            
            warnings = []
            errors = []
            status = HealthStatus.HEALTHY
            
            # Check error rates
            recent_errors = error_stats['recent_errors']
            total_errors = error_stats['total_errors']
            recovery_rate = error_stats['recovery_rate']
            
            if recent_errors > 5:
                warnings.append(f"High recent error count: {recent_errors}")
                status = HealthStatus.WARNING
            
            if recent_errors > 20:
                errors.append("Very high error rate")
                status = HealthStatus.CRITICAL
            
            if recovery_rate < 0.7:
                warnings.append(f"Low error recovery rate: {recovery_rate:.2f}")
                status = HealthStatus.WARNING
            
            if recovery_rate < 0.5:
                errors.append("Poor error recovery")
                status = HealthStatus.CRITICAL
            
            metrics = {
                'total_errors': total_errors,
                'recent_errors': recent_errors,
                'recovery_rate': recovery_rate,
                'errors_by_category': error_stats['errors_by_category'],
                'errors_by_component': error_stats['errors_by_component']
            }
            
            message = f"Error rates normal (Recent: {recent_errors}, Recovery: {recovery_rate:.2f})"
            if warnings:
                message = f"Error warnings: {', '.join(warnings)}"
            if errors:
                message = f"Error issues: {', '.join(errors)}"
            
            return ComponentHealth(
                name="errors",
                status=status,
                message=message,
                last_check=datetime.now(),
                metrics=metrics,
                warnings=warnings,
                errors=errors
            )
            
        except Exception as e:
            return ComponentHealth(
                name="errors",
                status=HealthStatus.CRITICAL,
                message=f"Error health check failed: {e}",
                last_check=datetime.now(),
                metrics={},
                warnings=[],
                errors=[str(e)]
            )
    
    def _check_performance_health(self) -> ComponentHealth:
        """Check performance metrics."""
        try:
            perf_summary = self.performance_monitor.get_performance_summary()
            
            warnings = []
            errors = []
            status = HealthStatus.HEALTHY
            
            # Check performance metrics
            success_rate = perf_summary['success_rate']
            avg_duration = perf_summary['average_duration_ms']
            total_ops = perf_summary['total_operations']
            
            if success_rate < 0.9:
                warnings.append(f"Low success rate: {success_rate:.2f}")
                status = HealthStatus.WARNING
            
            if success_rate < 0.7:
                errors.append("Very low success rate")
                status = HealthStatus.CRITICAL
            
            if avg_duration > 3000:
                warnings.append(f"High average response time: {avg_duration:.1f}ms")
                status = HealthStatus.WARNING
            
            if avg_duration > 10000:
                errors.append("Very high response time")
                status = HealthStatus.CRITICAL
            
            metrics = {
                'success_rate': success_rate,
                'average_duration_ms': avg_duration,
                'total_operations': total_ops,
                'recent_operations': perf_summary['recent_operations'],
                'components': perf_summary['components']
            }
            
            message = f"Performance normal (Success: {success_rate:.2f}, Avg: {avg_duration:.1f}ms)"
            if warnings:
                message = f"Performance warnings: {', '.join(warnings)}"
            if errors:
                message = f"Performance issues: {', '.join(errors)}"
            
            return ComponentHealth(
                name="performance",
                status=status,
                message=message,
                last_check=datetime.now(),
                metrics=metrics,
                warnings=warnings,
                errors=errors
            )
            
        except Exception as e:
            return ComponentHealth(
                name="performance",
                status=HealthStatus.CRITICAL,
                message=f"Performance health check failed: {e}",
                last_check=datetime.now(),
                metrics={},
                warnings=[],
                errors=[str(e)]
            )
    
    def _generate_health_summary(self, component_healths: Dict[str, Any]) -> Dict[str, Any]:
        """Generate health summary from component healths."""
        total_components = len(component_healths)
        healthy_components = sum(1 for h in component_healths.values() if h['status'] == 'healthy')
        warning_components = sum(1 for h in component_healths.values() if h['status'] == 'warning')
        critical_components = sum(1 for h in component_healths.values() if h['status'] in ['critical', 'unhealthy'])
        
        all_warnings = []
        all_errors = []
        
        for health in component_healths.values():
            all_warnings.extend(health.get('warnings', []))
            all_errors.extend(health.get('errors', []))
        
        return {
            'total_components': total_components,
            'healthy_components': healthy_components,
            'warning_components': warning_components,
            'critical_components': critical_components,
            'health_score': healthy_components / total_components if total_components > 0 else 0,
            'total_warnings': len(all_warnings),
            'total_errors': len(all_errors),
            'top_warnings': all_warnings[:5],
            'top_errors': all_errors[:5]
        }
    
    def _continuous_monitoring(self):
        """Continuous health monitoring in background."""
        while self.monitoring_active:
            try:
                health_report = self.get_overall_health()
                
                # Log health status
                if health_report['overall_status'] != 'healthy':
                    self.logger.warning(
                        f"Health check: {health_report['overall_status']}",
                        component="health_monitor",
                        metadata=health_report['summary']
                    )
                else:
                    self.logger.debug(
                        "Health check: healthy",
                        component="health_monitor",
                        metadata=health_report['summary']
                    )
                
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                self.logger.error(f"Health monitoring error: {e}")
                time.sleep(self.monitoring_interval)
    
    def get_health_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get health history for the specified number of hours."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        filtered_history = []
        for health_report in self.health_history:
            report_time = datetime.fromisoformat(health_report['timestamp'])
            if report_time >= cutoff_time:
                filtered_history.append(health_report)
        
        return filtered_history
    
    def get_diagnostic_report(self) -> Dict[str, Any]:
        """Get comprehensive diagnostic report."""
        return self.diagnostic_tools.generate_diagnostic_report()
    
    def cleanup(self):
        """Cleanup monitoring resources."""
        self.monitoring_active = False
        try:
            self.monitor_thread.join(timeout=5)
        except:
            pass
        
        self.logger.info("Health monitor cleaned up")