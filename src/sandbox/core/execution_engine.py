"""
Core Execution Engine for Swiss Sandbox

This module provides the ExecutionEngine class that handles Python, shell, and Manim
execution with proper timeout handling, context management, and environment isolation.
"""

import os
import sys
import time
import signal
import subprocess
import threading
import traceback
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, field
from contextlib import contextmanager
import logging
import io
import json

# Import from existing modules
from .execution_context import PersistentExecutionContext
from .manim_support import ManIMHelper
from .types import ExecutionContext, ExecutionResult, ResourceLimits, ExecutionRecord

# Import logging and error handling
from .logging_system import (
    StructuredLogger, ErrorHandler, PerformanceMonitor, ErrorCategory,
    with_error_handling, with_performance_monitoring
)

logger = logging.getLogger(__name__)


class ExecutionTimeoutError(Exception):
    """Raised when execution exceeds timeout limit."""
    pass


class ExecutionSecurityError(Exception):
    """Raised when execution violates security policies."""
    pass


# ExecutionRecord is now imported from types module


class TimeoutHandler:
    """Handles execution timeouts using threading and signals."""
    
    def __init__(self, timeout_seconds: int):
        self.timeout_seconds = timeout_seconds
        self.timer = None
        self.timed_out = False
    
    def _timeout_callback(self):
        """Called when timeout is reached."""
        self.timed_out = True
        # Send SIGINT to current process to interrupt execution
        try:
            os.kill(os.getpid(), signal.SIGINT)
        except:
            pass
    
    def start(self):
        """Start the timeout timer."""
        if self.timeout_seconds > 0:
            self.timer = threading.Timer(self.timeout_seconds, self._timeout_callback)
            self.timer.start()
    
    def cancel(self):
        """Cancel the timeout timer."""
        if self.timer:
            self.timer.cancel()
            self.timer = None
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cancel()
        if self.timed_out:
            raise ExecutionTimeoutError(f"Execution timed out after {self.timeout_seconds} seconds")


class ExecutionEngine:
    """
    Core execution engine that handles Python, shell, and Manim execution
    with proper timeout handling, context management, and environment isolation.
    """
    
    def __init__(self, security_manager=None, structured_logger=None, error_handler=None, performance_monitor=None):
        """Initialize the execution engine."""
        self.security_manager = security_manager
        self.execution_history: List[ExecutionRecord] = []
        self.active_contexts: Dict[str, PersistentExecutionContext] = {}
        self.manim_helpers: Dict[str, ManIMHelper] = {}
        
        # Logging and error handling
        self.structured_logger = structured_logger or StructuredLogger("execution_engine")
        self.error_handler = error_handler or ErrorHandler(self.structured_logger)
        self.performance_monitor = performance_monitor or PerformanceMonitor(self.structured_logger)
        
        # Performance tracking
        self.total_executions = 0
        self.successful_executions = 0
        self.failed_executions = 0
        
        self.structured_logger.info("ExecutionEngine initialized", component="execution_engine")
    
    @contextmanager
    def _change_working_directory(self, new_dir: str):
        """Context manager to temporarily change working directory."""
        original_dir = os.getcwd()
        try:
            os.chdir(new_dir)
            logger.debug(f"Changed working directory to: {new_dir}")
            yield
        finally:
            os.chdir(original_dir)
            logger.debug(f"Restored working directory to: {original_dir}")
    
    def get_or_create_persistent_context(self, context: ExecutionContext) -> PersistentExecutionContext:
        """Get or create a persistent execution context."""
        if context.workspace_id not in self.active_contexts:
            # Create new persistent context
            persistent_context = PersistentExecutionContext(
                session_id=context.session_id or context.workspace_id
            )
            
            # Configure based on ExecutionContext
            persistent_context.globals_dict.update(context.execution_globals)
            
            # Set up environment variables
            for key, value in context.environment_vars.items():
                os.environ[key] = value
            
            self.active_contexts[context.workspace_id] = persistent_context
            logger.info(f"Created persistent context for workspace: {context.workspace_id}")
        
        return self.active_contexts[context.workspace_id]
    
    @with_error_handling(ErrorCategory.EXECUTION, "execution_engine")
    @with_performance_monitoring("execution_engine", "execute_python")
    def execute_python(self, code: str, context: ExecutionContext) -> ExecutionResult:
        """
        Execute Python code with timeout handling and context management.
        
        Args:
            code: Python code to execute
            context: Execution context with configuration
            
        Returns:
            ExecutionResult with execution details
        """
        execution_id = f"py_{int(time.time() * 1000)}"
        start_time = time.time()
        
        self.structured_logger.info(
            f"Executing Python code",
            component="execution_engine",
            execution_id=execution_id,
            context_id=context.workspace_id
        )
        
        try:
            # Security validation
            if self.security_manager:
                validation_result = self.security_manager.validate_python_code(code)
                if not validation_result.is_safe:
                    return ExecutionResult(
                        success=False,
                        error=f"Security violation: {validation_result.reason}",
                        error_type="SecurityError",
                        execution_time=time.time() - start_time
                    )
            
            # Get persistent context
            persistent_context = self.get_or_create_persistent_context(context)
            
            # Execute with timeout and proper working directory
            with TimeoutHandler(context.resource_limits.max_execution_time):
                try:
                    # Change to workspace directory if available
                    workspace_path = context.environment_vars.get('WORKSPACE_PATH')
                    if workspace_path and os.path.exists(workspace_path):
                        with self._change_working_directory(workspace_path):
                            # Use the persistent context's execute_code method
                            result_dict = persistent_context.execute_code(
                                code=code,
                                cache_key=f"{context.workspace_id}_{hash(code)}",
                                validate=False  # Already validated above
                            )
                    else:
                        # Use the persistent context's execute_code method
                        result_dict = persistent_context.execute_code(
                            code=code,
                            cache_key=f"{context.workspace_id}_{hash(code)}",
                            validate=False  # Already validated above
                        )
                    
                    # Convert to ExecutionResult
                    execution_time = time.time() - start_time
                    result = ExecutionResult(
                        success=result_dict['success'],
                        output=result_dict['stdout'],
                        error=result_dict.get('error'),
                        error_type=result_dict.get('error_type'),
                        execution_time=execution_time,
                        artifacts=result_dict.get('artifacts', [])
                    )
                    
                    # Update statistics
                    self.total_executions += 1
                    if result.success:
                        self.successful_executions += 1
                    else:
                        self.failed_executions += 1
                    
                    # Store in history
                    record = ExecutionRecord(
                        execution_id=execution_id,
                        code=code,
                        language="python",
                        context_id=context.workspace_id,
                        result=result
                    )
                    self.execution_history.append(record)
                    
                    # Keep history manageable
                    if len(self.execution_history) > 1000:
                        self.execution_history = self.execution_history[-500:]
                    
                    self.structured_logger.info(
                        f"Python execution completed",
                        component="execution_engine",
                        execution_id=execution_id,
                        context_id=context.workspace_id,
                        success=result.success,
                        execution_time=result.execution_time
                    )
                    return result
                    
                except KeyboardInterrupt:
                    # Handle timeout interruption
                    raise ExecutionTimeoutError(f"Execution timed out after {context.resource_limits.max_execution_time} seconds")
                    
        except ExecutionTimeoutError as e:
            execution_time = time.time() - start_time
            self.total_executions += 1
            self.failed_executions += 1
            
            result = ExecutionResult(
                success=False,
                error=str(e),
                error_type="TimeoutError",
                execution_time=execution_time
            )
            
            logger.warning(f"Python execution timed out (ID: {execution_id})")
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.total_executions += 1
            self.failed_executions += 1
            
            result = ExecutionResult(
                success=False,
                error=str(e),
                error_type=type(e).__name__,
                execution_time=execution_time
            )
            
            logger.error(f"Python execution failed (ID: {execution_id}): {e}")
            return result
    
    @with_error_handling(ErrorCategory.EXECUTION, "execution_engine")
    @with_performance_monitoring("execution_engine", "execute_shell")
    def execute_shell(self, command: str, context: ExecutionContext) -> ExecutionResult:
        """
        Execute shell command with timeout handling and security validation.
        
        Args:
            command: Shell command to execute
            context: Execution context with configuration
            
        Returns:
            ExecutionResult with execution details
        """
        execution_id = f"sh_{int(time.time() * 1000)}"
        start_time = time.time()
        
        logger.info(f"Executing shell command (ID: {execution_id}): {command}")
        
        try:
            # Security validation
            if self.security_manager:
                validation_result = self.security_manager.validate_command(command)
                if not validation_result.is_safe:
                    return ExecutionResult(
                        success=False,
                        error=f"Security violation: {validation_result.reason}",
                        error_type="SecurityError",
                        execution_time=time.time() - start_time
                    )
            
            # Prepare working directory
            working_dir = context.artifacts_dir or Path.cwd()
            if not working_dir.exists():
                working_dir.mkdir(parents=True, exist_ok=True)
            
            # Prepare environment
            env = os.environ.copy()
            env.update(context.environment_vars)
            
            # Execute command with timeout
            try:
                process = subprocess.run(
                    command,
                    shell=True,
                    cwd=str(working_dir),
                    env=env,
                    timeout=context.resource_limits.max_execution_time,
                    capture_output=True,
                    text=True
                )
                
                execution_time = time.time() - start_time
                
                # Check for artifacts created during execution
                artifacts = []
                if context.artifacts_dir and context.artifacts_dir.exists():
                    for file_path in context.artifacts_dir.rglob('*'):
                        if file_path.is_file():
                            artifacts.append(str(file_path.relative_to(context.artifacts_dir)))
                
                result = ExecutionResult(
                    success=process.returncode == 0,
                    output=process.stdout,
                    error=process.stderr if process.returncode != 0 else None,
                    error_type="CommandError" if process.returncode != 0 else None,
                    execution_time=execution_time,
                    artifacts=artifacts,
                    metadata={
                        'return_code': process.returncode,
                        'command': command,
                        'working_directory': str(working_dir)
                    }
                )
                
                # Update statistics
                self.total_executions += 1
                if result.success:
                    self.successful_executions += 1
                else:
                    self.failed_executions += 1
                
                # Store in history
                record = ExecutionRecord(
                    execution_id=execution_id,
                    code=command,
                    language="shell",
                    context_id=context.workspace_id,
                    result=result
                )
                self.execution_history.append(record)
                
                logger.info(f"Shell execution completed (ID: {execution_id}, Return code: {process.returncode})")
                return result
                
            except subprocess.TimeoutExpired:
                execution_time = time.time() - start_time
                self.total_executions += 1
                self.failed_executions += 1
                
                result = ExecutionResult(
                    success=False,
                    error=f"Command timed out after {context.resource_limits.max_execution_time} seconds",
                    error_type="TimeoutError",
                    execution_time=execution_time,
                    metadata={
                        'command': command,
                        'timeout': context.resource_limits.max_execution_time
                    }
                )
                
                logger.warning(f"Shell execution timed out (ID: {execution_id})")
                return result
                
        except Exception as e:
            execution_time = time.time() - start_time
            self.total_executions += 1
            self.failed_executions += 1
            
            result = ExecutionResult(
                success=False,
                error=str(e),
                error_type=type(e).__name__,
                execution_time=execution_time
            )
            
            logger.error(f"Shell execution failed (ID: {execution_id}): {e}")
            return result
    
    @with_error_handling(ErrorCategory.EXECUTION, "execution_engine")
    @with_performance_monitoring("execution_engine", "execute_manim")
    def execute_manim(self, script: str, context: ExecutionContext, 
                     quality: str = 'medium', scene_name: Optional[str] = None) -> ExecutionResult:
        """
        Execute Manim script with timeout handling and artifact management.
        
        Args:
            script: Manim Python script to execute
            context: Execution context with configuration
            quality: Video quality ('low', 'medium', 'high')
            scene_name: Specific scene to render (optional)
            
        Returns:
            ExecutionResult with execution details
        """
        execution_id = f"manim_{int(time.time() * 1000)}"
        start_time = time.time()
        
        logger.info(f"Executing Manim script (ID: {execution_id})")
        
        try:
            # Security validation
            if self.security_manager:
                validation_result = self.security_manager.validate_python_code(script)
                if not validation_result.is_safe:
                    return ExecutionResult(
                        success=False,
                        error=f"Security violation: {validation_result.reason}",
                        error_type="SecurityError",
                        execution_time=time.time() - start_time
                    )
            
            # Get or create Manim helper
            if context.workspace_id not in self.manim_helpers:
                self.manim_helpers[context.workspace_id] = ManIMHelper(context.artifacts_dir)
            
            manim_helper = self.manim_helpers[context.workspace_id]
            
            # Check Manim installation
            is_installed, version_info = manim_helper.check_manim_installation()
            if not is_installed:
                return ExecutionResult(
                    success=False,
                    error=f"Manim not installed: {version_info}",
                    error_type="InstallationError",
                    execution_time=time.time() - start_time
                )
            
            # Create temporary file for the script
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(script)
                temp_script_path = f.name
            
            try:
                # Prepare Manim command
                quality_flags = {
                    'low': ['-ql'],
                    'medium': ['-qm'], 
                    'high': ['-qh']
                }
                
                manim_dir = context.artifacts_dir / 'manim'
                manim_dir.mkdir(parents=True, exist_ok=True)
                
                cmd = [
                    'manim',
                    temp_script_path,
                    '--media_dir', str(manim_dir),
                    '--disable_caching'
                ] + quality_flags.get(quality, ['-qm'])
                
                # Add scene name if specified
                if scene_name:
                    cmd.append(scene_name)
                
                # Prepare environment
                env = os.environ.copy()
                env.update(context.environment_vars)
                
                # Execute Manim with timeout
                process = subprocess.run(
                    cmd,
                    cwd=str(context.artifacts_dir),
                    env=env,
                    timeout=context.resource_limits.max_execution_time,
                    capture_output=True,
                    text=True
                )
                
                execution_time = time.time() - start_time
                
                # Find generated artifacts
                artifacts = []
                if manim_dir.exists():
                    for file_path in manim_dir.rglob('*'):
                        if file_path.is_file() and file_path.suffix in ['.mp4', '.png', '.gif', '.mov']:
                            artifacts.append(str(file_path.relative_to(context.artifacts_dir)))
                
                result = ExecutionResult(
                    success=process.returncode == 0,
                    output=process.stdout,
                    error=process.stderr if process.returncode != 0 else None,
                    error_type="ManIMError" if process.returncode != 0 else None,
                    execution_time=execution_time,
                    artifacts=artifacts,
                    metadata={
                        'return_code': process.returncode,
                        'quality': quality,
                        'scene_name': scene_name,
                        'manim_version': version_info,
                        'artifacts_count': len(artifacts)
                    }
                )
                
                # Update statistics
                self.total_executions += 1
                if result.success:
                    self.successful_executions += 1
                else:
                    self.failed_executions += 1
                
                # Store in history
                record = ExecutionRecord(
                    execution_id=execution_id,
                    code=script,
                    language="manim",
                    context_id=context.workspace_id,
                    result=result
                )
                self.execution_history.append(record)
                
                logger.info(f"Manim execution completed (ID: {execution_id}, Success: {result.success}, Artifacts: {len(artifacts)})")
                return result
                
            except subprocess.TimeoutExpired:
                execution_time = time.time() - start_time
                self.total_executions += 1
                self.failed_executions += 1
                
                result = ExecutionResult(
                    success=False,
                    error=f"Manim execution timed out after {context.resource_limits.max_execution_time} seconds",
                    error_type="TimeoutError",
                    execution_time=execution_time,
                    metadata={
                        'quality': quality,
                        'timeout': context.resource_limits.max_execution_time
                    }
                )
                
                logger.warning(f"Manim execution timed out (ID: {execution_id})")
                return result
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_script_path)
                except:
                    pass
                    
        except Exception as e:
            execution_time = time.time() - start_time
            self.total_executions += 1
            self.failed_executions += 1
            
            result = ExecutionResult(
                success=False,
                error=str(e),
                error_type=type(e).__name__,
                execution_time=execution_time
            )
            
            logger.error(f"Manim execution failed (ID: {execution_id}): {e}")
            return result
    
    def get_execution_history(self, context_id: Optional[str] = None, 
                            language: Optional[str] = None, 
                            limit: int = 100) -> List[ExecutionRecord]:
        """
        Get execution history with optional filtering.
        
        Args:
            context_id: Filter by context ID
            language: Filter by language ('python', 'shell', 'manim')
            limit: Maximum number of records to return
            
        Returns:
            List of execution records
        """
        filtered_history = self.execution_history
        
        if context_id:
            filtered_history = [r for r in filtered_history if r.context_id == context_id]
        
        if language:
            filtered_history = [r for r in filtered_history if r.language == language]
        
        # Sort by timestamp (most recent first) and limit
        filtered_history.sort(key=lambda r: r.timestamp, reverse=True)
        return filtered_history[:limit]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get execution engine statistics."""
        return {
            'total_executions': self.total_executions,
            'successful_executions': self.successful_executions,
            'failed_executions': self.failed_executions,
            'success_rate': self.successful_executions / max(self.total_executions, 1),
            'active_contexts': len(self.active_contexts),
            'history_size': len(self.execution_history),
            'languages': {
                'python': len([r for r in self.execution_history if r.language == 'python']),
                'shell': len([r for r in self.execution_history if r.language == 'shell']),
                'manim': len([r for r in self.execution_history if r.language == 'manim'])
            }
        }
    
    def cleanup_context(self, context_id: str) -> bool:
        """
        Clean up resources for a specific context.
        
        Args:
            context_id: Context ID to clean up
            
        Returns:
            True if cleanup was successful
        """
        try:
            if context_id in self.active_contexts:
                persistent_context = self.active_contexts[context_id]
                persistent_context.cleanup()
                del self.active_contexts[context_id]
            
            if context_id in self.manim_helpers:
                del self.manim_helpers[context_id]
            
            # Remove from history (optional - might want to keep for debugging)
            # self.execution_history = [r for r in self.execution_history if r.context_id != context_id]
            
            logger.info(f"Cleaned up context: {context_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cleanup context {context_id}: {e}")
            return False
    
    def cleanup_all(self):
        """Clean up all resources."""
        logger.info("Cleaning up ExecutionEngine resources...")
        
        for context_id in list(self.active_contexts.keys()):
            self.cleanup_context(context_id)
        
        self.execution_history.clear()
        self.active_contexts.clear()
        self.manim_helpers.clear()
        
        logger.info("ExecutionEngine cleanup completed")