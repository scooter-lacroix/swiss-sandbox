"""
Performance tests for the Swiss Sandbox system.

This module tests performance characteristics, resource usage, and scalability
of the Swiss Sandbox components under various load conditions.
"""

import pytest
import time
import asyncio
import psutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.sandbox.unified_server import UnifiedSandboxServer
from src.sandbox.core.types import ServerConfig, SecurityLevel


@pytest.mark.performance
class TestExecutionPerformance:
    """Test execution performance characteristics."""
    
    @pytest.fixture
    def performance_server(self, temp_dir):
        """Create a server optimized for performance testing."""
        config = ServerConfig(
            max_execution_time=60,
            max_memory_mb=1024,
            security_level=SecurityLevel.LOW,  # Reduced security for performance
            artifacts_retention_days=1,
            artifacts_dir=temp_dir / "artifacts",
            workspaces_dir=temp_dir / "workspaces",
            logs_dir=temp_dir / "logs"
        )
        return UnifiedSandboxServer(config)
    
    async def test_python_execution_speed(self, performance_server, performance_test_data):
        """Test Python execution speed for different code sizes."""
        test_cases = [
            ('small', performance_test_data['small_code']),
            ('medium', performance_test_data['medium_code']),
            ('large', performance_test_data['large_code'])
        ]
        
        results = {}
        
        for size, code in test_cases:
            start_time = time.time()
            result = await performance_server._execute_python_tool(
                code=code,
                workspace_id=f"perf_test_{size}"
            )
            end_time = time.time()
            
            execution_time = end_time - start_time
            results[size] = {
                'success': result['success'],
                'execution_time': execution_time,
                'reported_time': result.get('execution_time', 0)
            }
            
            assert result['success'], f"Failed to execute {size} code"
            print(f"{size.capitalize()} code execution: {execution_time:.3f}s")
        
        # Performance assertions
        assert results['small']['execution_time'] < 1.0, "Small code should execute quickly"
        assert results['medium']['execution_time'] < 5.0, "Medium code should execute reasonably fast"
        assert results['large']['execution_time'] < 15.0, "Large code should complete within timeout"
        
        # Execution time should generally increase with code size
        assert results['small']['execution_time'] < results['medium']['execution_time']
    
    async def test_concurrent_execution_performance(self, performance_server):
        """Test performance under concurrent execution load."""
        num_concurrent = 10
        
        async def single_execution(execution_id):
            code = f"""
import time
import math

# Simulate CPU work
start = time.time()
result = 0
for i in range(10000):
    result += math.sqrt(i)

end = time.time()
print(f"Execution {execution_id}: computed {{result:.2f}} in {{end-start:.3f}}s")
"""
            return await performance_server._execute_python_tool(
                code=code,
                workspace_id=f"concurrent_perf_{execution_id}"
            )
        
        # Measure concurrent execution time
        start_time = time.time()
        tasks = [single_execution(i) for i in range(num_concurrent)]
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        total_time = end_time - start_time
        
        # All executions should succeed
        for i, result in enumerate(results):
            assert result['success'], f"Concurrent execution {i} failed"
        
        # Concurrent execution should be faster than sequential
        # (assuming some parallelization benefit)
        expected_sequential_time = num_concurrent * 0.5  # Rough estimate
        assert total_time < expected_sequential_time, f"Concurrent execution not efficient: {total_time:.2f}s"
        
        print(f"Concurrent executions ({num_concurrent}): {total_time:.2f}s")
    
    async def test_memory_intensive_performance(self, performance_server, performance_test_data):
        """Test performance with memory-intensive operations."""
        start_time = time.time()
        
        result = await performance_server._execute_python_tool(
            code=performance_test_data['memory_intensive'],
            workspace_id="memory_perf_test"
        )
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        assert result['success'], "Memory-intensive operation should succeed"
        assert execution_time < 10.0, f"Memory operation too slow: {execution_time:.2f}s"
        
        print(f"Memory-intensive execution: {execution_time:.3f}s")
    
    async def test_cpu_intensive_performance(self, performance_server, performance_test_data):
        """Test performance with CPU-intensive operations."""
        start_time = time.time()
        
        result = await performance_server._execute_python_tool(
            code=performance_test_data['cpu_intensive'],
            workspace_id="cpu_perf_test"
        )
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        assert result['success'], "CPU-intensive operation should succeed"
        assert execution_time < 30.0, f"CPU operation too slow: {execution_time:.2f}s"
        
        print(f"CPU-intensive execution: {execution_time:.3f}s")
    
    async def test_startup_performance(self, temp_dir):
        """Test server startup performance."""
        config = ServerConfig(
            artifacts_dir=temp_dir / "startup_artifacts",
            workspaces_dir=temp_dir / "startup_workspaces",
            logs_dir=temp_dir / "startup_logs"
        )
        
        start_time = time.time()
        server = UnifiedSandboxServer(config)
        end_time = time.time()
        
        startup_time = end_time - start_time
        
        assert startup_time < 2.0, f"Server startup too slow: {startup_time:.3f}s"
        print(f"Server startup time: {startup_time:.3f}s")


@pytest.mark.performance
class TestResourceUsage:
    """Test resource usage characteristics."""
    
    def get_process_memory(self):
        """Get current process memory usage in MB."""
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024
    
    def get_process_cpu(self):
        """Get current process CPU usage percentage."""
        process = psutil.Process()
        return process.cpu_percent(interval=0.1)
    
    async def test_memory_usage_baseline(self, performance_server):
        """Test baseline memory usage."""
        initial_memory = self.get_process_memory()
        
        # Execute simple operations
        for i in range(10):
            result = await performance_server._execute_python_tool(
                code="print(f'Simple operation {i}')",
                workspace_id=f"memory_baseline_{i}"
            )
            assert result['success']
        
        final_memory = self.get_process_memory()
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable
        assert memory_increase < 50, f"Excessive memory usage: {memory_increase:.1f}MB"
        print(f"Memory usage increase: {memory_increase:.1f}MB")
    
    async def test_memory_cleanup_efficiency(self, performance_server):
        """Test memory cleanup after operations."""
        initial_memory = self.get_process_memory()
        
        # Execute memory-intensive operations
        for i in range(5):
            code = f"""
import numpy as np
# Create and delete large arrays
for j in range(10):
    arr = np.zeros((1000, 1000))  # ~8MB each
    del arr
print(f"Memory test {i} completed")
"""
            result = await performance_server._execute_python_tool(
                code=code,
                workspace_id=f"memory_cleanup_{i}"
            )
            assert result['success']
        
        # Force cleanup
        if hasattr(performance_server, 'cleanup'):
            performance_server.cleanup()
        
        # Wait for cleanup
        await asyncio.sleep(1)
        
        final_memory = self.get_process_memory()
        memory_increase = final_memory - initial_memory
        
        # Memory should not increase excessively after cleanup
        assert memory_increase < 100, f"Poor memory cleanup: {memory_increase:.1f}MB"
        print(f"Memory after cleanup: {memory_increase:.1f}MB increase")
    
    async def test_cpu_usage_efficiency(self, performance_server):
        """Test CPU usage efficiency."""
        # Measure CPU usage during idle
        idle_cpu = self.get_process_cpu()
        
        # Execute CPU-bound operation
        cpu_code = """
import math
result = 0
for i in range(100000):
    result += math.sin(i) * math.cos(i)
print(f"CPU test result: {result:.2f}")
"""
        
        start_time = time.time()
        result = await performance_server._execute_python_tool(
            code=cpu_code,
            workspace_id="cpu_usage_test"
        )
        end_time = time.time()
        
        execution_time = end_time - start_time
        
        assert result['success']
        
        # CPU usage should be reasonable
        print(f"CPU test execution time: {execution_time:.3f}s")
        print(f"Idle CPU usage: {idle_cpu:.1f}%")


@pytest.mark.performance
class TestScalability:
    """Test scalability characteristics."""
    
    async def test_workspace_scalability(self, performance_server):
        """Test performance with many workspaces."""
        num_workspaces = 50
        
        start_time = time.time()
        
        # Create many workspaces
        tasks = []
        for i in range(num_workspaces):
            task = performance_server._execute_python_tool(
                code=f"workspace_id = {i}; print(f'Workspace {{workspace_id}} active')",
                workspace_id=f"scale_workspace_{i}"
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        total_time = end_time - start_time
        
        # All should succeed
        for i, result in enumerate(results):
            assert result['success'], f"Workspace {i} failed"
        
        # Should complete in reasonable time
        assert total_time < 30.0, f"Workspace scaling too slow: {total_time:.2f}s"
        
        print(f"Created {num_workspaces} workspaces in {total_time:.2f}s")
        print(f"Average time per workspace: {total_time/num_workspaces:.3f}s")
    
    async def test_artifact_scalability(self, performance_server):
        """Test performance with many artifacts."""
        # Create many small artifacts
        artifact_code = """
import json
import time

start_time = time.time()
for i in range(100):
    data = {'id': i, 'timestamp': time.time(), 'data': f'artifact_{i}'}
    with open(f'artifact_{i:03d}.json', 'w') as f:
        json.dump(data, f)

end_time = time.time()
print(f"Created 100 artifacts in {end_time - start_time:.3f}s")
"""
        
        start_time = time.time()
        result = await performance_server._execute_python_tool(
            code=artifact_code,
            workspace_id="artifact_scale_test"
        )
        end_time = time.time()
        
        total_time = end_time - start_time
        
        assert result['success']
        assert "Created 100 artifacts" in result['output']
        
        # Should complete in reasonable time
        assert total_time < 10.0, f"Artifact creation too slow: {total_time:.2f}s"
        
        # Test artifact listing performance
        list_start = time.time()
        artifacts = await performance_server._list_artifacts_tool(
            workspace_id="artifact_scale_test"
        )
        list_end = time.time()
        
        list_time = list_end - list_start
        
        assert len(artifacts['artifacts']) >= 100
        assert list_time < 2.0, f"Artifact listing too slow: {list_time:.3f}s"
        
        print(f"Artifact creation: {total_time:.3f}s")
        print(f"Artifact listing: {list_time:.3f}s")
    
    async def test_execution_history_scalability(self, performance_server):
        """Test performance with large execution history."""
        # Generate many executions
        for i in range(100):
            result = await performance_server._execute_python_tool(
                code=f"print('Execution {i}')",
                workspace_id="history_scale_test"
            )
            assert result['success']
        
        # Test history retrieval performance
        start_time = time.time()
        
        # This would test execution engine's get_execution_history if exposed
        # For now, just verify the system still performs well
        result = await performance_server._execute_python_tool(
            code="print('History test completed')",
            workspace_id="history_scale_test"
        )
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        assert result['success']
        assert execution_time < 1.0, f"Execution slow with large history: {execution_time:.3f}s"


@pytest.mark.performance
@pytest.mark.slow
class TestStressTests:
    """Stress tests for the system."""
    
    async def test_sustained_load(self, performance_server):
        """Test system under sustained load."""
        duration = 30  # seconds
        start_time = time.time()
        execution_count = 0
        
        while time.time() - start_time < duration:
            result = await performance_server._execute_python_tool(
                code=f"import time; time.sleep(0.1); print('Load test {execution_count}')",
                workspace_id=f"load_test_{execution_count % 10}"  # Reuse workspaces
            )
            
            if result['success']:
                execution_count += 1
            else:
                print(f"Execution failed during load test: {result.get('error')}")
            
            # Small delay to prevent overwhelming
            await asyncio.sleep(0.05)
        
        total_time = time.time() - start_time
        executions_per_second = execution_count / total_time
        
        print(f"Sustained load test: {execution_count} executions in {total_time:.1f}s")
        print(f"Rate: {executions_per_second:.2f} executions/second")
        
        # Should maintain reasonable throughput
        assert executions_per_second > 1.0, f"Throughput too low: {executions_per_second:.2f}/s"
        assert execution_count > 20, f"Too few successful executions: {execution_count}"
    
    async def test_memory_stress(self, performance_server):
        """Test system under memory stress."""
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024
        
        # Execute memory-intensive operations
        for i in range(10):
            memory_code = f"""
import numpy as np
import gc

# Create large arrays
arrays = []
for j in range(5):
    arr = np.random.rand(1000, 1000)  # ~8MB each
    arrays.append(arr)

# Process the arrays
result = sum(np.sum(arr) for arr in arrays)
print(f"Memory stress test {i}: result = {{result:.2e}}")

# Clean up
del arrays
gc.collect()
"""
            
            result = await performance_server._execute_python_tool(
                code=memory_code,
                workspace_id=f"memory_stress_{i}"
            )
            
            assert result['success'], f"Memory stress test {i} failed"
        
        final_memory = psutil.Process().memory_info().rss / 1024 / 1024
        memory_increase = final_memory - initial_memory
        
        print(f"Memory stress test: {memory_increase:.1f}MB increase")
        
        # Memory increase should be reasonable
        assert memory_increase < 200, f"Excessive memory usage: {memory_increase:.1f}MB"


@pytest.mark.performance
class TestPerformanceRegression:
    """Test for performance regressions."""
    
    async def test_baseline_performance_metrics(self, performance_server):
        """Establish baseline performance metrics."""
        metrics = {}
        
        # Simple execution time
        start = time.time()
        result = await performance_server._execute_python_tool(
            code="print('Hello World')",
            workspace_id="baseline_test"
        )
        metrics['simple_execution'] = time.time() - start
        assert result['success']
        
        # Complex execution time
        complex_code = """
import json
import math

data = {'values': [math.sqrt(i) for i in range(1000)]}
with open('baseline_data.json', 'w') as f:
    json.dump(data, f)
print(f"Processed {len(data['values'])} values")
"""
        
        start = time.time()
        result = await performance_server._execute_python_tool(
            code=complex_code,
            workspace_id="baseline_test"
        )
        metrics['complex_execution'] = time.time() - start
        assert result['success']
        
        # Artifact listing time
        start = time.time()
        artifacts = await performance_server._list_artifacts_tool(
            workspace_id="baseline_test"
        )
        metrics['artifact_listing'] = time.time() - start
        
        # Print metrics for reference
        print("Baseline Performance Metrics:")
        for metric, value in metrics.items():
            print(f"  {metric}: {value:.3f}s")
        
        # Basic performance assertions
        assert metrics['simple_execution'] < 1.0, "Simple execution too slow"
        assert metrics['complex_execution'] < 5.0, "Complex execution too slow"
        assert metrics['artifact_listing'] < 1.0, "Artifact listing too slow"
        
        return metrics


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])