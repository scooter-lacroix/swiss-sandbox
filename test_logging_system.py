#!/usr/bin/env python3
"""
Test script for the comprehensive logging and error handling system.
"""

import sys
import time
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from sandbox.core.logging_system import (
    StructuredLogger, ErrorHandler, PerformanceMonitor, DiagnosticTools,
    ErrorCategory, LogLevel
)
from sandbox.core.health_monitor import HealthMonitor


def test_structured_logging():
    """Test structured logging functionality."""
    print("Testing structured logging...")
    
    logger = StructuredLogger("test_logger")
    
    # Test different log levels
    logger.debug("Debug message", component="test", metadata={'test': True})
    logger.info("Info message", component="test", context_id="test_context")
    logger.warning("Warning message", component="test", error_type="TestWarning")
    logger.error("Error message", component="test", stack_trace="test stack trace")
    logger.critical("Critical message", component="test")
    
    print("✓ Structured logging test completed")
    return logger


def test_error_handling(logger):
    """Test error handling and recovery."""
    print("Testing error handling...")
    
    error_handler = ErrorHandler(logger)
    
    # Test different error categories
    try:
        raise ValueError("Test execution error")
    except Exception as e:
        recovered = error_handler.handle_error(
            e, ErrorCategory.EXECUTION, "test_component",
            {'context_id': 'test_context', 'operation': 'test_operation'}
        )
        print(f"✓ Execution error handled, recovered: {recovered}")
    
    try:
        raise MemoryError("Test resource error")
    except Exception as e:
        recovered = error_handler.handle_error(
            e, ErrorCategory.RESOURCE, "test_component",
            {'context_id': 'test_context'}
        )
        print(f"✓ Resource error handled, recovered: {recovered}")
    
    # Get error statistics
    stats = error_handler.get_error_statistics()
    print(f"✓ Error statistics: {stats['total_errors']} total errors")
    
    print("✓ Error handling test completed")
    return error_handler


def test_performance_monitoring(logger):
    """Test performance monitoring."""
    print("Testing performance monitoring...")
    
    performance_monitor = PerformanceMonitor(logger)
    
    # Test operation measurement
    with performance_monitor.measure_operation("test_component", "test_operation", "test_context"):
        time.sleep(0.1)  # Simulate work
    
    with performance_monitor.measure_operation("test_component", "fast_operation"):
        time.sleep(0.01)  # Simulate fast work
    
    # Test failed operation
    try:
        with performance_monitor.measure_operation("test_component", "failing_operation"):
            raise RuntimeError("Test failure")
    except RuntimeError:
        pass
    
    # Get performance summary
    summary = performance_monitor.get_performance_summary()
    print(f"✓ Performance summary: {summary['total_operations']} operations")
    print(f"✓ Success rate: {summary['success_rate']:.2f}")
    print(f"✓ Average duration: {summary['average_duration_ms']:.2f}ms")
    
    print("✓ Performance monitoring test completed")
    return performance_monitor


def test_health_monitoring(logger, error_handler, performance_monitor):
    """Test health monitoring."""
    print("Testing health monitoring...")
    
    health_monitor = HealthMonitor(logger, error_handler, performance_monitor)
    
    # Get overall health
    health_report = health_monitor.get_overall_health()
    print(f"✓ Overall health status: {health_report['overall_status']}")
    print(f"✓ Components checked: {len(health_report['components'])}")
    
    # Get diagnostic report
    diagnostic_report = health_monitor.get_diagnostic_report()
    print(f"✓ Diagnostic report generated with {len(diagnostic_report)} sections")
    
    print("✓ Health monitoring test completed")
    return health_monitor


def test_diagnostic_tools(logger, error_handler, performance_monitor):
    """Test diagnostic tools."""
    print("Testing diagnostic tools...")
    
    diagnostic_tools = DiagnosticTools(logger, error_handler, performance_monitor)
    
    # Run health check
    health_check = diagnostic_tools.run_health_check()
    print(f"✓ Health check status: {health_check['overall_status']}")
    
    # Generate diagnostic report
    report = diagnostic_tools.generate_diagnostic_report()
    print(f"✓ Diagnostic report generated")
    
    print("✓ Diagnostic tools test completed")


def test_log_file_creation():
    """Test that log files are created properly."""
    print("Testing log file creation...")
    
    log_dir = Path("logs")
    if log_dir.exists():
        print(f"✓ Log directory exists: {log_dir}")
        
        # List log files
        log_files = list(log_dir.glob("*.log"))
        json_files = list(log_dir.glob("*.jsonl"))
        
        print(f"✓ Found {len(log_files)} log files")
        print(f"✓ Found {len(json_files)} JSON log files")
        
        # Check if structured logs contain valid JSON
        for json_file in json_files:
            try:
                with open(json_file, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        # Try to parse the last line as JSON
                        last_line = lines[-1].strip()
                        if last_line:
                            json.loads(last_line)
                            print(f"✓ Valid JSON in {json_file.name}")
            except (json.JSONDecodeError, FileNotFoundError):
                print(f"⚠ Invalid JSON or missing file: {json_file.name}")
    else:
        print("⚠ Log directory not found")


def main():
    """Run all tests."""
    print("Starting comprehensive logging and error handling system tests...\n")
    
    try:
        # Test structured logging
        logger = test_structured_logging()
        print()
        
        # Test error handling
        error_handler = test_error_handling(logger)
        print()
        
        # Test performance monitoring
        performance_monitor = test_performance_monitoring(logger)
        print()
        
        # Test health monitoring
        health_monitor = test_health_monitoring(logger, error_handler, performance_monitor)
        print()
        
        # Test diagnostic tools
        test_diagnostic_tools(logger, error_handler, performance_monitor)
        print()
        
        # Wait a moment for background threads to process
        time.sleep(2)
        
        # Test log file creation
        test_log_file_creation()
        print()
        
        # Cleanup
        logger.cleanup()
        performance_monitor.cleanup()
        health_monitor.cleanup()
        
        print("✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())