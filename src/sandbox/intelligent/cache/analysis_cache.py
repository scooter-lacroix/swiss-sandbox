"""
Caching implementation for codebase analysis results.
"""

import json
import pickle
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
import os

from .interfaces import AnalysisCacheInterface
from .models import AnalysisCacheEntry, CacheStats
from ..analyzer.models import CodebaseAnalysis


class AnalysisCache(AnalysisCacheInterface):
    """Cache for codebase analysis results with invalidation support."""
    
    def __init__(self, cache_dir: str, max_entries: int = 1000, default_ttl: int = 3600):
        """
        Initialize the analysis cache.
        
        Args:
            cache_dir: Directory for cache storage
            max_entries: Maximum number of cached entries
            default_ttl: Default time to live in seconds
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_entries = max_entries
        self.default_ttl = default_ttl
        
        # In-memory cache for quick access
        self._memory_cache: Dict[str, AnalysisCacheEntry] = {}
        
        # Statistics
        self._stats = CacheStats()
        
        # Load existing cache from disk
        self._load_cache_index()
    
    def _load_cache_index(self) -> None:
        """Load cache index from disk."""
        index_file = self.cache_dir / "cache_index.json"
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
        index_file = self.cache_dir / "cache_index.json"
        index_data = {}
        
        for key, entry in self._memory_cache.items():
            index_data[key] = {
                "workspace_hash": entry.workspace_hash,
                "created_at": entry.created_at.isoformat(),
                "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
                "access_count": entry.access_count
            }
        
        try:
            with open(index_file, 'w') as f:
                json.dump(index_data, f, indent=2)
        except Exception:
            pass  # Fail silently for index save errors
    
    def _generate_workspace_hash(self, workspace_path: str, 
                                file_timestamps: Dict[str, datetime]) -> str:
        """Generate a hash for the workspace state."""
        hash_data = {
            "workspace_path": workspace_path,
            "file_timestamps": {
                path: timestamp.isoformat() 
                for path, timestamp in sorted(file_timestamps.items())
            }
        }
        
        hash_str = json.dumps(hash_data, sort_keys=True)
        return hashlib.sha256(hash_str.encode()).hexdigest()
    
    def _get_file_timestamps(self, workspace_path: str) -> Dict[str, datetime]:
        """Get modification timestamps for all relevant files in the workspace."""
        timestamps = {}
        workspace_path = Path(workspace_path)
        
        if not workspace_path.exists():
            return timestamps
        
        # Get timestamps for common source files
        extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.go', '.rs', '.rb'}
        
        for file_path in workspace_path.rglob('*'):
            if (file_path.is_file() and 
                file_path.suffix.lower() in extensions and
                not any(part.startswith('.') for part in file_path.parts[len(workspace_path.parts):])):
                
                try:
                    stat = file_path.stat()
                    timestamps[str(file_path.relative_to(workspace_path))] = datetime.fromtimestamp(stat.st_mtime)
                except Exception:
                    continue
        
        return timestamps
    
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
        
        entry = AnalysisCacheEntry(
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
        
        index_file = self.cache_dir / "cache_index.json"
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
            "cache_type": "analysis"
        }
    
    def cache_analysis(self, workspace_hash: str, analysis: CodebaseAnalysis,
                      ttl: Optional[int] = None) -> bool:
        """Cache a codebase analysis result."""
        # Get current file timestamps for validation
        file_timestamps = self._get_file_timestamps(analysis.structure.root_path)
        
        # Create cache entry with additional metadata
        entry = AnalysisCacheEntry(
            key=workspace_hash,
            value=analysis,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(seconds=ttl or self.default_ttl),
            workspace_hash=workspace_hash,
            file_timestamps=file_timestamps
        )
        
        # Enforce max entries limit
        if len(self._memory_cache) >= self.max_entries:
            self._evict_lru_entry()
        
        self._memory_cache[workspace_hash] = entry
        self._stats.total_entries = len(self._memory_cache)
        
        # Save to disk
        self._save_entry_to_disk(workspace_hash, entry)
        self._save_cache_index()
        
        return True
    
    def get_analysis(self, workspace_hash: str) -> Optional[CodebaseAnalysis]:
        """Get cached analysis result."""
        entry = self._memory_cache.get(workspace_hash)
        if entry is None:
            self._stats.miss_count += 1
            return None
        
        if entry.is_expired:
            self.delete(workspace_hash)
            self._stats.miss_count += 1
            return None
        
        entry.touch()
        self._stats.hit_count += 1
        return entry.value
    
    def invalidate_analysis(self, workspace_hash: str) -> bool:
        """Invalidate cached analysis for a workspace."""
        return self.delete(workspace_hash)
    
    def is_analysis_valid(self, workspace_hash: str, 
                         file_timestamps: Dict[str, datetime]) -> bool:
        """Check if cached analysis is still valid based on file timestamps."""
        entry = self._memory_cache.get(workspace_hash)
        if entry is None or entry.is_expired:
            return False
        
        return entry.is_valid_for_files(file_timestamps)
    
    def _save_entry_to_disk(self, key: str, entry: AnalysisCacheEntry) -> None:
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