"""
Data models for caching system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional


@dataclass
class CacheEntry:
    """Represents a single cache entry."""
    key: str
    value: Any
    created_at: datetime
    expires_at: Optional[datetime] = None
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.last_accessed is None:
            self.last_accessed = self.created_at
    
    @property
    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at
    
    def touch(self) -> None:
        """Update access statistics."""
        self.access_count += 1
        self.last_accessed = datetime.now()


@dataclass
class AnalysisCacheEntry(CacheEntry):
    """Cache entry specifically for codebase analysis results."""
    workspace_hash: str = ""
    file_timestamps: Dict[str, datetime] = field(default_factory=dict)
    analysis_version: str = "1.0"
    
    def is_valid_for_files(self, current_timestamps: Dict[str, datetime]) -> bool:
        """Check if the cached analysis is still valid for the given file timestamps."""
        if self.is_expired:
            return False
            
        # Check if any tracked files have been modified
        for file_path, cached_timestamp in self.file_timestamps.items():
            current_timestamp = current_timestamps.get(file_path)
            if current_timestamp is None or current_timestamp > cached_timestamp:
                return False
                
        return True


@dataclass
class TaskPlanTemplate:
    """Template for task plans based on project characteristics."""
    template_key: str
    plan: 'TaskPlan'
    project_characteristics: Dict[str, Any]
    usage_count: int = 0
    success_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    last_used: Optional[datetime] = None
    similarity_threshold: float = 0.8
    
    @property
    def success_rate(self) -> float:
        """Calculate the success rate of this template."""
        if self.usage_count == 0:
            return 0.0
        return self.success_count / self.usage_count
    
    def calculate_similarity(self, other_characteristics: Dict[str, Any]) -> float:
        """Calculate similarity score with another set of project characteristics."""
        if not self.project_characteristics or not other_characteristics:
            return 0.0
            
        # Simple similarity calculation based on matching characteristics
        common_keys = set(self.project_characteristics.keys()) & set(other_characteristics.keys())
        if not common_keys:
            return 0.0
            
        matches = 0
        for key in common_keys:
            if self.project_characteristics[key] == other_characteristics[key]:
                matches += 1
                
        return matches / len(common_keys)


@dataclass
class ExecutionCacheEntry(CacheEntry):
    """Cache entry for execution results."""
    operation_type: str = ""
    operation_hash: str = ""
    dependent_files: List[str] = field(default_factory=list)
    environment_hash: str = ""
    
    def is_valid_for_files(self, current_file_hashes: Dict[str, str]) -> bool:
        """Check if the cached result is still valid for the given file states."""
        if self.is_expired:
            return False
            
        # Check if any dependent files have changed
        for file_path in self.dependent_files:
            if file_path in current_file_hashes:
                # For simplicity, we assume file hash is stored in metadata
                cached_hash = self.metadata.get(f"file_hash_{file_path}")
                if cached_hash != current_file_hashes[file_path]:
                    return False
                    
        return True


@dataclass
class CacheStats:
    """Statistics about cache performance."""
    total_entries: int = 0
    hit_count: int = 0
    miss_count: int = 0
    eviction_count: int = 0
    memory_usage_bytes: int = 0
    oldest_entry: Optional[datetime] = None
    newest_entry: Optional[datetime] = None
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total_requests = self.hit_count + self.miss_count
        if total_requests == 0:
            return 0.0
        return self.hit_count / total_requests
    
    @property
    def miss_rate(self) -> float:
        """Calculate cache miss rate."""
        return 1.0 - self.hit_rate