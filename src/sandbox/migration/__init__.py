"""
Migration package for consolidating scattered functionality.
"""

from .legacy_functionality import (
    ManimExecutor,
    WebAppManager,
    ArtifactInterceptor,
    IntelligentSandboxIntegration
)

__all__ = [
    'ManimExecutor',
    'WebAppManager', 
    'ArtifactInterceptor',
    'IntelligentSandboxIntegration'
]