#!/usr/bin/env python3
"""
Comprehensive test runner for Swiss Sandbox.

This script runs the complete test suite with different configurations
and generates detailed reports on test coverage, performance, and security.
"""

import os
import sys
import subprocess
import argparse
import time
from pathlib import Path


def run_command(command, description=""):
    """Run a command and return the result."""
    print(f"\n{'='*60}")
    print(f"Running: {description or command}")
    print(f"{'='*60}")
    
    start_time = time.time()
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    end_time = time.time()
    
    print(f"Exit code: {result.returncode}")
    print(f"Duration: {end_time - start_time:.2f}s")
    
    if result.stdout:
        print(f"\nSTDOUT:\n{result.stdout}")
    
    if result.stderr:
        print(f"\nSTDERR:\n{result.stderr}")
    
    return result


def main():
    parser = argparse.ArgumentParser(description="Run comprehensive Swiss Sandbox tests")
    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument("--integration", action="store_true", help="Run integration tests only")
    parser.add_argument("--performance", action="store_true", help="Run performance tests only")
    parser.add_argument("--security", action="store_true", help="Run security tests only")
    parser.add_argument("--coverage", action="store_true", help="Generate coverage report")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--parallel", "-n", type=int, help="Number of parallel workers")
    parser.add_argument("--timeout", type=int, default=300, help="Test timeout in seconds")
    
    args = parser.parse_args()
    
    # Base pytest command
    pytest_cmd = ["python", "-m", "pytest"]
    
    if args.verbose:
        pytest_cmd.append("-v")
    
    if args.parallel:
        pytest_cmd.extend(["-n", str(args.parallel)])
    
    pytest_cmd.extend(["--timeout", str(args.timeout)])
    
    # Determine which tests to run
    test_markers = []
    test_files = []
    
    if args.unit:
        test_markers.append("unit")
    if args.integration:
        test_markers.append("integration")
    if args.performance:
        test_markers.append("performance")
    if args.security:
        test_markers.append("security")
    
    # If no specific test type specified, run all
    if not any([args.unit, args.integration, args.performance, args.security]):
        print("Running all test types...")
        test_files = ["tests/"]
    else:
        # Add marker filters
        if test_markers:
            marker_expr = " or ".join(test_markers)
            pytest_cmd.extend(["-m", marker_expr])
        test_files = ["tests/"]
    
    # Add coverage if requested
    if args.coverage:
        pytest_cmd.extend([
            "--cov=src/sandbox",
            "--cov-report=html:htmlcov",
            "--cov-report=term-missing",
            "--cov-report=xml",
            "--cov-fail-under=80"
        ])
    
    # Add test files
    pytest_cmd.extend(test_files)
    
    # Run the tests
    print("Swiss Sandbox Comprehensive Test Suite")
    print("=" * 50)
    print(f"Command: {' '.join(pytest_cmd)}")
    
    start_time = time.time()
    result = subprocess.run(pytest_cmd)
    end_time = time.time()
    
    print(f"\nTotal test execution time: {end_time - start_time:.2f}s")
    
    if result.returncode == 0:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed!")
        
        # Run specific test categories to identify failures
        if not any([args.unit, args.integration, args.performance, args.security]):
            print("\nRunning test categories individually to identify issues...")
            
            categories = [
                ("unit", "Unit tests"),
                ("integration", "Integration tests"),
                ("performance", "Performance tests"),
                ("security", "Security tests")
            ]
            
            for marker, description in categories:
                print(f"\n{'-'*40}")
                print(f"Running {description}...")
                print(f"{'-'*40}")
                
                category_cmd = ["python", "-m", "pytest", "-m", marker, "tests/", "--tb=short"]
                if args.verbose:
                    category_cmd.append("-v")
                
                category_result = subprocess.run(category_cmd)
                if category_result.returncode == 0:
                    print(f"✅ {description} passed")
                else:
                    print(f"❌ {description} failed")
    
    # Generate additional reports
    if args.coverage and result.returncode == 0:
        print("\n" + "="*50)
        print("Generating additional reports...")
        print("="*50)
        
        # Coverage report
        print("\nCoverage report generated in htmlcov/")
        
        # Test summary
        summary_cmd = ["python", "-m", "pytest", "--collect-only", "-q", "tests/"]
        summary_result = subprocess.run(summary_cmd, capture_output=True, text=True)
        
        if summary_result.returncode == 0:
            lines = summary_result.stdout.split('\n')
            test_count = len([line for line in lines if 'test_' in line])
            print(f"Total tests discovered: {test_count}")
    
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())