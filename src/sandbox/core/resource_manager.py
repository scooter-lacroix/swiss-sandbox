"""
Comprehensive resource management system for the sandbox.

This module provides:
- Memory usage monitoring and limits
- Process lifecycle management
- Automatic cleanup systems
- Thread pool management
- Resource exhaustion protection
"""

import os
import sys
import time
import threading
import subprocess
import signal
import atexit
import psutil
import logging
import weakref
from typing import Dict, List, Optional, Set, Callable, Any
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import tempfile
import shutil

logger = logging.getLogger(__name__)

class ResourceLimits:
    """Configuration for resource limits."""
    MAX_MEMORY_MB = int(os.environ.get('SANDBOX_MAX_MEMORY_MB', 512))
    MAX_PROCESSES = int(os.environ.get('SANDBOX_MAX_PROCESSES', 10))
    MAX_ARTIFACTS_SIZE_MB = int(os.environ.get('SANDBOX_MAX_ARTIFACTS_MB', 100))
    MAX_EXECUTION_TIME_SEC = int(os.environ.get('SANDBOX_MAX_EXECUTION_TIME', 300))
    MAX_CACHE_SIZE = int(os.environ.get('SANDBOX_MAX_CACHE_SIZE', 1000))
    MAX_THREADS = int(os.environ.get('SANDBOX_MAX_THREADS', 5))
    MAX_SESSIONS = int(os.environ.get('SANDBOX_MAX_SESSIONS', 20))
    CLEANUP_INTERVAL_SEC = int(os.environ.get('SANDBOX_CLEANUP_INTERVAL', 300))
    ARTIFACT_MAX_AGE_HOURS = int(os.environ.get('SANDBOX_ARTIFACT_MAX_AGE', 24))


class ResourceMonitor:
    """Monitor system resource usage."""
    
    def __init__(self):
        self.process = psutil.Process()
        self.start_time = time.time()
        self.peak_memory = 0
        self.total_executions = 0
        
    def get_memory_usage_mb(self) -> float:
        """Get current memory usage in MB."""
        try:
            memory_mb = self.process.memory_info().rss / 1024 / 1024
            self.peak_memory = max(self.peak_memory, memory_mb)
            return memory_mb
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0
    
    def get_cpu_usage(self) -> float:
        """Get current CPU usage percentage."""
        try:
            return self.process.cpu_percent(interval=0.1)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0
    
    def get_disk_usage(self, path: str) -> Dict[str, float]:
        """Get disk usage for a path."""
        try:
            usage = shutil.disk_usage(path)
            return {
                'total_gb': usage.total / (1024**3),
                'used_gb': (usage.total - usage.free) / (1024**3),
                'free_gb': usage.free / (1024**3),
                'percent': ((usage.total - usage.free) / usage.total) * 100
            }
        except Exception:
            return {'total_gb': 0, 'used_gb': 0, 'free_gb': 0, 'percent': 0}
    
    def get_uptime(self) -> float:
        """Get process uptime in seconds."""
        return time.time() - self.start_time
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive resource statistics."""
        return {
            'memory_mb': self.get_memory_usage_mb(),
            'peak_memory_mb': self.peak_memory,
            'cpu_percent': self.get_cpu_usage(),
            'uptime_seconds': self.get_uptime(),
            'total_executions': self.total_executions,
            'limits': {
                'max_memory_mb': ResourceLimits.MAX_MEMORY_MB,
                'max_processes': ResourceLimits.MAX_PROCESSES,
                'max_artifacts_mb': ResourceLimits.MAX_ARTIFACTS_SIZE_MB
            }
        }


class ProcessManager:
    """Manage subprocess lifecycle with proper cleanup."""
    
    def __init__(self):
        self.processes: Dict[str, subprocess.Popen] = {}
        self.process_metadata: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.RLock()
        
        # Register cleanup handlers
        atexit.register(self.cleanup_all)
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle termination signals."""
        logger.info(f"Received signal {signum}, cleaning up processes...")
        self.cleanup_all()
        sys.exit(0)
    
    def add_process(self, process: subprocess.Popen, name: str = None, 
                   metadata: Dict[str, Any] = None) -> str:
        """Add a process to management."""
        with self.lock:
            if len(self.processes) >= ResourceLimits.MAX_PROCESSES:
                raise RuntimeError(f"Maximum processes limit ({ResourceLimits.MAX_PROCESSES}) reached")
            
            process_id = name or f"process_{len(self.processes)}_{int(time.time())}"
            self.processes[process_id] = process
            self.process_metadata[process_id] = {
                'created_at': datetime.now(),
                'pid': process.pid,
                'metadata': metadata or {}
            }
            
            logger.info(f"Added process {process_id} (PID: {process.pid})")
            return process_id
    
    def remove_process(self, process_id: str) -> bool:
        """Remove a process from management."""
        with self.lock:
            if process_id in self.processes:
                process = self.processes.pop(process_id)
                self.process_metadata.pop(process_id, None)
                
                # Terminate if still running
                if process.poll() is None:
                    try:
                        process.terminate()
                        process.wait(timeout=5)
                    except (subprocess.TimeoutExpired, OSError):
                        try:
                            process.kill()
                        except OSError:
                            pass
                
                logger.info(f"Removed process {process_id}")
                return True
            return False
    
    def get_process(self, process_id: str) -> Optional[subprocess.Popen]:
        """Get a managed process."""
        with self.lock:
            return self.processes.get(process_id)
    
    def list_processes(self) -> List[Dict[str, Any]]:
        """List all managed processes."""
        with self.lock:
            result = []
            for process_id, process in self.processes.items():
                metadata = self.process_metadata.get(process_id, {})
                result.append({
                    'id': process_id,
                    'pid': process.pid,
                    'running': process.poll() is None,
                    'created_at': metadata.get('created_at'),
                    'metadata': metadata.get('metadata', {})
                })
            return result
    
    def cleanup_finished(self) -> int:
        """Clean up finished processes."""
        with self.lock:
            finished = []
            for process_id, process in self.processes.items():
                if process.poll() is not None:
                    finished.append(process_id)
            
            for process_id in finished:
                self.remove_process(process_id)
            
            return len(finished)
    
    def cleanup_all(self) -> None:
        """Clean up all managed processes."""
        with self.lock:
            process_ids = list(self.processes.keys())
            for process_id in process_ids:
                self.remove_process(process_id)
            
            logger.info(f"Cleaned up {len(process_ids)} processes")


class ThreadPoolManager:
    """Manage thread pools with proper lifecycle."""
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(
            max_workers=ResourceLimits.MAX_THREADS,
            thread_name_prefix="sandbox-worker"
        )
        self.active_futures: Set[object] = set()
        self.lock = threading.RLock()
        
        # Register cleanup
        atexit.register(self.shutdown)
    
    def submit(self, fn: Callable, *args, **kwargs) -> object:
        """Submit a task to the thread pool."""
        with self.lock:
            future = self.executor.submit(fn, *args, **kwargs)
            self.active_futures.add(future)
            
            # Clean up completed futures
            completed = [f for f in self.active_futures if f.done()]
            for f in completed:
                self.active_futures.discard(f)
            
            return future
    
    def wait_for_completion(self, timeout: float = None) -> bool:
        """Wait for all tasks to complete."""
        with self.lock:
            if not self.active_futures:
                return True
            
            try:
                for future in as_completed(self.active_futures, timeout=timeout):
                    self.active_futures.discard(future)
                return True
            except TimeoutError:
                return False
    
    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the thread pool."""
        try:
            self.executor.shutdown(wait=wait)
        except Exception as e:
            logger.error(f"Error shutting down thread pool: {e}")


class CleanupManager:
    """Automatic cleanup system for resources."""
    
    def __init__(self, resource_manager: 'ResourceManager'):
        self.resource_manager = resource_manager
        self.cleanup_thread = None
        self.running = False
        self.lock = threading.RLock()
    
    def start(self):
        """Start the cleanup thread."""
        with self.lock:
            if not self.running:
                self.running = True
                self.cleanup_thread = threading.Thread(
                    target=self._cleanup_loop,
                    daemon=True,
                    name="sandbox-cleanup"
                )
                self.cleanup_thread.start()
                logger.info("Cleanup manager started")
    
    def stop(self):
        """Stop the cleanup thread."""
        with self.lock:
            self.running = False
            if self.cleanup_thread:
                self.cleanup_thread.join(timeout=5)
                logger.info("Cleanup manager stopped")
    
    def _cleanup_loop(self):
        """Main cleanup loop."""
        while self.running:
            try:
                self._perform_cleanup()
                time.sleep(ResourceLimits.CLEANUP_INTERVAL_SEC)
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                time.sleep(60)  # Wait longer on error
    
    def _perform_cleanup(self):
        """Perform cleanup tasks."""
        # Clean up finished processes
        finished_processes = self.resource_manager.process_manager.cleanup_finished()
        if finished_processes > 0:
            logger.info(f"Cleaned up {finished_processes} finished processes")
        
        # Clean up old artifacts
        cleaned_artifacts = self._cleanup_old_artifacts()
        if cleaned_artifacts > 0:
            logger.info(f"Cleaned up {cleaned_artifacts} old artifacts")
        
        # Clean up old sessions
        cleaned_sessions = self._cleanup_old_sessions()
        if cleaned_sessions > 0:
            logger.info(f"Cleaned up {cleaned_sessions} old sessions")
        
        # Check memory usage
        memory_mb = self.resource_manager.monitor.get_memory_usage_mb()
        if memory_mb > ResourceLimits.MAX_MEMORY_MB * 0.9:
            logger.warning(f"High memory usage: {memory_mb:.1f}MB")
            self._emergency_cleanup()
    
    def _cleanup_old_artifacts(self) -> int:
        """Clean up old artifact directories."""
        cleaned = 0
        temp_dir = Path(tempfile.gettempdir())
        cutoff_time = time.time() - (ResourceLimits.ARTIFACT_MAX_AGE_HOURS * 3600)
        
        try:
            for pattern in ['sandbox_artifacts_*', 'session_*']:
                for item in temp_dir.glob(pattern):
                    if item.is_dir():
                        try:
                            if item.stat().st_mtime < cutoff_time:
                                shutil.rmtree(item, ignore_errors=True)
                                cleaned += 1
                        except (OSError, FileNotFoundError):
                            pass
        except Exception as e:
            logger.error(f"Error cleaning old artifacts: {e}")
        
        return cleaned
    
    def _cleanup_old_sessions(self) -> int:
        """Clean up old session directories."""
        cleaned = 0
        try:
            # This would be implemented based on session storage location
            # For now, we'll use a placeholder
            pass
        except Exception as e:
            logger.error(f"Error cleaning old sessions: {e}")
        
        return cleaned
    
    def _emergency_cleanup(self):
        """Perform emergency cleanup when resources are low."""
        logger.warning("Performing emergency cleanup due to high resource usage")
        
        # Force cleanup of all caches
        if hasattr(self.resource_manager, 'execution_contexts'):
            for context in self.resource_manager.execution_contexts.values():
                if hasattr(context, 'clear_cache'):
                    context.clear_cache()
        
        # Force garbage collection
        import gc
        gc.collect()


class ResourceManager:
    """Central resource management system."""
    
    def __init__(self):
        self.monitor = ResourceMonitor()
        self.process_manager = ProcessManager()
        self.thread_pool = ThreadPoolManager()
        self.cleanup_manager = CleanupManager(self)
        self.execution_contexts: Dict[str, Any] = {}
        self.lock = threading.RLock()
        
        # Start cleanup manager
        self.cleanup_manager.start()
        
        logger.info("Resource manager initialized")
    
    def check_resource_limits(self) -> None:
        """Check if resource limits are exceeded."""
        # Check memory
        memory_mb = self.monitor.get_memory_usage_mb()
        if memory_mb > ResourceLimits.MAX_MEMORY_MB:
            raise ResourceError(f"Memory limit exceeded: {memory_mb:.1f}MB > {ResourceLimits.MAX_MEMORY_MB}MB")
        
        # Check processes
        process_count = len(self.process_manager.processes)
        if process_count > ResourceLimits.MAX_PROCESSES:
            raise ResourceError(f"Process limit exceeded: {process_count} > {ResourceLimits.MAX_PROCESSES}")
        
        # Check execution contexts
        if len(self.execution_contexts) > ResourceLimits.MAX_SESSIONS:
            raise ResourceError(f"Session limit exceeded: {len(self.execution_contexts)} > {ResourceLimits.MAX_SESSIONS}")
    
    def register_execution_context(self, session_id: str, context: Any) -> None:
        """Register an execution context."""
        with self.lock:
            self.check_resource_limits()
            self.execution_contexts[session_id] = context
    
    def unregister_execution_context(self, session_id: str) -> None:
        """Unregister an execution context."""
        with self.lock:
            if session_id in self.execution_contexts:
                context = self.execution_contexts.pop(session_id)
                if hasattr(context, 'cleanup'):
                    context.cleanup()
    
    def get_resource_stats(self) -> Dict[str, Any]:
        """Get comprehensive resource statistics."""
        stats = self.monitor.get_stats()
        stats.update({
            'processes': len(self.process_manager.processes),
            'active_contexts': len(self.execution_contexts),
            'thread_pool_active': len(self.thread_pool.active_futures),
            'cleanup_running': self.cleanup_manager.running,
            'disk_usage': self.monitor.get_disk_usage(tempfile.gettempdir())
        })
        return stats
    
    def emergency_shutdown(self) -> None:
        """Emergency shutdown of all resources."""
        logger.warning("Performing emergency shutdown")
        
        # Stop cleanup manager
        self.cleanup_manager.stop()
        
        # Clean up all execution contexts
        with self.lock:
            for session_id in list(self.execution_contexts.keys()):
                self.unregister_execution_context(session_id)
        
        # Clean up processes
        self.process_manager.cleanup_all()
        
        # Shutdown thread pool
        self.thread_pool.shutdown(wait=False)
        
        logger.info("Emergency shutdown complete")


class ResourceError(Exception):
    """Exception raised when resource limits are exceeded."""
    pass


# Global resource manager instance
_resource_manager = None


def get_resource_manager() -> ResourceManager:
    """Get the global resource manager instance."""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager()
    return _resource_manager
