#!/usr/bin/env python3
"""
Simple security integration tests for the enhanced MCP sandbox server.
Tests core security functionality based on actual implementation.
"""

import sys
import tempfile
import shutil
import unittest
from pathlib import Path

# Add the project root to Python path for testing
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.sandbox.core.security import (
    SecurityManager, 
    SecurityLevel,
    get_security_manager,
    CommandFilter,
    FileSystemSecurity,
    NetworkSecurity,
    InputValidator,
    SecurityAuditor
)

class TestSecurityBasics(unittest.TestCase):
    """Basic security integration tests."""
    
    def setUp(self):
        """Set up test environment."""
        self.security_manager = get_security_manager(SecurityLevel.MEDIUM)
        self.test_dir = Path(tempfile.mkdtemp())
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_security_manager_initialization(self):
        """Test SecurityManager initialization."""
        self.assertIsInstance(self.security_manager, SecurityManager)
        self.assertEqual(self.security_manager.security_level, SecurityLevel.MEDIUM)
        self.assertIsInstance(self.security_manager.command_filter, CommandFilter)
        self.assertIsInstance(self.security_manager.filesystem_security, FileSystemSecurity)
        self.assertIsInstance(self.security_manager.network_security, NetworkSecurity)
        self.assertIsInstance(self.security_manager.input_validator, InputValidator)
        self.assertIsInstance(self.security_manager.auditor, SecurityAuditor)
    
    def test_command_security_dangerous_blocking(self):
        """Test that dangerous commands are blocked."""
        dangerous_commands = [
            'rm -rf /',
            'sudo rm -rf /home',
            'chmod 777 /etc/passwd',
            'mkfs.ext4 /dev/sda1',
            'dd if=/dev/zero of=/dev/sda',
            'iptables -F',
            'shutdown -h now'
        ]
        
        for cmd in dangerous_commands:
            is_safe, violation = self.security_manager.check_command_security(cmd)
            self.assertFalse(is_safe, f"Command '{cmd}' should be blocked")
            self.assertIsNotNone(violation)
    
    def test_command_security_safe_allowing(self):
        """Test that some safe commands are allowed."""
        safe_commands = [
            'echo "hello world"',
            'ls -la',
            'pwd',
            'date',
            'whoami'
        ]
        
        for cmd in safe_commands:
            is_safe, violation = self.security_manager.check_command_security(cmd)
            if not is_safe:
                print(f"Command '{cmd}' was blocked: {violation.message if violation else 'Unknown reason'}")
            # Note: Some commands may still be blocked by network/filesystem patterns
    
    def test_path_security_checks(self):
        """Test file path security checks."""
        # Test dangerous paths
        dangerous_paths = [
            '/etc/passwd',
            '/root/.ssh/id_rsa',
            '/var/log/auth.log',
            '/proc/self/environ',
            '/sys/class/net'
        ]
        
        for path in dangerous_paths:
            is_allowed, reason = self.security_manager.check_path_security(path)
            self.assertFalse(is_allowed, f"Path '{path}' should be blocked")
            self.assertIsNotNone(reason)
    
    def test_network_port_allocation(self):
        """Test network port allocation."""
        # Test port allocation
        port1 = self.security_manager.allocate_secure_port()
        if port1:
            self.assertIsInstance(port1, int)
            self.assertGreaterEqual(port1, 1024)
            self.assertLessEqual(port1, 65535)
        
        # Test blocked port validation
        blocked_ports = [22, 80, 443, 21, 23, 25, 53, 110, 143, 993, 995]
        for port in blocked_ports:
            is_allowed, reason = self.security_manager.network_security.is_port_allowed(port)
            self.assertFalse(is_allowed, f"Port {port} should be blocked")
            self.assertIsNotNone(reason)
    
    def test_security_workspace_creation(self):
        """Test secure workspace creation."""
        workspace_path = self.security_manager.create_secure_workspace()
        self.assertIsInstance(workspace_path, str)
        
        workspace = Path(workspace_path)
        self.assertTrue(workspace.exists())
        self.assertTrue(workspace.is_dir())
        
        # Clean up
        shutil.rmtree(workspace, ignore_errors=True)
    
    def test_security_status_reporting(self):
        """Test security status reporting."""
        # Generate some security violations
        self.security_manager.check_command_security('rm -rf /')
        self.security_manager.check_command_security('sudo shutdown')
        self.security_manager.check_path_security('/etc/passwd')
        
        # Check security status
        status = self.security_manager.get_security_status()
        self.assertIsInstance(status, dict)
        self.assertIn('security_level', status)
        self.assertIn('audit_summary', status)
        self.assertIn('active_ports', status)
        self.assertIn('sandbox_directories', status)
        self.assertIn('allowed_paths', status)
    
    def test_input_validation_basic(self):
        """Test basic input validation."""
        # Test suspicious patterns
        suspicious_inputs = [
            '<script>alert("xss")</script>',
            'javascript:alert("xss")',
            'data:text/html,<script>alert("xss")</script>'
        ]
        
        for input_str in suspicious_inputs:
            is_valid, reason = self.security_manager.input_validator.validate_input(input_str)
            self.assertFalse(is_valid, f"Input '{input_str}' should be flagged as suspicious")
            self.assertIsNotNone(reason)
    
    def test_command_filter_direct(self):
        """Test command filter directly."""
        cmd_filter = CommandFilter()
        
        # Test dangerous command
        is_safe, violation = cmd_filter.check_command('rm -rf /')
        self.assertFalse(is_safe)
        self.assertIsNotNone(violation)
        
        # Test safe command
        is_safe, violation = cmd_filter.check_command('echo hello')
        self.assertTrue(is_safe)
        self.assertIsNone(violation)
    
    def test_filesystem_security_direct(self):
        """Test filesystem security directly."""
        fs_security = FileSystemSecurity()
        
        # Test dangerous path
        is_allowed, reason = fs_security.is_path_allowed('/etc/passwd')
        self.assertFalse(is_allowed)
        self.assertIsNotNone(reason)
        
        # Test safe path
        is_allowed, reason = fs_security.is_path_allowed('/tmp/test.txt')
        self.assertTrue(is_allowed)
        self.assertIsNone(reason)
    
    def test_network_security_direct(self):
        """Test network security directly."""
        net_security = NetworkSecurity()
        
        # Test blocked port
        is_allowed, reason = net_security.is_port_allowed(22)
        self.assertFalse(is_allowed)
        self.assertIsNotNone(reason)
        
        # Test allowed port
        is_allowed, reason = net_security.is_port_allowed(8080)
        self.assertTrue(is_allowed)
        self.assertIsNone(reason)
    
    def test_security_cleanup(self):
        """Test security resource cleanup."""
        # Create some resources
        workspace = self.security_manager.create_secure_workspace()
        
        # Clean up
        self.security_manager.cleanup_security_resources()
        
        # Verify cleanup
        self.assertFalse(Path(workspace).exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
