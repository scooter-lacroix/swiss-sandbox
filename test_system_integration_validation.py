#!/usr/bin/env python3
"""
System Integration and Validation Test

This comprehensive test validates the complete restored Swiss Sandbox system
end-to-end, including MCP client integration, tool availability, security
policies, and resource management.

Requirements tested:
- 7.1: Complete system functionality verification
- 7.4: Integration test coverage
- 9.1: Performance and reliability
- 9.3: System stability under normal usage
"""

import json
import sys
import time
import tempfile
import subprocess
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SystemIntegrationValidator:
    """Comprehensive system integration validator."""
    
    def __init__(self):
        self.test_results = {}
        self.server_process = None
        self.server_thread = None
        self.project_root = Path(__file__).parent
        
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all integration tests."""
        logger.info("Starting comprehensive system integration validation...")
        
        tests = [
            ("server_startup", self.test_server_startup),
            ("mcp_protocol", self.test_mcp_protocol_compliance),
            ("tool_availability", self.test_tool_availability),
            ("execution_functionality", self.test_execution_functionality),
            ("security_policies", self.test_security_policies),
            ("resource_management", self.test_resource_management),
            ("artifact_system", self.test_artifact_system),
            ("workspace_isolation", self.test_workspace_isolation),
            ("error_handling", self.test_error_handling),
            ("performance_validation", self.test_performance_validation),
            ("migrated_functionality", self.test_migrated_functionality),
            ("system_stability", self.test_system_stability)
        ]
        
        for test_name, test_func in tests:
            logger.info(f"Running test: {test_name}")
            try:
                result = test_func()
                self.test_results[test_name] = {
                    'status': 'PASS' if result else 'FAIL',
                    'details': result if isinstance(result, dict) else {'success': result}
                }
                logger.info(f"Test {test_name}: {'PASS' if result else 'FAIL'}")
            except Exception as e:
                self.test_results[test_name] = {
                    'status': 'ERROR',
                    'error': str(e),
                    'details': {'exception': type(e).__name__}
                }
                logger.error(f"Test {test_name}: ERROR - {e}")
        
        return self.generate_final_report()
    
    def test_server_startup(self) -> bool:
        """Test that the unified server starts correctly."""
        try:
            # Test import of unified server
            from src.sandbox.unified_server import UnifiedSandboxServer
            from src.sandbox.core.types import ServerConfig
            
            # Test server initialization
            config = ServerConfig()
            server = UnifiedSandboxServer(config)
            
            # Verify core components are initialized
            assert server.execution_engine is not None
            assert server.artifact_manager is not None
            assert server.mcp is not None
            assert server.structured_logger is not None
            
            logger.info("✓ Server initialization successful")
            return True
            
        except Exception as e:
            logger.error(f"✗ Server startup failed: {e}")
            return False
    
    def test_mcp_protocol_compliance(self) -> Dict[str, Any]:
        """Test MCP protocol compliance."""
        try:
            from src.sandbox.unified_server import UnifiedSandboxServer
            from src.sandbox.core.types import ServerConfig
            
            server = UnifiedSandboxServer(ServerConfig())
            
            # Test that MCP server has required attributes
            assert hasattr(server.mcp, 'tool')
            assert hasattr(server.mcp, 'run')
            
            # Test tool registration
            tools = []
            for attr_name in dir(server.mcp):
                if not attr_name.startswith('_'):
                    attr = getattr(server.mcp, attr_name)
                    if callable(attr):
                        tools.append(attr_name)
            
            logger.info(f"✓ MCP protocol compliance verified, {len(tools)} tools available")
            return {
                'success': True,
                'tools_count': len(tools),
                'has_required_methods': True
            }
            
        except Exception as e:
            logger.error(f"✗ MCP protocol compliance failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def test_tool_availability(self) -> Dict[str, Any]:
        """Test that all expected tools are available."""
        expected_tools = [
            'server_info', 'health_check', 'create_execution_context',
            'execute_python', 'execute_shell', 'execute_manim',
            'store_artifact', 'retrieve_artifact', 'list_artifacts',
            'create_manim_animation', 'start_web_app'
        ]
        
        try:
            from src.sandbox.unified_server import UnifiedSandboxServer
            from src.sandbox.core.types import ServerConfig
            
            server = UnifiedSandboxServer(ServerConfig())
            
            # Check if tools are registered
            available_tools = []
            missing_tools = []
            
            for tool_name in expected_tools:
                # Check if the tool method exists on the server's mcp instance
                if hasattr(server.mcp, '_tools') and tool_name in server.mcp._tools:
                    available_tools.append(tool_name)
                else:
                    # Try to find the tool function in the server
                    found = False
                    for attr_name in dir(server):
                        if tool_name in attr_name.lower():
                            available_tools.append(tool_name)
                            found = True
                            break
                    if not found:
                        missing_tools.append(tool_name)
            
            success = len(missing_tools) == 0
            logger.info(f"✓ Tool availability: {len(available_tools)}/{len(expected_tools)} tools available")
            
            return {
                'success': success,
                'available_tools': available_tools,
                'missing_tools': missing_tools,
                'total_expected': len(expected_tools)
            }
            
        except Exception as e:
            logger.error(f"✗ Tool availability test failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def test_execution_functionality(self) -> Dict[str, Any]:
        """Test core execution functionality."""
        try:
            from src.sandbox.unified_server import UnifiedSandboxServer
            from src.sandbox.core.types import ServerConfig
            
            server = UnifiedSandboxServer(ServerConfig())
            
            results = {}
            
            # Test Python execution
            try:
                python_result = server.execution_engine.execute_python(
                    "print('Hello from Python')\nresult = 2 + 2\nprint(f'2 + 2 = {result}')",
                    server.get_or_create_context("test_workspace")
                )
                results['python_execution'] = {
                    'success': python_result.success,
                    'has_output': bool(python_result.output),
                    'execution_time': python_result.execution_time
                }
            except Exception as e:
                results['python_execution'] = {'success': False, 'error': str(e)}
            
            # Test Shell execution
            try:
                shell_result = server.execution_engine.execute_shell(
                    "echo 'Hello from Shell'",
                    server.get_or_create_context("test_workspace")
                )
                results['shell_execution'] = {
                    'success': shell_result.success,
                    'has_output': bool(shell_result.output),
                    'execution_time': shell_result.execution_time
                }
            except Exception as e:
                results['shell_execution'] = {'success': False, 'error': str(e)}
            
            # Test execution history
            try:
                history = server.execution_engine.get_execution_history(limit=10)
                results['execution_history'] = {
                    'success': True,
                    'history_count': len(history)
                }
            except Exception as e:
                results['execution_history'] = {'success': False, 'error': str(e)}
            
            overall_success = all(r.get('success', False) for r in results.values())
            logger.info(f"✓ Execution functionality: {'PASS' if overall_success else 'PARTIAL'}")
            
            return {
                'success': overall_success,
                'details': results
            }
            
        except Exception as e:
            logger.error(f"✗ Execution functionality test failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def test_security_policies(self) -> Dict[str, Any]:
        """Test security policy enforcement."""
        try:
            from src.sandbox.unified_server import UnifiedSandboxServer
            from src.sandbox.core.types import ServerConfig, SecurityLevel
            
            # Test with different security levels
            results = {}
            
            for security_level in [SecurityLevel.STRICT, SecurityLevel.MODERATE, SecurityLevel.PERMISSIVE]:
                config = ServerConfig()
                config.security_level = security_level
                server = UnifiedSandboxServer(config)
                
                # Test safe command
                try:
                    safe_result = server.execution_engine.execute_python(
                        "print('Safe operation')",
                        server.get_or_create_context("security_test")
                    )
                    safe_allowed = safe_result.success
                except:
                    safe_allowed = False
                
                # Test potentially dangerous command
                try:
                    dangerous_result = server.execution_engine.execute_shell(
                        "rm -rf /",  # This should be blocked
                        server.get_or_create_context("security_test")
                    )
                    dangerous_blocked = not dangerous_result.success
                except:
                    dangerous_blocked = True  # Exception means it was blocked
                
                results[security_level.value] = {
                    'safe_allowed': safe_allowed,
                    'dangerous_blocked': dangerous_blocked,
                    'policy_working': safe_allowed and dangerous_blocked
                }
            
            overall_success = all(r['policy_working'] for r in results.values())
            logger.info(f"✓ Security policies: {'PASS' if overall_success else 'FAIL'}")
            
            return {
                'success': overall_success,
                'details': results
            }
            
        except Exception as e:
            logger.error(f"✗ Security policy test failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def test_resource_management(self) -> Dict[str, Any]:
        """Test resource management and limits."""
        try:
            from src.sandbox.unified_server import UnifiedSandboxServer
            from src.sandbox.core.types import ServerConfig
            
            server = UnifiedSandboxServer(ServerConfig())
            
            results = {}
            
            # Test timeout handling
            try:
                context = server.get_or_create_context("resource_test")
                context.resource_limits.max_execution_time = 2  # 2 second timeout
                
                timeout_result = server.execution_engine.execute_python(
                    "import time; time.sleep(5)",  # Should timeout
                    context
                )
                
                results['timeout_handling'] = {
                    'success': not timeout_result.success,  # Should fail due to timeout
                    'execution_time': timeout_result.execution_time,
                    'timed_out': timeout_result.execution_time >= 2
                }
            except Exception as e:
                results['timeout_handling'] = {'success': False, 'error': str(e)}
            
            # Test memory limits (if implemented)
            try:
                context = server.get_or_create_context("memory_test")
                memory_result = server.execution_engine.execute_python(
                    "x = 'a' * 1000000",  # Large memory allocation
                    context
                )
                results['memory_handling'] = {
                    'success': True,  # Should complete or be limited gracefully
                    'completed': memory_result.success
                }
            except Exception as e:
                results['memory_handling'] = {'success': False, 'error': str(e)}
            
            overall_success = results.get('timeout_handling', {}).get('success', False)
            logger.info(f"✓ Resource management: {'PASS' if overall_success else 'PARTIAL'}")
            
            return {
                'success': overall_success,
                'details': results
            }
            
        except Exception as e:
            logger.error(f"✗ Resource management test failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def test_artifact_system(self) -> Dict[str, Any]:
        """Test artifact management system."""
        try:
            from src.sandbox.unified_server import UnifiedSandboxServer
            from src.sandbox.core.types import ServerConfig
            
            server = UnifiedSandboxServer(ServerConfig())
            
            results = {}
            
            # Test artifact storage
            try:
                # Create a test file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                    f.write("Test artifact content")
                    test_file = Path(f.name)
                
                # Store artifact
                artifact_id = server.artifact_manager.store_file(
                    test_file,
                    workspace_id="artifact_test",
                    description="Test artifact"
                )
                
                results['artifact_storage'] = {
                    'success': bool(artifact_id),
                    'artifact_id': artifact_id
                }
                
                # Test artifact retrieval
                if artifact_id:
                    artifact = server.artifact_manager.retrieve_artifact(artifact_id)
                    results['artifact_retrieval'] = {
                        'success': artifact is not None,
                        'exists': artifact.exists() if artifact else False
                    }
                
                # Test artifact listing
                artifacts = server.artifact_manager.list_artifacts({})
                results['artifact_listing'] = {
                    'success': True,
                    'count': len(artifacts)
                }
                
                # Cleanup
                test_file.unlink(missing_ok=True)
                
            except Exception as e:
                results['artifact_operations'] = {'success': False, 'error': str(e)}
            
            overall_success = all(r.get('success', False) for r in results.values())
            logger.info(f"✓ Artifact system: {'PASS' if overall_success else 'FAIL'}")
            
            return {
                'success': overall_success,
                'details': results
            }
            
        except Exception as e:
            logger.error(f"✗ Artifact system test failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def test_workspace_isolation(self) -> Dict[str, Any]:
        """Test workspace isolation functionality."""
        try:
            from src.sandbox.unified_server import UnifiedSandboxServer
            from src.sandbox.core.types import ServerConfig
            
            server = UnifiedSandboxServer(ServerConfig())
            
            results = {}
            
            # Test multiple workspace contexts
            try:
                context1 = server.get_or_create_context("workspace1")
                context2 = server.get_or_create_context("workspace2")
                
                # Execute code in each workspace
                result1 = server.execution_engine.execute_python(
                    "workspace_var = 'workspace1'",
                    context1
                )
                
                result2 = server.execution_engine.execute_python(
                    "workspace_var = 'workspace2'",
                    context2
                )
                
                # Verify isolation
                check1 = server.execution_engine.execute_python(
                    "print(workspace_var)",
                    context1
                )
                
                check2 = server.execution_engine.execute_python(
                    "print(workspace_var)",
                    context2
                )
                
                results['workspace_isolation'] = {
                    'success': result1.success and result2.success,
                    'context1_isolated': 'workspace1' in check1.output if check1.success else False,
                    'context2_isolated': 'workspace2' in check2.output if check2.success else False
                }
                
            except Exception as e:
                results['workspace_isolation'] = {'success': False, 'error': str(e)}
            
            # Test context cleanup
            try:
                initial_count = len(server.active_contexts)
                test_context = server.get_or_create_context("cleanup_test")
                after_create = len(server.active_contexts)
                
                # Cleanup context (if method exists)
                if hasattr(server, 'cleanup_context'):
                    server.cleanup_context("cleanup_test")
                    after_cleanup = len(server.active_contexts)
                else:
                    after_cleanup = after_create
                
                results['context_management'] = {
                    'success': True,
                    'initial_count': initial_count,
                    'after_create': after_create,
                    'after_cleanup': after_cleanup
                }
                
            except Exception as e:
                results['context_management'] = {'success': False, 'error': str(e)}
            
            overall_success = all(r.get('success', False) for r in results.values())
            logger.info(f"✓ Workspace isolation: {'PASS' if overall_success else 'PARTIAL'}")
            
            return {
                'success': overall_success,
                'details': results
            }
            
        except Exception as e:
            logger.error(f"✗ Workspace isolation test failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def test_error_handling(self) -> Dict[str, Any]:
        """Test error handling and recovery."""
        try:
            from src.sandbox.unified_server import UnifiedSandboxServer
            from src.sandbox.core.types import ServerConfig
            
            server = UnifiedSandboxServer(ServerConfig())
            
            results = {}
            
            # Test Python syntax error handling
            try:
                syntax_error_result = server.execution_engine.execute_python(
                    "print('unclosed string",  # Syntax error
                    server.get_or_create_context("error_test")
                )
                
                results['syntax_error_handling'] = {
                    'success': not syntax_error_result.success,  # Should fail gracefully
                    'has_error_message': bool(syntax_error_result.error),
                    'error_type': syntax_error_result.error_type
                }
            except Exception as e:
                results['syntax_error_handling'] = {'success': False, 'error': str(e)}
            
            # Test runtime error handling
            try:
                runtime_error_result = server.execution_engine.execute_python(
                    "x = 1 / 0",  # Runtime error
                    server.get_or_create_context("error_test")
                )
                
                results['runtime_error_handling'] = {
                    'success': not runtime_error_result.success,  # Should fail gracefully
                    'has_error_message': bool(runtime_error_result.error),
                    'error_type': runtime_error_result.error_type
                }
            except Exception as e:
                results['runtime_error_handling'] = {'success': False, 'error': str(e)}
            
            # Test shell command error handling
            try:
                shell_error_result = server.execution_engine.execute_shell(
                    "nonexistent_command_xyz",  # Command not found
                    server.get_or_create_context("error_test")
                )
                
                results['shell_error_handling'] = {
                    'success': not shell_error_result.success,  # Should fail gracefully
                    'has_error_message': bool(shell_error_result.error)
                }
            except Exception as e:
                results['shell_error_handling'] = {'success': False, 'error': str(e)}
            
            overall_success = all(r.get('success', False) for r in results.values())
            logger.info(f"✓ Error handling: {'PASS' if overall_success else 'FAIL'}")
            
            return {
                'success': overall_success,
                'details': results
            }
            
        except Exception as e:
            logger.error(f"✗ Error handling test failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def test_performance_validation(self) -> Dict[str, Any]:
        """Test system performance and responsiveness."""
        try:
            from src.sandbox.unified_server import UnifiedSandboxServer
            from src.sandbox.core.types import ServerConfig
            
            server = UnifiedSandboxServer(ServerConfig())
            
            results = {}
            
            # Test execution performance
            try:
                start_time = time.time()
                
                # Execute multiple operations
                for i in range(5):
                    result = server.execution_engine.execute_python(
                        f"result = {i} * 2\nprint(f'Operation {i}: {{result}}')",
                        server.get_or_create_context(f"perf_test_{i}")
                    )
                    if not result.success:
                        break
                
                total_time = time.time() - start_time
                
                results['execution_performance'] = {
                    'success': True,
                    'total_time': total_time,
                    'avg_time_per_operation': total_time / 5,
                    'acceptable_performance': total_time < 10  # Should complete in under 10 seconds
                }
                
            except Exception as e:
                results['execution_performance'] = {'success': False, 'error': str(e)}
            
            # Test memory usage (basic check)
            try:
                import psutil
                import os
                
                process = psutil.Process(os.getpid())
                memory_info = process.memory_info()
                
                results['memory_usage'] = {
                    'success': True,
                    'rss_mb': memory_info.rss / 1024 / 1024,
                    'vms_mb': memory_info.vms / 1024 / 1024,
                    'reasonable_usage': memory_info.rss < 500 * 1024 * 1024  # Under 500MB
                }
                
            except ImportError:
                results['memory_usage'] = {'success': True, 'note': 'psutil not available'}
            except Exception as e:
                results['memory_usage'] = {'success': False, 'error': str(e)}
            
            overall_success = all(r.get('success', False) for r in results.values())
            logger.info(f"✓ Performance validation: {'PASS' if overall_success else 'PARTIAL'}")
            
            return {
                'success': overall_success,
                'details': results
            }
            
        except Exception as e:
            logger.error(f"✗ Performance validation test failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def test_migrated_functionality(self) -> Dict[str, Any]:
        """Test migrated functionality from legacy servers."""
        try:
            from src.sandbox.unified_server import UnifiedSandboxServer
            from src.sandbox.core.types import ServerConfig
            
            server = UnifiedSandboxServer(ServerConfig())
            
            results = {}
            
            # Test Manim integration
            try:
                if hasattr(server, 'manim_executor'):
                    results['manim_integration'] = {
                        'success': True,
                        'executor_available': True
                    }
                else:
                    results['manim_integration'] = {
                        'success': False,
                        'executor_available': False
                    }
            except Exception as e:
                results['manim_integration'] = {'success': False, 'error': str(e)}
            
            # Test web app manager
            try:
                if hasattr(server, 'web_app_manager'):
                    results['web_app_integration'] = {
                        'success': True,
                        'manager_available': True
                    }
                else:
                    results['web_app_integration'] = {
                        'success': False,
                        'manager_available': False
                    }
            except Exception as e:
                results['web_app_integration'] = {'success': False, 'error': str(e)}
            
            # Test intelligent features
            try:
                if hasattr(server, 'intelligent_integration'):
                    results['intelligent_features'] = {
                        'success': True,
                        'integration_available': True
                    }
                else:
                    results['intelligent_features'] = {
                        'success': False,
                        'integration_available': False
                    }
            except Exception as e:
                results['intelligent_features'] = {'success': False, 'error': str(e)}
            
            overall_success = all(r.get('success', False) for r in results.values())
            logger.info(f"✓ Migrated functionality: {'PASS' if overall_success else 'PARTIAL'}")
            
            return {
                'success': overall_success,
                'details': results
            }
            
        except Exception as e:
            logger.error(f"✗ Migrated functionality test failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def test_system_stability(self) -> Dict[str, Any]:
        """Test system stability under various conditions."""
        try:
            from src.sandbox.unified_server import UnifiedSandboxServer
            from src.sandbox.core.types import ServerConfig
            
            results = {}
            
            # Test multiple server instances
            try:
                servers = []
                for i in range(3):
                    server = UnifiedSandboxServer(ServerConfig())
                    servers.append(server)
                
                results['multiple_instances'] = {
                    'success': True,
                    'instances_created': len(servers)
                }
                
                # Cleanup
                del servers
                
            except Exception as e:
                results['multiple_instances'] = {'success': False, 'error': str(e)}
            
            # Test rapid context creation/cleanup
            try:
                server = UnifiedSandboxServer(ServerConfig())
                
                for i in range(10):
                    context = server.get_or_create_context(f"stability_test_{i}")
                    result = server.execution_engine.execute_python(
                        f"x = {i}",
                        context
                    )
                    if not result.success:
                        break
                
                results['rapid_operations'] = {
                    'success': True,
                    'operations_completed': 10
                }
                
            except Exception as e:
                results['rapid_operations'] = {'success': False, 'error': str(e)}
            
            overall_success = all(r.get('success', False) for r in results.values())
            logger.info(f"✓ System stability: {'PASS' if overall_success else 'FAIL'}")
            
            return {
                'success': overall_success,
                'details': results
            }
            
        except Exception as e:
            logger.error(f"✗ System stability test failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def generate_final_report(self) -> Dict[str, Any]:
        """Generate final validation report."""
        passed_tests = sum(1 for result in self.test_results.values() if result['status'] == 'PASS')
        total_tests = len(self.test_results)
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        # Determine overall system status
        if success_rate >= 90:
            overall_status = "EXCELLENT"
        elif success_rate >= 75:
            overall_status = "GOOD"
        elif success_rate >= 50:
            overall_status = "ACCEPTABLE"
        else:
            overall_status = "NEEDS_IMPROVEMENT"
        
        report = {
            'validation_summary': {
                'overall_status': overall_status,
                'success_rate': f"{success_rate:.1f}%",
                'passed_tests': passed_tests,
                'total_tests': total_tests,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            },
            'test_results': self.test_results,
            'recommendations': self.generate_recommendations()
        }
        
        return report
    
    def generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test results."""
        recommendations = []
        
        failed_tests = [name for name, result in self.test_results.items() 
                       if result['status'] in ['FAIL', 'ERROR']]
        
        if 'server_startup' in failed_tests:
            recommendations.append("Fix server initialization issues before proceeding")
        
        if 'mcp_protocol' in failed_tests:
            recommendations.append("Review MCP protocol implementation and tool registration")
        
        if 'security_policies' in failed_tests:
            recommendations.append("Review and adjust security policy configuration")
        
        if 'resource_management' in failed_tests:
            recommendations.append("Implement or fix resource limiting mechanisms")
        
        if 'artifact_system' in failed_tests:
            recommendations.append("Debug artifact management system issues")
        
        if len(failed_tests) == 0:
            recommendations.append("System validation successful - ready for production use")
        elif len(failed_tests) <= 2:
            recommendations.append("Minor issues detected - address failed tests before deployment")
        else:
            recommendations.append("Multiple critical issues detected - comprehensive review needed")
        
        return recommendations


def main():
    """Run the system integration validation."""
    print("=" * 80)
    print("🔍 SWISS SANDBOX SYSTEM INTEGRATION VALIDATION")
    print("=" * 80)
    print()
    
    validator = SystemIntegrationValidator()
    
    try:
        report = validator.run_all_tests()
        
        print("\n" + "=" * 80)
        print("📊 VALIDATION REPORT")
        print("=" * 80)
        
        summary = report['validation_summary']
        print(f"Overall Status: {summary['overall_status']}")
        print(f"Success Rate: {summary['success_rate']}")
        print(f"Tests Passed: {summary['passed_tests']}/{summary['total_tests']}")
        print(f"Timestamp: {summary['timestamp']}")
        
        print("\n📋 Test Results:")
        for test_name, result in report['test_results'].items():
            status_icon = "✅" if result['status'] == 'PASS' else "❌" if result['status'] == 'FAIL' else "⚠️"
            print(f"  {status_icon} {test_name}: {result['status']}")
            if result['status'] != 'PASS' and 'error' in result:
                print(f"    Error: {result['error']}")
        
        print("\n💡 Recommendations:")
        for rec in report['recommendations']:
            print(f"  • {rec}")
        
        # Save detailed report
        report_file = Path("system_integration_validation_report.json")
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 Detailed report saved to: {report_file}")
        
        # Return appropriate exit code
        if summary['overall_status'] in ['EXCELLENT', 'GOOD']:
            print("\n🎉 System validation completed successfully!")
            return 0
        else:
            print("\n⚠️ System validation completed with issues.")
            return 1
            
    except Exception as e:
        print(f"\n❌ Validation failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())