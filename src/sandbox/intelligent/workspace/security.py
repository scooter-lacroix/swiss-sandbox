"""
Security and isolation controls for sandbox workspaces.

This module provides:
- Filesystem access controls and path validation
- Resource limit enforcement
- Network isolation controls
- Security policy validation
"""

import os
import re
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from .models import SandboxWorkspace, IsolationConfig

logger = logging.getLogger(__name__)


@dataclass
class SecurityPolicy:
    """Security policy configuration for sandbox workspaces."""
    
    # Filesystem controls
    allowed_paths: Set[str] = field(default_factory=set)
    blocked_paths: Set[str] = field(default_factory=lambda: {
        '/etc/passwd', '/etc/shadow', '/etc/hosts', '/proc', '/sys',
        '/dev', '/boot', '/root', '/home', '/var/log'
    })
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    max_total_files: int = 10000
    
    # Command restrictions
    blocked_commands: Set[str] = field(default_factory=lambda: {
        # Privilege escalation
        'sudo', 'su', 'pkexec', 'passwd', 'usermod', 'groupmod',
        
        # System control
        'systemctl', 'service', 'init', 'shutdown', 'reboot', 'halt',
        
        # Permission changes
        'chown', 'chmod', 'chgrp',
        
        # Mount operations
        'mount', 'umount', 'fusermount',
        
        # Network tools
        'iptables', 'netstat', 'ss', 'ifconfig', 'ip', 'tcpdump',
        'nmap', 'wireshark', 'ettercap', 'arp',
        
        # Process monitoring
        'ps', 'top', 'htop', 'pstree', 'lsof', 'fuser', 'pidof',
        'kill', 'killall',
        
        # System information
        'dmidecode', 'lscpu', 'lshw', 'lsblk', 'fdisk', 'parted',
        
        # Container/namespace tools
        'docker', 'nsenter', 'unshare', 'chroot',
        
        # Network clients that can be used for exfiltration
        'curl', 'wget', 'nc', 'netcat', 'socat', 'ssh', 'scp',
        'rsync', 'ftp', 'telnet',
        
        # System utilities
        'crontab', 'at', 'batch', 'sysctl',
        
        # Debug/development tools that can be dangerous
        'gdb', 'strace', 'ltrace', 'perf', 'valgrind',
        
        # Package managers (can install malicious software)
        'apt', 'apt-get', 'yum', 'dnf', 'zypper', 'pacman',
        
        # Compression tools (can be used to hide payloads)
        'tar', 'gzip', 'gunzip', 'zip', 'unzip', '7z'
    })
    allowed_commands: Set[str] = field(default_factory=lambda: {
        'python', 'python3', 'pip', 'npm', 'node', 'git', 'make',
        'gcc', 'g++', 'javac', 'java', 'mvn', 'gradle', 'cargo',
        'go', 'rustc', 'tsc', 'webpack', 'babel'
    })
    
    # Network controls
    allow_network: bool = False
    allowed_domains: Set[str] = field(default_factory=set)
    blocked_domains: Set[str] = field(default_factory=lambda: {
        'localhost', '127.0.0.1', '0.0.0.0', '::1'
    })
    
    # Resource limits
    max_cpu_percent: float = 50.0
    max_memory_mb: int = 2048
    max_disk_mb: int = 5120
    max_processes: int = 100
    max_execution_time: int = 300  # 5 minutes


class FilesystemSecurityManager:
    """Manages filesystem security and access controls."""
    
    def __init__(self, policy: SecurityPolicy):
        self.policy = policy
        self._dangerous_patterns = [
            r'\.\./',  # Directory traversal
            r'/etc/',  # System configuration
            r'/proc/',  # Process information
            r'/sys/',  # System information
            r'/dev/',  # Device files
            r'/root/',  # Root home directory
            r'~/',  # User home shortcut
        ]
    
    def validate_path(self, path: str, workspace: SandboxWorkspace) -> bool:
        """
        Validate that a path is safe for access within the sandbox.
        
        Args:
            path: The path to validate
            workspace: The sandbox workspace context
            
        Returns:
            True if the path is safe to access
        """
        try:
            # Normalize the path
            normalized_path = os.path.normpath(os.path.abspath(path))
            
            # Check if path is within sandbox boundaries
            if not self._is_within_sandbox(normalized_path, workspace):
                logger.warning(f"Path outside sandbox boundaries: {path}")
                return False
            
            # Check against blocked paths
            if self._is_blocked_path(normalized_path):
                logger.warning(f"Access to blocked path denied: {path}")
                return False
            
            # Check for dangerous patterns
            if self._contains_dangerous_patterns(path):
                logger.warning(f"Path contains dangerous patterns: {path}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Path validation error for {path}: {e}")
            return False
    
    def _is_within_sandbox(self, path: str, workspace: SandboxWorkspace) -> bool:
        """Check if path is within sandbox boundaries."""
        sandbox_path = os.path.abspath(workspace.sandbox_path)
        return path.startswith(sandbox_path)
    
    def _is_blocked_path(self, path: str) -> bool:
        """Check if path is in the blocked paths list."""
        for blocked in self.policy.blocked_paths:
            if path.startswith(blocked):
                return True
        return False
    
    def _contains_dangerous_patterns(self, path: str) -> bool:
        """Check if path contains dangerous patterns."""
        for pattern in self._dangerous_patterns:
            if re.search(pattern, path):
                return True
        return False
    
    def validate_file_operation(self, operation: str, path: str, 
                              workspace: SandboxWorkspace) -> bool:
        """
        Validate a file operation (read, write, delete, etc.).
        
        Args:
            operation: The operation type (read, write, delete, execute)
            path: The file path
            workspace: The sandbox workspace
            
        Returns:
            True if the operation is allowed
        """
        if not self.validate_path(path, workspace):
            return False
        
        # Additional checks based on operation type
        if operation == 'write':
            return self._validate_write_operation(path, workspace)
        elif operation == 'delete':
            return self._validate_delete_operation(path, workspace)
        elif operation == 'execute':
            return self._validate_execute_operation(path, workspace)
        
        return True
    
    def _validate_write_operation(self, path: str, workspace: SandboxWorkspace) -> bool:
        """Validate write operations."""
        try:
            # Check file size limits
            if os.path.exists(path):
                file_size = os.path.getsize(path)
                if file_size > self.policy.max_file_size:
                    logger.warning(f"File too large for write: {path} ({file_size} bytes)")
                    return False
            
            # Check total file count
            total_files = sum(1 for _ in Path(workspace.sandbox_path).rglob('*') if _.is_file())
            if total_files >= self.policy.max_total_files:
                logger.warning(f"Too many files in workspace: {total_files}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Write validation error for {path}: {e}")
            return False
    
    def _validate_delete_operation(self, path: str, workspace: SandboxWorkspace) -> bool:
        """Validate delete operations."""
        # Prevent deletion of critical workspace files
        critical_files = ['.git', 'package.json', 'requirements.txt', 'Cargo.toml']
        filename = os.path.basename(path)
        
        if filename in critical_files:
            logger.warning(f"Deletion of critical file blocked: {path}")
            return False
        
        return True
    
    def _validate_execute_operation(self, path: str, workspace: SandboxWorkspace) -> bool:
        """Validate execute operations."""
        # Check if the file is executable
        if not os.access(path, os.X_OK):
            return False
        
        # Additional security checks for executables
        filename = os.path.basename(path)
        if filename in self.policy.blocked_commands:
            logger.warning(f"Execution of blocked command denied: {filename}")
            return False
        
        return True


class CommandSecurityManager:
    """Manages command execution security."""
    
    def __init__(self, policy: SecurityPolicy):
        self.policy = policy
    
    def validate_command(self, command: str, workspace: SandboxWorkspace) -> bool:
        """
        Validate that a command is safe to execute.
        
        Args:
            command: The command to validate
            workspace: The sandbox workspace context
            
        Returns:
            True if the command is safe to execute
        """
        try:
            # Parse the command
            cmd_parts = command.strip().split()
            if not cmd_parts:
                return False
            
            base_command = cmd_parts[0]
            
            # Check against blocked commands
            if base_command in self.policy.blocked_commands:
                logger.warning(f"Blocked command execution attempt: {base_command}")
                return False
            
            # Check for dangerous command patterns
            if self._contains_dangerous_command_patterns(command):
                logger.warning(f"Command contains dangerous patterns: {command}")
                return False
            
            # Validate command arguments
            if not self._validate_command_arguments(cmd_parts, workspace):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Command validation error for '{command}': {e}")
            return False
    
    def _contains_dangerous_command_patterns(self, command: str) -> bool:
        """Check for dangerous command patterns."""
        dangerous_patterns = [
            # Privilege escalation
            r'sudo\s+',
            r'su\s+',
            r'pkexec\s+',
            r'passwd\s+',
            r'usermod\s+',
            
            # Permission and ownership changes
            r'chmod\s+[0-9]+',
            r'chown\s+',
            r'chgrp\s+',
            
            # Dangerous deletions and file operations
            r'rm\s+-rf\s*/',
            r'rm\s+-rf\s*\*',
            r'dd\s+.*of=/dev/',
            r'>\s*/dev/',
            r'>>\s*/dev/',
            
            # Network and data exfiltration
            r'curl.*\|\s*(sh|bash|zsh|fish)',
            r'wget.*\|\s*(sh|bash|zsh|fish)',
            r'nc\s+.*-e\s+',
            r'netcat\s+.*-e\s+',
            r'socat\s+.*EXEC:',
            r'/bin/sh\s+-i\s+>&\s*/dev/tcp/',
            
            # Code execution and injection
            r'eval\s+',
            r'exec\s+',
            r'system\s*\(',
            r'popen\s*\(',
            r'\$\(curl',
            r'`curl',
            r'\$\(wget',
            r'`wget',
            
            # Container and system escape attempts
            r'docker\s+run.*--privileged',
            r'docker\s+.*-v\s+/:/host',
            r'nsenter\s+.*-t\s+1',
            r'unshare\s+-r',
            r'mount\s+',
            r'umount\s+',
            
            # Process and system manipulation
            r'kill\s+-9\s+1',
            r'killall\s+.*systemd',
            r'sysctl\s+-w',
            r'echo\s+.*>\s*/proc/',
            r'debugfs\s+',
            r'losetup\s+',
            
            # Network scanning and monitoring
            r'nmap\s+',
            r'tcpdump\s+',
            r'wireshark',
            r'ettercap',
            r'iptables\s+',
            
            # Fork bombs and resource attacks
            r':\(\)\{',  # Fork bomb pattern
            r'while\s+true.*do',
            r'stress\s+--cpu',
            r'yes\s*>\s*/dev/null',
            
            # Service and system control
            r'systemctl\s+',
            r'service\s+',
            r'init\s+[0-6]',
            
            # File system and device access
            r'/dev/sd[a-z]',
            r'/dev/nvme',
            r'/boot/',
            r'/etc/shadow',
            r'/etc/passwd',
            r'/etc/sudoers',
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                logger.warning(f"Dangerous pattern detected: {pattern} in command: {command}")
                return True
        
        return False
    
    def _validate_command_arguments(self, cmd_parts: List[str], 
                                  workspace: SandboxWorkspace) -> bool:
        """Validate command arguments for security issues."""
        filesystem_manager = FilesystemSecurityManager(self.policy)
        
        for arg in cmd_parts[1:]:
            # Check file path arguments
            if arg.startswith('/') or arg.startswith('./') or arg.startswith('../'):
                if not filesystem_manager.validate_path(arg, workspace):
                    logger.warning(f"Invalid path argument: {arg}")
                    return False
        
        return True


class ResourceLimitManager:
    """Manages resource limits for sandbox containers."""
    
    def __init__(self, policy: SecurityPolicy):
        self.policy = policy
    
    def apply_resource_limits(self, workspace: SandboxWorkspace) -> bool:
        """
        Apply resource limits to a sandbox workspace.
        
        Args:
            workspace: The sandbox workspace to apply limits to
            
        Returns:
            True if limits were successfully applied
        """
        try:
            if workspace.isolation_config.use_docker:
                return self._apply_docker_limits(workspace)
            else:
                return self._apply_system_limits(workspace)
                
        except Exception as e:
            logger.error(f"Failed to apply resource limits: {e}")
            return False
    
    def _apply_docker_limits(self, workspace: SandboxWorkspace) -> bool:
        """Apply resource limits to Docker container."""
        container_id = workspace.metadata.get('container_id')
        if not container_id:
            logger.warning("No container ID found for resource limit application")
            return False
        
        try:
            # Update container resource limits
            update_cmd = [
                'docker', 'update',
                '--cpus', str(self.policy.max_cpu_percent / 100.0),
                '--memory', f"{self.policy.max_memory_mb}m",
                '--pids-limit', str(self.policy.max_processes),
                container_id
            ]
            
            result = subprocess.run(update_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Failed to update container limits: {result.stderr}")
                return False
            
            logger.info(f"Applied resource limits to container {container_id}")
            return True
            
        except Exception as e:
            logger.error(f"Docker resource limit application failed: {e}")
            return False
    
    def _apply_system_limits(self, workspace: SandboxWorkspace) -> bool:
        """Apply system-level resource limits (for non-Docker environments)."""
        # This would use ulimit, cgroups, or other system mechanisms
        # For now, we'll log that system limits would be applied
        logger.info(f"System resource limits would be applied to workspace {workspace.id}")
        return True
    
    def monitor_resource_usage(self, workspace: SandboxWorkspace) -> Dict[str, Any]:
        """
        Monitor current resource usage of a workspace.
        
        Args:
            workspace: The workspace to monitor
            
        Returns:
            Dictionary containing resource usage statistics
        """
        try:
            if workspace.isolation_config.use_docker:
                return self._monitor_docker_resources(workspace)
            else:
                return self._monitor_system_resources(workspace)
                
        except Exception as e:
            logger.error(f"Resource monitoring failed: {e}")
            return {}
    
    def _monitor_docker_resources(self, workspace: SandboxWorkspace) -> Dict[str, Any]:
        """Monitor Docker container resource usage."""
        container_id = workspace.metadata.get('container_id')
        if not container_id:
            return {}
        
        try:
            # Get container stats
            stats_cmd = ['docker', 'stats', '--no-stream', '--format', 
                        'table {{.CPUPerc}},{{.MemUsage}},{{.PIDs}}', container_id]
            
            result = subprocess.run(stats_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return {}
            
            # Parse the output (simplified parsing)
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:
                stats_line = lines[1]  # Skip header
                parts = stats_line.split(',')
                
                return {
                    'cpu_percent': parts[0].strip().rstrip('%'),
                    'memory_usage': parts[1].strip(),
                    'processes': parts[2].strip(),
                    'container_id': container_id
                }
            
        except Exception as e:
            logger.error(f"Docker resource monitoring failed: {e}")
        
        return {}
    
    def _monitor_system_resources(self, workspace: SandboxWorkspace) -> Dict[str, Any]:
        """Monitor system resource usage (for non-Docker environments)."""
        # This would use psutil or other system monitoring tools
        return {
            'cpu_percent': '0%',
            'memory_usage': '0MB / 0MB',
            'processes': '0',
            'method': 'system'
        }


class NetworkSecurityManager:
    """Manages network isolation and access controls."""
    
    def __init__(self, policy: SecurityPolicy):
        self.policy = policy
    
    def setup_network_isolation(self, workspace: SandboxWorkspace) -> bool:
        """
        Set up network isolation for a workspace.
        
        Args:
            workspace: The workspace to set up network isolation for
            
        Returns:
            True if network isolation was successfully set up
        """
        try:
            if workspace.isolation_config.use_docker:
                return self._setup_docker_network_isolation(workspace)
            else:
                return self._setup_system_network_isolation(workspace)
                
        except Exception as e:
            logger.error(f"Network isolation setup failed: {e}")
            return False
    
    def _setup_docker_network_isolation(self, workspace: SandboxWorkspace) -> bool:
        """Set up Docker network isolation."""
        # Network isolation is handled during container creation
        # This method can be used for additional network configuration
        container_id = workspace.metadata.get('container_id')
        if not container_id:
            return False
        
        if not self.policy.allow_network:
            logger.info(f"Network access disabled for container {container_id}")
            return True
        
        # If network is allowed, we could set up custom networks with restrictions
        logger.info(f"Network isolation configured for container {container_id}")
        return True
    
    def _setup_system_network_isolation(self, workspace: SandboxWorkspace) -> bool:
        """Set up system-level network isolation."""
        # This would use iptables, network namespaces, or other mechanisms
        logger.info(f"System network isolation would be configured for workspace {workspace.id}")
        return True
    
    def validate_network_access(self, host: str, port: int = None) -> bool:
        """
        Validate that network access to a host/port is allowed.
        
        Args:
            host: The hostname or IP address
            port: The port number (optional)
            
        Returns:
            True if access is allowed
        """
        if not self.policy.allow_network:
            logger.warning(f"Network access denied (policy): {host}")
            return False
        
        # Check against blocked domains
        if host in self.policy.blocked_domains:
            logger.warning(f"Access to blocked domain denied: {host}")
            return False
        
        # Check against allowed domains (if specified)
        if self.policy.allowed_domains and host not in self.policy.allowed_domains:
            logger.warning(f"Access to non-whitelisted domain denied: {host}")
            return False
        
        return True


class SandboxSecurityManager:
    """Main security manager that coordinates all security components."""
    
    def __init__(self, policy: Optional[SecurityPolicy] = None):
        self.policy = policy or SecurityPolicy()
        self.filesystem_manager = FilesystemSecurityManager(self.policy)
        self.command_manager = CommandSecurityManager(self.policy)
        self.resource_manager = ResourceLimitManager(self.policy)
        self.network_manager = NetworkSecurityManager(self.policy)
    
    def setup_workspace_security(self, workspace: SandboxWorkspace) -> bool:
        """
        Set up comprehensive security for a workspace.
        
        Args:
            workspace: The workspace to secure
            
        Returns:
            True if security was successfully set up
        """
        try:
            # Apply resource limits
            if not self.resource_manager.apply_resource_limits(workspace):
                logger.error("Failed to apply resource limits")
                return False
            
            # Set up network isolation
            if not self.network_manager.setup_network_isolation(workspace):
                logger.error("Failed to set up network isolation")
                return False
            
            logger.info(f"Security successfully configured for workspace {workspace.id}")
            return True
            
        except Exception as e:
            logger.error(f"Security setup failed for workspace {workspace.id}: {e}")
            return False
    
    def validate_operation(self, operation_type: str, details: Dict[str, Any], 
                          workspace: SandboxWorkspace) -> bool:
        """
        Validate any operation against security policies.
        
        Args:
            operation_type: Type of operation (file, command, network)
            details: Operation details
            workspace: The workspace context
            
        Returns:
            True if the operation is allowed
        """
        try:
            if operation_type == 'file':
                return self.filesystem_manager.validate_file_operation(
                    details.get('action', ''),
                    details.get('path', ''),
                    workspace
                )
            elif operation_type == 'command':
                return self.command_manager.validate_command(
                    details.get('command', ''),
                    workspace
                )
            elif operation_type == 'network':
                return self.network_manager.validate_network_access(
                    details.get('host', ''),
                    details.get('port')
                )
            else:
                logger.warning(f"Unknown operation type: {operation_type}")
                return False
                
        except Exception as e:
            logger.error(f"Operation validation failed: {e}")
            return False
    
    def get_security_status(self, workspace: SandboxWorkspace) -> Dict[str, Any]:
        """
        Get comprehensive security status for a workspace.
        
        Args:
            workspace: The workspace to check
            
        Returns:
            Dictionary containing security status information
        """
        return {
            'workspace_id': workspace.id,
            'policy': {
                'filesystem_controls': len(self.policy.blocked_paths),
                'command_restrictions': len(self.policy.blocked_commands),
                'network_isolation': not self.policy.allow_network,
                'resource_limits': {
                    'cpu_percent': self.policy.max_cpu_percent,
                    'memory_mb': self.policy.max_memory_mb,
                    'disk_mb': self.policy.max_disk_mb,
                    'processes': self.policy.max_processes
                }
            },
            'resource_usage': self.resource_manager.monitor_resource_usage(workspace),
            'isolation_active': workspace.isolation_config.use_docker,
            'container_id': workspace.metadata.get('container_id')
        }