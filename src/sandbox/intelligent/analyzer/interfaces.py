"""
Abstract interfaces for codebase analysis components.
"""

from abc import ABC, abstractmethod
from typing import List
from ..workspace.models import SandboxWorkspace
from .models import CodebaseAnalysis, CodebaseStructure, DependencyGraph, Pattern, CodeMetrics


class CodebaseAnalyzerInterface(ABC):
    """Abstract interface for codebase analysis operations."""
    
    @abstractmethod
    def analyze_structure(self, workspace: SandboxWorkspace) -> CodebaseStructure:
        """
        Analyze the structure of the codebase.
        
        Args:
            workspace: The sandbox workspace to analyze
            
        Returns:
            CodebaseStructure containing the analysis results
        """
        pass
    
    @abstractmethod
    def identify_patterns(self, structure: CodebaseStructure) -> List[Pattern]:
        """
        Identify architectural and code patterns in the codebase.
        
        Args:
            structure: The codebase structure to analyze
            
        Returns:
            List of identified patterns
        """
        pass
    
    @abstractmethod
    def extract_dependencies(self, workspace: SandboxWorkspace) -> DependencyGraph:
        """
        Extract and analyze dependencies from the codebase.
        
        Args:
            workspace: The sandbox workspace to analyze
            
        Returns:
            DependencyGraph containing dependency information
        """
        pass
    
    @abstractmethod
    def calculate_metrics(self, workspace: SandboxWorkspace) -> CodeMetrics:
        """
        Calculate code quality and complexity metrics.
        
        Args:
            workspace: The sandbox workspace to analyze
            
        Returns:
            CodeMetrics containing calculated metrics
        """
        pass
    
    @abstractmethod
    def generate_summary(self, analysis: CodebaseAnalysis) -> str:
        """
        Generate a comprehensive summary of the codebase analysis.
        
        Args:
            analysis: The complete codebase analysis
            
        Returns:
            String summary of the analysis
        """
        pass
    
    @abstractmethod
    def analyze_codebase(self, workspace: SandboxWorkspace) -> CodebaseAnalysis:
        """
        Perform complete codebase analysis.
        
        Args:
            workspace: The sandbox workspace to analyze
            
        Returns:
            Complete CodebaseAnalysis result
        """
        pass