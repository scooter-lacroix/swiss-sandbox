#!/usr/bin/env python3
"""
Test script for connection limits and rate limiting functionality.
"""

import sys
import os
import time
import json
from pathlib import Path

# Add the src directory to Python path
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from sandbox.core.connection_manager import ConnectionManager, SlidingWindowRateLimiter, initialize_connection_manager
from sandbox.intelligent.config import get_config_manager


def test_connection_limits():
    """Test connection limit functionality."""
    print("🧪 Testing Connection Limits...")

    # Create connection manager with low limits for testing
    manager = ConnectionManager(
        max_connections=3,
        max_per_ip=2,
        connection_timeout=3600,
        enable_ip_filtering=True
    )

    # Test adding connections
    results = []

    # Add first connection
    success1, msg1 = manager.add_connection("conn1", "192.168.1.100")
    results.append(("Connection 1", success1, msg1))

    # Add second connection from same IP
    success2, msg2 = manager.add_connection("conn2", "192.168.1.100")
    results.append(("Connection 2 (same IP)", success2, msg2))

    # Add third connection from same IP (should fail)
    success3, msg3 = manager.add_connection("conn3", "192.168.1.100")
    results.append(("Connection 3 (same IP, should fail)", success3, msg3))

    # Add fourth connection from different IP
    success4, msg4 = manager.add_connection("conn4", "192.168.1.101")
    results.append(("Connection 4 (different IP)", success4, msg4))

    # Add fifth connection (should fail due to total limit)
    success5, msg5 = manager.add_connection("conn5", "192.168.1.102")
    results.append(("Connection 5 (should fail total limit)", success5, msg5))

    # Print results
    for name, success, msg in results:
        status = "✅" if success else "❌"
        print(f"  {status} {name}: {msg}")

    # Test connection stats
    stats = manager.get_connection_stats()
    print(f"  📊 Connection stats: {stats['total_connections']} connections")

    # Expected results: connections 1, 2, 4 should succeed; 3 and 5 should fail
    expected_success = [True, True, False, True, False]
    actual_success = [r[1] for r in results]
    return actual_success == expected_success


def test_rate_limiting():
    """Test rate limiting functionality."""
    print("\n🧪 Testing Rate Limiting...")

    # Create rate limiter with low limits for testing
    limiter = SlidingWindowRateLimiter(
        max_requests=3,  # 3 requests per window
        window_seconds=10,  # 10 second window
        burst_limit=2
    )

    connection_id = "test_conn"
    results = []

    # Make requests within limit
    for i in range(3):
        allowed, retry_after = limiter.is_allowed(connection_id)
        results.append((f"Request {i+1}", allowed, retry_after))
        time.sleep(0.1)  # Small delay

    # Make request that should be denied
    allowed4, retry_after4 = limiter.is_allowed(connection_id)
    results.append(("Request 4 (should be denied)", allowed4, retry_after4))

    # Wait for window to reset and try again
    print("  ⏳ Waiting for rate limit window to reset...")
    time.sleep(11)

    allowed5, retry_after5 = limiter.is_allowed(connection_id)
    results.append(("Request 5 (after reset)", allowed5, retry_after5))

    # Print results
    for name, allowed, retry_after in results:
        status = "✅" if allowed else "❌"
        retry_info = f" (retry after {retry_after:.1f}s)" if not allowed else ""
        print(f"  {status} {name}: allowed={allowed}{retry_info}")

    # Check expected results: first 3 should be allowed, 4th denied, 5th allowed after reset
    expected = [True, True, True, False, True]
    actual = [r[1] for r in results]

    return actual == expected


def test_configuration_integration():
    """Test configuration integration."""
    print("\n🧪 Testing Configuration Integration...")

    try:
        # Get config manager
        config_manager = get_config_manager()
        config = config_manager.config

        print(f"  📋 Connection limits enabled: {config.enable_connection_limits}")
        print(f"  📋 Rate limiting enabled: {config.enable_rate_limiting}")
        print(f"  📋 Max connections: {config.connection_limits.max_concurrent_connections}")
        print(f"  📋 Max requests/minute: {config.rate_limits.max_requests_per_minute}")

        # Initialize connection manager with config
        manager = initialize_connection_manager(config)

        # Test that it initializes correctly
        stats = manager.get_connection_stats()
        print(f"  📊 Manager initialized with {stats['total_connections']} connections")

        return True

    except Exception as e:
        print(f"  ❌ Configuration test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("🚀 Testing Connection Limits and Rate Limiting Implementation")
    print("=" * 60)

    test_results = []

    # Test connection limits
    test_results.append(("Connection Limits", test_connection_limits()))

    # Test rate limiting
    test_results.append(("Rate Limiting", test_rate_limiting()))

    # Test configuration integration
    test_results.append(("Configuration Integration", test_configuration_integration()))

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Results Summary:")

    all_passed = True
    for test_name, passed in test_results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {status}: {test_name}")
        all_passed = all_passed and passed

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 All tests passed! Connection limits and rate limiting are working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the implementation.")
        return 1


if __name__ == "__main__":
    sys.exit(main())