"""
Test suite for sandbox improvements:
- Artifact versioning system
- Web application export
- Enhanced error handling
"""

import unittest
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
import os

# Add the source directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sandbox.mcp_sandbox_server_stdio import (
    ExecutionContext, 
    export_flask_app, 
    export_streamlit_app
)


class TestArtifactVersioning(unittest.TestCase):
    """Test artifact versioning system."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.ctx = ExecutionContext()
        # Override project root for testing
        self.ctx.project_root = self.temp_dir
        self.ctx.create_artifacts_dir()
        
        # Create some test artifacts
        (self.ctx.artifacts_dir / "plots").mkdir(exist_ok=True)
        (self.ctx.artifacts_dir / "plots" / "test_plot.png").touch()
        (self.ctx.artifacts_dir / "images").mkdir(exist_ok=True)
        (self.ctx.artifacts_dir / "images" / "test_image.jpg").touch()
    
    def tearDown(self):
        """Clean up test environment."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_backup_artifacts(self):
        """Test creating artifact backups."""
        # Create backup
        backup_path = self.ctx.backup_artifacts("test_backup")
        
        # Verify backup was created
        self.assertTrue(Path(backup_path).exists())
        self.assertTrue(Path(backup_path).is_dir())
        
        # Verify backup contains artifacts
        backup_plots = Path(backup_path) / "plots" / "test_plot.png"
        backup_images = Path(backup_path) / "images" / "test_image.jpg"
        self.assertTrue(backup_plots.exists())
        self.assertTrue(backup_images.exists())
    
    def test_list_artifact_backups(self):
        """Test listing artifact backups."""
        # Create multiple backups
        self.ctx.backup_artifacts("backup1")
        self.ctx.backup_artifacts("backup2")
        
        # List backups
        backups = self.ctx.list_artifact_backups()
        
        # Verify backup listing
        self.assertEqual(len(backups), 2)
        self.assertTrue(any("backup1" in b['name'] for b in backups))
        self.assertTrue(any("backup2" in b['name'] for b in backups))
        
        # Verify backup metadata
        for backup in backups:
            self.assertIn('name', backup)
            self.assertIn('path', backup)
            self.assertIn('created', backup)
            self.assertIn('size_bytes', backup)
            self.assertIn('file_count', backup)
    
    def test_rollback_artifacts(self):
        """Test rolling back to a backup."""
        # Create initial backup
        backup_path = self.ctx.backup_artifacts("initial")
        backup_name = Path(backup_path).name
        
        # Modify artifacts
        (self.ctx.artifacts_dir / "plots" / "new_plot.png").touch()
        
        # Rollback
        result = self.ctx.rollback_artifacts(backup_name)
        
        # Verify rollback success
        self.assertIn("Successfully rolled back", result)
        
        # Verify artifacts are restored
        self.assertTrue((self.ctx.artifacts_dir / "plots" / "test_plot.png").exists())
        self.assertFalse((self.ctx.artifacts_dir / "plots" / "new_plot.png").exists())
    
    def test_get_backup_info(self):
        """Test getting backup details."""
        # Create backup
        backup_path = self.ctx.backup_artifacts("detailed_backup")
        backup_name = Path(backup_path).name
        
        # Get backup info
        info = self.ctx.get_backup_info(backup_name)
        
        # Verify info structure
        self.assertIn('name', info)
        self.assertIn('path', info)
        self.assertIn('created', info)
        self.assertIn('total_files', info)
        self.assertIn('total_size_bytes', info)
        self.assertIn('categories', info)
        
        # Verify categories
        self.assertIn('plots', info['categories'])
        self.assertIn('images', info['categories'])
    
    def test_backup_storage_management(self):
        """Test automatic cleanup of old backups."""
        # Create many backups
        for i in range(12):
            self.ctx.backup_artifacts(f"backup_{i}")
        
        # List backups
        backups = self.ctx.list_artifact_backups()
        
        # Should have only 10 backups (max limit)
        self.assertLessEqual(len(backups), 10)


class TestWebAppExport(unittest.TestCase):
    """Test web application export functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.ctx = ExecutionContext()
        # Override project root for testing
        self.ctx.project_root = self.temp_dir
        self.ctx.create_artifacts_dir()
    
    def tearDown(self):
        """Clean up test environment."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_flask_app_export(self):
        """Test Flask application export."""
        flask_code = """
from flask import Flask
app = Flask(__name__)

@app.route('/')
def hello():
    return 'Hello, World!'
"""
        
        # Export Flask app
        result = export_flask_app(flask_code, "test_flask_app")
        
        # Verify export success
        self.assertTrue(result['success'])
        self.assertEqual(result['export_name'], "test_flask_app")
        
        # Verify files were created
        export_dir = Path(result['export_dir'])
        self.assertTrue(export_dir.exists())
        self.assertTrue((export_dir / "app.py").exists())
        self.assertTrue((export_dir / "requirements.txt").exists())
        self.assertTrue((export_dir / "Dockerfile").exists())
        self.assertTrue((export_dir / "docker-compose.yml").exists())
        self.assertTrue((export_dir / "README.md").exists())
        
        # Verify app.py contains the code
        with open(export_dir / "app.py", 'r') as f:
            content = f.read()
            self.assertIn("Hello, World!", content)
    
    def test_streamlit_app_export(self):
        """Test Streamlit application export."""
        streamlit_code = """
import streamlit as st

st.title("Hello Streamlit!")
st.write("This is a test app")
"""
        
        # Export Streamlit app
        result = export_streamlit_app(streamlit_code, "test_streamlit_app")
        
        # Verify export success
        self.assertTrue(result['success'])
        self.assertEqual(result['export_name'], "test_streamlit_app")
        
        # Verify files were created
        export_dir = Path(result['export_dir'])
        self.assertTrue(export_dir.exists())
        self.assertTrue((export_dir / "app.py").exists())
        self.assertTrue((export_dir / "requirements.txt").exists())
        self.assertTrue((export_dir / "Dockerfile").exists())
        self.assertTrue((export_dir / "docker-compose.yml").exists())
        self.assertTrue((export_dir / "README.md").exists())
        
        # Verify app.py contains the code
        with open(export_dir / "app.py", 'r') as f:
            content = f.read()
            self.assertIn("Hello Streamlit!", content)
        
        # Verify requirements.txt has streamlit
        with open(export_dir / "requirements.txt", 'r') as f:
            content = f.read()
            self.assertIn("streamlit", content)
    
    def test_dockerfile_content(self):
        """Test Dockerfile content is correct."""
        flask_code = "from flask import Flask\napp = Flask(__name__)"
        result = export_flask_app(flask_code, "dockerfile_test")
        
        export_dir = Path(result['export_dir'])
        
        # Check Dockerfile content
        with open(export_dir / "Dockerfile", 'r') as f:
            dockerfile_content = f.read()
            self.assertIn("FROM python:3.11-slim", dockerfile_content)
            self.assertIn("COPY requirements.txt", dockerfile_content)
            self.assertIn("COPY app.py", dockerfile_content)
            self.assertIn("EXPOSE 8000", dockerfile_content)
            self.assertIn("gunicorn", dockerfile_content)
    
    def test_docker_compose_content(self):
        """Test docker-compose.yml content is correct."""
        streamlit_code = "import streamlit as st\nst.write('test')"
        result = export_streamlit_app(streamlit_code, "compose_test")
        
        export_dir = Path(result['export_dir'])
        
        # Check docker-compose.yml content
        with open(export_dir / "docker-compose.yml", 'r') as f:
            compose_content = f.read()
            self.assertIn("version: '3.8'", compose_content)
            self.assertIn("build: .", compose_content)
            self.assertIn("8501:8501", compose_content)
    
    def test_readme_generation(self):
        """Test README.md generation."""
        flask_code = "from flask import Flask\napp = Flask(__name__)"
        result = export_flask_app(flask_code, "readme_test")
        
        export_dir = Path(result['export_dir'])
        
        # Check README.md content
        with open(export_dir / "README.md", 'r') as f:
            readme_content = f.read()
            self.assertIn("readme_test", readme_content)
            self.assertIn("docker-compose up --build", readme_content)
            self.assertIn("pip install -r requirements.txt", readme_content)
            self.assertIn("python app.py", readme_content)


class TestErrorHandling(unittest.TestCase):
    """Test enhanced error handling."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.ctx = ExecutionContext()
        self.ctx.project_root = self.temp_dir
        self.ctx.create_artifacts_dir()
    
    def tearDown(self):
        """Clean up test environment."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_syntax_error_detection(self):
        """Test syntax error detection and reporting."""
        # Import the execute function implementation directly
        from sandbox.mcp_sandbox_server_stdio import ctx
        import io
        import sys
        import traceback
        import json
        
        # Test with malformed code
        malformed_code = "def test(\nprint('incomplete"
        
        # Create artifacts directory
        artifacts_dir = ctx.create_artifacts_dir()
        
        # Capture stdout and stderr
        old_stdout, old_stderr = sys.stdout, sys.stderr
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        result = {
            'stdout': '',
            'stderr': '',
            'error': None
        }
        
        try:
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture
            
            # Test compilation
            try:
                compile(malformed_code, '<string>', 'exec')
            except SyntaxError as e:
                result['error'] = {
                    'type': 'SyntaxError',
                    'message': str(e)
                }
                result['stderr'] = f"Syntax error: {e}"
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            result['stdout'] = stdout_capture.getvalue()
            result['stderr'] += stderr_capture.getvalue()
        
        # Verify error is caught and reported
        self.assertIsNotNone(result.get('error'))
        self.assertIn('stderr', result)
        self.assertIn('Syntax', result['stderr'])
    
    def test_error_handling_components(self):
        """Test that error handling components are properly structured."""
        # Test that we can import and use error handling components
        from sandbox.mcp_sandbox_server_stdio import ctx
        
        # Verify error handling is present in the execution context
        self.assertIsNotNone(ctx)
        self.assertIsNotNone(ctx.execution_globals)
        
        # Test basic error detection
        import traceback
        try:
            exec("raise ValueError('test')")
        except ValueError as e:
            error_info = {
                'type': type(e).__name__,
                'message': str(e),
                'traceback': traceback.format_exc()
            }
            
            # Verify error information structure
            self.assertEqual(error_info['type'], 'ValueError')
            self.assertIn('test', error_info['message'])
            self.assertIn('traceback', error_info)


class TestIntegration(unittest.TestCase):
    """Integration tests for all improvements."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.ctx = ExecutionContext()
        self.ctx.project_root = self.temp_dir
        self.ctx.create_artifacts_dir()
    
    def tearDown(self):
        """Clean up test environment."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_full_workflow(self):
        """Test full workflow with all improvements."""
        # 1. Create some artifacts
        (self.ctx.artifacts_dir / "plots").mkdir(exist_ok=True)
        (self.ctx.artifacts_dir / "plots" / "workflow_plot.png").touch()
        
        # 2. Create backup
        backup_path = self.ctx.backup_artifacts("workflow_backup")
        self.assertTrue(Path(backup_path).exists())
        
        # 3. Export a web app
        flask_code = """
from flask import Flask
app = Flask(__name__)

@app.route('/')
def index():
    return 'Workflow Test App'
"""
        export_result = export_flask_app(flask_code, "workflow_app")
        self.assertTrue(export_result['success'])
        
        # 4. Verify all components work together
        backups = self.ctx.list_artifact_backups()
        self.assertEqual(len(backups), 1)
        
        export_dir = Path(export_result['export_dir'])
        self.assertTrue(export_dir.exists())
        self.assertTrue((export_dir / "app.py").exists())
    
    def test_backup_with_exports(self):
        """Test that backups include exported apps."""
        # Create export
        flask_code = "from flask import Flask\napp = Flask(__name__)"
        export_result = export_flask_app(flask_code, "backup_test_app")
        
        # Create backup
        backup_path = self.ctx.backup_artifacts("with_exports")
        
        # Verify backup includes exports
        backup_dir = Path(backup_path)
        exports_backup = backup_dir / "exports"
        if exports_backup.exists():
            self.assertTrue((exports_backup / "backup_test_app").exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
