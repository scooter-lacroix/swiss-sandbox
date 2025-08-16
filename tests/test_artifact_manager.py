"""
Tests for the ArtifactManager class.

This module tests artifact storage, retrieval, metadata tracking,
versioning, and cleanup functionality.
"""

import pytest
import tempfile
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from src.sandbox.core.artifact_manager import (
    ArtifactManager, ArtifactMetadata, Artifact, ArtifactInfo, RetentionPolicy
)
from src.sandbox.core.types import ServerConfig, SecurityLevel


class TestArtifactMetadata:
    """Test ArtifactMetadata class."""
    
    def test_to_dict(self):
        """Test metadata serialization to dictionary."""
        metadata = ArtifactMetadata(
            artifact_id="test-123",
            name="test.txt",
            original_path="/tmp/test.txt",
            size=1024,
            created=datetime(2023, 1, 1, 12, 0, 0),
            modified=datetime(2023, 1, 1, 12, 30, 0),
            content_type=".txt",
            mime_type="text/plain",
            hash_sha256="abc123",
            category="document",
            tags=["test", "sample"],
            version=1,
            workspace_id="ws-123",
            user_id="user-456",
            description="Test file"
        )
        
        result = metadata.to_dict()
        
        assert result['artifact_id'] == "test-123"
        assert result['name'] == "test.txt"
        assert result['size'] == 1024
        assert result['created'] == "2023-01-01T12:00:00"
        assert result['modified'] == "2023-01-01T12:30:00"
        assert result['tags'] == ["test", "sample"]
        assert result['version'] == 1
    
    def test_from_dict(self):
        """Test metadata deserialization from dictionary."""
        data = {
            'artifact_id': "test-123",
            'name': "test.txt",
            'original_path': "/tmp/test.txt",
            'size': 1024,
            'created': "2023-01-01T12:00:00",
            'modified': "2023-01-01T12:30:00",
            'content_type': ".txt",
            'mime_type': "text/plain",
            'hash_sha256': "abc123",
            'category': "document",
            'tags': ["test", "sample"],
            'version': 1,
            'parent_id': None,
            'workspace_id': "ws-123",
            'user_id': "user-456",
            'description': "Test file"
        }
        
        metadata = ArtifactMetadata.from_dict(data)
        
        assert metadata.artifact_id == "test-123"
        assert metadata.name == "test.txt"
        assert metadata.size == 1024
        assert metadata.created == datetime(2023, 1, 1, 12, 0, 0)
        assert metadata.modified == datetime(2023, 1, 1, 12, 30, 0)
        assert metadata.tags == ["test", "sample"]


class TestArtifact:
    """Test Artifact class."""
    
    def test_read_content(self, tmp_path):
        """Test reading artifact content as bytes."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_content = b"Hello, World!"
        test_file.write_bytes(test_content)
        
        # Create artifact
        metadata = ArtifactMetadata(
            artifact_id="test-123",
            name="test.txt",
            original_path=str(test_file),
            size=len(test_content),
            created=datetime.now(),
            modified=datetime.now(),
            content_type=".txt",
            mime_type="text/plain",
            hash_sha256="abc123",
            category="document"
        )
        
        artifact = Artifact(metadata=metadata, storage_path=test_file)
        
        assert artifact.read_content() == test_content
    
    def test_read_text(self, tmp_path):
        """Test reading artifact content as text."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_content = "Hello, World!"
        test_file.write_text(test_content)
        
        # Create artifact
        metadata = ArtifactMetadata(
            artifact_id="test-123",
            name="test.txt",
            original_path=str(test_file),
            size=len(test_content),
            created=datetime.now(),
            modified=datetime.now(),
            content_type=".txt",
            mime_type="text/plain",
            hash_sha256="abc123",
            category="document"
        )
        
        artifact = Artifact(metadata=metadata, storage_path=test_file)
        
        assert artifact.read_text() == test_content
    
    def test_exists(self, tmp_path):
        """Test checking if artifact exists."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        
        metadata = ArtifactMetadata(
            artifact_id="test-123",
            name="test.txt",
            original_path=str(test_file),
            size=4,
            created=datetime.now(),
            modified=datetime.now(),
            content_type=".txt",
            mime_type="text/plain",
            hash_sha256="abc123",
            category="document"
        )
        
        artifact = Artifact(metadata=metadata, storage_path=test_file)
        
        assert artifact.exists() is True
        
        # Delete file and test again
        test_file.unlink()
        assert artifact.exists() is False


class TestArtifactManager:
    """Test ArtifactManager class."""
    
    @pytest.fixture
    def config(self):
        """Create test server configuration."""
        return ServerConfig(
            artifacts_retention_days=7,
            security_level=SecurityLevel.MODERATE
        )
    
    @pytest.fixture
    def manager(self, config, tmp_path):
        """Create test artifact manager."""
        return ArtifactManager(config=config, base_dir=tmp_path / "artifacts")
    
    def test_initialization(self, config, tmp_path):
        """Test artifact manager initialization."""
        base_dir = tmp_path / "artifacts"
        manager = ArtifactManager(config=config, base_dir=base_dir)
        
        assert manager.base_dir == base_dir
        assert manager.storage_dir == base_dir / "storage"
        assert manager.metadata_dir == base_dir / "metadata"
        assert manager.storage_dir.exists()
        assert manager.metadata_dir.exists()
        assert manager.index_file.exists()
    
    def test_categorize_file(self, manager):
        """Test file categorization."""
        assert manager._categorize_file(Path("test.py")) == "code"
        assert manager._categorize_file(Path("test.mp4")) == "video"
        assert manager._categorize_file(Path("test.png")) == "image"
        assert manager._categorize_file(Path("test.html")) == "web"
        assert manager._categorize_file(Path("test.pdf")) == "document"
        assert manager._categorize_file(Path("test.json")) == "data"
        assert manager._categorize_file(Path("test.zip")) == "archive"
        assert manager._categorize_file(Path("media/test.mp4")) == "manim"
        assert manager._categorize_file(Path("temp/test.tmp")) == "temporary"
        assert manager._categorize_file(Path("test.unknown")) == "other"
    
    def test_store_artifact(self, manager):
        """Test storing an artifact."""
        content = b"Hello, World!"
        metadata = ArtifactMetadata(
            artifact_id="test-123",
            name="test.txt",
            original_path="/tmp/test.txt",
            size=len(content),
            created=datetime.now(),
            modified=datetime.now(),
            content_type=".txt",
            mime_type="text/plain",
            hash_sha256="",
            category="document",
            workspace_id="ws-123"
        )
        
        artifact_id = manager.store_artifact(content, metadata)
        
        assert artifact_id == "test-123"
        assert "test-123" in manager._index['artifacts']
        
        # Check storage file exists
        storage_path = manager.storage_dir / "test-123_test.txt"
        assert storage_path.exists()
        assert storage_path.read_bytes() == content
        
        # Check metadata file exists
        metadata_path = manager.metadata_dir / "test-123.json"
        assert metadata_path.exists()
        
        # Check index updated
        index_entry = manager._index['artifacts']['test-123']
        assert index_entry['name'] == "test.txt"
        assert index_entry['category'] == "document"
    
    def test_store_file(self, manager, tmp_path):
        """Test storing a file as an artifact."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_content = "Hello, World!"
        test_file.write_text(test_content)
        
        artifact_id = manager.store_file(
            test_file,
            workspace_id="ws-123",
            user_id="user-456",
            tags=["test"],
            description="Test file"
        )
        
        assert artifact_id is not None
        assert artifact_id in manager._index['artifacts']
        
        # Retrieve and verify
        artifact = manager.retrieve_artifact(artifact_id)
        assert artifact is not None
        assert artifact.metadata.name == "test.txt"
        assert artifact.metadata.workspace_id == "ws-123"
        assert artifact.metadata.user_id == "user-456"
        assert artifact.metadata.tags == ["test"]
        assert artifact.metadata.description == "Test file"
        assert artifact.read_text() == test_content
    
    def test_store_file_not_found(self, manager, tmp_path):
        """Test storing a non-existent file."""
        non_existent_file = tmp_path / "does_not_exist.txt"
        
        with pytest.raises(FileNotFoundError):
            manager.store_file(non_existent_file)
    
    def test_retrieve_artifact(self, manager):
        """Test retrieving an artifact."""
        # Store an artifact first
        content = b"Test content"
        metadata = ArtifactMetadata(
            artifact_id="test-456",
            name="test.txt",
            original_path="/tmp/test.txt",
            size=len(content),
            created=datetime.now(),
            modified=datetime.now(),
            content_type=".txt",
            mime_type="text/plain",
            hash_sha256="",
            category="document"
        )
        
        manager.store_artifact(content, metadata)
        
        # Retrieve the artifact
        artifact = manager.retrieve_artifact("test-456")
        
        assert artifact is not None
        assert artifact.metadata.artifact_id == "test-456"
        assert artifact.metadata.name == "test.txt"
        assert artifact.read_content() == content
    
    def test_retrieve_artifact_not_found(self, manager):
        """Test retrieving a non-existent artifact."""
        artifact = manager.retrieve_artifact("does-not-exist")
        assert artifact is None
    
    def test_list_artifacts(self, manager, tmp_path):
        """Test listing artifacts."""
        # Store multiple artifacts
        for i in range(3):
            test_file = tmp_path / f"test{i}.txt"
            test_file.write_text(f"Content {i}")
            
            manager.store_file(
                test_file,
                workspace_id=f"ws-{i}",
                tags=[f"tag{i}"],
                description=f"Test file {i}"
            )
        
        # List all artifacts
        artifacts = manager.list_artifacts()
        assert len(artifacts) == 3
        
        # Test filtering by workspace
        artifacts = manager.list_artifacts({'workspace_id': 'ws-1'})
        assert len(artifacts) == 1
        assert artifacts[0].name == "test1.txt"
        
        # Test filtering by tags
        artifacts = manager.list_artifacts({'tags': ['tag2']})
        assert len(artifacts) == 1
        assert artifacts[0].name == "test2.txt"
    
    def test_list_artifacts_with_date_filter(self, manager, tmp_path):
        """Test listing artifacts with date filters."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        # Store artifact
        artifact_id = manager.store_file(test_file)
        
        # Test date filters
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        tomorrow = now + timedelta(days=1)
        
        # Should find artifact created after yesterday
        artifacts = manager.list_artifacts({'created_after': yesterday})
        assert len(artifacts) == 1
        
        # Should not find artifact created after tomorrow
        artifacts = manager.list_artifacts({'created_after': tomorrow})
        assert len(artifacts) == 0
        
        # Should find artifact created before tomorrow
        artifacts = manager.list_artifacts({'created_before': tomorrow})
        assert len(artifacts) == 1
        
        # Should not find artifact created before yesterday
        artifacts = manager.list_artifacts({'created_before': yesterday})
        assert len(artifacts) == 0
    
    def test_cleanup_artifacts_by_age(self, manager, tmp_path):
        """Test cleanup by age policy."""
        # Create old artifact
        old_file = tmp_path / "old.txt"
        old_file.write_text("old content")
        old_artifact_id = manager.store_file(old_file)
        
        # Manually set creation date to be old
        metadata_path = manager.metadata_dir / f"{old_artifact_id}.json"
        with open(metadata_path, 'r') as f:
            metadata_dict = json.load(f)
        
        old_date = datetime.now() - timedelta(days=10)
        metadata_dict['created'] = old_date.isoformat()
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata_dict, f)
        
        # Create new artifact
        new_file = tmp_path / "new.txt"
        new_file.write_text("new content")
        new_artifact_id = manager.store_file(new_file)
        
        # Cleanup artifacts older than 5 days
        policy = RetentionPolicy(max_age_days=5)
        results = manager.cleanup_artifacts(policy)
        
        assert results['deleted_artifacts'] == 1
        assert results['total_artifacts'] == 2  # Before cleanup
        
        # Verify old artifact is gone
        assert manager.retrieve_artifact(old_artifact_id) is None
        # Verify new artifact still exists
        assert manager.retrieve_artifact(new_artifact_id) is not None
    
    def test_cleanup_artifacts_by_category(self, manager, tmp_path):
        """Test cleanup by category policy."""
        # Create temporary file
        temp_file = tmp_path / "temp.tmp"
        temp_file.write_text("temporary content")
        temp_artifact_id = manager.store_file(temp_file)
        
        # Create document file
        doc_file = tmp_path / "document.txt"
        doc_file.write_text("document content")
        doc_artifact_id = manager.store_file(doc_file)
        
        # Cleanup temporary files
        policy = RetentionPolicy(categories_to_clean=['temporary'])
        results = manager.cleanup_artifacts(policy)
        
        assert results['deleted_artifacts'] == 1
        assert 'temporary' in results['deleted_by_category']
        
        # Verify temporary artifact is gone
        assert manager.retrieve_artifact(temp_artifact_id) is None
        # Verify document artifact still exists
        assert manager.retrieve_artifact(doc_artifact_id) is not None
    
    def test_cleanup_artifacts_preserve_tags(self, manager, tmp_path):
        """Test cleanup with preserve tags policy."""
        # Create temporary file with important tag
        temp_file = tmp_path / "temp.tmp"
        temp_file.write_text("important temporary content")
        temp_artifact_id = manager.store_file(temp_file, tags=['important'])
        
        # Create temporary file without important tag
        temp_file2 = tmp_path / "temp2.tmp"
        temp_file2.write_text("regular temporary content")
        temp_artifact_id2 = manager.store_file(temp_file2)
        
        # Cleanup temporary files but preserve important ones
        policy = RetentionPolicy(
            categories_to_clean=['temporary'],
            preserve_tags=['important']
        )
        results = manager.cleanup_artifacts(policy)
        
        assert results['deleted_artifacts'] == 1
        
        # Verify important artifact is preserved
        assert manager.retrieve_artifact(temp_artifact_id) is not None
        # Verify regular temporary artifact is gone
        assert manager.retrieve_artifact(temp_artifact_id2) is None
    
    def test_get_storage_stats(self, manager, tmp_path):
        """Test getting storage statistics."""
        # Store some artifacts
        for i in range(3):
            test_file = tmp_path / f"test{i}.txt"
            content = f"Content {i}" * 100  # Make files different sizes
            test_file.write_text(content)
            manager.store_file(test_file)
        
        stats = manager.get_storage_stats()
        
        assert stats['total_artifacts'] == 3
        assert stats['total_size_bytes'] > 0
        assert stats['total_size_mb'] > 0
        assert 'document' in stats['categories']
        assert stats['categories']['document']['count'] == 3
        assert stats['categories']['document']['size'] > 0
    
    def test_auto_cleanup(self, manager, tmp_path):
        """Test automatic cleanup based on server configuration."""
        # Create temporary file
        temp_file = tmp_path / "temp.tmp"
        temp_file.write_text("temporary content")
        manager.store_file(temp_file)
        
        # Create cache file
        cache_file = tmp_path / "cache.cache"
        cache_file.write_text("cache content")
        manager.store_file(cache_file)
        
        # Create document file
        doc_file = tmp_path / "document.txt"
        doc_file.write_text("document content")
        manager.store_file(doc_file)
        
        # Run auto cleanup
        results = manager.auto_cleanup()
        
        # Should clean up temporary and cache files
        assert results['deleted_artifacts'] >= 2
        assert 'temporary' in results['deleted_by_category'] or 'cache' in results['deleted_by_category']
    
    def test_index_persistence(self, config, tmp_path):
        """Test that index persists across manager instances."""
        base_dir = tmp_path / "artifacts"
        
        # Create first manager and store artifact
        manager1 = ArtifactManager(config=config, base_dir=base_dir)
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        artifact_id = manager1.store_file(test_file)
        
        # Create second manager and verify artifact exists
        manager2 = ArtifactManager(config=config, base_dir=base_dir)
        artifact = manager2.retrieve_artifact(artifact_id)
        
        assert artifact is not None
        assert artifact.metadata.name == "test.txt"
        assert artifact.read_text() == "test content"
    
    def test_calculate_file_hash(self, manager, tmp_path):
        """Test file hash calculation."""
        test_file = tmp_path / "test.txt"
        test_content = "Hello, World!"
        test_file.write_text(test_content)
        
        hash_value = manager._calculate_file_hash(test_file)
        
        # Verify it's a valid SHA256 hash (64 hex characters)
        assert len(hash_value) == 64
        assert all(c in '0123456789abcdef' for c in hash_value)
        
        # Verify same content produces same hash
        test_file2 = tmp_path / "test2.txt"
        test_file2.write_text(test_content)
        hash_value2 = manager._calculate_file_hash(test_file2)
        
        assert hash_value == hash_value2


class TestRetentionPolicy:
    """Test RetentionPolicy class."""
    
    def test_default_policy(self):
        """Test default retention policy."""
        policy = RetentionPolicy()
        
        assert policy.max_age_days is None
        assert policy.max_total_size_mb is None
        assert policy.max_artifacts_per_category is None
        assert policy.categories_to_clean is None
        assert policy.preserve_tags is None
    
    def test_custom_policy(self):
        """Test custom retention policy."""
        policy = RetentionPolicy(
            max_age_days=30,
            max_total_size_mb=1000,
            categories_to_clean=['temporary', 'cache'],
            preserve_tags=['important']
        )
        
        assert policy.max_age_days == 30
        assert policy.max_total_size_mb == 1000
        assert policy.categories_to_clean == ['temporary', 'cache']
        assert policy.preserve_tags == ['important']


if __name__ == "__main__":
    pytest.main([__file__])