"""
Caching implementation for execution results.
"""

import json
import pickle
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List, Set

from .interfaces import ExecutionCacheInterface
from .models import ExecutionCacheEntry, CacheStats
from ..executor.models import ExecutionResult


class ExecutionCache(ExecutionCacheInterface):
    """Cache for execution results with file dependency tracking."""
    
    def __init__(self, cache_dir: str, max_entries: int = 2000, default_ttl: int = 1800):
        """
        Initialize the execution cache.
        
        Args:
            cache_dir: Directory for cache storage
            max_entries: Maximum number of cached entries
            default_ttl: Default time to live in seconds (30 minutes)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_entries = max_entries
        self.default_ttl = default_ttl
        
        # In-memory cache for quick access
        self._memory_cache: Dict[str, ExecutionCacheEntry] = {}
        
        # Track which operations are cacheable
        self._cacheable_operations = {
            "test_execution",
            "build_operation", 
            "lint_check",
            "static_analysis",
            "dependency_install"
        }
        
        # Operations that should never be cached
        self._non_cacheable_operations = {
            "file_write",
            "file_delete",
            "git_commit",
            "deploy",
            "publish"
        }
        
        # Statistics
        self._stats = CacheStats()
        
        # Load existing cache from disk
        self._load_cache_index()
    
    def _load_cache_index(self) -> None:
        """Load cache index from disk."""
        index_file = self.cache_dir / "execution_index.json"
        if index_file.exists():
            try:
                with open(index_file, 'r') as f:
                    index_data = json.load(f)
                
                for key, entry_info in index_data.items():
                    # Load the actual cache entry
                    entry_file = self.cache_dir / f"{key}.pkl"
                    if entry_file.exists():
                        try:
                            with open(entry_file, 'rb') as f:
                                entry = pickle.load(f)
                            
                            if not entry.is_expired:
                                self._memory_cache[key] = entry
                                self._stats.total_entries += 1
                        except Exception:
                            # Remove corrupted entry
                            entry_file.unlink(missing_ok=True)
            except Exception:
                # If index is corrupted, start fresh
                pass
    
    def _save_cache_index(self) -> None:
        """Save cache index to disk."""
        index_file = self.cache_dir / "execution_index.json"
        index_data = {}
        
        for key, entry in self._memory_cache.items():
            index_data[key] = {
                "operation_type": entry.operation_type,
                "operation_hash": entry.operation_hash,
                "created_at": entry.created_at.isoformat(),
                "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
                "access_count": entry.access_count,
                "dependent_files": entry.dependent_files
            }
        
        try:
            with open(index_file, 'w') as f:
                json.dump(index_data, f, indent=2)
        except Exception:
            pass  # Fail silently for index save errors
    
    def _generate_operation_hash(self, operation_type: str, 
                                parameters: Dict[str, Any]) -> str:
        """Generate a hash for the operation parameters."""
        hash_data = {
            "operation_type": operation_type,
            "parameters": self._normalize_parameters(parameters)
        }
        
        hash_str = json.dumps(hash_data, sort_keys=True, default=str)
        return hashlib.sha256(hash_str.encode()).hexdigest()
    
    def _normalize_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize parameters for consistent hashing."""
        normalized = {}
        
        for key, value in parameters.items():
            if isinstance(value, (str, int, float, bool)):
                normalized[key] = value
            elif isinstance(value, (list, tuple)):
                normalized[key] = sorted(str(v) for v in value)
            elif isinstance(value, dict):
                normalized[key] = self._normalize_parameters(value)
            else:
                normalized[key] = str(value)
        
        return normalized
    
    def _extract_dependent_files(self, parameters: Dict[str, Any]) -> List[str]:
        """Extract file dependencies from operation parameters."""
        dependent_files = []
        
        # Common parameter names that indicate file dependencies
        file_params = ['file_path', 'input_file', 'source_file', 'config_file', 'files']
        
        for param_name, param_value in parameters.items():
            if param_name in file_params:
                if isinstance(param_value, str):
                    dependent_files.append(param_value)
                elif isinstance(param_value, (list, tuple)):
                    dependent_files.extend(str(f) for f in param_value)
        
        return dependent_files
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache."""
        entry = self._memory_cache.get(key)
        if entry is None:
            self._stats.miss_count += 1
            return None
        
        if entry.is_expired:
            self.delete(key)
            self._stats.miss_count += 1
            return None
        
        entry.touch()
        self._stats.hit_count += 1
        return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in the cache."""
        ttl = ttl or self.default_ttl
        expires_at = datetime.now() + timedelta(seconds=ttl) if ttl > 0 else None
        
        entry = ExecutionCacheEntry(
            key=key,
            value=value,
            created_at=datetime.now(),
            expires_at=expires_at
        )
        
        # Enforce max entries limit
        if len(self._memory_cache) >= self.max_entries:
            self._evict_lru_entry()
        
        self._memory_cache[key] = entry
        self._stats.total_entries = len(self._memory_cache)
        
        # Save to disk
        self._save_entry_to_disk(key, entry)
        self._save_cache_index()
        
        return True
    
    def delete(self, key: str) -> bool:
        """Delete a value from the cache."""
        if key in self._memory_cache:
            del self._memory_cache[key]
            self._stats.total_entries = len(self._memory_cache)
            
            # Remove from disk
            entry_file = self.cache_dir / f"{key}.pkl"
            entry_file.unlink(missing_ok=True)
            
            self._save_cache_index()
            return True
        
        return False
    
    def clear(self) -> bool:
        """Clear all cached values."""
        self._memory_cache.clear()
        self._stats = CacheStats()
        
        # Clear disk cache
        for file_path in self.cache_dir.glob("*.pkl"):
            file_path.unlink(missing_ok=True)
        
        index_file = self.cache_dir / "execution_index.json"
        index_file.unlink(missing_ok=True)
        
        return True
    
    def exists(self, key: str) -> bool:
        """Check if a key exists in the cache."""
        entry = self._memory_cache.get(key)
        return entry is not None and not entry.is_expired
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        memory_usage = sum(
            len(pickle.dumps(entry)) for entry in self._memory_cache.values()
        )
        
        return {
            "total_entries": self._stats.total_entries,
            "hit_count": self._stats.hit_count,
            "miss_count": self._stats.miss_count,
            "hit_rate": self._stats.hit_rate,
            "memory_usage_bytes": memory_usage,
            "cache_type": "execution"
        }
    
    def cache_execution_result(self, operation_hash: str, result: ExecutionResult,
                              ttl: Optional[int] = None) -> bool:
        """Cache an execution result for repeated operations."""
        ttl = ttl or self.default_ttl
        expires_at = datetime.now() + timedelta(seconds=ttl) if ttl > 0 else None
        
        entry = ExecutionCacheEntry(
            key=operation_hash,
            value=result,
            created_at=datetime.now(),
            expires_at=expires_at,
            operation_hash=operation_hash
        )
        
        # Enforce max entries limit
        if len(self._memory_cache) >= self.max_entries:
            self._evict_lru_entry()
        
        self._memory_cache[operation_hash] = entry
        self._stats.total_entries = len(self._memory_cache)
        
        # Save to disk
        self._save_entry_to_disk(operation_hash, entry)
        self._save_cache_index()
        
        return True
    
    def get_execution_result(self, operation_hash: str) -> Optional[ExecutionResult]:
        """Get cached execution result."""
        entry = self._memory_cache.get(operation_hash)
        if entry is None:
            self._stats.miss_count += 1
            return None
        
        if entry.is_expired:
            self.delete(operation_hash)
            self._stats.miss_count += 1
            return None
        
        entry.touch()
        self._stats.hit_count += 1
        return entry.value
    
    def is_operation_cacheable(self, operation_type: str, 
                              parameters: Dict[str, Any]) -> bool:
        """Check if an operation is suitable for caching."""
        # Never cache operations that modify state
        if operation_type in self._non_cacheable_operations:
            return False
        
        # Always cache known safe operations
        if operation_type in self._cacheable_operations:
            return True
        
        # Check for side effects in parameters
        if any(param in parameters for param in ['write', 'delete', 'modify', 'create']):
            return False
        
        # Default to not cacheable for unknown operations
        return False
    
    def invalidate_related_results(self, file_paths: List[str]) -> int:
        """Invalidate cached results that depend on specific files."""
        invalidated_count = 0
        file_paths_set = set(file_paths)
        
        keys_to_delete = []
        
        for key, entry in self._memory_cache.items():
            # Check if any dependent files have changed
            if any(dep_file in file_paths_set for dep_file in entry.dependent_files):
                keys_to_delete.append(key)
        
        for key in keys_to_delete:
            if self.delete(key):
                invalidated_count += 1
        
        return invalidated_count
    
    def cache_operation_result(self, operation_type: str, parameters: Dict[str, Any],
                              result: ExecutionResult, ttl: Optional[int] = None) -> bool:
        """Cache an operation result with full context."""
        if not self.is_operation_cacheable(operation_type, parameters):
            return False
        
        operation_hash = self._generate_operation_hash(operation_type, parameters)
        dependent_files = self._extract_dependent_files(parameters)
        
        ttl = ttl or self.default_ttl
        expires_at = datetime.now() + timedelta(seconds=ttl) if ttl > 0 else None
        
        entry = ExecutionCacheEntry(
            key=operation_hash,
            value=result,
            created_at=datetime.now(),
            expires_at=expires_at,
            operation_type=operation_type,
            operation_hash=operation_hash,
            dependent_files=dependent_files
        )
        
        # Store file hashes in metadata for validation
        for file_path in dependent_files:
            try:
                if Path(file_path).exists():
                    with open(file_path, 'rb') as f:
                        file_hash = hashlib.sha256(f.read()).hexdigest()
                    entry.metadata[f"file_hash_{file_path}"] = file_hash
            except Exception:
                continue
        
        # Enforce max entries limit
        if len(self._memory_cache) >= self.max_entries:
            self._evict_lru_entry()
        
        self._memory_cache[operation_hash] = entry
        self._stats.total_entries = len(self._memory_cache)
        
        # Save to disk
        self._save_entry_to_disk(operation_hash, entry)
        self._save_cache_index()
        
        return True
    
    def get_operation_result(self, operation_type: str, 
                            parameters: Dict[str, Any]) -> Optional[ExecutionResult]:
        """Get cached result for an operation."""
        if not self.is_operation_cacheable(operation_type, parameters):
            return None
        
        operation_hash = self._generate_operation_hash(operation_type, parameters)
        return self.get_execution_result(operation_hash)
    
    def invalidate_workspace(self, workspace_path: str) -> int:
        """Invalidate all cached results for a workspace."""
        invalidated_count = 0
        workspace_path = str(Path(workspace_path).resolve())
        
        keys_to_delete = []
        
        for key, entry in self._memory_cache.items():
            # Check if any dependent files are in the workspace
            for dep_file in entry.dependent_files:
                try:
                    if str(Path(dep_file).resolve()).startswith(workspace_path):
                        keys_to_delete.append(key)
                        break
                except Exception:
                    continue
        
        for key in keys_to_delete:
            if self.delete(key):
                invalidated_count += 1
        
        return invalidated_count
    
    def _save_entry_to_disk(self, key: str, entry: ExecutionCacheEntry) -> None:
        """Save a cache entry to disk."""
        entry_file = self.cache_dir / f"{key}.pkl"
        try:
            with open(entry_file, 'wb') as f:
                pickle.dump(entry, f)
        except Exception:
            pass  # Fail silently for disk save errors
    
    def _evict_lru_entry(self) -> None:
        """Evict the least recently used entry."""
        if not self._memory_cache:
            return
        
        # Find LRU entry
        lru_key = min(
            self._memory_cache.keys(),
            key=lambda k: self._memory_cache[k].last_accessed or datetime.min
        )
        
        self.delete(lru_key)
        self._stats.eviction_count += 1
    
    def cleanup_expired(self) -> int:
        """Clean up expired entries."""
        expired_keys = [
            key for key, entry in self._memory_cache.items()
            if entry.is_expired
        ]
        
        for key in expired_keys:
            self.delete(key)
        
        return len(expired_keys)
    
    def evict_lru_entries(self, count: int) -> int:
        """Evict a specific number of LRU entries."""
        evicted = 0
        
        while evicted < count and self._memory_cache:
            self._evict_lru_entry()
            evicted += 1
        
        return evicted