"""
Workspace lifecycle management for sandbox environments.

This module provides:
- Workspace creation, cleanup, and merge-back functionality
- Session management for multiple concurrent sandboxes
- Workspace status tracking and monitoring
- Lifecycle event handling and notifications
"""

import os
import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum

from .models import SandboxWorkspace, IsolationConfig
from .cloner import WorkspaceCloner
from .security import SecurityPolicy
from ..types import WorkspaceStatus

logger = logging.getLogger(__name__)


class LifecycleEvent(Enum):
    """Lifecycle events that can occur during workspace management."""
    WORKSPACE_CREATED = "workspace_created"
    WORKSPACE_ACTIVATED = "workspace_activated"
    WORKSPACE_SUSPENDED = "workspace_suspended"
    WORKSPACE_RESUMED = "workspace_resumed"
    WORKSPACE_CLEANUP_STARTED = "workspace_cleanup_started"
    WORKSPACE_DESTROYED = "workspace_destroyed"
    WORKSPACE_MERGED = "workspace_merged"
    SESSION_STARTED = "session_started"
    SESSION_ENDED = "session_ended"
    ERROR_OCCURRED = "error_occurred"


@dataclass
class LifecycleEventData:
    """Data associated with a lifecycle event."""
    event: LifecycleEvent
    workspace_id: str
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[Exception] = None


@dataclass
class WorkspaceSession:
    """Represents a workspace session with metadata."""
    session_id: str
    workspace: SandboxWorkspace
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def update_access(self):
        """Update the last accessed time and increment access count."""
        self.last_accessed = datetime.now()
        self.access_count += 1


class WorkspaceLifecycleManager:
    """
    Manages the complete lifecycle of sandbox workspaces.
    
    This class handles:
    - Workspace creation and initialization
    - Session management for concurrent workspaces
    - Status tracking and monitoring
    - Cleanup and resource management
    - Event handling and notifications
    """
    
    def __init__(self, security_policy: Optional[SecurityPolicy] = None,
                 max_concurrent_workspaces: int = 10,
                 workspace_timeout_minutes: int = 60):
        """
        Initialize the lifecycle manager.
        
        Args:
            security_policy: Security policy for workspaces
            max_concurrent_workspaces: Maximum number of concurrent workspaces
            workspace_timeout_minutes: Timeout for inactive workspaces
        """
        self._cloner = WorkspaceCloner(security_policy)
        self._sessions: Dict[str, WorkspaceSession] = {}
        self._event_handlers: List[Callable[[LifecycleEventData], None]] = []
        self._max_concurrent = max_concurrent_workspaces
        self._timeout_minutes = workspace_timeout_minutes
        self._monitoring_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        self._lock = threading.RLock()
        
        # Start monitoring thread
        self._start_monitoring()
    
    def add_event_handler(self, handler: Callable[[LifecycleEventData], None]):
        """
        Add an event handler for lifecycle events.
        
        Args:
            handler: Function to call when events occur
        """
        self._event_handlers.append(handler)
    
    def remove_event_handler(self, handler: Callable[[LifecycleEventData], None]):
        """
        Remove an event handler.
        
        Args:
            handler: Handler function to remove
        """
        if handler in self._event_handlers:
            self._event_handlers.remove(handler)
    
    def _emit_event(self, event: LifecycleEvent, workspace_id: str, 
                   details: Dict[str, Any] = None, error: Exception = None):
        """
        Emit a lifecycle event to all registered handlers.
        
        Args:
            event: The event type
            workspace_id: ID of the workspace
            details: Additional event details
            error: Error information if applicable
        """
        event_data = LifecycleEventData(
            event=event,
            workspace_id=workspace_id,
            timestamp=datetime.now(),
            details=details or {},
            error=error
        )
        
        for handler in self._event_handlers:
            try:
                handler(event_data)
            except Exception as e:
                logger.error(f"Event handler failed: {e}")
    
    def create_workspace(self, source_path: str, session_id: str = None,
                        isolation_config: Optional[IsolationConfig] = None,
                        metadata: Dict[str, Any] = None) -> WorkspaceSession:
        """
        Create a new workspace session.
        
        Args:
            source_path: Path to the source workspace to clone
            session_id: Optional session ID (generated if not provided)
            isolation_config: Isolation configuration
            metadata: Additional session metadata
            
        Returns:
            WorkspaceSession object
            
        Raises:
            RuntimeError: If maximum concurrent workspaces exceeded
            Exception: If workspace creation fails
        """
        with self._lock:
            # Check concurrent workspace limit
            if len(self._sessions) >= self._max_concurrent:
                self._cleanup_expired_sessions()
                if len(self._sessions) >= self._max_concurrent:
                    raise RuntimeError(f"Maximum concurrent workspaces ({self._max_concurrent}) exceeded")
            
            # Generate session ID if not provided
            if session_id is None:
                session_id = f"session_{int(time.time())}_{len(self._sessions)}"
            
            if session_id in self._sessions:
                raise ValueError(f"Session ID already exists: {session_id}")
            
            try:
                # Create the workspace
                self._emit_event(LifecycleEvent.SESSION_STARTED, session_id, 
                               {"source_path": source_path})
                
                workspace = self._cloner.clone_workspace(
                    source_path, session_id, isolation_config
                )
                
                # Set up isolation
                if not self._cloner.setup_isolation(workspace):
                    logger.warning(f"Failed to set up isolation for workspace {session_id}")
                
                # Create session
                session = WorkspaceSession(
                    session_id=session_id,
                    workspace=workspace,
                    created_at=datetime.now(),
                    last_accessed=datetime.now(),
                    metadata=metadata or {}
                )
                
                self._sessions[session_id] = session
                
                self._emit_event(LifecycleEvent.WORKSPACE_CREATED, session_id, {
                    "workspace_path": workspace.sandbox_path,
                    "isolation_enabled": workspace.isolation_config.use_docker
                })
                
                logger.info(f"Created workspace session {session_id}")
                return session
                
            except Exception as e:
                self._emit_event(LifecycleEvent.ERROR_OCCURRED, session_id, 
                               {"operation": "create_workspace"}, e)
                logger.error(f"Failed to create workspace session {session_id}: {e}")
                raise
    
    def get_session(self, session_id: str) -> Optional[WorkspaceSession]:
        """
        Get a workspace session by ID.
        
        Args:
            session_id: The session ID
            
        Returns:
            WorkspaceSession if found, None otherwise
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.update_access()
            return session
    
    def list_sessions(self) -> List[WorkspaceSession]:
        """
        List all active workspace sessions.
        
        Returns:
            List of active WorkspaceSession objects
        """
        with self._lock:
            return list(self._sessions.values())
    
    def suspend_workspace(self, session_id: str) -> bool:
        """
        Suspend a workspace (pause but don't destroy).
        
        Args:
            session_id: The session ID to suspend
            
        Returns:
            True if suspended successfully
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                logger.warning(f"Session not found for suspension: {session_id}")
                return False
            
            try:
                # For Docker containers, we can pause them
                if session.workspace.isolation_config.use_docker:
                    container_id = session.workspace.metadata.get('container_id')
                    if container_id:
                        import subprocess
                        result = subprocess.run(['docker', 'pause', container_id], 
                                              capture_output=True, text=True)
                        if result.returncode == 0:
                            session.workspace.status = WorkspaceStatus.SUSPENDED
                            self._emit_event(LifecycleEvent.WORKSPACE_SUSPENDED, session_id)
                            logger.info(f"Suspended workspace {session_id}")
                            return True
                        else:
                            logger.error(f"Failed to pause container {container_id}: {result.stderr}")
                            return False
                
                # For non-Docker workspaces, just mark as suspended
                session.workspace.status = WorkspaceStatus.SUSPENDED
                self._emit_event(LifecycleEvent.WORKSPACE_SUSPENDED, session_id)
                return True
                
            except Exception as e:
                self._emit_event(LifecycleEvent.ERROR_OCCURRED, session_id, 
                               {"operation": "suspend_workspace"}, e)
                logger.error(f"Failed to suspend workspace {session_id}: {e}")
                return False
    
    def resume_workspace(self, session_id: str) -> bool:
        """
        Resume a suspended workspace.
        
        Args:
            session_id: The session ID to resume
            
        Returns:
            True if resumed successfully
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                logger.warning(f"Session not found for resumption: {session_id}")
                return False
            
            try:
                # For Docker containers, unpause them
                if session.workspace.isolation_config.use_docker:
                    container_id = session.workspace.metadata.get('container_id')
                    if container_id:
                        import subprocess
                        result = subprocess.run(['docker', 'unpause', container_id], 
                                              capture_output=True, text=True)
                        if result.returncode == 0:
                            session.workspace.status = WorkspaceStatus.ACTIVE
                            session.update_access()
                            self._emit_event(LifecycleEvent.WORKSPACE_RESUMED, session_id)
                            logger.info(f"Resumed workspace {session_id}")
                            return True
                        else:
                            logger.error(f"Failed to unpause container {container_id}: {result.stderr}")
                            return False
                
                # For non-Docker workspaces, just mark as active
                session.workspace.status = WorkspaceStatus.ACTIVE
                session.update_access()
                self._emit_event(LifecycleEvent.WORKSPACE_RESUMED, session_id)
                return True
                
            except Exception as e:
                self._emit_event(LifecycleEvent.ERROR_OCCURRED, session_id, 
                               {"operation": "resume_workspace"}, e)
                logger.error(f"Failed to resume workspace {session_id}: {e}")
                return False
    
    def merge_workspace_changes(self, session_id: str, target_path: str) -> bool:
        """
        Merge changes from a workspace back to the target path.
        
        Args:
            session_id: The session ID
            target_path: Path to merge changes back to
            
        Returns:
            True if merge was successful
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                logger.warning(f"Session not found for merge: {session_id}")
                return False
            
            try:
                result = self._cloner.merge_changes_back(session.workspace, target_path)
                if result:
                    self._emit_event(LifecycleEvent.WORKSPACE_MERGED, session_id, {
                        "target_path": target_path
                    })
                    logger.info(f"Merged changes from workspace {session_id} to {target_path}")
                else:
                    logger.error(f"Failed to merge changes from workspace {session_id}")
                
                return result
                
            except Exception as e:
                self._emit_event(LifecycleEvent.ERROR_OCCURRED, session_id, 
                               {"operation": "merge_workspace_changes"}, e)
                logger.error(f"Failed to merge workspace changes {session_id}: {e}")
                return False
    
    def destroy_workspace(self, session_id: str) -> bool:
        """
        Destroy a workspace session and clean up resources.
        
        Args:
            session_id: The session ID to destroy
            
        Returns:
            True if destroyed successfully
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                logger.warning(f"Session not found for destruction: {session_id}")
                return False
            
            try:
                self._emit_event(LifecycleEvent.WORKSPACE_CLEANUP_STARTED, session_id)
                
                # Clean up the workspace
                result = self._cloner.cleanup_workspace(session.workspace)
                
                # Remove from sessions
                del self._sessions[session_id]
                
                if result:
                    self._emit_event(LifecycleEvent.WORKSPACE_DESTROYED, session_id)
                    self._emit_event(LifecycleEvent.SESSION_ENDED, session_id)
                    logger.info(f"Destroyed workspace session {session_id}")
                else:
                    logger.warning(f"Workspace cleanup had issues for session {session_id}")
                
                return result
                
            except Exception as e:
                self._emit_event(LifecycleEvent.ERROR_OCCURRED, session_id, 
                               {"operation": "destroy_workspace"}, e)
                logger.error(f"Failed to destroy workspace {session_id}: {e}")
                return False
    
    def get_workspace_status(self, session_id: str) -> Dict[str, Any]:
        """
        Get comprehensive status information for a workspace.
        
        Args:
            session_id: The session ID
            
        Returns:
            Dictionary containing status information
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return {"error": "Session not found"}
            
            # Get security status
            security_status = self._cloner.get_security_status(session.workspace)
            
            return {
                "session_id": session_id,
                "workspace_status": session.workspace.status.value,
                "created_at": session.created_at.isoformat(),
                "last_accessed": session.last_accessed.isoformat(),
                "access_count": session.access_count,
                "workspace_path": session.workspace.sandbox_path,
                "source_path": session.workspace.source_path,
                "isolation_config": {
                    "use_docker": session.workspace.isolation_config.use_docker,
                    "container_image": session.workspace.isolation_config.container_image,
                    "cpu_limit": session.workspace.isolation_config.cpu_limit,
                    "memory_limit": session.workspace.isolation_config.memory_limit,
                    "network_isolation": session.workspace.isolation_config.network_isolation
                },
                "security_status": security_status,
                "metadata": session.metadata
            }
    
    def _cleanup_expired_sessions(self):
        """Clean up expired sessions based on timeout."""
        current_time = datetime.now()
        timeout_delta = timedelta(minutes=self._timeout_minutes)
        
        expired_sessions = []
        for session_id, session in self._sessions.items():
            if current_time - session.last_accessed > timeout_delta:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            logger.info(f"Cleaning up expired session: {session_id}")
            self.destroy_workspace(session_id)
    
    def _start_monitoring(self):
        """Start the monitoring thread for workspace lifecycle management."""
        if self._monitoring_thread is None or not self._monitoring_thread.is_alive():
            self._monitoring_thread = threading.Thread(
                target=self._monitoring_loop,
                daemon=True,
                name="WorkspaceLifecycleMonitor"
            )
            self._monitoring_thread.start()
            logger.info("Started workspace lifecycle monitoring")
    
    def _monitoring_loop(self):
        """Main monitoring loop that runs in a separate thread."""
        while not self._shutdown_event.is_set():
            try:
                # Clean up expired sessions every 5 minutes
                self._cleanup_expired_sessions()
                
                # Wait for 5 minutes or until shutdown
                self._shutdown_event.wait(300)  # 5 minutes
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                # Wait a bit before retrying
                self._shutdown_event.wait(60)  # 1 minute
    
    def shutdown(self):
        """
        Shutdown the lifecycle manager and clean up all resources.
        """
        logger.info("Shutting down workspace lifecycle manager")
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Wait for monitoring thread to finish
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            self._monitoring_thread.join(timeout=10)
        
        # Clean up all active sessions
        with self._lock:
            session_ids = list(self._sessions.keys())
            for session_id in session_ids:
                try:
                    self.destroy_workspace(session_id)
                except Exception as e:
                    logger.error(f"Error cleaning up session {session_id}: {e}")
        
        # Clean up cloner resources
        self._cloner.cleanup_all()
        
        logger.info("Workspace lifecycle manager shutdown complete")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about workspace lifecycle management.
        
        Returns:
            Dictionary containing statistics
        """
        with self._lock:
            active_sessions = len(self._sessions)
            suspended_sessions = sum(1 for s in self._sessions.values() 
                                   if s.workspace.status == WorkspaceStatus.SUSPENDED)
            
            # Calculate average session age
            current_time = datetime.now()
            total_age = sum((current_time - s.created_at).total_seconds() 
                          for s in self._sessions.values())
            avg_age_seconds = total_age / active_sessions if active_sessions > 0 else 0
            
            return {
                "active_sessions": active_sessions,
                "suspended_sessions": suspended_sessions,
                "max_concurrent": self._max_concurrent,
                "timeout_minutes": self._timeout_minutes,
                "average_session_age_seconds": avg_age_seconds,
                "monitoring_active": self._monitoring_thread.is_alive() if self._monitoring_thread else False
            }