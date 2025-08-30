#!/usr/bin/env python3
"""
Test script to verify configurable timeout mechanisms in the Swiss Sandbox.

This script tests:
1. Environment variable configuration for timeouts
2. Canvas display timeout behavior
3. Executor timeout behavior
4. No timeout (infinite) behavior
"""

import os
import sys
import time
import tempfile
import subprocess
import asyncio
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from sandbox.ultimate.canvas_display import CanvasDisplay
from sandbox.intelligent.executor.sandbox_executor import SandboxExecutor


def test_environment_timeout_config():
    """Test that environment variables control timeout behavior."""
    print("🧪 Testing environment variable timeout configuration...")

    # Test 1: Set environment variable for canvas timeout
    os.environ['SANDBOX_EXECUTION_TIMEOUT'] = '10'  # 10 seconds
    canvas = CanvasDisplay()
    assert canvas.execution_timeout == 10, f"Expected 10, got {canvas.execution_timeout}"
    print("✅ Canvas timeout configured via environment variable")

    # Test 2: Set environment variable to disable timeout
    os.environ['SANDBOX_EXECUTION_TIMEOUT'] = 'none'
    canvas = CanvasDisplay()
    assert canvas.execution_timeout is None, f"Expected None, got {canvas.execution_timeout}"
    print("✅ Canvas timeout disabled via environment variable")

    # Test 3: Test executor timeout configuration
    os.environ['SANDBOX_COMMAND_TIMEOUT'] = '5'  # 5 seconds
    with tempfile.TemporaryDirectory() as tmpdir:
        executor = SandboxExecutor(tmpdir)
        # This should timeout after 5 seconds
        start_time = time.time()
        result = executor.execute_command("sleep 10")
        elapsed = time.time() - start_time

        # Check if timeout occurred by looking at exit code and error message
        if result.exit_code == -1 and 'timed out' in result.error_output.lower():
            assert 4.5 <= elapsed <= 6.0, f"Timeout took {elapsed} seconds, expected ~5"
            print("✅ Executor timeout configured via environment variable")
        else:
            print(f"Command completed without timeout: exit_code={result.exit_code}, output='{result.output}', error='{result.error_output}'")
            assert False, "Command should have timed out"

    # Test 4: Disable executor timeout
    os.environ['SANDBOX_COMMAND_TIMEOUT'] = '0'
    with tempfile.TemporaryDirectory() as tmpdir:
        executor = SandboxExecutor(tmpdir)
        # This should not timeout (but we'll interrupt it)
        start_time = time.time()
        try:
            result = executor.execute_command("sleep 2")
            elapsed = time.time() - start_time
            assert elapsed >= 1.5, f"Command completed too quickly: {elapsed} seconds"
            print("✅ Executor timeout disabled via environment variable")
        except subprocess.TimeoutExpired:
            assert False, "Command should not have timed out"

    # Clean up environment
    if 'SANDBOX_EXECUTION_TIMEOUT' in os.environ:
        del os.environ['SANDBOX_EXECUTION_TIMEOUT']
    if 'SANDBOX_COMMAND_TIMEOUT' in os.environ:
        del os.environ['SANDBOX_COMMAND_TIMEOUT']


async def test_canvas_timeout_behavior():
    """Test Canvas display timeout behavior."""
    print("\n🧪 Testing Canvas display timeout behavior...")

    # Test with timeout
    canvas = CanvasDisplay(execution_timeout=3)
    test_code = "import time; time.sleep(5); print('Should not print')"

    start_time = time.time()
    result = await canvas._execute_code(test_code, "python")
    elapsed = time.time() - start_time

    assert not result['success'], "Code execution should have failed due to timeout"
    assert 'timed out' in result['error'].lower(), f"Expected timeout error, got: {result['error']}"
    assert 2.5 <= elapsed <= 4.0, f"Timeout took {elapsed} seconds, expected ~3"
    print("✅ Canvas timeout behavior works correctly")

    # Test without timeout
    canvas = CanvasDisplay(execution_timeout=None)
    test_code = "import time; time.sleep(1); print('Success')"

    start_time = time.time()
    result = await canvas._execute_code(test_code, "python")
    elapsed = time.time() - start_time

    assert result['success'], f"Code execution should have succeeded: {result.get('error', '')}"
    assert elapsed >= 0.8, f"Command completed too quickly: {elapsed} seconds"
    print("✅ Canvas no-timeout behavior works correctly")


def test_executor_timeout_behavior():
    """Test executor timeout behavior."""
    print("\n🧪 Testing executor timeout behavior...")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Test with timeout
        executor = SandboxExecutor(tmpdir)

        start_time = time.time()
        result = executor.execute_command("sleep 10", timeout=2)
        elapsed = time.time() - start_time

        # Check if timeout occurred
        if result.exit_code == -1 and 'timed out' in result.error_output.lower():
            assert 1.5 <= elapsed <= 3.0, f"Timeout took {elapsed} seconds, expected ~2"
            print("✅ Executor timeout behavior works correctly")
        else:
            print(f"Command completed without timeout: exit_code={result.exit_code}, error='{result.error_output}'")
            assert False, "Command should have timed out"

        # Test without timeout
        start_time = time.time()
        result = executor.execute_command("sleep 1", timeout=None)
        elapsed = time.time() - start_time

        assert result.exit_code == 0, f"Command failed: {result.error_output}"
        assert elapsed >= 0.8, f"Command completed too quickly: {elapsed} seconds"
        print("✅ Executor no-timeout behavior works correctly")


async def main():
    """Run all timeout configuration tests."""
    print("🚀 Testing Configurable Timeout Mechanisms")
    print("=" * 50)

    try:
        test_environment_timeout_config()
        await test_canvas_timeout_behavior()
        test_executor_timeout_behavior()

        print("\n" + "=" * 50)
        print("🎉 All timeout configuration tests passed!")
        print("\n📋 Timeout Configuration Summary:")
        print("   • SANDBOX_EXECUTION_TIMEOUT: Controls Canvas display timeouts")
        print("   • SANDBOX_COMMAND_TIMEOUT: Controls executor command timeouts")
        print("   • Set to 'none' or '0' to disable timeouts")
        print("   • Set to a number (seconds) to enable timeouts")
        print("   • Canvas defaults to no timeout for long-running processes")
        print("   • Executors default to 5-minute timeout for safety")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))