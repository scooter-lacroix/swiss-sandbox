"""
Integration tests for SecurityManager with existing types and systems.
"""

import pytest
from pathlib import Path
from src.sandbox.core.security import SecurityManager, SecurityLevel
from src.sandbox.core.types import ExecutionContext, ResourceLimits, SecurityLevel as TypesSecurityLevel


class TestSecurityIntegration:
    """Test SecurityManager integration with existing types."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.manager = SecurityManager(SecurityLevel.MEDIUM)
    
    def test_security_level_compatibility(self):
        """Test that SecurityLevel enums are compatible."""
        # Both modules should have the same security levels
        security_levels = [SecurityLevel.LOW, SecurityLevel.MEDIUM, SecurityLevel.HIGH]
        types_levels = [TypesSecurityLevel.LOW, TypesSecurityLevel.MODERATE, TypesSecurityLevel.HIGH]
        
        # Should be able to convert between them
        for sec_level in security_levels:
            if sec_level == SecurityLevel.MEDIUM:
                # MEDIUM maps to MODERATE in types
                assert TypesSecurityLevel.MODERATE.value == "moderate"
            else:
                # Others should have matching names
                matching_type = getattr(TypesSecurityLevel, sec_level.name, None)
                assert matching_type is not None
    
    def test_execution_context_integration(self):
        """Test SecurityManager with ExecutionContext."""
        # Create execution context
        context = ExecutionContext(
            workspace_id="test_workspace",
            security_level=TypesSecurityLevel.MODERATE,
            resource_limits=ResourceLimits(
                max_execution_time=30,
                max_memory_mb=512
            )
        )
        
        # SecurityManager should work with context
        assert context.security_level == TypesSecurityLevel.MODERATE
        assert context.resource_limits.max_execution_time == 30
        
        # Test command security with context
        is_safe, violation = self.manager.check_command_security("python script.py")
        assert is_safe
        
        is_safe, violation = self.manager.check_command_security("rm -rf /")
        assert not is_safe
    
    def test_resource_limits_integration(self):
        """Test resource limits integration."""
        # Get limits from SecurityManager
        limits = self.manager.get_resource_limits()
        
        # Should be compatible with ResourceLimits
        resource_limits = ResourceLimits(
            max_execution_time=limits['max_execution_time'],
            max_memory_mb=limits['max_memory_mb'],
            max_processes=limits['max_processes']
        )
        
        assert resource_limits.max_execution_time == 30
        assert resource_limits.max_memory_mb == 512
        assert resource_limits.max_processes == 10
    
    def test_workspace_security_integration(self):
        """Test workspace security integration."""
        # Create secure workspace
        workspace_path = self.manager.create_secure_workspace()
        workspace_path_obj = Path(workspace_path)
        
        assert workspace_path_obj.exists()
        assert workspace_path_obj.is_dir()
        
        # Test path security
        is_allowed, reason = self.manager.check_path_security(workspace_path)
        assert is_allowed
        
        # Test dangerous path
        is_allowed, reason = self.manager.check_path_security("/etc/passwd")
        assert not is_allowed
        assert "restricted" in reason.lower()
        
        # Cleanup
        self.manager.cleanup_security_resources()
    
    def test_balanced_security_workflow(self):
        """Test a complete balanced security workflow."""
        # This simulates a typical development workflow
        
        # 1. Create workspace
        workspace = self.manager.create_secure_workspace()
        
        # 2. Check common development commands
        dev_commands = [
            "python -m pip install requests",
            "git clone https://github.com/user/repo.git",
            "npm install",
            "curl -s https://api.github.com/user",
            "python script.py",
            "bash build.sh"
        ]
        
        for command in dev_commands:
            is_safe, violation = self.manager.check_command_security(command)
            assert is_safe, f"Development command blocked: {command}"
        
        # 3. Check Python code security
        safe_code = """
import requests
import json

response = requests.get('https://api.github.com/user')
data = response.json()
print(json.dumps(data, indent=2))
"""
        is_safe, violation = self.manager.check_python_code_security(safe_code)
        assert is_safe
        
        # 4. Verify dangerous operations are blocked
        dangerous_commands = [
            "rm -rf /",
            "sudo systemctl stop ssh",
            "chmod 777 /etc/passwd"
        ]
        
        for command in dangerous_commands:
            is_safe, violation = self.manager.check_command_security(command)
            assert not is_safe, f"Dangerous command allowed: {command}"
        
        # 5. Get security status
        status = self.manager.get_security_status()
        assert status['security_level'] == 'medium'
        
        # 6. Cleanup
        self.manager.cleanup_security_resources()


if __name__ == "__main__":
    pytest.main([__file__])