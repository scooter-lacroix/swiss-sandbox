"""
Concrete implementation of workspace cloning functionality.
"""

import os
import shutil
import subprocess
import tempfile
import uuid
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from .interfaces import WorkspaceClonerInterface
from .models import SandboxWorkspace, IsolationConfig
from .security import SandboxSecurityManager, SecurityPolicy
from ..types import WorkspaceStatus

logger = logging.getLogger(__name__)


class WorkspaceCloner(WorkspaceClonerInterface):
    """
    Concrete implementation of workspace cloning with Docker isolation support.
    
    This class handles:
    - Complete filesystem cloning with proper permissions
    - Git history preservation
    - Docker container setup for isolation
    - Resource limit enforcement
    - Cleanup and lifecycle management
    """
    
    def __init__(self, security_policy: Optional[SecurityPolicy] = None):
        self._active_containers: Dict[str, str] = {}  # workspace_id -> container_id
        self._temp_directories: List[str] = []  # Track temp dirs for cleanup
        self._security_manager = SandboxSecurityManager(security_policy)
    
    def clone_workspace(self, source_path: str, sandbox_id: str = None,
                       isolation_config: Optional[IsolationConfig] = None) -> SandboxWorkspace:
        """Create an isolated copy of the host workspace."""
        if sandbox_id is None:
            sandbox_id = str(uuid.uuid4())
            
        if isolation_config is None:
            isolation_config = IsolationConfig()
        
        # Validate source path
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source path does not exist: {source_path}")
        
        if not os.path.isdir(source_path):
            raise ValueError(f"Source path is not a directory: {source_path}")
        
        # Create sandbox directory
        sandbox_base = os.path.join(tempfile.gettempdir(), "intelligent_sandbox")
        os.makedirs(sandbox_base, exist_ok=True)
        sandbox_path = os.path.join(sandbox_base, f"workspace_{sandbox_id}")
        
        try:
            # Create the workspace object first
            workspace = SandboxWorkspace(
                id=sandbox_id,
                source_path=os.path.abspath(source_path),
                sandbox_path=os.path.abspath(sandbox_path),
                isolation_config=isolation_config,
                created_at=None,  # Will be set in __post_init__
                status=WorkspaceStatus.CREATING
            )
            
            # Perform the actual cloning
            self._clone_filesystem(workspace)
            
            # Preserve git history if requested and available
            if self._has_git_repository(workspace.source_path):
                self.preserve_git_history(workspace)
            
            # Set up security for the workspace
            if not self._security_manager.setup_workspace_security(workspace):
                logger.warning(f"Failed to set up security for workspace {sandbox_id}")
            
            logger.info(f"Successfully cloned workspace {sandbox_id} from {source_path} to {sandbox_path}")
            return workspace
            
        except Exception as e:
            # Cleanup on failure
            if os.path.exists(sandbox_path):
                shutil.rmtree(sandbox_path, ignore_errors=True)
            logger.error(f"Failed to clone workspace: {e}")
            raise
    
    def _clone_filesystem(self, workspace: SandboxWorkspace) -> None:
        """Clone the filesystem with proper permissions and exclusions."""
        source_path = workspace.source_path
        sandbox_path = workspace.sandbox_path
        
        # Define patterns to exclude from cloning
        exclude_patterns = [
            '.git/objects',  # We'll handle git separately
            '__pycache__',
            '*.pyc',
            '.pytest_cache',
            'node_modules',
            '.venv',
            'venv',
            '.env',
            '.DS_Store',
            'Thumbs.db',
            '*.log',
            'tmp',
            'temp'
        ]
        
        try:
            # Use rsync for efficient copying with exclusions if available
            if shutil.which('rsync'):
                self._rsync_clone(source_path, sandbox_path, exclude_patterns)
            else:
                # Fallback to Python-based copying
                self._python_clone(source_path, sandbox_path, exclude_patterns)
                
        except Exception as e:
            logger.error(f"Filesystem cloning failed: {e}")
            raise
    
    def _rsync_clone(self, source_path: str, sandbox_path: str, exclude_patterns: List[str]) -> None:
        """Use rsync for efficient cloning."""
        rsync_cmd = ['rsync', '-av', '--progress']
        
        # Add exclusion patterns
        for pattern in exclude_patterns:
            rsync_cmd.extend(['--exclude', pattern])
        
        # Add source and destination
        rsync_cmd.extend([f"{source_path}/", sandbox_path])
        
        result = subprocess.run(rsync_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"rsync failed: {result.stderr}")
    
    def _python_clone(self, source_path: str, sandbox_path: str, exclude_patterns: List[str]) -> None:
        """Python-based filesystem cloning as fallback."""
        def should_exclude(path: str) -> bool:
            """Check if a path should be excluded based on patterns."""
            path_name = os.path.basename(path)
            for pattern in exclude_patterns:
                if pattern.startswith('*'):
                    if path_name.endswith(pattern[1:]):
                        return True
                elif pattern in path:
                    return True
            return False
        
        def copy_tree(src: str, dst: str) -> None:
            """Recursively copy directory tree with exclusions."""
            if should_exclude(src):
                return
            
            if os.path.isdir(src):
                os.makedirs(dst, exist_ok=True)
                for item in os.listdir(src):
                    src_item = os.path.join(src, item)
                    dst_item = os.path.join(dst, item)
                    copy_tree(src_item, dst_item)
            else:
                shutil.copy2(src, dst)
        
        copy_tree(source_path, sandbox_path)
    
    def _has_git_repository(self, path: str) -> bool:
        """Check if the path contains a git repository."""
        return os.path.exists(os.path.join(path, '.git'))
    
    def preserve_git_history(self, workspace: SandboxWorkspace) -> bool:
        """Preserve git history in the cloned workspace."""
        source_git = os.path.join(workspace.source_path, '.git')
        sandbox_git = os.path.join(workspace.sandbox_path, '.git')
        
        if not os.path.exists(source_git):
            logger.warning(f"No git repository found in source: {workspace.source_path}")
            return False
        
        try:
            # Copy the entire .git directory
            if os.path.exists(sandbox_git):
                shutil.rmtree(sandbox_git)
            
            shutil.copytree(source_git, sandbox_git)
            
            # Reset the working directory to match the current state
            result = subprocess.run(
                ['git', 'reset', '--hard', 'HEAD'],
                cwd=workspace.sandbox_path,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.warning(f"Git reset failed: {result.stderr}")
                return False
            
            logger.info(f"Git history preserved for workspace {workspace.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to preserve git history: {e}")
            return False
    
    def setup_isolation(self, workspace: SandboxWorkspace) -> bool:
        """Set up Docker isolation for the workspace."""
        if not workspace.isolation_config.use_docker:
            # No Docker isolation requested
            workspace.status = WorkspaceStatus.ACTIVE
            return True
        
        try:
            # Check if Docker is available
            if not self._is_docker_available():
                logger.warning("Docker not available, skipping isolation setup")
                workspace.status = WorkspaceStatus.ACTIVE
                return True
            
            # Create and start Docker container
            container_id = self._create_docker_container(workspace)
            if container_id:
                self._active_containers[workspace.id] = container_id
                workspace.status = WorkspaceStatus.ACTIVE
                workspace.metadata['container_id'] = container_id
                logger.info(f"Docker isolation set up for workspace {workspace.id}, container: {container_id}")
                return True
            else:
                logger.error(f"Failed to create Docker container for workspace {workspace.id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to setup isolation: {e}")
            return False
    
    def _is_docker_available(self) -> bool:
        """Check if Docker is available and running."""
        try:
            result = subprocess.run(['docker', 'version'], capture_output=True, text=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def _create_docker_container(self, workspace: SandboxWorkspace) -> Optional[str]:
        """Create a Docker container for the workspace."""
        config = workspace.isolation_config
        
        # Build Docker run command
        docker_cmd = [
            'docker', 'run', '-d',
            '--name', f"sandbox_{workspace.id}",
            '--workdir', '/workspace',
            '-v', f"{workspace.sandbox_path}:/workspace",
        ]
        
        # Add resource limits
        if config.cpu_limit:
            docker_cmd.extend(['--cpus', config.cpu_limit])
        if config.memory_limit:
            docker_cmd.extend(['--memory', config.memory_limit])
        
        # Add network isolation
        if config.network_isolation:
            if config.allowed_hosts:
                # TODO: Implement custom network with allowed hosts
                docker_cmd.extend(['--network', 'bridge'])
            else:
                docker_cmd.extend(['--network', 'none'])
        
        # Add environment variables
        for key, value in config.environment_vars.items():
            docker_cmd.extend(['-e', f"{key}={value}"])
        
        # Add mount points
        for host_path, container_path in config.mount_points.items():
            docker_cmd.extend(['-v', f"{host_path}:{container_path}"])
        
        # Add the container image and command
        docker_cmd.extend([config.container_image, 'sleep', 'infinity'])
        
        try:
            result = subprocess.run(docker_cmd, capture_output=True, text=True)
            if result.returncode == 0:
                container_id = result.stdout.strip()
                logger.info(f"Created Docker container {container_id} for workspace {workspace.id}")
                return container_id
            else:
                logger.error(f"Docker container creation failed: {result.stderr}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to create Docker container: {e}")
            return None
    
    def cleanup_workspace(self, workspace: SandboxWorkspace) -> bool:
        """Clean up and destroy the sandbox workspace."""
        success = True
        
        try:
            # Stop and remove Docker container if it exists
            if workspace.id in self._active_containers:
                container_id = self._active_containers[workspace.id]
                if self._cleanup_docker_container(container_id):
                    del self._active_containers[workspace.id]
                else:
                    success = False
            
            # Remove the sandbox directory
            if os.path.exists(workspace.sandbox_path):
                shutil.rmtree(workspace.sandbox_path, ignore_errors=True)
                if os.path.exists(workspace.sandbox_path):
                    logger.warning(f"Failed to completely remove sandbox directory: {workspace.sandbox_path}")
                    success = False
            
            workspace.status = WorkspaceStatus.DESTROYED
            logger.info(f"Cleaned up workspace {workspace.id}")
            
        except Exception as e:
            logger.error(f"Failed to cleanup workspace {workspace.id}: {e}")
            success = False
        
        return success
    
    def _cleanup_docker_container(self, container_id: str) -> bool:
        """Stop and remove a Docker container."""
        try:
            # Stop the container
            subprocess.run(['docker', 'stop', container_id], capture_output=True)
            
            # Remove the container
            result = subprocess.run(['docker', 'rm', container_id], capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"Removed Docker container {container_id}")
                return True
            else:
                logger.error(f"Failed to remove Docker container {container_id}: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to cleanup Docker container {container_id}: {e}")
            return False
    
    def merge_changes_back(self, workspace: SandboxWorkspace, target_path: str) -> bool:
        """Merge changes from sandbox back to the original workspace."""
        if not os.path.exists(workspace.sandbox_path):
            logger.error(f"Sandbox path does not exist: {workspace.sandbox_path}")
            return False
        
        if not os.path.exists(target_path):
            logger.error(f"Target path does not exist: {target_path}")
            return False
        
        try:
            # Use rsync for efficient merging if available
            if shutil.which('rsync'):
                rsync_cmd = [
                    'rsync', '-av', '--progress',
                    '--exclude', '.git',  # Don't merge git changes
                    f"{workspace.sandbox_path}/",
                    target_path
                ]
                
                result = subprocess.run(rsync_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.error(f"rsync merge failed: {result.stderr}")
                    return False
            else:
                # Python-based merging
                self._python_merge(workspace.sandbox_path, target_path)
            
            logger.info(f"Successfully merged changes from workspace {workspace.id} to {target_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to merge changes: {e}")
            return False
    
    def _python_merge(self, source_path: str, target_path: str) -> None:
        """Python-based file merging."""
        def merge_tree(src: str, dst: str) -> None:
            """Recursively merge directory tree."""
            if os.path.isdir(src):
                os.makedirs(dst, exist_ok=True)
                for item in os.listdir(src):
                    if item == '.git':  # Skip git directory
                        continue
                    src_item = os.path.join(src, item)
                    dst_item = os.path.join(dst, item)
                    merge_tree(src_item, dst_item)
            else:
                shutil.copy2(src, dst)
        
        merge_tree(source_path, target_path)
    
    def get_active_workspaces(self) -> Dict[str, str]:
        """Get a dictionary of active workspace IDs and their container IDs."""
        return self._active_containers.copy()
    
    def cleanup_all(self) -> None:
        """Clean up all active containers and temporary directories."""
        # Clean up Docker containers
        for workspace_id, container_id in list(self._active_containers.items()):
            self._cleanup_docker_container(container_id)
            del self._active_containers[workspace_id]
        
        # Clean up temporary directories
        for temp_dir in self._temp_directories:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
        
        self._temp_directories.clear()
        logger.info("Cleaned up all workspace resources")
    
    def validate_operation(self, operation_type: str, details: Dict[str, Any], 
                          workspace: SandboxWorkspace) -> bool:
        """
        Validate an operation against security policies.
        
        Args:
            operation_type: Type of operation (file, command, network)
            details: Operation details
            workspace: The workspace context
            
        Returns:
            True if the operation is allowed
        """
        return self._security_manager.validate_operation(operation_type, details, workspace)
    
    def get_security_status(self, workspace: SandboxWorkspace) -> Dict[str, Any]:
        """
        Get security status for a workspace.
        
        Args:
            workspace: The workspace to check
            
        Returns:
            Dictionary containing security status information
        """
        return self._security_manager.get_security_status(workspace)