"""
Unified Swiss Sandbox MCP Server - Swiss army knife of AI toolkits

This is the consolidated, authoritative MCP server that replaces all fragmented
server implementations. It provides a single entry point for all Swiss Sandbox
functionality with proper error handling, security, and resource management.
"""

import json
import logging
import sys
import traceback
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

from fastmcp import FastMCP

# Import core types
from .core.types import (
    SecurityLevel, ResourceLimits, ExecutionContext, 
    ExecutionResult, ServerConfig
)

# Import logging and error handling system
from .core.logging_system import (
    StructuredLogger, ErrorHandler, PerformanceMonitor, 
    ErrorCategory, with_error_handling, with_performance_monitoring
)
from .core.health_monitor import HealthMonitor

# Configure basic logging as fallback
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class UnifiedSandboxServer:
    """
    Unified Swiss Sandbox MCP Server
    
    This server consolidates all Swiss Sandbox functionality into a single,
    reliable, and maintainable MCP server implementation.
    """
    
    def __init__(self, config: Optional[ServerConfig] = None):
        """Initialize the unified server."""
        self.config = config or ServerConfig()
        self.mcp = FastMCP("Swiss Sandbox Ultimate")
        
        # Initialize logging and error handling system
        log_dir = Path("logs")
        self.structured_logger = StructuredLogger("unified_server", log_dir)
        self.error_handler = ErrorHandler(self.structured_logger)
        self.performance_monitor = PerformanceMonitor(self.structured_logger)
        self.health_monitor = HealthMonitor(
            self.structured_logger, self.error_handler, self.performance_monitor
        )
        
        # Import ExecutionEngine here to avoid circular imports
        from .core.execution_engine import ExecutionEngine
        
        # Core components
        self.execution_engine = ExecutionEngine()
        self.security_manager = None  # Will be initialized in task 3
        
        # Initialize artifact manager (Task 4)
        from .core.artifact_manager import ArtifactManager
        self.artifact_manager = ArtifactManager(config=self.config)
        
        self.workspace_manager = None  # Will be initialized in task 5
        
        # Initialize migrated functionality (Task 7)
        from .migration import (
            ManimExecutor, WebAppManager, ArtifactInterceptor, 
            IntelligentSandboxIntegration
        )
        
        # Determine project root
        self.project_root = Path(__file__).parent.parent.parent
        
        # Initialize migrated components
        self.manim_executor = ManimExecutor(self.project_root)
        self.web_app_manager = WebAppManager(self.project_root)
        self.intelligent_integration = IntelligentSandboxIntegration(self.project_root)
        
        # Track active workspace sessions for intelligent features
        self.active_workspace_sessions = {}
        
        # Server state
        self.active_contexts: Dict[str, ExecutionContext] = {}
        self.server_start_time = datetime.now()
        
        # Configure logging
        logging.getLogger().setLevel(getattr(logging, self.config.log_level))
        
        self.structured_logger.info(
            f"Initialized UnifiedSandboxServer with config",
            component="unified_server",
            metadata=self.config.to_dict()
        )
        
        # Register core tools
        self._register_core_tools()
        self._register_execution_tools()
        self._register_artifact_tools()
        self._register_migrated_tools()
        self._register_diagnostic_tools()
    
    def _register_core_tools(self):
        """Register core MCP tools."""
        
        @self.mcp.tool()
        def server_info() -> str:
            """Get information about the Swiss Sandbox server."""
            info = {
                'server_name': 'Swiss Sandbox Ultimate',
                'version': '2.0.0',
                'start_time': self.server_start_time.isoformat(),
                'config': self.config.to_dict(),
                'active_contexts': len(self.active_contexts),
                'features': {
                    'python_execution': True,
                    'shell_execution': True,
                    'manim_support': self.config.enable_manim,
                    'web_apps': self.config.enable_web_apps,
                    'intelligent_features': self.config.enable_intelligent_features,
                    'artifact_management': True,
                    'workspace_isolation': True
                }
            }
            return json.dumps(info, indent=2)
        
        @self.mcp.tool()
        def health_check() -> str:
            """Perform a comprehensive health check of the server."""
            try:
                with self.performance_monitor.measure_operation("unified_server", "health_check"):
                    health_report = self.health_monitor.get_overall_health()
                    return json.dumps(health_report, indent=2)
                    
            except Exception as e:
                self.error_handler.handle_error(
                    e, ErrorCategory.SYSTEM, "unified_server",
                    {'operation': 'health_check'}
                )
                return json.dumps({
                    'status': 'unhealthy',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }, indent=2)
        
        @self.mcp.tool()
        def create_execution_context(
            workspace_id: str,
            user_id: Optional[str] = None,
            security_level: str = "moderate"
        ) -> str:
            """Create a new execution context."""
            try:
                # Validate security level
                try:
                    sec_level = SecurityLevel(security_level)
                except ValueError:
                    return json.dumps({
                        'success': False,
                        'error': f'Invalid security level: {security_level}. Valid options: {[e.value for e in SecurityLevel]}'
                    })
                
                # Create execution context
                context = ExecutionContext(
                    workspace_id=workspace_id,
                    user_id=user_id,
                    security_level=sec_level
                )
                
                # Store context
                self.active_contexts[workspace_id] = context
                
                logger.info(f"Created execution context for workspace: {workspace_id}")
                
                return json.dumps({
                    'success': True,
                    'workspace_id': workspace_id,
                    'context_info': {
                        'security_level': sec_level.value,
                        'artifacts_dir': str(context.artifacts_dir),
                        'resource_limits': {
                            'max_execution_time': context.resource_limits.max_execution_time,
                            'max_memory_mb': context.resource_limits.max_memory_mb
                        }
                    }
                }, indent=2)
                
            except Exception as e:
                logger.error(f"Failed to create execution context: {e}")
                return json.dumps({
                    'success': False,
                    'error': str(e),
                    'traceback': traceback.format_exc()
                })
        
        @self.mcp.tool()
        def list_contexts() -> str:
            """List all active execution contexts."""
            contexts_info = []
            for workspace_id, context in self.active_contexts.items():
                contexts_info.append({
                    'workspace_id': workspace_id,
                    'user_id': context.user_id,
                    'security_level': context.security_level.value,
                    'artifacts_dir': str(context.artifacts_dir),
                    'session_id': context.session_id
                })
            
            return json.dumps({
                'active_contexts': len(self.active_contexts),
                'contexts': contexts_info
            }, indent=2)
        
        @self.mcp.tool()
        def cleanup_context(workspace_id: str) -> str:
            """Clean up an execution context."""
            try:
                if workspace_id not in self.active_contexts:
                    return json.dumps({
                        'success': False,
                        'error': f'Context not found: {workspace_id}'
                    })
                
                context = self.active_contexts[workspace_id]
                
                # Clean up artifacts directory
                if context.artifacts_dir and context.artifacts_dir.exists():
                    import shutil
                    shutil.rmtree(context.artifacts_dir, ignore_errors=True)
                
                # Remove from active contexts
                del self.active_contexts[workspace_id]
                
                logger.info(f"Cleaned up execution context: {workspace_id}")
                
                return json.dumps({
                    'success': True,
                    'workspace_id': workspace_id,
                    'message': 'Context cleaned up successfully'
                })
                
            except Exception as e:
                logger.error(f"Failed to cleanup context {workspace_id}: {e}")
                return json.dumps({
                    'success': False,
                    'error': str(e),
                    'traceback': traceback.format_exc()
                })
    
    def _register_execution_tools(self):
        """Register execution-related MCP tools."""
        
        @self.mcp.tool()
        def execute_python(
            code: str,
            workspace_id: str = "default",
            timeout: int = 30
        ) -> str:
            """Execute Python code in a sandboxed environment."""
            try:
                # Get or create execution context
                context = self.get_or_create_context(workspace_id)
                context.resource_limits.max_execution_time = timeout
                
                # Execute code
                result = self.execution_engine.execute_python(code, context)
                
                return json.dumps({
                    'success': result.success,
                    'output': result.output,
                    'error': result.error,
                    'error_type': result.error_type,
                    'execution_time': result.execution_time,
                    'artifacts': result.artifacts,
                    'metadata': result.metadata
                }, indent=2)
                
            except Exception as e:
                logger.error(f"Python execution failed: {e}")
                return json.dumps({
                    'success': False,
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'traceback': traceback.format_exc()
                })
        
        @self.mcp.tool()
        def execute_shell(
            command: str,
            workspace_id: str = "default",
            timeout: int = 30
        ) -> str:
            """Execute shell command in a sandboxed environment."""
            try:
                # Get or create execution context
                context = self.get_or_create_context(workspace_id)
                context.resource_limits.max_execution_time = timeout
                
                # Execute command
                result = self.execution_engine.execute_shell(command, context)
                
                return json.dumps({
                    'success': result.success,
                    'output': result.output,
                    'error': result.error,
                    'error_type': result.error_type,
                    'execution_time': result.execution_time,
                    'artifacts': result.artifacts,
                    'metadata': result.metadata
                }, indent=2)
                
            except Exception as e:
                logger.error(f"Shell execution failed: {e}")
                return json.dumps({
                    'success': False,
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'traceback': traceback.format_exc()
                })
        
        @self.mcp.tool()
        def execute_manim(
            script: str,
            workspace_id: str = "default",
            quality: str = "medium",
            scene_name: Optional[str] = None,
            timeout: int = 60
        ) -> str:
            """Execute Manim script to create mathematical animations."""
            try:
                # Get or create execution context
                context = self.get_or_create_context(workspace_id)
                context.resource_limits.max_execution_time = timeout
                
                # Execute Manim script
                result = self.execution_engine.execute_manim(
                    script, context, quality, scene_name
                )
                
                return json.dumps({
                    'success': result.success,
                    'output': result.output,
                    'error': result.error,
                    'error_type': result.error_type,
                    'execution_time': result.execution_time,
                    'artifacts': result.artifacts,
                    'metadata': result.metadata
                }, indent=2)
                
            except Exception as e:
                logger.error(f"Manim execution failed: {e}")
                return json.dumps({
                    'success': False,
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'traceback': traceback.format_exc()
                })
        
        @self.mcp.tool()
        def get_execution_history(
            workspace_id: Optional[str] = None,
            language: Optional[str] = None,
            limit: int = 50
        ) -> str:
            """Get execution history with optional filtering."""
            try:
                history = self.execution_engine.get_execution_history(
                    context_id=workspace_id,
                    language=language,
                    limit=limit
                )
                
                history_data = [record.to_dict() for record in history]
                
                return json.dumps({
                    'success': True,
                    'history': history_data,
                    'count': len(history_data)
                }, indent=2)
                
            except Exception as e:
                logger.error(f"Failed to get execution history: {e}")
                return json.dumps({
                    'success': False,
                    'error': str(e),
                    'traceback': traceback.format_exc()
                })
        
        @self.mcp.tool()
        def get_execution_statistics() -> str:
            """Get execution engine statistics."""
            try:
                stats = self.execution_engine.get_statistics()
                
                return json.dumps({
                    'success': True,
                    'statistics': stats
                }, indent=2)
                
            except Exception as e:
                logger.error(f"Failed to get execution statistics: {e}")
                return json.dumps({
                    'success': False,
                    'error': str(e),
                    'traceback': traceback.format_exc()
                })
    
    def _register_artifact_tools(self):
        """Register artifact management MCP tools."""
        
        @self.mcp.tool()
        def store_artifact(
            file_path: str,
            workspace_id: Optional[str] = None,
            user_id: Optional[str] = None,
            tags: Optional[str] = None,
            description: Optional[str] = None
        ) -> str:
            """Store a file as an artifact in the artifact management system."""
            try:
                file_path_obj = Path(file_path)
                if not file_path_obj.exists():
                    return json.dumps({
                        'success': False,
                        'error': f'File not found: {file_path}'
                    })
                
                # Parse tags if provided
                tag_list = []
                if tags:
                    tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
                
                # Store the artifact
                artifact_id = self.artifact_manager.store_file(
                    file_path_obj,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    tags=tag_list,
                    description=description
                )
                
                return json.dumps({
                    'success': True,
                    'artifact_id': artifact_id,
                    'message': f'Artifact stored successfully: {file_path_obj.name}'
                }, indent=2)
                
            except Exception as e:
                logger.error(f"Failed to store artifact: {e}")
                return json.dumps({
                    'success': False,
                    'error': str(e),
                    'traceback': traceback.format_exc()
                })
        
        @self.mcp.tool()
        def retrieve_artifact(artifact_id: str) -> str:
            """Retrieve an artifact by ID and get its metadata and content path."""
            try:
                artifact = self.artifact_manager.retrieve_artifact(artifact_id)
                
                if artifact is None:
                    return json.dumps({
                        'success': False,
                        'error': f'Artifact not found: {artifact_id}'
                    })
                
                return json.dumps({
                    'success': True,
                    'artifact': {
                        'metadata': artifact.metadata.to_dict(),
                        'storage_path': str(artifact.storage_path),
                        'exists': artifact.exists(),
                        'size_bytes': artifact.metadata.size
                    }
                }, indent=2)
                
            except Exception as e:
                logger.error(f"Failed to retrieve artifact: {e}")
                return json.dumps({
                    'success': False,
                    'error': str(e),
                    'traceback': traceback.format_exc()
                })
        
        @self.mcp.tool()
        def list_artifacts(
            category: Optional[str] = None,
            workspace_id: Optional[str] = None,
            user_id: Optional[str] = None,
            tags: Optional[str] = None,
            limit: int = 50
        ) -> str:
            """List artifacts with optional filtering."""
            try:
                # Build filter criteria
                filter_criteria = {}
                if category:
                    filter_criteria['category'] = category
                if workspace_id:
                    filter_criteria['workspace_id'] = workspace_id
                if user_id:
                    filter_criteria['user_id'] = user_id
                if tags:
                    tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
                    filter_criteria['tags'] = tag_list
                
                # Get artifacts
                artifacts = self.artifact_manager.list_artifacts(filter_criteria)
                
                # Limit results
                if len(artifacts) > limit:
                    artifacts = artifacts[:limit]
                
                # Convert to serializable format
                artifact_data = []
                for artifact_info in artifacts:
                    artifact_data.append({
                        'artifact_id': artifact_info.artifact_id,
                        'name': artifact_info.name,
                        'size': artifact_info.size,
                        'created': artifact_info.created.isoformat(),
                        'category': artifact_info.category,
                        'tags': artifact_info.tags,
                        'version': artifact_info.version
                    })
                
                return json.dumps({
                    'success': True,
                    'artifacts': artifact_data,
                    'count': len(artifact_data),
                    'total_found': len(artifacts),
                    'limited': len(artifacts) > limit
                }, indent=2)
                
            except Exception as e:
                logger.error(f"Failed to list artifacts: {e}")
                return json.dumps({
                    'success': False,
                    'error': str(e),
                    'traceback': traceback.format_exc()
                })
        
        @self.mcp.tool()
        def get_artifact_content(artifact_id: str, as_text: bool = True) -> str:
            """Get the content of an artifact."""
            try:
                artifact = self.artifact_manager.retrieve_artifact(artifact_id)
                
                if artifact is None:
                    return json.dumps({
                        'success': False,
                        'error': f'Artifact not found: {artifact_id}'
                    })
                
                if not artifact.exists():
                    return json.dumps({
                        'success': False,
                        'error': f'Artifact file does not exist: {artifact_id}'
                    })
                
                try:
                    if as_text:
                        content = artifact.read_text()
                        content_type = 'text'
                    else:
                        content = artifact.read_content().hex()
                        content_type = 'binary_hex'
                    
                    return json.dumps({
                        'success': True,
                        'content': content,
                        'content_type': content_type,
                        'size': len(content),
                        'metadata': artifact.metadata.to_dict()
                    }, indent=2)
                    
                except UnicodeDecodeError:
                    # If text reading fails, return as binary
                    content = artifact.read_content().hex()
                    return json.dumps({
                        'success': True,
                        'content': content,
                        'content_type': 'binary_hex',
                        'size': len(content) // 2,  # Hex is 2 chars per byte
                        'metadata': artifact.metadata.to_dict(),
                        'note': 'Content returned as hex due to binary data'
                    }, indent=2)
                
            except Exception as e:
                logger.error(f"Failed to get artifact content: {e}")
                return json.dumps({
                    'success': False,
                    'error': str(e),
                    'traceback': traceback.format_exc()
                })
        
        @self.mcp.tool()
        def cleanup_artifacts(
            max_age_days: Optional[int] = None,
            categories: Optional[str] = None,
            preserve_tags: Optional[str] = None,
            dry_run: bool = True
        ) -> str:
            """Clean up artifacts based on retention policy."""
            try:
                from .core.artifact_manager import RetentionPolicy
                
                # Parse categories and preserve tags
                categories_list = None
                if categories:
                    categories_list = [cat.strip() for cat in categories.split(',') if cat.strip()]
                
                preserve_tags_list = None
                if preserve_tags:
                    preserve_tags_list = [tag.strip() for tag in preserve_tags.split(',') if tag.strip()]
                
                # Create retention policy
                policy = RetentionPolicy(
                    max_age_days=max_age_days,
                    categories_to_clean=categories_list,
                    preserve_tags=preserve_tags_list
                )
                
                # Perform cleanup
                results = self.artifact_manager.cleanup_artifacts(policy)
                
                return json.dumps({
                    'success': True,
                    'cleanup_results': results,
                    'dry_run': dry_run
                }, indent=2)
                
            except Exception as e:
                logger.error(f"Failed to cleanup artifacts: {e}")
                return json.dumps({
                    'success': False,
                    'error': str(e),
                    'traceback': traceback.format_exc()
                })
        
        @self.mcp.tool()
        def get_storage_stats() -> str:
            """Get artifact storage statistics."""
            try:
                stats = self.artifact_manager.get_storage_stats()
                
                return json.dumps({
                    'success': True,
                    'storage_stats': stats
                }, indent=2)
                
            except Exception as e:
                logger.error(f"Failed to get storage stats: {e}")
                return json.dumps({
                    'success': False,
                    'error': str(e),
                    'traceback': traceback.format_exc()
                })
        
        @self.mcp.tool()
        def auto_cleanup_artifacts() -> str:
            """Perform automatic cleanup based on server configuration."""
            try:
                results = self.artifact_manager.auto_cleanup()
                
                return json.dumps({
                    'success': True,
                    'cleanup_results': results,
                    'message': 'Automatic cleanup completed'
                }, indent=2)
                
            except Exception as e:
                logger.error(f"Failed to perform auto cleanup: {e}")
                return json.dumps({
                    'success': False,
                    'error': str(e),
                    'traceback': traceback.format_exc()
                })
    
    def _register_migrated_tools(self):
        """Register migrated functionality tools."""
        
        @self.mcp.tool()
        def create_manim_animation(
            script: str,
            workspace_id: str = "default",
            quality: str = "medium_quality",
            timeout: int = 300
        ) -> str:
            """Create a Manim animation from script code."""
            try:
                # Get or create execution context
                context = self.get_or_create_context(workspace_id)
                
                # Execute Manim script using migrated executor
                result = self.manim_executor.execute_manim_code(
                    script, context.artifacts_dir, quality
                )
                
                return json.dumps({
                    'success': result['success'],
                    'animation_id': result['animation_id'],
                    'video_path': result['video_path'],
                    'output': result['output'],
                    'error': result['error'],
                    'execution_time': result['execution_time'],
                    'scenes_found': result['scenes_found'],
                    'artifacts_dir': result['artifacts_dir']
                }, indent=2)
                
            except Exception as e:
                logger.error(f"Manim animation creation failed: {e}")
                return json.dumps({
                    'success': False,
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'traceback': traceback.format_exc()
                })
        
        @self.mcp.tool()
        def start_web_app(
            code: str,
            app_type: str = "flask",
            workspace_id: str = "default"
        ) -> str:
            """Start a web application (Flask or Streamlit)."""
            try:
                # Get or create execution context
                context = self.get_or_create_context(workspace_id)
                
                # Launch web app using migrated manager
                url = self.web_app_manager.launch_web_app(
                    code, app_type, context.artifacts_dir
                )
                
                if url:
                    return json.dumps({
                        'success': True,
                        'url': url,
                        'app_type': app_type,
                        'workspace_id': workspace_id,
                        'message': f'{app_type.title()} application launched successfully'
                    }, indent=2)
                else:
                    return json.dumps({
                        'success': False,
                        'error': f'Failed to launch {app_type} application',
                        'app_type': app_type
                    })
                
            except Exception as e:
                logger.error(f"Web app launch failed: {e}")
                return json.dumps({
                    'success': False,
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'traceback': traceback.format_exc()
                })
        
        @self.mcp.tool()
        def export_web_app(
            code: str,
            app_type: str = "flask",
            export_name: Optional[str] = None,
            workspace_id: str = "default"
        ) -> str:
            """Export a web application as Docker container and files."""
            try:
                # Get or create execution context
                context = self.get_or_create_context(workspace_id)
                
                # Export web app using migrated manager
                if app_type == "flask":
                    result = self.web_app_manager.export_flask_app(
                        code, context.artifacts_dir, export_name
                    )
                elif app_type == "streamlit":
                    result = self.web_app_manager.export_streamlit_app(
                        code, context.artifacts_dir, export_name
                    )
                else:
                    return json.dumps({
                        'success': False,
                        'error': f'Unsupported app type: {app_type}. Use "flask" or "streamlit".'
                    })
                
                return json.dumps(result, indent=2)
                
            except Exception as e:
                logger.error(f"Web app export failed: {e}")
                return json.dumps({
                    'success': False,
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'traceback': traceback.format_exc()
                })
        
        @self.mcp.tool()
        def execute_with_artifacts(
            code: str,
            workspace_id: str = "default",
            enable_matplotlib_capture: bool = True,
            enable_pil_capture: bool = True,
            timeout: int = 30
        ) -> str:
            """Execute Python code with automatic artifact capture."""
            try:
                # Get or create execution context
                context = self.get_or_create_context(workspace_id)
                context.resource_limits.max_execution_time = timeout
                
                # Set up artifact interceptor
                from .migration import ArtifactInterceptor
                interceptor = ArtifactInterceptor(context.artifacts_dir)
                
                # Apply monkey patches if requested
                matplotlib_patched = False
                pil_patched = False
                
                if enable_matplotlib_capture:
                    matplotlib_patched = interceptor.monkey_patch_matplotlib()
                
                if enable_pil_capture:
                    pil_patched = interceptor.monkey_patch_pil()
                
                # Execute code
                result = self.execution_engine.execute_python(code, context)
                
                # Collect artifacts
                artifacts = interceptor.collect_artifacts()
                
                return json.dumps({
                    'success': result.success,
                    'output': result.output,
                    'error': result.error,
                    'error_type': result.error_type,
                    'execution_time': result.execution_time,
                    'artifacts': artifacts,
                    'artifact_capture': {
                        'matplotlib_patched': matplotlib_patched,
                        'pil_patched': pil_patched,
                        'artifacts_collected': len(artifacts)
                    },
                    'metadata': result.metadata
                }, indent=2)
                
            except Exception as e:
                logger.error(f"Artifact execution failed: {e}")
                return json.dumps({
                    'success': False,
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'traceback': traceback.format_exc()
                })
        
        @self.mcp.tool()
        def create_workspace(
            source_path: str,
            workspace_id: Optional[str] = None
        ) -> str:
            """Create an isolated workspace from a source directory (intelligent sandbox feature)."""
            try:
                # Use intelligent sandbox integration
                result = self.intelligent_integration.create_workspace_session(
                    source_path, workspace_id
                )
                
                if result and result.get('success'):
                    # Store the session for later use
                    self.active_workspace_sessions[result['workspace_id']] = result
                    
                    return json.dumps({
                        'success': True,
                        'workspace_id': result['workspace_id'],
                        'sandbox_path': result['sandbox_path'],
                        'isolation_enabled': result['isolation_enabled'],
                        'message': f"Workspace '{result['workspace_id']}' created successfully",
                        'intelligent_features_available': self.intelligent_integration.components_available
                    }, indent=2)
                else:
                    return json.dumps({
                        'success': False,
                        'error': result.get('error', 'Failed to create workspace'),
                        'intelligent_features_available': self.intelligent_integration.components_available,
                        'message': 'Intelligent sandbox components may not be available'
                    })
                
            except Exception as e:
                logger.error(f"Workspace creation failed: {e}")
                return json.dumps({
                    'success': False,
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'traceback': traceback.format_exc()
                })
        
        @self.mcp.tool()
        def analyze_codebase(workspace_id: str) -> str:
            """Analyze codebase structure in a workspace (intelligent sandbox feature)."""
            try:
                if workspace_id not in self.active_workspace_sessions:
                    return json.dumps({
                        'success': False,
                        'error': f'Workspace "{workspace_id}" not found. Create it first with create_workspace.'
                    })
                
                workspace_session = self.active_workspace_sessions[workspace_id]
                
                # Use intelligent sandbox integration
                result = self.intelligent_integration.analyze_codebase(workspace_session)
                
                if result and result.get('success'):
                    return json.dumps({
                        'success': True,
                        'workspace_id': workspace_id,
                        'analysis': result['analysis'],
                        'message': f"Codebase analysis completed for workspace '{workspace_id}'"
                    }, indent=2)
                else:
                    return json.dumps({
                        'success': False,
                        'error': result.get('error', 'Failed to analyze codebase'),
                        'intelligent_features_available': self.intelligent_integration.components_available
                    })
                
            except Exception as e:
                logger.error(f"Codebase analysis failed: {e}")
                return json.dumps({
                    'success': False,
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'traceback': traceback.format_exc()
                })
        
        @self.mcp.tool()
        def destroy_workspace(workspace_id: str) -> str:
            """Destroy an isolated workspace and clean up resources."""
            try:
                if workspace_id not in self.active_workspace_sessions:
                    return json.dumps({
                        'success': False,
                        'error': f'Workspace "{workspace_id}" not found'
                    })
                
                # Remove from active sessions
                del self.active_workspace_sessions[workspace_id]
                
                # Clean up execution context if it exists
                if workspace_id in self.active_contexts:
                    context = self.active_contexts[workspace_id]
                    if context.artifacts_dir and context.artifacts_dir.exists():
                        shutil.rmtree(context.artifacts_dir, ignore_errors=True)
                    del self.active_contexts[workspace_id]
                
                return json.dumps({
                    'success': True,
                    'workspace_id': workspace_id,
                    'message': f"Workspace '{workspace_id}' destroyed successfully"
                }, indent=2)
                
            except Exception as e:
                logger.error(f"Workspace destruction failed: {e}")
                return json.dumps({
                    'success': False,
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'traceback': traceback.format_exc()
                })
        
        @self.mcp.tool()
        def list_manim_animations(workspace_id: Optional[str] = None) -> str:
            """List all Manim animations in workspace(s)."""
            try:
                animations = []
                
                if workspace_id:
                    # List animations for specific workspace
                    if workspace_id in self.active_contexts:
                        context = self.active_contexts[workspace_id]
                        if context.artifacts_dir and context.artifacts_dir.exists():
                            manim_dirs = list(context.artifacts_dir.glob("manim_*"))
                            for manim_dir in manim_dirs:
                                animation_id = manim_dir.name.replace("manim_", "")
                                video_files = list(manim_dir.rglob("*.mp4"))
                                animations.append({
                                    'animation_id': animation_id,
                                    'workspace_id': workspace_id,
                                    'directory': str(manim_dir),
                                    'video_files': [str(f) for f in video_files],
                                    'has_video': len(video_files) > 0
                                })
                else:
                    # List animations for all workspaces
                    for ws_id, context in self.active_contexts.items():
                        if context.artifacts_dir and context.artifacts_dir.exists():
                            manim_dirs = list(context.artifacts_dir.glob("manim_*"))
                            for manim_dir in manim_dirs:
                                animation_id = manim_dir.name.replace("manim_", "")
                                video_files = list(manim_dir.rglob("*.mp4"))
                                animations.append({
                                    'animation_id': animation_id,
                                    'workspace_id': ws_id,
                                    'directory': str(manim_dir),
                                    'video_files': [str(f) for f in video_files],
                                    'has_video': len(video_files) > 0
                                })
                
                return json.dumps({
                    'success': True,
                    'animations': animations,
                    'count': len(animations),
                    'manim_available': self.manim_executor.manim_available
                }, indent=2)
                
            except Exception as e:
                logger.error(f"Failed to list Manim animations: {e}")
                return json.dumps({
                    'success': False,
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'traceback': traceback.format_exc()
                })
        
        @self.mcp.tool()
        def get_migrated_features_status() -> str:
            """Get status of all migrated features and their availability."""
            try:
                return json.dumps({
                    'success': True,
                    'migrated_features': {
                        'manim_executor': {
                            'available': self.manim_executor.manim_available,
                            'project_root': str(self.manim_executor.project_root),
                            'venv_path': str(self.manim_executor.venv_path)
                        },
                        'web_app_manager': {
                            'available': True,
                            'active_servers': len(self.web_app_manager.active_web_servers),
                            'server_urls': list(self.web_app_manager.active_web_servers.keys())
                        },
                        'intelligent_integration': {
                            'components_available': self.intelligent_integration.components_available,
                            'active_workspace_sessions': len(self.active_workspace_sessions)
                        }
                    },
                    'project_root': str(self.project_root)
                }, indent=2)
                
            except Exception as e:
                logger.error(f"Failed to get migrated features status: {e}")
                return json.dumps({
                    'success': False,
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'traceback': traceback.format_exc()
                })
    
    def get_or_create_context(self, workspace_id: str) -> ExecutionContext:
        """Get existing context or create a new one."""
        if workspace_id not in self.active_contexts:
            context = ExecutionContext(workspace_id=workspace_id)
            self.active_contexts[workspace_id] = context
            logger.info(f"Created new execution context for workspace: {workspace_id}")
        
        return self.active_contexts[workspace_id]
    
    def start(self, transport: str = 'stdio', host: str = '127.0.0.1', port: int = 8765):
        """Start the MCP server."""
        logger.info(f"Starting Swiss Sandbox Ultimate MCP Server")
        logger.info(f"Transport: {transport}")
        logger.info(f"Config: {self.config.to_dict()}")
        
        try:
            if transport == 'stdio':
                self.mcp.run()
            elif transport == 'http':
                self.mcp.run(transport='http', host=host, port=port)
            else:
                raise ValueError(f"Unsupported transport: {transport}")
                
        except KeyboardInterrupt:
            logger.info("Server shutdown requested")
            self._cleanup()
        except Exception as e:
            logger.error(f"Server error: {e}")
            logger.error(traceback.format_exc())
            raise
    
    def _register_diagnostic_tools(self):
        """Register diagnostic and monitoring MCP tools."""
        
        @self.mcp.tool()
        def get_diagnostic_report() -> str:
            """Get comprehensive diagnostic report."""
            try:
                with self.performance_monitor.measure_operation("unified_server", "diagnostic_report"):
                    report = self.health_monitor.get_diagnostic_report()
                    return json.dumps(report, indent=2)
                    
            except Exception as e:
                self.error_handler.handle_error(
                    e, ErrorCategory.SYSTEM, "unified_server",
                    {'operation': 'diagnostic_report'}
                )
                return json.dumps({
                    'success': False,
                    'error': str(e),
                    'traceback': traceback.format_exc()
                })
        
        @self.mcp.tool()
        def get_error_statistics() -> str:
            """Get error statistics and recovery information."""
            try:
                stats = self.error_handler.get_error_statistics()
                return json.dumps({
                    'success': True,
                    'error_statistics': stats
                }, indent=2)
                
            except Exception as e:
                return json.dumps({
                    'success': False,
                    'error': str(e),
                    'traceback': traceback.format_exc()
                })
        
        @self.mcp.tool()
        def get_performance_metrics() -> str:
            """Get performance metrics and monitoring data."""
            try:
                metrics = self.performance_monitor.get_performance_summary()
                return json.dumps({
                    'success': True,
                    'performance_metrics': metrics
                }, indent=2)
                
            except Exception as e:
                return json.dumps({
                    'success': False,
                    'error': str(e),
                    'traceback': traceback.format_exc()
                })
        
        @self.mcp.tool()
        def get_health_history(hours: int = 24) -> str:
            """Get health monitoring history."""
            try:
                history = self.health_monitor.get_health_history(hours)
                return json.dumps({
                    'success': True,
                    'health_history': history,
                    'hours_requested': hours,
                    'records_found': len(history)
                }, indent=2)
                
            except Exception as e:
                return json.dumps({
                    'success': False,
                    'error': str(e),
                    'traceback': traceback.format_exc()
                })
        
        @self.mcp.tool()
        def trigger_garbage_collection() -> str:
            """Trigger garbage collection and cleanup."""
            try:
                import gc
                import psutil
                
                # Get memory usage before
                process = psutil.Process()
                memory_before = process.memory_info().rss / 1024 / 1024  # MB
                
                # Trigger garbage collection
                collected = gc.collect()
                
                # Get memory usage after
                memory_after = process.memory_info().rss / 1024 / 1024  # MB
                memory_freed = memory_before - memory_after
                
                self.structured_logger.info(
                    f"Garbage collection completed",
                    component="unified_server",
                    metadata={
                        'objects_collected': collected,
                        'memory_before_mb': memory_before,
                        'memory_after_mb': memory_after,
                        'memory_freed_mb': memory_freed
                    }
                )
                
                return json.dumps({
                    'success': True,
                    'objects_collected': collected,
                    'memory_before_mb': memory_before,
                    'memory_after_mb': memory_after,
                    'memory_freed_mb': memory_freed
                }, indent=2)
                
            except Exception as e:
                return json.dumps({
                    'success': False,
                    'error': str(e),
                    'traceback': traceback.format_exc()
                })
    
    def _cleanup(self):
        """Clean up server resources."""
        self.structured_logger.info("Cleaning up server resources...", component="unified_server")
        
        # Clean up monitoring and logging components
        if hasattr(self, 'health_monitor'):
            self.health_monitor.cleanup()
        
        if hasattr(self, 'performance_monitor'):
            self.performance_monitor.cleanup()
        
        if hasattr(self, 'structured_logger'):
            self.structured_logger.cleanup()
        
        # Clean up execution engine
        if self.execution_engine:
            self.execution_engine.cleanup_all()
        
        # Clean up migrated functionality
        if hasattr(self, 'web_app_manager'):
            self.web_app_manager.cleanup_web_servers()
        
        # Clean up all active contexts
        for workspace_id in list(self.active_contexts.keys()):
            try:
                context = self.active_contexts[workspace_id]
                if context.artifacts_dir and context.artifacts_dir.exists():
                    import shutil
                    shutil.rmtree(context.artifacts_dir, ignore_errors=True)
                del self.active_contexts[workspace_id]
            except Exception as e:
                logger.error(f"Error cleaning up context {workspace_id}: {e}")
        
        # Clean up workspace sessions
        if hasattr(self, 'active_workspace_sessions'):
            self.active_workspace_sessions.clear()
        
        logger.info("Server cleanup completed")


def load_config(config_path: Optional[str] = None) -> ServerConfig:
    """Load server configuration from file or use defaults."""
    if config_path and Path(config_path).exists():
        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)
            return ServerConfig.from_dict(config_data)
        except Exception as e:
            logger.warning(f"Failed to load config from {config_path}: {e}")
            logger.info("Using default configuration")
    
    return ServerConfig()


def main():
    """Main entry point for the unified server."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Swiss Sandbox Ultimate MCP Server')
    parser.add_argument('--transport', choices=['stdio', 'http'], default='stdio',
                       help='Transport protocol (default: stdio)')
    parser.add_argument('--host', default='127.0.0.1',
                       help='Host for HTTP transport (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=8765,
                       help='Port for HTTP transport (default: 8765)')
    parser.add_argument('--config', type=str,
                       help='Path to configuration file')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       default='INFO', help='Logging level (default: INFO)')
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    config.log_level = args.log_level
    
    # Create and start server
    server = UnifiedSandboxServer(config)
    server.start(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()