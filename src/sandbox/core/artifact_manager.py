"""
Artifact Management System for Swiss Sandbox

This module provides comprehensive artifact storage, retrieval, metadata tracking,
versioning, and cleanup capabilities for the unified sandbox server.
"""

import os
import json
import shutil
import hashlib
import mimetypes
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
import uuid
import logging

from .types import ServerConfig

logger = logging.getLogger(__name__)


@dataclass
class ArtifactMetadata:
    """Metadata for an artifact."""
    artifact_id: str
    name: str
    original_path: str
    size: int
    created: datetime
    modified: datetime
    content_type: str
    mime_type: str
    hash_sha256: str
    category: str
    tags: List[str] = field(default_factory=list)
    version: int = 1
    parent_id: Optional[str] = None
    workspace_id: Optional[str] = None
    user_id: Optional[str] = None
    description: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'artifact_id': self.artifact_id,
            'name': self.name,
            'original_path': self.original_path,
            'size': self.size,
            'created': self.created.isoformat(),
            'modified': self.modified.isoformat(),
            'content_type': self.content_type,
            'mime_type': self.mime_type,
            'hash_sha256': self.hash_sha256,
            'category': self.category,
            'tags': self.tags,
            'version': self.version,
            'parent_id': self.parent_id,
            'workspace_id': self.workspace_id,
            'user_id': self.user_id,
            'description': self.description
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ArtifactMetadata':
        """Create from dictionary."""
        data = data.copy()
        data['created'] = datetime.fromisoformat(data['created'])
        data['modified'] = datetime.fromisoformat(data['modified'])
        return cls(**data)


@dataclass
class Artifact:
    """Complete artifact with metadata and content access."""
    metadata: ArtifactMetadata
    storage_path: Path
    
    def read_content(self) -> bytes:
        """Read artifact content as bytes."""
        return self.storage_path.read_bytes()
    
    def read_text(self, encoding: str = 'utf-8') -> str:
        """Read artifact content as text."""
        return self.storage_path.read_text(encoding=encoding)
    
    def exists(self) -> bool:
        """Check if artifact file exists."""
        return self.storage_path.exists()


@dataclass
class ArtifactInfo:
    """Lightweight artifact information for listings."""
    artifact_id: str
    name: str
    size: int
    created: datetime
    category: str
    tags: List[str]
    version: int


@dataclass
class RetentionPolicy:
    """Policy for artifact cleanup and retention."""
    max_age_days: Optional[int] = None
    max_total_size_mb: Optional[int] = None
    max_artifacts_per_category: Optional[int] = None
    categories_to_clean: Optional[List[str]] = None
    preserve_tags: Optional[List[str]] = None


class ArtifactManager:
    """
    Comprehensive artifact management system with storage, retrieval,
    metadata tracking, versioning, and cleanup capabilities.
    """
    
    def __init__(self, config: ServerConfig, base_dir: Optional[Path] = None):
        """
        Initialize the artifact manager.
        
        Args:
            config: Server configuration
            base_dir: Base directory for artifact storage (defaults to temp dir)
        """
        self.config = config
        
        if base_dir is None:
            import tempfile
            base_dir = Path(tempfile.gettempdir()) / "swiss_sandbox_artifacts"
        
        self.base_dir = Path(base_dir)
        self.storage_dir = self.base_dir / "storage"
        self.metadata_dir = self.base_dir / "metadata"
        self.index_file = self.base_dir / "artifact_index.json"
        
        # Create directories
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        
        # Load or create index
        self._load_index()
        
        # Save index to ensure file exists
        self._save_index()
        
        logger.info(f"ArtifactManager initialized with base_dir: {self.base_dir}")
    
    def _load_index(self) -> None:
        """Load the artifact index from disk."""
        try:
            if self.index_file.exists():
                with open(self.index_file, 'r') as f:
                    self._index = json.load(f)
            else:
                self._index = {
                    'artifacts': {},
                    'categories': {},
                    'last_cleanup': None,
                    'version': '1.0'
                }
        except Exception as e:
            logger.warning(f"Failed to load artifact index: {e}")
            self._index = {
                'artifacts': {},
                'categories': {},
                'last_cleanup': None,
                'version': '1.0'
            }
    
    def _save_index(self) -> None:
        """Save the artifact index to disk."""
        try:
            with open(self.index_file, 'w') as f:
                json.dump(self._index, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save artifact index: {e}")
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file."""
        hash_sha256 = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.warning(f"Failed to calculate hash for {file_path}: {e}")
            return "unknown"
    
    def _categorize_file(self, file_path: Path) -> str:
        """Categorize file based on extension and content."""
        suffix = file_path.suffix.lower()
        path_str = str(file_path).lower()
        
        # Manim specific (check first to prioritize manim categorization)
        if "manim" in path_str or "media" in path_str:
            return "manim"
        # Temporary files (only by extension or specific temp/cache directory names)
        elif (suffix in ['.tmp', '.cache'] or 
              file_path.name.startswith('temp') or file_path.name.startswith('cache') or
              any(part in ['temp', 'cache', 'tmp'] for part in file_path.parts)):
            return "temporary"
        # Video files
        elif suffix in ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.gif']:
            return "video"
        # Image files
        elif suffix in ['.png', '.jpg', '.jpeg', '.bmp', '.svg', '.tiff']:
            return "image"
        # Web files
        elif suffix in ['.html', '.css', '.js']:
            return "web"
        # Documents
        elif suffix in ['.pdf', '.doc', '.docx', '.txt', '.md', '.rtf']:
            return "document"
        # Code files
        elif suffix in ['.py', '.js', '.cpp', '.java', '.c', '.h', '.rs', '.go']:
            return "code"
        # Data files
        elif suffix in ['.csv', '.xlsx', '.json', '.xml', '.yaml', '.yml']:
            return "data"
        # Archives
        elif suffix in ['.zip', '.tar', '.gz', '.rar', '.7z']:
            return "archive"
        else:
            return "other"
    
    def store_artifact(self, content: bytes, metadata: ArtifactMetadata) -> str:
        """
        Store an artifact with its metadata.
        
        Args:
            content: Artifact content as bytes
            metadata: Artifact metadata
            
        Returns:
            Artifact ID
        """
        try:
            # Generate storage path
            storage_path = self.storage_dir / f"{metadata.artifact_id}_{metadata.name}"
            
            # Write content to storage
            storage_path.write_bytes(content)
            
            # Update metadata with actual file info
            stat = storage_path.stat()
            metadata.size = stat.st_size
            metadata.modified = datetime.fromtimestamp(stat.st_mtime)
            metadata.hash_sha256 = self._calculate_file_hash(storage_path)
            
            # Save metadata
            metadata_path = self.metadata_dir / f"{metadata.artifact_id}.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata.to_dict(), f, indent=2)
            
            # Update index
            self._index['artifacts'][metadata.artifact_id] = {
                'name': metadata.name,
                'category': metadata.category,
                'size': metadata.size,
                'created': metadata.created.isoformat(),
                'storage_path': str(storage_path),
                'metadata_path': str(metadata_path)
            }
            
            # Update category index
            if metadata.category not in self._index['categories']:
                self._index['categories'][metadata.category] = []
            self._index['categories'][metadata.category].append(metadata.artifact_id)
            
            self._save_index()
            
            logger.info(f"Stored artifact {metadata.artifact_id}: {metadata.name}")
            return metadata.artifact_id
            
        except Exception as e:
            logger.error(f"Failed to store artifact {metadata.artifact_id}: {e}")
            raise
    
    def store_file(self, file_path: Path, workspace_id: Optional[str] = None,
                   user_id: Optional[str] = None, tags: Optional[List[str]] = None,
                   description: Optional[str] = None) -> str:
        """
        Store a file as an artifact.
        
        Args:
            file_path: Path to the file to store
            workspace_id: Associated workspace ID
            user_id: Associated user ID
            tags: Tags for the artifact
            description: Description of the artifact
            
        Returns:
            Artifact ID
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Generate artifact ID
        artifact_id = str(uuid.uuid4())
        
        # Get file info
        stat = file_path.stat()
        mime_type, _ = mimetypes.guess_type(str(file_path))
        
        # Create metadata
        metadata = ArtifactMetadata(
            artifact_id=artifact_id,
            name=file_path.name,
            original_path=str(file_path),
            size=stat.st_size,
            created=datetime.fromtimestamp(stat.st_ctime),
            modified=datetime.fromtimestamp(stat.st_mtime),
            content_type=file_path.suffix.lower(),
            mime_type=mime_type or "application/octet-stream",
            hash_sha256="",  # Will be calculated during storage
            category=self._categorize_file(file_path),
            tags=tags or [],
            workspace_id=workspace_id,
            user_id=user_id,
            description=description
        )
        
        # Read and store content
        content = file_path.read_bytes()
        return self.store_artifact(content, metadata)
    
    def retrieve_artifact(self, artifact_id: str) -> Optional[Artifact]:
        """
        Retrieve an artifact by ID.
        
        Args:
            artifact_id: Artifact ID
            
        Returns:
            Artifact object or None if not found
        """
        try:
            if artifact_id not in self._index['artifacts']:
                return None
            
            # Load metadata
            metadata_path = Path(self._index['artifacts'][artifact_id]['metadata_path'])
            if not metadata_path.exists():
                logger.warning(f"Metadata file missing for artifact {artifact_id}")
                return None
            
            with open(metadata_path, 'r') as f:
                metadata_dict = json.load(f)
            
            metadata = ArtifactMetadata.from_dict(metadata_dict)
            storage_path = Path(self._index['artifacts'][artifact_id]['storage_path'])
            
            return Artifact(metadata=metadata, storage_path=storage_path)
            
        except Exception as e:
            logger.error(f"Failed to retrieve artifact {artifact_id}: {e}")
            return None
    
    def list_artifacts(self, filter_criteria: Optional[Dict[str, Any]] = None) -> List[ArtifactInfo]:
        """
        List artifacts with optional filtering.
        
        Args:
            filter_criteria: Dictionary with filter criteria:
                - category: Filter by category
                - workspace_id: Filter by workspace
                - user_id: Filter by user
                - tags: Filter by tags (any match)
                - created_after: Filter by creation date
                - created_before: Filter by creation date
                
        Returns:
            List of ArtifactInfo objects
        """
        artifacts = []
        
        for artifact_id, index_info in self._index['artifacts'].items():
            try:
                # Load full metadata for filtering
                metadata_path = Path(index_info['metadata_path'])
                if not metadata_path.exists():
                    continue
                
                with open(metadata_path, 'r') as f:
                    metadata_dict = json.load(f)
                
                metadata = ArtifactMetadata.from_dict(metadata_dict)
                
                # Apply filters
                if filter_criteria:
                    if 'category' in filter_criteria and metadata.category != filter_criteria['category']:
                        continue
                    if 'workspace_id' in filter_criteria and metadata.workspace_id != filter_criteria['workspace_id']:
                        continue
                    if 'user_id' in filter_criteria and metadata.user_id != filter_criteria['user_id']:
                        continue
                    if 'tags' in filter_criteria:
                        filter_tags = filter_criteria['tags']
                        if not any(tag in metadata.tags for tag in filter_tags):
                            continue
                    if 'created_after' in filter_criteria:
                        if metadata.created < filter_criteria['created_after']:
                            continue
                    if 'created_before' in filter_criteria:
                        if metadata.created > filter_criteria['created_before']:
                            continue
                
                # Create artifact info
                artifact_info = ArtifactInfo(
                    artifact_id=metadata.artifact_id,
                    name=metadata.name,
                    size=metadata.size,
                    created=metadata.created,
                    category=metadata.category,
                    tags=metadata.tags,
                    version=metadata.version
                )
                
                artifacts.append(artifact_info)
                
            except Exception as e:
                logger.warning(f"Failed to process artifact {artifact_id}: {e}")
                continue
        
        # Sort by creation date (newest first)
        artifacts.sort(key=lambda x: x.created, reverse=True)
        return artifacts
    
    def cleanup_artifacts(self, retention_policy: RetentionPolicy) -> Dict[str, Any]:
        """
        Clean up artifacts based on retention policy.
        
        Args:
            retention_policy: Cleanup policy
            
        Returns:
            Cleanup results
        """
        results = {
            'total_artifacts': len(self._index['artifacts']),
            'deleted_artifacts': 0,
            'freed_space_bytes': 0,
            'errors': [],
            'deleted_by_category': {}
        }
        
        artifacts_to_delete = []
        
        try:
            # Get all artifacts with metadata
            for artifact_id, index_info in self._index['artifacts'].items():
                try:
                    metadata_path = Path(index_info['metadata_path'])
                    if not metadata_path.exists():
                        continue
                    
                    with open(metadata_path, 'r') as f:
                        metadata_dict = json.load(f)
                    
                    metadata = ArtifactMetadata.from_dict(metadata_dict)
                    should_delete = False
                    
                    # Check age policy
                    if retention_policy.max_age_days is not None:
                        age = datetime.now() - metadata.created
                        if age.days > retention_policy.max_age_days:
                            should_delete = True
                    
                    # Check category policy
                    if retention_policy.categories_to_clean:
                        if metadata.category in retention_policy.categories_to_clean:
                            should_delete = True
                    
                    # Check preserve tags
                    if retention_policy.preserve_tags:
                        if any(tag in metadata.tags for tag in retention_policy.preserve_tags):
                            should_delete = False
                    
                    if should_delete:
                        artifacts_to_delete.append((artifact_id, metadata))
                        
                except Exception as e:
                    results['errors'].append(f"Failed to evaluate artifact {artifact_id}: {e}")
            
            # Sort by creation date (oldest first) for deletion
            artifacts_to_delete.sort(key=lambda x: x[1].created)
            
            # Apply size limit if specified
            if retention_policy.max_total_size_mb is not None:
                current_size = sum(info['size'] for info in self._index['artifacts'].values())
                max_size_bytes = retention_policy.max_total_size_mb * 1024 * 1024
                
                if current_size > max_size_bytes:
                    # Delete oldest artifacts until under size limit
                    for artifact_id, metadata in artifacts_to_delete:
                        if current_size <= max_size_bytes:
                            break
                        current_size -= metadata.size
            
            # Perform deletions
            for artifact_id, metadata in artifacts_to_delete:
                try:
                    self._delete_artifact(artifact_id)
                    results['deleted_artifacts'] += 1
                    results['freed_space_bytes'] += metadata.size
                    
                    # Track by category
                    category = metadata.category
                    if category not in results['deleted_by_category']:
                        results['deleted_by_category'][category] = 0
                    results['deleted_by_category'][category] += 1
                    
                except Exception as e:
                    results['errors'].append(f"Failed to delete artifact {artifact_id}: {e}")
            
            # Update last cleanup time
            self._index['last_cleanup'] = datetime.now().isoformat()
            self._save_index()
            
            logger.info(f"Cleanup completed: deleted {results['deleted_artifacts']} artifacts, "
                       f"freed {results['freed_space_bytes'] / 1024 / 1024:.2f} MB")
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            results['errors'].append(f"Cleanup failed: {e}")
        
        return results
    
    def _delete_artifact(self, artifact_id: str) -> None:
        """Delete an artifact and its metadata."""
        if artifact_id not in self._index['artifacts']:
            return
        
        index_info = self._index['artifacts'][artifact_id]
        
        # Delete storage file
        storage_path = Path(index_info['storage_path'])
        if storage_path.exists():
            storage_path.unlink()
        
        # Delete metadata file
        metadata_path = Path(index_info['metadata_path'])
        if metadata_path.exists():
            metadata_path.unlink()
        
        # Remove from index
        category = index_info.get('category')
        if category and category in self._index['categories']:
            if artifact_id in self._index['categories'][category]:
                self._index['categories'][category].remove(artifact_id)
            if not self._index['categories'][category]:
                del self._index['categories'][category]
        
        del self._index['artifacts'][artifact_id]
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        total_size = 0
        category_stats = {}
        
        for artifact_id, info in self._index['artifacts'].items():
            size = info.get('size', 0)
            category = info.get('category', 'unknown')
            
            total_size += size
            
            if category not in category_stats:
                category_stats[category] = {'count': 0, 'size': 0}
            
            category_stats[category]['count'] += 1
            category_stats[category]['size'] += size
        
        return {
            'total_artifacts': len(self._index['artifacts']),
            'total_size_bytes': total_size,
            'total_size_mb': total_size / 1024 / 1024,
            'categories': category_stats,
            'last_cleanup': self._index.get('last_cleanup'),
            'storage_dir': str(self.storage_dir),
            'metadata_dir': str(self.metadata_dir)
        }
    
    def auto_cleanup(self) -> Dict[str, Any]:
        """Perform automatic cleanup based on server configuration."""
        policy = RetentionPolicy(
            max_age_days=self.config.artifacts_retention_days,
            categories_to_clean=['temporary', 'cache'],
            preserve_tags=['important', 'keep']
        )
        
        return self.cleanup_artifacts(policy)