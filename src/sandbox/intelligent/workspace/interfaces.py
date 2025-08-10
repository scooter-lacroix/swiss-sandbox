"""
Abstract interfaces for workspace management components.
"""

from abc import ABC, abstractmethod
from typing import Optional
from .models import SandboxWorkspace, IsolationConfig


class WorkspaceClonerInterface(ABC):
    """Abstract interface for workspace cloning operations."""
    
    @abstractmethod
    def clone_workspace(self, source_path: str, sandbox_id: str, 
                       isolation_config: Optional[IsolationConfig] = None) -> SandboxWorkspace:
        """
        Create an isolated copy of the host workspace.
        
        Args:
            source_path: Path to the source workspace
            sandbox_id: Unique identifier for the sandbox
            isolation_config: Configuration for isolation settings
            
        Returns:
            SandboxWorkspace instance representing the cloned workspace
        """
        pass
    
    @abstractmethod
    def preserve_git_history(self, workspace: SandboxWorkspace) -> bool:
        """
        Preserve git history in the cloned workspace.
        
        Args:
            workspace: The sandbox workspace to preserve git history for
            
        Returns:
            True if git history was successfully preserved
        """
        pass
    
    @abstractmethod
    def setup_isolation(self, workspace: SandboxWorkspace) -> bool:
        """
        Set up isolation for the workspace (containers, chroot, etc.).
        
        Args:
            workspace: The workspace to set up isolation for
            
        Returns:
            True if isolation was successfully set up
        """
        pass
    
    @abstractmethod
    def cleanup_workspace(self, workspace: SandboxWorkspace) -> bool:
        """
        Clean up and destroy the sandbox workspace.
        
        Args:
            workspace: The workspace to clean up
            
        Returns:
            True if cleanup was successful
        """
        pass
    
    @abstractmethod
    def merge_changes_back(self, workspace: SandboxWorkspace, 
                          target_path: str) -> bool:
        """
        Merge changes from sandbox back to the original workspace.
        
        Args:
            workspace: The sandbox workspace with changes
            target_path: Path to merge changes back to
            
        Returns:
            True if merge was successful
        """
        pass