"""
Integration tests for artifact management in the unified server.

This module tests the integration between the ArtifactManager and UnifiedSandboxServer.
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock

from src.sandbox.unified_server import UnifiedSandboxServer
from src.sandbox.core.types import ServerConfig, SecurityLevel


class TestArtifactIntegration:
    """Test artifact management integration with unified server."""
    
    @pytest.fixture
    def config(self):
        """Create test server configuration."""
        return ServerConfig(
            artifacts_retention_days=7,
            security_level=SecurityLevel.MODERATE
        )
    
    @pytest.fixture
    def server(self, config, tmp_path):
        """Create test unified server with artifact manager."""
        # Mock the MCP server to avoid actual MCP initialization
        with tempfile.TemporaryDirectory() as temp_dir:
            config_with_temp = ServerConfig(
                artifacts_retention_days=7,
                security_level=SecurityLevel.MODERATE
            )
            
            server = UnifiedSandboxServer(config_with_temp)
            # Override artifact manager base directory for testing
            server.artifact_manager.base_dir = tmp_path / "artifacts"
            server.artifact_manager.storage_dir = server.artifact_manager.base_dir / "storage"
            server.artifact_manager.metadata_dir = server.artifact_manager.base_dir / "metadata"
            server.artifact_manager.index_file = server.artifact_manager.base_dir / "artifact_index.json"
            
            # Create directories
            server.artifact_manager.storage_dir.mkdir(parents=True, exist_ok=True)
            server.artifact_manager.metadata_dir.mkdir(parents=True, exist_ok=True)
            server.artifact_manager._save_index()
            
            return server
    
    def test_server_initialization_with_artifact_manager(self, server):
        """Test that server initializes with artifact manager."""
        assert server.artifact_manager is not None
        assert server.artifact_manager.base_dir.exists()
        assert server.artifact_manager.storage_dir.exists()
        assert server.artifact_manager.metadata_dir.exists()
    
    def test_artifact_manager_configuration(self, server):
        """Test that artifact manager uses server configuration."""
        assert server.artifact_manager.config.artifacts_retention_days == 7
        assert server.artifact_manager.config.security_level == SecurityLevel.MODERATE
    
    def test_store_and_retrieve_artifact_integration(self, server, tmp_path):
        """Test storing and retrieving artifacts through the server."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_content = "Hello, World!"
        test_file.write_text(test_content)
        
        # Store artifact
        artifact_id = server.artifact_manager.store_file(
            test_file,
            workspace_id="test-workspace",
            user_id="test-user",
            tags=["test"],
            description="Test file"
        )
        
        # Retrieve artifact
        artifact = server.artifact_manager.retrieve_artifact(artifact_id)
        
        assert artifact is not None
        assert artifact.metadata.workspace_id == "test-workspace"
        assert artifact.metadata.user_id == "test-user"
        assert artifact.metadata.tags == ["test"]
        assert artifact.read_text() == test_content
    
    def test_artifact_cleanup_integration(self, server, tmp_path):
        """Test artifact cleanup integration."""
        # Create temporary file
        temp_file = tmp_path / "temp.tmp"
        temp_file.write_text("temporary content")
        server.artifact_manager.store_file(temp_file)
        
        # Create document file
        doc_file = tmp_path / "document.txt"
        doc_file.write_text("document content")
        server.artifact_manager.store_file(doc_file)
        
        # Perform auto cleanup (should clean temporary files)
        results = server.artifact_manager.auto_cleanup()
        
        assert results['deleted_artifacts'] >= 1
        assert 'temporary' in results.get('deleted_by_category', {})
    
    def test_storage_stats_integration(self, server, tmp_path):
        """Test storage statistics integration."""
        # Store some artifacts
        for i in range(3):
            test_file = tmp_path / f"test{i}.txt"
            test_file.write_text(f"Content {i}")
            server.artifact_manager.store_file(test_file)
        
        # Get storage stats
        stats = server.artifact_manager.get_storage_stats()
        
        assert stats['total_artifacts'] == 3
        assert stats['total_size_bytes'] > 0
        assert len(stats['categories']) > 0
    
    def test_artifact_categorization_integration(self, server, tmp_path):
        """Test that artifacts are properly categorized."""
        # Create files of different types
        files = [
            ("test.py", "code"),
            ("test.mp4", "video"),
            ("test.png", "image"),
            ("test.html", "web"),
            ("test.pdf", "document"),
            ("test.json", "data"),
            ("temp.tmp", "temporary")
        ]
        
        for filename, expected_category in files:
            test_file = tmp_path / filename
            test_file.write_text("test content")
            artifact_id = server.artifact_manager.store_file(test_file)
            
            artifact = server.artifact_manager.retrieve_artifact(artifact_id)
            assert artifact.metadata.category == expected_category
    
    def test_artifact_filtering_integration(self, server, tmp_path):
        """Test artifact filtering functionality."""
        # Create artifacts with different properties
        for i in range(3):
            test_file = tmp_path / f"test{i}.txt"
            test_file.write_text(f"Content {i}")
            server.artifact_manager.store_file(
                test_file,
                workspace_id=f"workspace-{i % 2}",  # Alternate workspaces
                tags=[f"tag{i}"]
            )
        
        # Test filtering by workspace
        artifacts = server.artifact_manager.list_artifacts({'workspace_id': 'workspace-0'})
        assert len(artifacts) == 2  # Should have artifacts 0 and 2
        
        # Test filtering by tags
        artifacts = server.artifact_manager.list_artifacts({'tags': ['tag1']})
        assert len(artifacts) == 1
        assert artifacts[0].name == "test1.txt"
    
    def test_artifact_versioning_integration(self, server, tmp_path):
        """Test artifact versioning functionality."""
        # Create test file
        test_file = tmp_path / "versioned.txt"
        test_file.write_text("Version 1")
        
        # Store first version
        artifact_id = server.artifact_manager.store_file(test_file)
        artifact = server.artifact_manager.retrieve_artifact(artifact_id)
        
        assert artifact.metadata.version == 1
        assert artifact.read_text() == "Version 1"
    
    def test_artifact_hash_calculation_integration(self, server, tmp_path):
        """Test that artifact hashes are calculated correctly."""
        # Create test file
        test_file = tmp_path / "hash_test.txt"
        test_content = "Content for hash testing"
        test_file.write_text(test_content)
        
        # Store artifact
        artifact_id = server.artifact_manager.store_file(test_file)
        artifact = server.artifact_manager.retrieve_artifact(artifact_id)
        
        # Verify hash is calculated
        assert artifact.metadata.hash_sha256 != ""
        assert len(artifact.metadata.hash_sha256) == 64  # SHA256 is 64 hex chars
        
        # Create another file with same content
        test_file2 = tmp_path / "hash_test2.txt"
        test_file2.write_text(test_content)
        
        artifact_id2 = server.artifact_manager.store_file(test_file2)
        artifact2 = server.artifact_manager.retrieve_artifact(artifact_id2)
        
        # Same content should produce same hash
        assert artifact.metadata.hash_sha256 == artifact2.metadata.hash_sha256
    
    def test_artifact_metadata_persistence_integration(self, server, tmp_path):
        """Test that artifact metadata persists correctly."""
        # Create test file
        test_file = tmp_path / "persist_test.txt"
        test_file.write_text("Persistence test")
        
        # Store artifact with metadata
        artifact_id = server.artifact_manager.store_file(
            test_file,
            workspace_id="persist-workspace",
            user_id="persist-user",
            tags=["persist", "test"],
            description="Persistence test file"
        )
        
        # Retrieve and verify metadata
        artifact = server.artifact_manager.retrieve_artifact(artifact_id)
        
        assert artifact.metadata.workspace_id == "persist-workspace"
        assert artifact.metadata.user_id == "persist-user"
        assert artifact.metadata.tags == ["persist", "test"]
        assert artifact.metadata.description == "Persistence test file"
        assert artifact.metadata.name == "persist_test.txt"
        assert artifact.metadata.category == "document"


if __name__ == "__main__":
    pytest.main([__file__])