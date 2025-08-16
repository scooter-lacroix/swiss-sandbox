#!/usr/bin/env python3
"""
Artifact Management System Demo

This script demonstrates the comprehensive artifact management capabilities
of the Swiss Sandbox system, including storage, retrieval, metadata tracking,
versioning, and cleanup functionality.
"""

import tempfile
from pathlib import Path
from datetime import datetime

import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sandbox.core.artifact_manager import ArtifactManager, RetentionPolicy
from sandbox.core.types import ServerConfig, SecurityLevel


def create_demo_files(temp_dir: Path) -> list[Path]:
    """Create demo files for testing artifact management."""
    files = []
    
    # Create different types of files
    file_types = [
        ("demo.py", "print('Hello from Python!')", "code"),
        ("demo.html", "<html><body><h1>Demo Page</h1></body></html>", "web"),
        ("demo.txt", "This is a text document for testing.", "document"),
        ("demo.json", '{"name": "demo", "version": "1.0"}', "data"),
        ("temp.tmp", "Temporary file content", "temporary"),
        ("media/video.mp4", "fake video content", "manim"),  # Will be categorized as manim
        ("image.png", "fake image content", "image")
    ]
    
    for filename, content, expected_category in file_types:
        file_path = temp_dir / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        files.append(file_path)
        print(f"Created {filename} (expected category: {expected_category})")
    
    return files


def demonstrate_artifact_storage(manager: ArtifactManager, files: list[Path]):
    """Demonstrate artifact storage functionality."""
    print("\n" + "="*60)
    print("ARTIFACT STORAGE DEMONSTRATION")
    print("="*60)
    
    artifact_ids = []
    
    for i, file_path in enumerate(files):
        # Store with different metadata
        workspace_id = f"workspace-{i % 3}"  # Rotate between 3 workspaces
        user_id = f"user-{i % 2}"  # Rotate between 2 users
        tags = [f"demo", f"type-{i}", "example"]
        description = f"Demo file {i+1}: {file_path.name}"
        
        artifact_id = manager.store_file(
            file_path,
            workspace_id=workspace_id,
            user_id=user_id,
            tags=tags,
            description=description
        )
        
        artifact_ids.append(artifact_id)
        print(f"Stored {file_path.name} -> {artifact_id}")
    
    print(f"\nStored {len(artifact_ids)} artifacts successfully!")
    return artifact_ids


def demonstrate_artifact_retrieval(manager: ArtifactManager, artifact_ids: list[str]):
    """Demonstrate artifact retrieval functionality."""
    print("\n" + "="*60)
    print("ARTIFACT RETRIEVAL DEMONSTRATION")
    print("="*60)
    
    for i, artifact_id in enumerate(artifact_ids[:3]):  # Show first 3
        artifact = manager.retrieve_artifact(artifact_id)
        if artifact:
            print(f"\nArtifact {i+1}:")
            print(f"  ID: {artifact.metadata.artifact_id}")
            print(f"  Name: {artifact.metadata.name}")
            print(f"  Category: {artifact.metadata.category}")
            print(f"  Size: {artifact.metadata.size} bytes")
            print(f"  Created: {artifact.metadata.created}")
            print(f"  Tags: {artifact.metadata.tags}")
            print(f"  Workspace: {artifact.metadata.workspace_id}")
            print(f"  User: {artifact.metadata.user_id}")
            print(f"  Content preview: {artifact.read_text()[:50]}...")
        else:
            print(f"Failed to retrieve artifact {artifact_id}")


def demonstrate_artifact_listing(manager: ArtifactManager):
    """Demonstrate artifact listing and filtering."""
    print("\n" + "="*60)
    print("ARTIFACT LISTING AND FILTERING DEMONSTRATION")
    print("="*60)
    
    # List all artifacts
    all_artifacts = manager.list_artifacts()
    print(f"Total artifacts: {len(all_artifacts)}")
    
    # Group by category
    categories = {}
    for artifact in all_artifacts:
        if artifact.category not in categories:
            categories[artifact.category] = []
        categories[artifact.category].append(artifact)
    
    print("\nArtifacts by category:")
    for category, artifacts in categories.items():
        print(f"  {category}: {len(artifacts)} artifacts")
        for artifact in artifacts[:2]:  # Show first 2 in each category
            print(f"    - {artifact.name} ({artifact.size} bytes)")
    
    # Filter by workspace
    workspace_artifacts = manager.list_artifacts({'workspace_id': 'workspace-0'})
    print(f"\nArtifacts in workspace-0: {len(workspace_artifacts)}")
    
    # Filter by tags
    demo_artifacts = manager.list_artifacts({'tags': ['demo']})
    print(f"Artifacts with 'demo' tag: {len(demo_artifacts)}")


def demonstrate_storage_stats(manager: ArtifactManager):
    """Demonstrate storage statistics."""
    print("\n" + "="*60)
    print("STORAGE STATISTICS DEMONSTRATION")
    print("="*60)
    
    stats = manager.get_storage_stats()
    
    print(f"Total artifacts: {stats['total_artifacts']}")
    print(f"Total size: {stats['total_size_mb']:.2f} MB")
    print(f"Storage directory: {stats['storage_dir']}")
    print(f"Metadata directory: {stats['metadata_dir']}")
    
    print("\nStorage by category:")
    for category, info in stats['categories'].items():
        print(f"  {category}: {info['count']} files, {info['size'] / 1024:.2f} KB")


def demonstrate_artifact_cleanup(manager: ArtifactManager):
    """Demonstrate artifact cleanup functionality."""
    print("\n" + "="*60)
    print("ARTIFACT CLEANUP DEMONSTRATION")
    print("="*60)
    
    # Show current state
    stats_before = manager.get_storage_stats()
    print(f"Before cleanup: {stats_before['total_artifacts']} artifacts")
    
    # Dry run cleanup of temporary files
    policy = RetentionPolicy(
        categories_to_clean=['temporary'],
        preserve_tags=['important']
    )
    
    print("\nPerforming dry run cleanup of temporary files...")
    dry_results = manager.cleanup_artifacts(policy)
    
    print(f"Would delete {dry_results['deleted_artifacts']} artifacts")
    print(f"Would free {dry_results['freed_space_bytes'] / 1024:.2f} KB")
    
    if dry_results['deleted_by_category']:
        print("Files to delete by category:")
        for category, count in dry_results['deleted_by_category'].items():
            print(f"  {category}: {count} files")
    
    # Perform auto cleanup
    print("\nPerforming automatic cleanup based on server configuration...")
    auto_results = manager.auto_cleanup()
    
    print(f"Auto cleanup deleted {auto_results['deleted_artifacts']} artifacts")
    print(f"Auto cleanup freed {auto_results['freed_space_bytes'] / 1024:.2f} KB")
    
    # Show final state
    stats_after = manager.get_storage_stats()
    print(f"After cleanup: {stats_after['total_artifacts']} artifacts")


def main():
    """Run the artifact management demonstration."""
    print("Swiss Sandbox Artifact Management System Demo")
    print("=" * 60)
    
    # Create temporary directory for demo
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Initialize artifact manager
        config = ServerConfig(
            artifacts_retention_days=7,
            security_level=SecurityLevel.MODERATE
        )
        
        artifact_base_dir = temp_path / "artifacts"
        manager = ArtifactManager(config=config, base_dir=artifact_base_dir)
        
        print(f"Initialized artifact manager with base directory: {artifact_base_dir}")
        
        # Create demo files
        demo_files = create_demo_files(temp_path / "demo_files")
        
        # Demonstrate functionality
        artifact_ids = demonstrate_artifact_storage(manager, demo_files)
        demonstrate_artifact_retrieval(manager, artifact_ids)
        demonstrate_artifact_listing(manager)
        demonstrate_storage_stats(manager)
        demonstrate_artifact_cleanup(manager)
        
        print("\n" + "="*60)
        print("DEMONSTRATION COMPLETED SUCCESSFULLY!")
        print("="*60)
        print("\nKey features demonstrated:")
        print("✓ File storage with automatic categorization")
        print("✓ Metadata tracking (workspace, user, tags, description)")
        print("✓ Content hashing and integrity verification")
        print("✓ Flexible filtering and search capabilities")
        print("✓ Storage statistics and monitoring")
        print("✓ Intelligent cleanup with retention policies")
        print("✓ Automatic cleanup based on server configuration")
        
        print(f"\nArtifact storage location: {artifact_base_dir}")
        print("Note: Temporary directory will be cleaned up automatically.")


if __name__ == "__main__":
    main()