#!/usr/bin/env python3
"""
Workspace Export System for Intelligent Sandbox

Provides functionality to export workspaces and files created within the sandbox.

Requirements: 6.1, 6.2, 6.3
"""

import os
import sys
import json
import shutil
import zipfile
import tarfile
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class WorkspaceExporter:
    """
    Handles exporting of sandbox workspaces to various formats.
    """
    
    def __init__(self, export_dir: str = None):
        """Initialize the workspace exporter.
        
        Args:
            export_dir: Directory to store exports (default: ~/sandbox_exports)
        """
        if export_dir:
            self.export_dir = Path(export_dir)
        else:
            self.export_dir = Path.home() / "sandbox_exports"
        
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.export_history = []
        
        logger.info(f"WorkspaceExporter initialized with export dir: {self.export_dir}")
    
    def export_workspace(
        self,
        workspace_path: str,
        workspace_id: str,
        format: str = "zip",
        include_metadata: bool = True,
        include_history: bool = True
    ) -> Dict[str, Any]:
        """Export a single workspace.
        
        Args:
            workspace_path: Path to the workspace directory
            workspace_id: ID of the workspace
            format: Export format ('zip', 'tar', 'tar.gz', 'directory')
            include_metadata: Include workspace metadata
            include_history: Include execution history
        
        Returns:
            Export result with path and details
        """
        try:
            workspace_path = Path(workspace_path)
            if not workspace_path.exists():
                return {
                    "success": False,
                    "error": f"Workspace path does not exist: {workspace_path}"
                }
            
            # Generate export filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_name = f"{workspace_id}_{timestamp}"
            
            # Create metadata if requested
            metadata = None
            if include_metadata:
                metadata = self._create_metadata(
                    workspace_id,
                    workspace_path,
                    include_history
                )
            
            # Export based on format
            if format == "zip":
                export_path = self._export_to_zip(
                    workspace_path,
                    export_name,
                    metadata
                )
            elif format == "tar":
                export_path = self._export_to_tar(
                    workspace_path,
                    export_name,
                    metadata,
                    compress=False
                )
            elif format == "tar.gz":
                export_path = self._export_to_tar(
                    workspace_path,
                    export_name,
                    metadata,
                    compress=True
                )
            elif format == "directory":
                export_path = self._export_to_directory(
                    workspace_path,
                    export_name,
                    metadata
                )
            else:
                return {
                    "success": False,
                    "error": f"Unsupported format: {format}"
                }
            
            # Record export in history
            export_record = {
                "workspace_id": workspace_id,
                "timestamp": timestamp,
                "format": format,
                "path": str(export_path),
                "size": self._get_file_size(export_path)
            }
            self.export_history.append(export_record)
            
            logger.info(f"Successfully exported workspace {workspace_id} to {export_path}")
            
            return {
                "success": True,
                "export_path": str(export_path),
                "format": format,
                "size": export_record["size"],
                "timestamp": timestamp
            }
            
        except Exception as e:
            logger.error(f"Failed to export workspace: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def export_all_workspaces(
        self,
        workspaces: Dict[str, str],
        format: str = "zip"
    ) -> Dict[str, Any]:
        """Export all active workspaces.
        
        Args:
            workspaces: Dictionary of workspace_id -> workspace_path
            format: Export format
        
        Returns:
            Export results for all workspaces
        """
        results = []
        
        for workspace_id, workspace_path in workspaces.items():
            result = self.export_workspace(
                workspace_path,
                workspace_id,
                format
            )
            results.append({
                "workspace_id": workspace_id,
                "success": result["success"],
                "path": result.get("export_path"),
                "error": result.get("error")
            })
        
        successful = sum(1 for r in results if r["success"])
        
        return {
            "success": successful > 0,
            "total": len(workspaces),
            "successful": successful,
            "failed": len(workspaces) - successful,
            "exports": results
        }
    
    def export_selective_files(
        self,
        files: List[str],
        export_name: str,
        format: str = "zip"
    ) -> Dict[str, Any]:
        """Export specific files only.
        
        Args:
            files: List of file paths to export
            export_name: Name for the export
            format: Export format
        
        Returns:
            Export result
        """
        try:
            # Create temporary directory for selective export
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Copy selected files to temp directory
                for file_path in files:
                    source = Path(file_path)
                    if source.exists():
                        # Preserve directory structure
                        relative_path = source.name
                        if source.is_absolute():
                            try:
                                relative_path = source.relative_to(Path.cwd())
                            except ValueError:
                                relative_path = source.name
                        
                        dest = temp_path / relative_path
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        
                        if source.is_file():
                            shutil.copy2(source, dest)
                        elif source.is_dir():
                            shutil.copytree(source, dest)
                
                # Export from temp directory
                if format == "zip":
                    export_path = self._export_to_zip(
                        temp_path,
                        export_name,
                        None
                    )
                elif format == "tar.gz":
                    export_path = self._export_to_tar(
                        temp_path,
                        export_name,
                        None,
                        compress=True
                    )
                else:
                    export_path = self._export_to_zip(
                        temp_path,
                        export_name,
                        None
                    )
            
            return {
                "success": True,
                "export_path": str(export_path),
                "files_exported": len(files),
                "format": format
            }
            
        except Exception as e:
            logger.error(f"Failed to export selective files: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def list_exports(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List previous exports.
        
        Args:
            limit: Maximum number of exports to return
        
        Returns:
            List of export records
        """
        # Get exports from history
        exports = self.export_history[-limit:] if limit else self.export_history
        
        # Also scan export directory for any exports not in history
        for file_path in self.export_dir.iterdir():
            if file_path.is_file() and file_path.suffix in ['.zip', '.tar', '.gz']:
                # Check if already in history
                if not any(e["path"] == str(file_path) for e in exports):
                    exports.append({
                        "path": str(file_path),
                        "size": self._get_file_size(file_path),
                        "timestamp": datetime.fromtimestamp(
                            file_path.stat().st_mtime
                        ).strftime("%Y%m%d_%H%M%S")
                    })
        
        # Sort by timestamp (newest first)
        exports.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        return exports[:limit] if limit else exports
    
    def cleanup_old_exports(self, days: int = 30) -> Dict[str, Any]:
        """Clean up exports older than specified days.
        
        Args:
            days: Number of days to keep exports
        
        Returns:
            Cleanup result
        """
        try:
            cutoff_time = datetime.now().timestamp() - (days * 86400)
            removed = []
            kept = []
            
            for file_path in self.export_dir.iterdir():
                if file_path.is_file():
                    if file_path.stat().st_mtime < cutoff_time:
                        file_path.unlink()
                        removed.append(str(file_path))
                    else:
                        kept.append(str(file_path))
            
            return {
                "success": True,
                "removed": len(removed),
                "kept": len(kept),
                "removed_files": removed
            }
            
        except Exception as e:
            logger.error(f"Failed to cleanup old exports: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_export_status(self, export_path: str) -> Dict[str, Any]:
        """Get status of an export.
        
        Args:
            export_path: Path to the export file
        
        Returns:
            Export status information
        """
        try:
            path = Path(export_path)
            
            if not path.exists():
                return {
                    "success": False,
                    "error": "Export file not found"
                }
            
            stat = path.stat()
            
            return {
                "success": True,
                "path": str(path),
                "size": self._get_file_size(path),
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "format": path.suffix[1:] if path.suffix else "unknown"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def verify_export(self, export_path: str) -> Dict[str, Any]:
        """Verify integrity of an export.
        
        Args:
            export_path: Path to the export file
        
        Returns:
            Verification result
        """
        try:
            path = Path(export_path)
            
            if not path.exists():
                return {
                    "success": False,
                    "error": "Export file not found"
                }
            
            # Try to open/list contents based on format
            if path.suffix == ".zip":
                with zipfile.ZipFile(path, 'r') as zf:
                    files = zf.namelist()
                    return {
                        "success": True,
                        "valid": True,
                        "files_count": len(files),
                        "format": "zip"
                    }
            
            elif path.suffix in [".tar", ".gz"]:
                mode = 'r:gz' if path.suffix == '.gz' else 'r'
                with tarfile.open(path, mode) as tf:
                    files = tf.getnames()
                    return {
                        "success": True,
                        "valid": True,
                        "files_count": len(files),
                        "format": "tar.gz" if path.suffix == '.gz' else "tar"
                    }
            
            else:
                return {
                    "success": False,
                    "error": "Unknown export format"
                }
                
        except Exception as e:
            return {
                "success": False,
                "valid": False,
                "error": str(e)
            }
    
    # Private helper methods
    
    def _create_metadata(
        self,
        workspace_id: str,
        workspace_path: Path,
        include_history: bool
    ) -> Dict[str, Any]:
        """Create metadata for the export."""
        metadata = {
            "workspace_id": workspace_id,
            "export_timestamp": datetime.now().isoformat(),
            "workspace_path": str(workspace_path),
            "files_count": sum(1 for _ in workspace_path.rglob('*') if _.is_file()),
            "total_size": sum(
                f.stat().st_size for f in workspace_path.rglob('*') if f.is_file()
            )
        }
        
        if include_history:
            # Add execution history if available
            history_file = workspace_path / ".sandbox_history.json"
            if history_file.exists():
                with open(history_file, 'r') as f:
                    metadata["execution_history"] = json.load(f)
        
        return metadata
    
    def _export_to_zip(
        self,
        source_path: Path,
        export_name: str,
        metadata: Optional[Dict[str, Any]]
    ) -> Path:
        """Export to ZIP format."""
        export_path = self.export_dir / f"{export_name}.zip"
        
        with zipfile.ZipFile(export_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add metadata if provided
            if metadata:
                zf.writestr(
                    "METADATA.json",
                    json.dumps(metadata, indent=2)
                )
            
            # Add all files from source
            for file_path in source_path.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(source_path)
                    zf.write(file_path, arcname)
        
        return export_path
    
    def _export_to_tar(
        self,
        source_path: Path,
        export_name: str,
        metadata: Optional[Dict[str, Any]],
        compress: bool = False
    ) -> Path:
        """Export to TAR format."""
        extension = ".tar.gz" if compress else ".tar"
        export_path = self.export_dir / f"{export_name}{extension}"
        
        mode = 'w:gz' if compress else 'w'
        with tarfile.open(export_path, mode) as tf:
            # Add metadata if provided
            if metadata:
                metadata_bytes = json.dumps(metadata, indent=2).encode('utf-8')
                metadata_info = tarfile.TarInfo(name="METADATA.json")
                metadata_info.size = len(metadata_bytes)
                tf.addfile(metadata_info, fileobj=BytesIO(metadata_bytes))
            
            # Add all files from source
            tf.add(source_path, arcname=export_name)
        
        return export_path
    
    def _export_to_directory(
        self,
        source_path: Path,
        export_name: str,
        metadata: Optional[Dict[str, Any]]
    ) -> Path:
        """Export to directory format."""
        export_path = self.export_dir / export_name
        
        # Copy entire directory
        shutil.copytree(source_path, export_path, dirs_exist_ok=True)
        
        # Add metadata if provided
        if metadata:
            metadata_file = export_path / "METADATA.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
        
        return export_path
    
    def _get_file_size(self, path: Path) -> str:
        """Get human-readable file size."""
        size = path.stat().st_size if path.exists() else 0
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        
        return f"{size:.2f} TB"


# Import for TAR metadata
from io import BytesIO


if __name__ == "__main__":
    # Example usage
    exporter = WorkspaceExporter()
    
    print("Workspace Export System initialized")
    print(f"Export directory: {exporter.export_dir}")
    
    # Example: Export a test workspace
    test_workspace = Path.cwd() / "test_workspace"
    if test_workspace.exists():
        result = exporter.export_workspace(
            str(test_workspace),
            "test-workspace",
            format="zip"
        )
        print(f"Export result: {result}")
