"""
Codebase analysis components for the intelligent sandbox system.

Handles codebase structure analysis, pattern recognition, and dependency mapping.
"""

from .analyzer import CodebaseAnalyzer
from .models import CodebaseAnalysis, CodebaseStructure, DependencyGraph, Pattern, CodeMetrics

__all__ = [
    'CodebaseAnalyzer',
    'CodebaseAnalysis',
    'CodebaseStructure', 
    'DependencyGraph',
    'Pattern',
    'CodeMetrics'
]