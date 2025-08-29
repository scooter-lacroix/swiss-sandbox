"""
Workspace Manager for the Swiss Sandbox core system.

This module provides workspace management and isolation capabilities,
integrating with the existing intelligent workspace system while providing
a simplified interface for the core execution engine.

Requirements: 6.1, 6.2, 5.2
"""

import os
import tempfile
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime

from .types import ExecutionContext, ResourceLimits, SecurityLevel
from ..intelligent.workspace.lifecycle import WorkspaceLifecycleManager, WorkspaceSession
from ..intelligent.workspace.models import IsolationConfig, SandboxWorkspace
from ..intelligent.workspace.security import SecurityPolicy
from ..intelligent.types import WorkspaceStatus

logger = logging.getLogger(__name__)


@dataclass
class WorkspaceConfig:
    """Configuration for workspace creation."""
    workspace_id: str
    use_isolation: bool = True
    use_docker: bool = False
    container_image: str = "python:3.11-slim"
    cpu_limit: Optional[str] = "1.0"
    memory_limit: Optional[str] = "512M"
    disk_limit: Optional[str] = "1G"
    network_isolation: bool = True
    environment_vars: Dict[str, str] = field(default_factory=dict)
    mount_points: Dict[str, str] = field(default_factory=dict)
    cleanup_on_exit: bool = True


@dataclass
class Workspace:
    """Represents a managed workspace."""
    workspace_id: str
    workspace_path: Path
    source_path: Optional[Path] = None
    config: Optional[WorkspaceConfig] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_isolated: bool = False
    session: Optional[WorkspaceSession] = None
    
    def update_access(self):
        """Update the last accessed time."""
        self.last_accessed = datetime.now()
        if self.session:
            self.session.update_access()


class WorkspaceManager:
    """
    Manages workspace creation, isolation, and cleanup for the Swiss Sandbox.
    
    This class provides a simplified interface for workspace management while
    leveraging the existing intelligent workspace system for advanced features.
    """
    
    def __init__(self, 
                 base_workspace_dir: Optional[str] = None,
                 enable_intelligent_features: bool = True,
                 max_concurrent_workspaces: int = 10):
        """
        Initialize the workspace manager.
        
        Args:
            base_workspace_dir: Base directory for workspaces (default: temp dir)
            enable_intelligent_features: Enable intelligent workspace features
            max_concurrent_workspaces: Maximum concurrent workspaces
        """
        # Set up base workspace directory
        if base_workspace_dir:
            self.base_workspace_dir = Path(base_workspace_dir)
        else:
            self.base_workspace_dir = Path.home() / ".swiss_sandbox" / "workspaces"

        self.base_workspace_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize workspace tracking
        self._workspaces: Dict[str, Workspace] = {}
        self._max_concurrent = max_concurrent_workspaces
        
        # Initialize intelligent workspace manager if enabled
        self._intelligent_enabled = enable_intelligent_features
        self._lifecycle_manager: Optional[WorkspaceLifecycleManager] = None
        
        if self._intelligent_enabled:
            try:
                security_policy = SecurityPolicy()
                self._lifecycle_manager = WorkspaceLifecycleManager(
                    security_policy=security_policy,
                    max_concurrent_workspaces=max_concurrent_workspaces,
                    workspace_timeout_minutes=60
                )
                logger.info("Intelligent workspace features enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize intelligent features: {e}")
                self._intelligent_enabled = False
        
        logger.info(f"WorkspaceManager initialized with base dir: {self.base_workspace_dir}")
    
    def create_workspace(self, 
                        workspace_id: str,
                        source_path: Optional[str] = None,
                        config: Optional[WorkspaceConfig] = None) -> Workspace:
        """
        Create a new workspace.
        
        Args:
            workspace_id: Unique identifier for the workspace
            source_path: Optional source path to clone from
            config: Workspace configuration
            
        Returns:
            Workspace object
            
        Raises:
            ValueError: If workspace ID already exists
            RuntimeError: If maximum concurrent workspaces exceeded
        """
        if workspace_id in self._workspaces:
            raise ValueError(f"Workspace ID already exists: {workspace_id}")
        
        if len(self._workspaces) >= self._max_concurrent:
            self._cleanup_expired_workspaces()
            if len(self._workspaces) >= self._max_concurrent:
                raise RuntimeError(f"Maximum concurrent workspaces ({self._max_concurrent}) exceeded")
        
        # Use provided config or create default
        if config is None:
            config = WorkspaceConfig(workspace_id=workspace_id)
        
        try:
            # Create workspace using intelligent features if available and isolation is requested
            if self._intelligent_enabled and config.use_isolation and self._lifecycle_manager:
                workspace = self._create_intelligent_workspace(workspace_id, source_path, config)
            else:
                workspace = self._create_simple_workspace(workspace_id, source_path, config)
            
            self._workspaces[workspace_id] = workspace
            logger.info(f"Created workspace: {workspace_id}")
            return workspace
            
        except Exception as e:
            logger.error(f"Failed to create workspace {workspace_id}: {e}")
            raise
    
    def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        """
        Get a workspace by ID.
        
        Args:
            workspace_id: The workspace ID
            
        Returns:
            Workspace object if found, None otherwise
        """
        workspace = self._workspaces.get(workspace_id)
        if workspace:
            workspace.update_access()
        return workspace
    
    def list_workspaces(self) -> List[Workspace]:
        """
        List all active workspaces.
        
        Returns:
            List of Workspace objects
        """
        return list(self._workspaces.values())
    
    def get_workspace_path(self, workspace_id: str) -> Optional[Path]:
        """
        Get the filesystem path for a workspace.
        
        Args:
            workspace_id: The workspace ID
            
        Returns:
            Path to the workspace directory, or None if not found
        """
        workspace = self.get_workspace(workspace_id)
        return workspace.workspace_path if workspace else None
    
    def setup_environment(self, workspace_id: str, 
                         environment_vars: Optional[Dict[str, str]] = None,
                         python_path: Optional[List[str]] = None) -> bool:
        """
        Set up the environment for a workspace.
        
        Args:
            workspace_id: The workspace ID
            environment_vars: Environment variables to set
            python_path: Additional Python paths
            
        Returns:
            True if setup was successful
        """
        workspace = self.get_workspace(workspace_id)
        if not workspace:
            logger.error(f"Workspace not found: {workspace_id}")
            return False
        
        try:
            # Set up environment variables
            if environment_vars:
                workspace.metadata.setdefault('environment_vars', {}).update(environment_vars)
            
            # Set up Python path
            if python_path:
                workspace.metadata.setdefault('python_path', []).extend(python_path)
            
            # Create virtual environment if requested
            if workspace.config and workspace.config.use_isolation:
                venv_path = workspace.workspace_path / ".venv"
                if not venv_path.exists():
                    self._create_virtual_environment(workspace.workspace_path)
            
            logger.info(f"Environment setup completed for workspace: {workspace_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup environment for workspace {workspace_id}: {e}")
            return False
    
    def cleanup_workspace(self, workspace_id: str) -> bool:
        """
        Clean up and remove a workspace.
        
        Args:
            workspace_id: The workspace ID to clean up
            
        Returns:
            True if cleanup was successful
        """
        workspace = self._workspaces.get(workspace_id)
        if not workspace:
            logger.warning(f"Workspace not found for cleanup: {workspace_id}")
            return False
        
        try:
            # Clean up intelligent workspace if applicable
            if workspace.session and self._lifecycle_manager:
                self._lifecycle_manager.destroy_workspace(workspace_id)
            else:
                # Clean up simple workspace
                if workspace.workspace_path.exists():
                    shutil.rmtree(workspace.workspace_path, ignore_errors=True)
            
            # Remove from tracking
            del self._workspaces[workspace_id]
            
            logger.info(f"Cleaned up workspace: {workspace_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cleanup workspace {workspace_id}: {e}")
            return False
    
    def get_workspace_status(self, workspace_id: str) -> Dict[str, Any]:
        """
        Get comprehensive status information for a workspace.
        
        Args:
            workspace_id: The workspace ID
            
        Returns:
            Dictionary containing status information
        """
        workspace = self._workspaces.get(workspace_id)
        if not workspace:
            return {"error": "Workspace not found"}
        
        status = {
            "workspace_id": workspace_id,
            "workspace_path": str(workspace.workspace_path),
            "source_path": str(workspace.source_path) if workspace.source_path else None,
            "created_at": workspace.created_at.isoformat(),
            "last_accessed": workspace.last_accessed.isoformat(),
            "is_isolated": workspace.is_isolated,
            "metadata": workspace.metadata
        }
        
        # Add intelligent workspace status if available
        if workspace.session and self._lifecycle_manager:
            intelligent_status = self._lifecycle_manager.get_workspace_status(workspace_id)
            status.update(intelligent_status)
        
        return status
    
    def create_execution_context(self, workspace_id: str,
                               resource_limits: Optional[ResourceLimits] = None,
                               security_level: SecurityLevel = SecurityLevel.MODERATE) -> Optional[ExecutionContext]:
        """
        Create an execution context for a workspace.
        
        Args:
            workspace_id: The workspace ID
            resource_limits: Resource limits for execution
            security_level: Security level for execution
            
        Returns:
            ExecutionContext object, or None if workspace not found
        """
        workspace = self.get_workspace(workspace_id)
        if not workspace:
            return None
        
        # Use provided resource limits or create defaults
        if resource_limits is None:
            resource_limits = ResourceLimits()
        
        # Get environment variables from workspace
        env_vars = workspace.metadata.get('environment_vars', {})
        
        # Add workspace path to environment variables so execution can use it
        env_vars['WORKSPACE_PATH'] = str(workspace.workspace_path)
        
        # Create artifacts directory
        artifacts_dir = workspace.workspace_path / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)
        
        return ExecutionContext(
            workspace_id=workspace_id,
            environment_vars=env_vars,
            resource_limits=resource_limits,
            security_level=security_level,
            artifacts_dir=artifacts_dir
        )
    
    def shutdown(self):
        """
        Shutdown the workspace manager and clean up all resources.
        """
        logger.info("Shutting down workspace manager")
        
        # Clean up all workspaces
        workspace_ids = list(self._workspaces.keys())
        for workspace_id in workspace_ids:
            try:
                self.cleanup_workspace(workspace_id)
            except Exception as e:
                logger.error(f"Error cleaning up workspace {workspace_id}: {e}")
        
        # Shutdown intelligent workspace manager
        if self._lifecycle_manager:
            self._lifecycle_manager.shutdown()
        
        logger.info("Workspace manager shutdown complete")
    
    # Private helper methods
    
    def _create_intelligent_workspace(self, workspace_id: str, 
                                    source_path: Optional[str],
                                    config: WorkspaceConfig) -> Workspace:
        """Create a workspace using intelligent features."""
        # Create isolation config
        isolation_config = IsolationConfig(
            use_docker=config.use_docker,
            container_image=config.container_image,
            cpu_limit=config.cpu_limit,
            memory_limit=config.memory_limit,
            disk_limit=config.disk_limit,
            network_isolation=config.network_isolation,
            environment_vars=config.environment_vars,
            mount_points=config.mount_points
        )
        
        # Use current directory as source if not provided
        if source_path is None:
            source_path = str(Path.cwd())
        
        # Create workspace session
        if self._lifecycle_manager is None:
            raise RuntimeError("Lifecycle manager not available for intelligent workspace creation")
        session = self._lifecycle_manager.create_workspace(
            source_path=source_path,
            session_id=workspace_id,
            isolation_config=isolation_config,
            metadata={"created_by": "core_workspace_manager"}
        )
        
        return Workspace(
            workspace_id=workspace_id,
            workspace_path=Path(session.workspace.sandbox_path),
            source_path=Path(source_path) if source_path else None,
            config=config,
            is_isolated=True,
            session=session,
            metadata={"intelligent_workspace": True}
        )
    
    def _create_simple_workspace(self, workspace_id: str,
                                source_path: Optional[str],
                                config: WorkspaceConfig) -> Workspace:
        """Create a simple workspace without intelligent features."""
        # Create workspace directory
        workspace_path = self.base_workspace_dir / workspace_id
        workspace_path.mkdir(parents=True, exist_ok=True)
        
        # Copy source files if provided
        if source_path and Path(source_path).exists():
            source_path_obj = Path(source_path)
            if source_path_obj.is_file():
                shutil.copy2(source_path_obj, workspace_path)
            else:
                # Copy directory contents
                for item in source_path_obj.iterdir():
                    if item.is_file():
                        shutil.copy2(item, workspace_path)
                    elif item.is_dir() and not item.name.startswith('.'):
                        shutil.copytree(item, workspace_path / item.name, dirs_exist_ok=True)
        
        return Workspace(
            workspace_id=workspace_id,
            workspace_path=workspace_path,
            source_path=Path(source_path) if source_path else None,
            config=config,
            is_isolated=False,
            metadata={"simple_workspace": True}
        )
    
    def _create_virtual_environment(self, workspace_path: Path) -> bool:
        """Create a virtual environment in the workspace."""
        try:
            import subprocess
            import sys
            
            venv_path = workspace_path / ".venv"
            
            # Create virtual environment
            result = subprocess.run([
                sys.executable, "-m", "venv", str(venv_path)
            ], capture_output=True, text=True, cwd=workspace_path)
            
            if result.returncode == 0:
                logger.info(f"Created virtual environment at {venv_path}")
                return True
            else:
                logger.error(f"Failed to create virtual environment: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error creating virtual environment: {e}")
            return False
    
    def _cleanup_expired_workspaces(self):
        """Clean up expired workspaces to free up slots."""
        # For now, just clean up the oldest workspaces if we're at capacity
        # In the future, this could be based on last access time
        if len(self._workspaces) >= self._max_concurrent:
            # Sort by creation time and remove oldest
            sorted_workspaces = sorted(
                self._workspaces.items(),
                key=lambda x: x[1].created_at
            )
            
            # Remove oldest workspace
            oldest_id = sorted_workspaces[0][0]
            logger.info(f"Cleaning up oldest workspace to free capacity: {oldest_id}")
            self.cleanup_workspace(oldest_id)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about workspace management.
        
        Returns:
            Dictionary containing statistics
        """
        stats = {
            "active_workspaces": len(self._workspaces),
            "max_concurrent": self._max_concurrent,
            "intelligent_features_enabled": self._intelligent_enabled,
            "base_workspace_dir": str(self.base_workspace_dir)
        }
        
        # Add intelligent workspace statistics if available
        if self._lifecycle_manager:
            intelligent_stats = self._lifecycle_manager.get_statistics()
            stats["intelligent_stats"] = intelligent_stats
        
        return stats