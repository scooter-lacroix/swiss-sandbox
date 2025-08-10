"""
Data models for codebase analysis.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional


@dataclass
class Pattern:
    """Represents an architectural or code pattern found in the codebase."""
    name: str
    type: str  # architectural, design, code_style, etc.
    confidence: float  # 0.0 to 1.0
    description: str
    locations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CodeMetrics:
    """Code quality and complexity metrics."""
    lines_of_code: int = 0
    cyclomatic_complexity: float = 0.0
    maintainability_index: float = 0.0
    test_coverage: float = 0.0
    technical_debt_ratio: float = 0.0
    duplication_percentage: float = 0.0
    metrics_by_file: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class DependencyInfo:
    """Information about a single dependency."""
    name: str
    version: str
    type: str  # direct, transitive, dev, etc.
    source: str  # npm, pip, maven, etc.
    license: Optional[str] = None
    vulnerabilities: List[str] = field(default_factory=list)


@dataclass
class DependencyGraph:
    """Represents the dependency structure of the codebase."""
    dependencies: List[DependencyInfo] = field(default_factory=list)
    dependency_files: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    outdated: List[str] = field(default_factory=list)
    
    def get_by_name(self, name: str) -> Optional[DependencyInfo]:
        """Get dependency by name."""
        for dep in self.dependencies:
            if dep.name == name:
                return dep
        return None


@dataclass
class CodebaseStructure:
    """Represents the structure of the codebase."""
    root_path: str
    languages: List[str] = field(default_factory=list)
    frameworks: List[str] = field(default_factory=list)
    file_tree: Dict[str, Any] = field(default_factory=dict)
    entry_points: List[str] = field(default_factory=list)
    test_directories: List[str] = field(default_factory=list)
    config_files: List[str] = field(default_factory=list)
    documentation_files: List[str] = field(default_factory=list)
    
    def get_all_files(self) -> List[str]:
        """Get a flat list of all file paths from the file tree."""
        # Use cached files if available for better performance
        if hasattr(self, '_cached_files'):
            return self._cached_files
        return self._extract_files_from_tree(self.file_tree)
    
    def _extract_files_from_tree(self, tree: Dict[str, Any], prefix: str = "") -> List[str]:
        """Recursively extract file paths from the tree structure."""
        files = []
        
        for name, value in tree.items():
            current_path = f"{prefix}/{name}" if prefix else name
            
            if value is None:  # It's a file
                files.append(current_path)
            elif isinstance(value, dict):  # It's a directory
                files.extend(self._extract_files_from_tree(value, current_path))
        
        return sorted(files)


@dataclass
class CodebaseAnalysis:
    """Complete analysis result of a codebase."""
    structure: CodebaseStructure
    dependencies: DependencyGraph
    patterns: List[Pattern]
    metrics: CodeMetrics
    summary: str
    analysis_timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.analysis_timestamp:
            self.analysis_timestamp = datetime.now()