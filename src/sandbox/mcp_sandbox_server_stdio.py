from fastmcp import FastMCP
import io
import sys
import os
import traceback
import json
import uuid
import tempfile
import shutil
import subprocess
from .core.resource_manager import get_resource_manager
from .core.security import get_security_manager, SecurityLevel
import threading
import time
import socket
import base64
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

# Set up logging to file instead of stderr to avoid MCP protocol interference
log_file = Path(tempfile.gettempdir()) / "sandbox_mcp_server.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        # Only use console handler for critical errors
        logging.StreamHandler(sys.stderr) if os.getenv('SANDBOX_MCP_DEBUG') else logging.NullHandler()
    ]
)
logger = logging.getLogger(__name__)

# Create FastMCP server named "python-sandbox"
mcp = FastMCP("python-sandbox")

# Global state for execution context
class ExecutionContext:
    def __init__(self):
        # Compute project_root dynamically from current file location
        # When installed as package, __file__ is in src/sandbox/, so go up 2 levels
        current_file = Path(__file__).resolve()
        if 'src/sandbox' in str(current_file):
            # Installed package: go from src/sandbox/mcp_*.py to project root
            self.project_root = current_file.parent.parent.parent
        else:
            # Development: assume file is in project root
            self.project_root = current_file.parent
        
        # Set up sandbox working area one level above project root
        self.sandbox_area = self.project_root.parent / "sandbox_area"
        self.sandbox_area.mkdir(exist_ok=True)
        
        self.venv_path = self.project_root / ".venv"
        self.artifacts_dir = None
        self.web_servers = {}  # Track running web servers
        self.execution_globals = {}  # Persistent globals across executions
        self.compilation_cache = {}  # Cache for compiled code
        self.cache_hits = 0
        self.cache_misses = 0
        self._setup_environment()
    
    def _setup_environment(self):
        """Setup sys.path and virtual environment with robust path detection."""
        # Compute absolute paths
        project_root_str = str(self.project_root)
        project_parent_str = str(self.project_root.parent)  # Add parent to find 'sandbox' package
        
        # Detect venv site-packages dynamically
        venv_site_packages = None
        if self.venv_path.exists():
            # Try multiple Python versions
            for py_version in ['python3.11', 'python3.12', 'python3.10', 'python3.9']:
                candidate = self.venv_path / "lib" / py_version / "site-packages"
                if candidate.exists():
                    venv_site_packages = candidate
                    break
        
        # De-duplicate sys.path using OrderedDict to preserve order
        from collections import OrderedDict
        current_paths = OrderedDict.fromkeys(sys.path)
        
        # Paths to add (parent first for package imports, then project root)
        paths_to_add = [project_parent_str, project_root_str]
        if venv_site_packages:
            paths_to_add.append(str(venv_site_packages))
        
        # Add new paths at the beginning, preserving order and avoiding duplicates
        new_sys_path = []
        for path in paths_to_add:
            if path not in current_paths:
                new_sys_path.append(path)
                current_paths[path] = None  # Mark as added
        
        # Rebuild sys.path with new paths first
        sys.path[:] = new_sys_path + list(current_paths.keys())
        
        # Set up virtual environment activation
        if self.venv_path.exists():
            venv_python = self.venv_path / "bin" / "python"
            venv_bin = self.venv_path / "bin"
            
            if venv_python.exists():
                # Set environment variables for venv activation
                os.environ['VIRTUAL_ENV'] = str(self.venv_path)
                
                # Prepend venv/bin to PATH if not already present
                current_path = os.environ.get('PATH', '')
                venv_bin_str = str(venv_bin)
                if venv_bin_str not in current_path.split(os.pathsep):
                    os.environ['PATH'] = f"{venv_bin_str}{os.pathsep}{current_path}"
                
                # Update sys.executable to point to venv python
                sys.executable = str(venv_python)
        
        logger.info(f"Project root: {self.project_root}")
        logger.info(f"Virtual env: {self.venv_path if self.venv_path.exists() else 'Not found'}")
        logger.info(f"sys.executable: {sys.executable}")
        logger.info(f"sys.path (first 5): {sys.path[:5]}")
        logger.info(f"VIRTUAL_ENV: {os.environ.get('VIRTUAL_ENV', 'Not set')}")
    
    def create_artifacts_dir(self) -> str:
        """Create a structured directory for execution artifacts within the project."""
        execution_id = str(uuid.uuid4())[:8]
        # Create artifacts directory within project
        artifacts_root = self.project_root / "artifacts"
        artifacts_root.mkdir(exist_ok=True)
        
        # Create session-specific directory with timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = f"session_{timestamp}_{execution_id}"
        
        self.artifacts_dir = artifacts_root / session_dir
        self.artifacts_dir.mkdir(exist_ok=True)
        
        # Create subdirectories for different artifact types (expanded categories)
        (self.artifacts_dir / "plots").mkdir(exist_ok=True)
        (self.artifacts_dir / "images").mkdir(exist_ok=True)
        (self.artifacts_dir / "animations").mkdir(exist_ok=True)
        (self.artifacts_dir / "files").mkdir(exist_ok=True)
        (self.artifacts_dir / "audio").mkdir(exist_ok=True)
        (self.artifacts_dir / "data").mkdir(exist_ok=True)
        (self.artifacts_dir / "models").mkdir(exist_ok=True)
        (self.artifacts_dir / "documents").mkdir(exist_ok=True)
        (self.artifacts_dir / "web_assets").mkdir(exist_ok=True)
        
        return str(self.artifacts_dir)
    
    def cleanup_artifacts(self):
        """Clean up artifacts directory."""
        if self.artifacts_dir and self.artifacts_dir.exists():
            shutil.rmtree(self.artifacts_dir, ignore_errors=True)
    
    def backup_artifacts(self, backup_name: str = None) -> str:
        """Create a versioned backup of current artifacts."""
        if not self.artifacts_dir or not self.artifacts_dir.exists():
            return "No artifacts directory to backup"
        
        # Create backup directory structure
        backup_root = self.project_root / "artifact_backups"
        backup_root.mkdir(exist_ok=True)
        
        # Generate backup name with timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if backup_name:
            backup_name = f"{backup_name}_{timestamp}"
        else:
            backup_name = f"backup_{timestamp}"
        
        backup_path = backup_root / backup_name
        
        # Copy artifacts to backup
        shutil.copytree(self.artifacts_dir, backup_path)
        
        # Cleanup old backups to manage storage
        self._cleanup_old_backups(backup_root)
        
        return str(backup_path)
    
    def _cleanup_old_backups(self, backup_root: Path, max_backups: int = 10):
        """Clean up old backup directories to prevent storage overflow."""
        try:
            # Get all backup directories sorted by modification time
            backups = [d for d in backup_root.iterdir() if d.is_dir()]
            backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # Remove old backups beyond the limit
            for backup in backups[max_backups:]:
                shutil.rmtree(backup, ignore_errors=True)
                logger.info(f"Removed old backup: {backup}")
                
        except Exception as e:
            logger.warning(f"Failed to cleanup old backups: {e}")
    
    def list_artifact_backups(self) -> List[Dict[str, Any]]:
        """List all available artifact backups."""
        backup_root = self.project_root / "artifact_backups"
        if not backup_root.exists():
            return []
        
        backups = []
        for backup_dir in backup_root.iterdir():
            if backup_dir.is_dir():
                try:
                    stat = backup_dir.stat()
                    size = sum(f.stat().st_size for f in backup_dir.rglob('*') if f.is_file())
                    backups.append({
                        'name': backup_dir.name,
                        'path': str(backup_dir),
                        'created': stat.st_ctime,
                        'modified': stat.st_mtime,
                        'size_bytes': size,
                        'size_mb': size / (1024 * 1024),
                        'file_count': len(list(backup_dir.rglob('*')))
                    })
                except Exception as e:
                    logger.warning(f"Failed to stat backup {backup_dir}: {e}")
        
        # Sort by creation time (newest first)
        backups.sort(key=lambda x: x['created'], reverse=True)
        return backups
    
    def rollback_artifacts(self, backup_name: str) -> str:
        """Rollback to a previous artifact version with improved validation."""
        backup_root = self.project_root / "artifact_backups"
        
        # Enhanced validation
        if not backup_root.exists():
            return f"No backups directory found. Available backups: none"
        
        backup_path = backup_root / backup_name
        
        if not backup_path.exists():
            # Provide helpful feedback about available backups
            available_backups = [d.name for d in backup_root.iterdir() if d.is_dir()]
            if available_backups:
                return f"Backup '{backup_name}' not found. Available backups: {', '.join(available_backups[:5])}{'...' if len(available_backups) > 5 else ''}"
            else:
                return f"Backup '{backup_name}' not found. No backups available."
        
        if not self.artifacts_dir:
            return "No current artifacts directory. Please create artifacts first."
        
        # Create backup of current artifacts before rollback
        current_backup = self.backup_artifacts("pre_rollback")
        
        try:
            # Remove current artifacts
            if self.artifacts_dir and self.artifacts_dir.exists():
                shutil.rmtree(self.artifacts_dir)
            
            # Copy backup to current artifacts location
            shutil.copytree(backup_path, self.artifacts_dir)
            
            return f"Successfully rolled back to backup '{backup_name}'. Previous state saved as '{Path(current_backup).name}'"
            
        except Exception as e:
            return f"Failed to rollback: {str(e)}"
    
    def get_backup_info(self, backup_name: str) -> Dict[str, Any]:
        """Get detailed information about a specific backup."""
        backup_root = self.project_root / "artifact_backups"
        backup_path = backup_root / backup_name
        
        if not backup_path.exists():
            return {'error': f"Backup '{backup_name}' not found"}
        
        try:
            stat = backup_path.stat()
            files = list(backup_path.rglob('*'))
            
            # Categorize files
            categories = {}
            for file_path in files:
                if file_path.is_file():
                    category = file_path.parent.name
                    if category not in categories:
                        categories[category] = []
                    categories[category].append({
                        'name': file_path.name,
                        'size': file_path.stat().st_size,
                        'extension': file_path.suffix
                    })
            
            return {
                'name': backup_name,
                'path': str(backup_path),
                'created': stat.st_ctime,
                'modified': stat.st_mtime,
                'total_files': len([f for f in files if f.is_file()]),
                'total_size_bytes': sum(f.stat().st_size for f in files if f.is_file()),
                'categories': categories
            }
            
        except Exception as e:
            return {'error': f"Failed to get backup info: {str(e)}"}

# Global execution context
ctx = ExecutionContext()
resource_manager = get_resource_manager()
security_manager = get_security_manager(SecurityLevel.MEDIUM)

def monkey_patch_matplotlib():
    """Monkey patch matplotlib to save plots to artifacts directory."""
    try:
        import matplotlib
        matplotlib.use('Agg')  # Use non-interactive backend
        import matplotlib.pyplot as plt
        
        original_show = plt.show
        
        def patched_show(*args, **kwargs):
            if ctx.artifacts_dir:
                plots_dir = ctx.artifacts_dir / "plots"
                plots_dir.mkdir(exist_ok=True)
                figure_path = plots_dir / f"plot_{uuid.uuid4().hex[:8]}.png"
                plt.savefig(figure_path, dpi=150, bbox_inches='tight')
                logger.info(f"Plot saved to: {figure_path}")
            return original_show(*args, **kwargs)
        
        plt.show = patched_show
        return True
    except ImportError:
        return False

def execute_manim_code(manim_code: str, quality: str = 'medium_quality') -> Dict[str, Any]:
    """Execute Manim code and save animation to artifacts directory with enhanced support."""
    if not ctx.artifacts_dir:
        ctx.create_artifacts_dir()
    
    # Create a subdirectory for this specific animation
    animation_id = str(uuid.uuid4())[:8]
    manim_dir = ctx.artifacts_dir / f"manim_{animation_id}"
    manim_dir.mkdir(exist_ok=True)
    
    script_path = manim_dir / "scene.py"
    
    result = {
        'success': False,
        'output': '',
        'error': None,
        'video_path': None,
        'animation_id': animation_id,
        'artifacts_dir': str(manim_dir),
        'scenes_found': [],
        'execution_time': 0
    }
    
    start_time = time.time()
    
    try:
        # Enhance Manim code with proper imports if missing
        if 'from manim import *' not in manim_code and 'import manim' not in manim_code:
            manim_code = 'from manim import *\n' + manim_code
        
        # Write the Manim script
        with open(script_path, 'w') as f:
            f.write(manim_code)
        
        # Determine quality flags
        quality_flags = {
            'low_quality': ['-ql'],
            'medium_quality': ['-qm'],
            'high_quality': ['-qh'],
            'production_quality': ['-qp']
        }.get(quality, ['-qm'])
        
        # Try to use virtual environment first
        manim_executable = None
        if ctx.venv_path.exists():
            venv_manim = ctx.venv_path / 'bin' / 'manim'
            if venv_manim.exists():
                manim_executable = str(venv_manim)
        
        # Fallback to system manim or python -m manim
        if not manim_executable:
            # Try python -m manim with virtual environment python
            if ctx.venv_path.exists():
                venv_python = ctx.venv_path / 'bin' / 'python'
                if venv_python.exists():
                    cmd = [str(venv_python), '-m', 'manim'] + quality_flags + [str(script_path)]
                else:
                    cmd = [sys.executable, '-m', 'manim'] + quality_flags + [str(script_path)]
            else:
                cmd = [sys.executable, '-m', 'manim'] + quality_flags + [str(script_path)]
        else:
            cmd = [manim_executable] + quality_flags + [str(script_path)]
        
        # Set up environment for Manim execution
        env = os.environ.copy()
        if ctx.venv_path.exists():
            env['VIRTUAL_ENV'] = str(ctx.venv_path)
            env['PATH'] = f"{ctx.venv_path / 'bin'}{os.pathsep}{env.get('PATH', '')}"
        
        logger.info(f"Executing Manim with command: {' '.join(cmd)}")
        
        process = subprocess.run(
            cmd,
            cwd=str(manim_dir),
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            env=env
        )
        
        result['output'] = process.stdout
        result['execution_time'] = time.time() - start_time
        
        if process.returncode == 0:
            result['success'] = True
            
            # Find the generated files
            media_dir = manim_dir / "media"
            if media_dir.exists():
                # Look for video files
                video_files = list(media_dir.rglob("*.mp4"))
                image_files = list(media_dir.rglob("*.png"))
                
                if video_files:
                    result['video_path'] = str(video_files[0])
                    logger.info(f"Manim animation saved to: {video_files[0]}")
                
                if image_files:
                    result['image_files'] = [str(f) for f in image_files]
                
                # Extract scene names from output
                import re
                scene_matches = re.findall(r'Scene: ([A-Za-z0-9_]+)', result['output'])
                result['scenes_found'] = scene_matches
                
                if not video_files and not image_files:
                    result['error'] = 'No output files generated'
            else:
                result['error'] = 'No media directory found'
        else:
            result['success'] = False
            result['error'] = process.stderr or 'Manim execution failed'
            
    except subprocess.TimeoutExpired:
        result['error'] = 'Manim execution timed out (5 minutes)'
        result['execution_time'] = time.time() - start_time
    except Exception as e:
        result['error'] = f'Error during Manim execution: {str(e)}'
        result['execution_time'] = time.time() - start_time
        logger.error(f"Manim execution error: {e}")
    
    return result

def monkey_patch_pil():
    """Monkey patch PIL to save images to artifacts directory."""
    try:
        from PIL import Image
        
        original_show = Image.Image.show
        original_save = Image.Image.save
        
        def patched_show(self, title=None, command=None):
            if ctx.artifacts_dir:
                images_dir = ctx.artifacts_dir / "images"
                images_dir.mkdir(exist_ok=True)
                image_path = images_dir / f"image_{uuid.uuid4().hex[:8]}.png"
                self.save(image_path)
                logger.info(f"Image saved to: {image_path}")
            return original_show(self, title, command)
        
        def patched_save(self, fp, format=None, **params):
            result = original_save(self, fp, format, **params)
            # If saving to artifacts dir, log it
            if ctx.artifacts_dir and str(fp).startswith(str(ctx.artifacts_dir)):
                logger.info(f"Image saved to artifacts: {fp}")
            return result
        
        Image.Image.show = patched_show
        Image.Image.save = patched_save
        return True
    except ImportError:
        return False

def find_free_port(start_port=8000):
    """Find a free port starting from start_port."""
    for port in range(start_port, start_port + 100):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return port
        except OSError:
            continue
    raise RuntimeError("No free ports available")

def launch_web_app(code: str, app_type: str) -> Optional[str]:
    """Launch a web application and return the URL."""
    try:
        resource_manager.check_resource_limits()
        port = find_free_port()
        resource_manager.process_manager.cleanup_finished()
    
        if app_type == 'flask':
            # Modify Flask code to run on specific port
            modified_code = code + f"\nif __name__ == '__main__': app.run(host='127.0.0.1', port={port}, debug=False)"
        elif app_type == 'streamlit':
            # For Streamlit, we need to create a temporary file and run it
            script_path = ctx.artifacts_dir / f"streamlit_app_{uuid.uuid4().hex[:8]}.py"
            with open(script_path, 'w') as f:
                f.write(code)
            
            # Launch Streamlit in subprocess
            cmd = [sys.executable, '-m', 'streamlit', 'run', str(script_path), '--server.port', str(port), '--server.headless', 'true']
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Register process with resource manager
            process_id = resource_manager.process_manager.add_process(
                process, 
                name=f"streamlit_{port}",
                metadata={'type': 'streamlit', 'port': port}
            )
            
            # Give it time to start
            time.sleep(2)
            
            if process.poll() is None:  # Still running
                url = f"http://127.0.0.1:{port}"
                ctx.web_servers[url] = process_id
                return url
            else:
                return None
        else:
            return None
        
        if app_type == 'flask':
            # Execute the modified Flask code in a separate thread
            def run_flask():
                exec(modified_code, ctx.execution_globals)
            
            # Use resource manager for thread management
            future = resource_manager.thread_pool.submit(run_flask)
            time.sleep(1)  # Give Flask time to start
            
            url = f"http://127.0.0.1:{port}"
            return url
            
    except Exception as e:
        logger.error(f"Failed to launch web app: {e}")
        return None

def export_flask_app(code: str, export_name: str = None) -> Dict[str, Any]:
    """Export Flask application as static files and Docker container."""
    if not ctx.artifacts_dir:
        ctx.create_artifacts_dir()
    
    export_id = str(uuid.uuid4())[:8]
    export_name = export_name or f"flask_app_{export_id}"
    export_dir = ctx.artifacts_dir / "exports" / export_name
    export_dir.mkdir(parents=True, exist_ok=True)
    
    result = {
        'success': False,
        'export_name': export_name,
        'export_dir': str(export_dir),
        'files_created': [],
        'docker_image': None,
        'static_site': None,
        'error': None
    }
    
    try:
        # Create Flask app file
        app_file = export_dir / "app.py"
        with open(app_file, 'w') as f:
            f.write(code)
        result['files_created'].append(str(app_file))
        
        # Create requirements.txt
        requirements_file = export_dir / "requirements.txt"
        with open(requirements_file, 'w') as f:
            f.write("Flask>=2.0.0\n")
            f.write("gunicorn>=20.0.0\n")
        result['files_created'].append(str(requirements_file))
        
        # Create Dockerfile
        dockerfile = export_dir / "Dockerfile"
        dockerfile_content = '''FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]
'''
        with open(dockerfile, 'w') as f:
            f.write(dockerfile_content)
        result['files_created'].append(str(dockerfile))
        
        # Create docker-compose.yml
        compose_file = export_dir / "docker-compose.yml"
        compose_content = f'''version: '3.8'
services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - FLASK_ENV=production
'''
        with open(compose_file, 'w') as f:
            f.write(compose_content)
        result['files_created'].append(str(compose_file))
        
        # Create README.md with instructions
        readme_file = export_dir / "README.md"
        readme_content = f'''# {export_name}

Exported Flask application from sandbox.

## Running with Docker

```bash
docker-compose up --build
```

The application will be available at http://localhost:8000

## Running locally

```bash
pip install -r requirements.txt
python app.py
```

## Files

- `app.py` - Main Flask application
- `requirements.txt` - Python dependencies
- `Dockerfile` - Docker configuration
- `docker-compose.yml` - Docker Compose configuration
'''
        with open(readme_file, 'w') as f:
            f.write(readme_content)
        result['files_created'].append(str(readme_file))
        
        # Try to build Docker image if Docker is available
        try:
            docker_build_result = subprocess.run(
                ['docker', 'build', '-t', f'sandbox-{export_name}', str(export_dir)],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if docker_build_result.returncode == 0:
                result['docker_image'] = f'sandbox-{export_name}'
                logger.info(f"Docker image built successfully: sandbox-{export_name}")
            else:
                logger.warning(f"Docker build failed: {docker_build_result.stderr}")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.info("Docker not available or build timed out")
        
        result['success'] = True
        result['export_dir'] = str(export_dir)
        
    except Exception as e:
        result['error'] = str(e)
        logger.error(f"Failed to export Flask app: {e}")
    
    return result

def export_streamlit_app(code: str, export_name: str = None) -> Dict[str, Any]:
    """Export Streamlit application as Docker container."""
    if not ctx.artifacts_dir:
        ctx.create_artifacts_dir()
    
    export_id = str(uuid.uuid4())[:8]
    export_name = export_name or f"streamlit_app_{export_id}"
    export_dir = ctx.artifacts_dir / "exports" / export_name
    export_dir.mkdir(parents=True, exist_ok=True)
    
    result = {
        'success': False,
        'export_name': export_name,
        'export_dir': str(export_dir),
        'files_created': [],
        'docker_image': None,
        'error': None
    }
    
    try:
        # Create Streamlit app file
        app_file = export_dir / "app.py"
        with open(app_file, 'w') as f:
            f.write(code)
        result['files_created'].append(str(app_file))
        
        # Create requirements.txt
        requirements_file = export_dir / "requirements.txt"
        with open(requirements_file, 'w') as f:
            f.write("streamlit>=1.28.0\n")
            f.write("pandas>=1.5.0\n")
            f.write("numpy>=1.24.0\n")
        result['files_created'].append(str(requirements_file))
        
        # Create Dockerfile
        dockerfile = export_dir / "Dockerfile"
        dockerfile_content = '''FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
'''
        with open(dockerfile, 'w') as f:
            f.write(dockerfile_content)
        result['files_created'].append(str(dockerfile))
        
        # Create docker-compose.yml
        compose_file = export_dir / "docker-compose.yml"
        compose_content = f'''version: '3.8'
services:
  web:
    build: .
    ports:
      - "8501:8501"
    environment:
      - STREAMLIT_SERVER_PORT=8501
      - STREAMLIT_SERVER_ADDRESS=0.0.0.0
'''
        with open(compose_file, 'w') as f:
            f.write(compose_content)
        result['files_created'].append(str(compose_file))
        
        # Create README.md with instructions
        readme_file = export_dir / "README.md"
        readme_content = f'''# {export_name}

Exported Streamlit application from sandbox.

## Running with Docker

```bash
docker-compose up --build
```

The application will be available at http://localhost:8501

## Running locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Files

- `app.py` - Main Streamlit application
- `requirements.txt` - Python dependencies
- `Dockerfile` - Docker configuration
- `docker-compose.yml` - Docker Compose configuration
'''
        with open(readme_file, 'w') as f:
            f.write(readme_content)
        result['files_created'].append(str(readme_file))
        
        # Try to build Docker image if Docker is available
        try:
            docker_build_result = subprocess.run(
                ['docker', 'build', '-t', f'sandbox-{export_name}', str(export_dir)],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if docker_build_result.returncode == 0:
                result['docker_image'] = f'sandbox-{export_name}'
                logger.info(f"Docker image built successfully: sandbox-{export_name}")
            else:
                logger.warning(f"Docker build failed: {docker_build_result.stderr}")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.info("Docker not available or build timed out")
        
        result['success'] = True
        result['export_dir'] = str(export_dir)
        
    except Exception as e:
        result['error'] = str(e)
        logger.error(f"Failed to export Streamlit app: {e}")
    
    return result

def collect_artifacts() -> List[Dict[str, Any]]:
    """Collect all artifacts from the artifacts directory (recursive)."""
    artifacts = []
    if not ctx.artifacts_dir or not ctx.artifacts_dir.exists():
        return artifacts
    
    # Use rglob to search recursively through all subdirectories
    for file_path in ctx.artifacts_dir.rglob('*'):
        if file_path.is_file():
            try:
                # Read file as base64 for embedding
                with open(file_path, 'rb') as f:
                    content = base64.b64encode(f.read()).decode('utf-8')
                
                # Calculate relative path from artifacts_dir for better organization
                relative_path = file_path.relative_to(ctx.artifacts_dir)
                
                artifacts.append({
                    'name': file_path.name,
                    'path': str(file_path),
                    'relative_path': str(relative_path),
                    'type': file_path.suffix.lower(),
                    'content_base64': content,
                    'size': file_path.stat().st_size,
                    'category': file_path.parent.name  # e.g., 'plots', 'images', etc.
                })
            except Exception as e:
                logger.error(f"Error reading artifact {file_path}: {e}")
    
    return artifacts

@mcp.tool
def execute(code: str, interactive: bool = False, web_app_type: Optional[str] = None) -> str:
    """
    Execute Python code with enhanced features:
    - Robust sys.path and venv activation
    - Module import error handling with full traceback
    - Artifact interception and storage
    - Web app launch support
    - Interactive REPL mode
    
    Args:
        code: Python code to execute
        interactive: If True, drop into interactive REPL after execution
        web_app_type: Type of web app to launch ('flask' or 'streamlit')
    
    Returns:
        JSON string containing execution results, artifacts, and metadata
    """
    # Create artifacts directory for this execution
    artifacts_dir = ctx.create_artifacts_dir()
    
    # Set up monkey patches
    matplotlib_patched = monkey_patch_matplotlib()
    pil_patched = monkey_patch_pil()
    
    # Capture stdout and stderr
    old_stdout, old_stderr = sys.stdout, sys.stderr
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    
    result = {
        'stdout': '',
        'stderr': '',
        'error': None,
        'artifacts': [],
        'web_url': None,
        'execution_info': {
            'sys_executable': sys.executable,
            'sys_path_first_3': sys.path[:3],
            'project_root': str(ctx.project_root),
            'artifacts_dir': artifacts_dir,
            'matplotlib_patched': matplotlib_patched,
            'pil_patched': pil_patched
        }
    }
    
    try:
        sys.stdout = stdout_capture
        sys.stderr = stderr_capture
        
        # Check if this is a web app
        if web_app_type in ['flask', 'streamlit']:
            url = launch_web_app(code, web_app_type)
            if url:
                result['web_url'] = url
                result['stdout'] = f"Web application launched at: {url}"
            else:
                result['stderr'] = f"Failed to launch {web_app_type} application"
        else:
            # Regular code execution
            logger.debug(f"Executing code: {repr(code)}")
            logger.debug(f"Code length: {len(code)}")
            logger.debug(f"Code lines: {code.count(chr(10)) + 1}")
            
            # Check for common issues that might indicate truncation
            if len(code) > 10:  # Only check for non-trivial code
                # Check for unterminated strings or parentheses
                if code.count('"') % 2 != 0 or code.count("'") % 2 != 0:
                    logger.warning("Code appears to have unmatched quotes - possible truncation")
                    result['stderr'] = "Warning: Code appears to have unmatched quotes. This might indicate the code was truncated during transmission."
                
                # Check for unmatched parentheses
                open_parens = code.count('(') - code.count(')')
                if open_parens != 0:
                    logger.warning(f"Code has unmatched parentheses ({open_parens} open) - possible truncation")
                    result['stderr'] = f"Warning: Code has {open_parens} unmatched opening parentheses. This might indicate the code was truncated during transmission."
            
            # Test compilation first
            try:
                compile(code, '<string>', 'exec')
                logger.debug("Code compilation successful")
            except SyntaxError as e:
                logger.error(f"Syntax error during compilation: {e}")
                logger.error(f"Error line: {e.lineno}")
                logger.error(f"Error text: {e.text}")
                logger.error(f"Error position: {e.offset}")
                
                # Provide helpful error message if it looks like truncation
                if 'was never closed' in str(e) or 'unterminated' in str(e).lower():
                    error_msg = (f"Syntax error: {e}\n\n"
                               f"This error often occurs when code is truncated during transmission.\n"
                               f"The code received was {len(code)} characters long with {code.count(chr(10)) + 1} lines.\n"
                               f"Please try sending the code in smaller chunks or verify the complete code was transmitted.")
                    result['stderr'] = error_msg
                    result['error'] = {
                        'type': 'TruncationError',
                        'message': error_msg,
                        'original_error': str(e),
                        'code_length': len(code),
                        'code_lines': code.count(chr(10)) + 1
                    }
                    return json.dumps(result, indent=2)
                
                raise
            exec(code, ctx.execution_globals)
        
        # Interactive REPL mode
        if interactive:
            result['stdout'] += "\n[Interactive mode enabled - code executed successfully]\n"
            result['stdout'] += "Note: REPL mode would be available in a real terminal session\n"
    
    except ImportError as e:
        # Enhanced import error handling
        error_trace = traceback.format_exc()
        module_name = str(e).split("'")[1] if "'" in str(e) else "unknown"
        
        error_details = {
            'type': 'ImportError',
            'message': str(e),
            'module': module_name,
            'traceback': error_trace,
            'sys_path': sys.path[:5],  # First 5 paths for debugging
            'attempted_paths': [p for p in sys.path if Path(p).exists()]
        }
        result['error'] = error_details
        result['stderr'] = f"Import Error: {e}\n\nFull traceback:\n{error_trace}"
    
    except Exception as e:
        # General exception handling
        error_trace = traceback.format_exc()
        result['error'] = {
            'type': type(e).__name__,
            'message': str(e),
            'traceback': error_trace
        }
        result['stderr'] = f"Error: {e}\n\nFull traceback:\n{error_trace}"
    
    finally:
        # Restore stdout/stderr
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        
        # Capture output
        result['stdout'] += stdout_capture.getvalue()
        result['stderr'] += stderr_capture.getvalue()
        
        # Collect artifacts
        result['artifacts'] = collect_artifacts()
    
    return json.dumps(result, indent=2)

@mcp.tool
def list_artifacts() -> str:
    """List all current artifacts with detailed information."""
    artifacts = collect_artifacts()
    if not artifacts:
        return "No artifacts found."
    
    result = "Current artifacts:\n"
    result += "=" * 50 + "\n"
    
    # Group artifacts by category
    by_category = {}
    for artifact in artifacts:
        category = artifact.get('category', 'root')
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(artifact)
    
    for category, items in by_category.items():
        result += f"\n{category.upper()}:\n"
        result += "-" * 20 + "\n"
        for artifact in items:
            size_kb = artifact['size'] / 1024
            result += f"  • {artifact['name']} ({size_kb:.1f} KB) - {artifact['type']}\n"
            result += f"    Path: {artifact['relative_path']}\n"
    
    result += f"\nTotal: {len(artifacts)} artifacts\n"
    return result

@mcp.tool
def clear_cache(important_only: bool = False) -> str:
    """Clear the compilation cache, optionally preserving important commands."""
    if important_only:
        # Logic to preserve important commands goes here
        preserved_commands = ["import", "def", "class"]
        ctx.compilation_cache = {k: v for k, v in ctx.compilation_cache.items() if any(cmd in k for cmd in preserved_commands)}
    else:
        ctx.compilation_cache.clear()
    
    ctx.cache_hits = 0
    ctx.cache_misses = 0
    return "Cache cleared successfully."

@mcp.tool
def cleanup_artifacts() -> str:
    """Clean up all artifacts and temporary files."""
    ctx.cleanup_artifacts()
    # Also cleanup web servers
    for url, process in ctx.web_servers.items():
        try:
            process.terminate()
        except:
            pass
    ctx.web_servers.clear()
    return "Artifacts and web servers cleaned up."

@mcp.tool
def start_repl() -> str:
    """Start an interactive REPL session (simulated for MCP)."""
    # In a real implementation, this would stream stdin/stdout over MCP
    # For now, we provide a simulation
    return json.dumps({
        'status': 'repl_started',
        'message': 'Interactive REPL session started (simulated)',
        'note': 'In a full implementation, this would provide streaming I/O over MCP',
        'globals_available': list(ctx.execution_globals.keys()),
        'sys_path_active': sys.path[:3]
    }, indent=2)

@mcp.tool
def start_web_app(code: str, app_type: str = 'flask') -> str:
    """Launch a web application and return connection details."""
    url = launch_web_app(code, app_type)
    if url:
        return json.dumps({
            'status': 'success',
            'url': url,
            'app_type': app_type,
            'message': f'{app_type.title()} application launched successfully'
        }, indent=2)
    else:
        return json.dumps({
            'status': 'error',
            'app_type': app_type,
            'message': f'Failed to launch {app_type} application'
        }, indent=2)

@mcp.tool
def cleanup_temp_artifacts(max_age_hours: int = 24) -> str:
    """Clean up old temporary artifact directories."""
    cleaned = 0
    temp_dir = Path(tempfile.gettempdir())
    
    try:
        for item in temp_dir.glob('sandbox_artifacts_*'):
            if item.is_dir():
                # Check age
                age_hours = (time.time() - item.stat().st_mtime) / 3600
                if age_hours > max_age_hours:
                    shutil.rmtree(item, ignore_errors=True)
                    cleaned += 1
    except Exception as e:
        logger.error(f"Error during temp cleanup: {e}")
    
    return json.dumps({
        'cleaned_directories': cleaned,
        'max_age_hours': max_age_hours,
        'message': f'Cleaned {cleaned} old artifact directories'
    }, indent=2)

@mcp.tool
def shell_execute(command: str, working_directory: Optional[str] = None, timeout: int = 30) -> str:
    """
    Execute a shell command safely in a controlled environment.
    
    Args:
        command: The shell command to execute
        working_directory: Directory to run the command in (defaults to sandbox_area)
        timeout: Maximum execution time in seconds
    
    Returns:
        JSON string containing execution results, stdout, stderr, and metadata
    
    CAUTION: Commands execute in isolated sandbox_area. Avoid system modifications.
    """
    # Set working directory - default to sandbox_area for safety
    if working_directory is None:
        working_directory = str(ctx.sandbox_area)
    
    # Enhanced security checks using security manager
    is_safe, violation = security_manager.check_command_security(command)
    if not is_safe:
        return json.dumps({
            'stdout': '',
            'stderr': f'Command blocked for security: {violation.message}',
            'return_code': -1,
            'error': {
                'type': 'SecurityError',
                'message': violation.message,
                'level': violation.level.value,
                'command': command
            },
            'execution_info': {
                'working_directory': working_directory,
                'timeout': timeout,
                'command_blocked': True,
                'security_violation': True
            }
        }, indent=2)
    
    result = {
        'stdout': '',
        'stderr': '',
        'return_code': 0,
        'error': None,
        'execution_info': {
            'working_directory': working_directory,
            'timeout': timeout,
            'command': command,
            'command_blocked': False
        }
    }
    
    try:
        # Execute the command with timeout
        process = subprocess.run(
            command,
            shell=True,
            cwd=working_directory,
            timeout=timeout,
            capture_output=True,
            text=True,
            env=os.environ.copy()  # Use current environment including VIRTUAL_ENV
        )
        
        result['stdout'] = process.stdout
        result['stderr'] = process.stderr
        result['return_code'] = process.returncode
        
        if process.returncode != 0:
            result['error'] = {
                'type': 'CommandError',
                'message': f'Command failed with return code {process.returncode}',
                'return_code': process.returncode
            }
            
    except subprocess.TimeoutExpired:
        result['error'] = {
            'type': 'TimeoutError',
            'message': f'Command timed out after {timeout} seconds',
            'timeout': timeout
        }
        result['stderr'] = f'Command timed out after {timeout} seconds'
        result['return_code'] = -2
        
    except Exception as e:
        result['error'] = {
            'type': type(e).__name__,
            'message': str(e),
            'traceback': traceback.format_exc()
        }
        result['stderr'] = f'Error executing command: {e}'
        result['return_code'] = -3
    
    return json.dumps(result, indent=2)

@mcp.tool
def create_manim_animation(manim_code: str, quality: str = 'medium_quality') -> str:
    """
    Create a Manim animation from Python code.
    
    Args:
        manim_code: Python code containing Manim scene definitions
        quality: Animation quality ('low_quality', 'medium_quality', 'high_quality', 'production_quality')
    
    Returns:
        JSON string with execution results, video path, and metadata
    """
    result = execute_manim_code(manim_code, quality)
    return json.dumps(result, indent=2)

@mcp.tool
def list_manim_animations() -> str:
    """List all Manim animations in the current artifacts directory."""
    if not ctx.artifacts_dir or not ctx.artifacts_dir.exists():
        return "No artifacts directory found. Create an animation first."
    
    animations = []
    for item in ctx.artifacts_dir.iterdir():
        if item.is_dir() and item.name.startswith('manim_'):
            animation_info = {
                'animation_id': item.name.replace('manim_', ''),
                'path': str(item),
                'created': item.stat().st_ctime,
                'size_mb': sum(f.stat().st_size for f in item.rglob('*') if f.is_file()) / 1024 / 1024
            }
            
            # Find video files
            video_files = list(item.rglob('*.mp4'))
            if video_files:
                animation_info['video_file'] = str(video_files[0])
                animation_info['video_size_mb'] = video_files[0].stat().st_size / 1024 / 1024
            
            animations.append(animation_info)
    
    if not animations:
        return "No Manim animations found."
    
    return json.dumps({
        'total_animations': len(animations),
        'animations': animations
    }, indent=2)

@mcp.tool
def cleanup_manim_animation(animation_id: str) -> str:
    """Clean up a specific Manim animation directory."""
    if not ctx.artifacts_dir or not ctx.artifacts_dir.exists():
        return "No artifacts directory found."
    
    manim_dir = ctx.artifacts_dir / f"manim_{animation_id}"
    
    if not manim_dir.exists():
        return f"Animation directory not found: {animation_id}"
    
    try:
        shutil.rmtree(manim_dir)
        return f"Successfully cleaned up animation: {animation_id}"
    except Exception as e:
        return f"Failed to clean up animation {animation_id}: {str(e)}"

@mcp.tool
def get_manim_examples() -> str:
    """Get example Manim code snippets for common animations."""
    examples = {
        'simple_circle': '''
from manim import *

class SimpleCircle(Scene):
    def construct(self):
        circle = Circle()
        circle.set_fill(PINK, opacity=0.5)
        self.play(Create(circle))
        self.wait(1)
''',
        'moving_square': '''
from manim import *

class MovingSquare(Scene):
    def construct(self):
        square = Square()
        square.set_fill(BLUE, opacity=0.5)
        self.play(Create(square))
        self.play(square.animate.shift(RIGHT * 2))
        self.play(square.animate.shift(UP * 2))
        self.wait(1)
''',
        'text_animation': '''
from manim import *

class TextAnimation(Scene):
    def construct(self):
        text = Text("Hello, Manim!")
        text.set_color(YELLOW)
        self.play(Write(text))
        self.play(text.animate.scale(1.5))
        self.wait(1)
''',
        'graph_plot': '''
from manim import *

class GraphPlot(Scene):
    def construct(self):
        axes = Axes(
            x_range=[-3, 3, 1],
            y_range=[-3, 3, 1],
            x_length=6,
            y_length=6
        )
        axes.add_coordinates()
        
        graph = axes.plot(lambda x: x**2, color=BLUE)
        graph_label = axes.get_graph_label(graph, label="f(x) = x^2")
        
        self.play(Create(axes))
        self.play(Create(graph))
        self.play(Write(graph_label))
        self.wait(1)
'''
    }
    
    return json.dumps({
        'examples': examples,
        'usage': "Use create_manim_animation() with any of these examples to generate animations."
    }, indent=2)

@mcp.tool
def get_execution_info() -> str:
    """Get information about the current execution environment."""
    info = {
        'project_root': str(ctx.project_root),
        'venv_path': str(ctx.venv_path),
        'venv_active': ctx.venv_path.exists(),
        'sys_executable': sys.executable,
        'sys_path_length': len(sys.path),
        'sys_path_first_5': sys.path[:5],
        'artifacts_dir': str(ctx.artifacts_dir) if ctx.artifacts_dir else None,
        'web_servers': list(ctx.web_servers.keys()),
        'global_variables': list(ctx.execution_globals.keys()),
        'virtual_env': os.environ.get('VIRTUAL_ENV'),
        'path_contains_venv': str(ctx.venv_path / 'bin') in os.environ.get('PATH', ''),
        'current_working_directory': os.getcwd(),
        'shell_available': True,
        'manim_available': shutil.which('manim') is not None
    }
    return json.dumps(info, indent=2)

@mcp.tool
def get_artifact_report() -> str:
    """Get comprehensive artifact report with categorization and metadata."""
    if not ctx.artifacts_dir or not ctx.artifacts_dir.exists():
        return json.dumps({
            'status': 'no_artifacts',
            'message': 'No artifacts directory found. Execute some code first.'
        }, indent=2)
    
    # Use the enhanced artifact system from PersistentExecutionContext
    from .core.execution_context import PersistentExecutionContext
    
    # Create a temporary context to use the enhanced artifact methods
    temp_ctx = PersistentExecutionContext()
    temp_ctx.artifacts_dir = ctx.artifacts_dir
    
    try:
        report = temp_ctx.get_artifact_report()
        return json.dumps(report, indent=2)
    except Exception as e:
        return json.dumps({
            'status': 'error',
            'message': f'Failed to generate artifact report: {str(e)}'
        }, indent=2)

@mcp.tool
def categorize_artifacts() -> str:
    """Categorize artifacts by type with detailed metadata."""
    if not ctx.artifacts_dir or not ctx.artifacts_dir.exists():
        return json.dumps({
            'status': 'no_artifacts',
            'message': 'No artifacts directory found. Execute some code first.'
        }, indent=2)
    
    # Use the enhanced artifact system from PersistentExecutionContext
    from .core.execution_context import PersistentExecutionContext
    
    # Create a temporary context to use the enhanced artifact methods
    temp_ctx = PersistentExecutionContext()
    temp_ctx.artifacts_dir = ctx.artifacts_dir
    
    try:
        categories = temp_ctx.categorize_artifacts()
        return json.dumps(categories, indent=2)
    except Exception as e:
        return json.dumps({
            'status': 'error',
            'message': f'Failed to categorize artifacts: {str(e)}'
        }, indent=2)

@mcp.tool
def cleanup_artifacts_by_type(artifact_type: str) -> str:
    """Clean up artifacts of a specific type.
    
    Args:
        artifact_type: Type of artifacts to clean (e.g., 'images', 'videos', 'plots', 'manim')
    
    Returns:
        JSON string with cleanup results
    """
    if not ctx.artifacts_dir or not ctx.artifacts_dir.exists():
        return json.dumps({
            'status': 'no_artifacts',
            'message': 'No artifacts directory found.'
        }, indent=2)
    
    # Use the enhanced artifact system from PersistentExecutionContext
    from .core.execution_context import PersistentExecutionContext
    
    # Create a temporary context to use the enhanced artifact methods
    temp_ctx = PersistentExecutionContext()
    temp_ctx.artifacts_dir = ctx.artifacts_dir
    
    try:
        categorized = temp_ctx.categorize_artifacts()
        
        if artifact_type not in categorized:
            return json.dumps({
                'status': 'error',
                'message': f'Artifact type "{artifact_type}" not found',
                'available_types': list(categorized.keys())
            }, indent=2)
        
        cleaned_count = 0
        for file_info in categorized[artifact_type]:
            try:
                file_path = Path(file_info['full_path'])
                if file_path.exists():
                    file_path.unlink()
                    cleaned_count += 1
            except Exception as e:
                logger.warning(f"Failed to delete {file_info['path']}: {e}")
        
        return json.dumps({
            'status': 'success',
            'artifact_type': artifact_type,
            'cleaned_count': cleaned_count,
            'message': f'Successfully cleaned {cleaned_count} {artifact_type} artifacts'
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            'status': 'error',
            'message': f'Failed to cleanup artifacts: {str(e)}'
        }, indent=2)

@mcp.tool
def start_enhanced_repl() -> str:
    """Start an enhanced REPL session with IPython support and magic commands."""
    try:
        # Check if IPython is available
        try:
            import IPython
            from IPython.terminal.interactiveshell import TerminalInteractiveShell
            ipython_available = True
            ipython_version = IPython.__version__
        except ImportError:
            ipython_available = False
            ipython_version = None
        
        # Check other commonly used packages
        packages_status = {}
        common_packages = [
            'numpy', 'pandas', 'matplotlib', 'scipy', 'sklearn', 'sympy', 
            'requests', 'beautifulsoup4', 'jupyter', 'notebook', 'plotly',
            'seaborn', 'opencv-python', 'pillow', 'tensorflow', 'torch',
            'flask', 'streamlit', 'fastapi', 'django', 'manim'
        ]
        
        for package in common_packages:
            try:
                __import__(package.replace('-', '_'))
                packages_status[package] = 'available'
            except ImportError:
                packages_status[package] = 'not_installed'
        
        # Check network connectivity (basic test)
        network_available = False
        try:
            # Test connectivity to Google DNS
            import socket
            socket.create_connection(('8.8.8.8', 53), timeout=3)
            network_available = True
        except (socket.error, OSError):
            network_available = False
        
        # Start IPython session if available
        if ipython_available:
            try:
                # Create IPython shell with custom configuration
                shell = TerminalInteractiveShell.instance()
                
                # Set up custom namespace with sandbox context
                shell.user_ns.update(ctx.execution_globals)
                shell.user_ns['ctx'] = ctx
                shell.user_ns['artifacts_dir'] = ctx.artifacts_dir
                
                # Define custom magic commands
                def artifacts_magic(line):
                    """List and manage artifacts."""
                    if not line.strip():
                        return list_artifacts()
                    elif line.strip() == 'backup':
                        return backup_current_artifacts()
                    elif line.strip().startswith('backup '):
                        backup_name = line.strip()[7:]
                        return backup_current_artifacts(backup_name)
                    elif line.strip() == 'list_backups':
                        return list_artifact_backups()
                    else:
                        return "Usage: %artifacts [backup [name] | list_backups]"
                
                def install_magic(line):
                    """Install packages."""
                    if not line.strip():
                        return "Usage: %install package_name [version]"
                    parts = line.strip().split()
                    package_name = parts[0]
                    version = parts[1] if len(parts) > 1 else None
                    return install_package(package_name, version)
                
                def packages_magic(line):
                    """List installed packages."""
                    return list_installed_packages()
                
                def env_info_magic(line):
                    """Show environment information."""
                    return get_execution_info()
                
                def manim_magic(line):
                    """Execute Manim animations."""
                    if not line.strip():
                        return get_manim_examples()
                    else:
                        return create_manim_animation(line.strip())
                
                # Register magic commands
                shell.register_magic_function(artifacts_magic, 'line', 'artifacts')
                shell.register_magic_function(install_magic, 'line', 'install')
                shell.register_magic_function(packages_magic, 'line', 'packages')
                shell.register_magic_function(env_info_magic, 'line', 'env_info')
                shell.register_magic_function(manim_magic, 'line', 'manim')
                
                # Configure IPython settings
                shell.colors = 'Linux'  # Enable syntax highlighting
                shell.confirm_exit = False
                shell.history_manager.enabled = True
                
                # Set up matplotlib for inline plotting if available
                try:
                    import matplotlib
                    matplotlib.use('Agg')
                    shell.run_line_magic('matplotlib', 'inline')
                except ImportError:
                    pass
                
                # Welcome message
                welcome_msg = f"""
Welcome to Enhanced Sandbox REPL!
IPython {ipython_version} - Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}

Custom Magic Commands:
  %artifacts      - Manage artifacts
  %install pkg    - Install packages
  %packages       - List installed packages
  %env_info       - Environment information
  %manim [code]   - Manim animations

Network: {'Available' if network_available else 'Blocked'}
Packages: {len([p for p in packages_status.values() if p == 'available'])}/{len(packages_status)} available
Artifacts: {str(ctx.artifacts_dir) if ctx.artifacts_dir else 'None'}
"""
                
                print(welcome_msg)
                
                # Start the IPython session
                # Note: This would normally block, but in MCP context we return info
                repl_info = {
                    'status': 'ipython_repl_started',
                    'ipython_available': True,
                    'ipython_version': ipython_version,
                    'network_available': network_available,
                    'features': {
                        'tab_completion': True,
                        'history': True,
                        'magic_commands': True,
                        'syntax_highlighting': True,
                        'artifact_management': True,
                        'manim_support': True,
                        'virtual_env': ctx.venv_path.exists(),
                        'package_installation': ctx.venv_path.exists(),
                        'network_access': network_available,
                        'custom_magics': True
                    },
                    'available_magic_commands': [
                        '%artifacts - List and manage artifacts',
                        '%install pkg - Install packages',
                        '%packages - List installed packages',
                        '%env_info - Show environment information',
                        '%manim [code] - Execute Manim animations',
                        '%who - List variables',
                        '%whos - Detailed variable info',
                        '%history - Command history',
                        '%time - Time execution',
                        '%timeit - Benchmark code'
                    ],
                    'package_status': packages_status,
                    'missing_packages': [pkg for pkg, status in packages_status.items() if status == 'not_installed'],
                    'installed_packages': [pkg for pkg, status in packages_status.items() if status == 'available'],
                    'globals_available': list(ctx.execution_globals.keys()),
                    'artifacts_dir': str(ctx.artifacts_dir) if ctx.artifacts_dir else None,
                    'virtual_env': os.environ.get('VIRTUAL_ENV'),
                    'shell_instance': 'TerminalInteractiveShell configured',
                    'message': f'IPython {ipython_version} REPL started with custom magic commands and artifact management'
                }
                
                return json.dumps(repl_info, indent=2)
                
            except Exception as e:
                # Fall back to basic info if IPython setup fails
                repl_info = {
                    'status': 'ipython_setup_failed',
                    'ipython_available': True,
                    'ipython_version': ipython_version,
                    'error': str(e),
                    'message': f'IPython available but setup failed: {str(e)}. Falling back to basic info.'
                }
                return json.dumps(repl_info, indent=2)
        
        # Fallback for when IPython is not available
        repl_info = {
            'status': 'basic_repl_started',
            'ipython_available': False,
            'ipython_version': None,
            'network_available': network_available,
            'features': {
                'tab_completion': False,
                'history': False,
                'magic_commands': False,
                'syntax_highlighting': False,
                'artifact_management': True,
                'manim_support': True,
                'virtual_env': ctx.venv_path.exists(),
                'package_installation': ctx.venv_path.exists(),
                'network_access': network_available
            },
            'available_commands': [
                'Use execute() function to run Python code',
                'Use install_package() to install packages',
                'Use list_artifacts() to manage artifacts',
                'Use get_execution_info() for environment info'
            ],
            'package_status': packages_status,
            'missing_packages': [pkg for pkg, status in packages_status.items() if status == 'not_installed'],
            'installed_packages': [pkg for pkg, status in packages_status.items() if status == 'available'],
            'globals_available': list(ctx.execution_globals.keys()),
            'artifacts_dir': str(ctx.artifacts_dir) if ctx.artifacts_dir else None,
            'virtual_env': os.environ.get('VIRTUAL_ENV'),
            'recommendation': 'Install IPython for enhanced REPL: install_package("ipython")',
            'message': f'Basic REPL info provided. IPython not available. Network: {"available" if network_available else "blocked"}, Packages: {len([p for p in packages_status.values() if p == "available"])}/{len(packages_status)} available'
        }
        
        return json.dumps(repl_info, indent=2)
        
    except Exception as e:
        return json.dumps({
            'status': 'error',
            'message': f'Failed to start enhanced REPL: {str(e)}'
        }, indent=2)

@mcp.tool
def execute_with_artifacts(code: str, track_artifacts: bool = True) -> str:
    """Execute Python code with enhanced artifact tracking and categorization.
    
    Args:
        code: Python code to execute
        track_artifacts: Whether to track and categorize artifacts
    
    Returns:
        JSON string with execution results and detailed artifact information
    """
    # Create artifacts directory for this execution
    artifacts_dir = ctx.create_artifacts_dir()
    
    # Set up monkey patches
    matplotlib_patched = monkey_patch_matplotlib()
    pil_patched = monkey_patch_pil()
    
    # Track artifacts before execution
    from .core.execution_context import PersistentExecutionContext
    temp_ctx = PersistentExecutionContext()
    temp_ctx.artifacts_dir = Path(artifacts_dir)
    
    artifacts_before = temp_ctx._get_current_artifacts() if track_artifacts else set()
    
    # Capture stdout and stderr
    old_stdout, old_stderr = sys.stdout, sys.stderr
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    
    result = {
        'stdout': '',
        'stderr': '',
        'error': None,
        'artifacts': [],
        'artifact_report': None,
        'execution_info': {
            'sys_executable': sys.executable,
            'artifacts_dir': artifacts_dir,
            'matplotlib_patched': matplotlib_patched,
            'pil_patched': pil_patched,
            'track_artifacts': track_artifacts
        }
    }
    
    try:
        sys.stdout = stdout_capture
        sys.stderr = stderr_capture
        
        # Execute the code
        exec(code, ctx.execution_globals)
        
    except Exception as e:
        # Handle exceptions
        error_trace = traceback.format_exc()
        result['error'] = {
            'type': type(e).__name__,
            'message': str(e),
            'traceback': error_trace
        }
        result['stderr'] = f"Error: {e}\n\nFull traceback:\n{error_trace}"
    
    finally:
        # Restore stdout/stderr
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        
        # Capture output
        result['stdout'] = stdout_capture.getvalue()
        result['stderr'] += stderr_capture.getvalue()
        
        # Track new artifacts
        if track_artifacts:
            artifacts_after = temp_ctx._get_current_artifacts()
            new_artifacts = artifacts_after - artifacts_before
            
            if new_artifacts:
                result['artifacts'] = list(new_artifacts)
                result['artifact_report'] = temp_ctx.get_artifact_report()
    
    return json.dumps(result, indent=2)

@mcp.tool
def backup_current_artifacts(backup_name: str = None) -> str:
    """Create a backup of current artifacts with optional custom name.
    
    Args:
        backup_name: Optional custom name for the backup
    
    Returns:
        JSON string with backup information
    """
    backup_path = ctx.backup_artifacts(backup_name)
    
    if backup_path and backup_path != "No artifacts directory to backup":
        return json.dumps({
            'status': 'success',
            'backup_path': backup_path,
            'backup_name': Path(backup_path).name,
            'message': f'Artifacts backed up successfully to {Path(backup_path).name}'
        }, indent=2)
    else:
        return json.dumps({
            'status': 'error',
            'message': backup_path or 'Failed to create backup'
        }, indent=2)

@mcp.tool
def list_artifact_backups() -> str:
    """List all available artifact backups with detailed information.
    
    Returns:
        JSON string with backup listing
    """
    backups = ctx.list_artifact_backups()
    
    if not backups:
        return json.dumps({
            'status': 'no_backups',
            'message': 'No artifact backups found',
            'backups': []
        }, indent=2)
    
    # Format timestamps for better readability
    import datetime
    for backup in backups:
        backup['created_formatted'] = datetime.datetime.fromtimestamp(backup['created']).strftime('%Y-%m-%d %H:%M:%S')
        backup['modified_formatted'] = datetime.datetime.fromtimestamp(backup['modified']).strftime('%Y-%m-%d %H:%M:%S')
    
    return json.dumps({
        'status': 'success',
        'total_backups': len(backups),
        'backups': backups,
        'message': f'Found {len(backups)} artifact backups'
    }, indent=2)

@mcp.tool
def rollback_to_backup(backup_name: str) -> str:
    """Rollback artifacts to a previous backup version.
    
    Args:
        backup_name: Name of the backup to rollback to
    
    Returns:
        JSON string with rollback results
    """
    result = ctx.rollback_artifacts(backup_name)
    
    if "Successfully rolled back" in result:
        return json.dumps({
            'status': 'success',
            'message': result,
            'backup_name': backup_name
        }, indent=2)
    else:
        return json.dumps({
            'status': 'error',
            'message': result,
            'backup_name': backup_name
        }, indent=2)

@mcp.tool
def get_backup_details(backup_name: str) -> str:
    """Get detailed information about a specific backup.
    
    Args:
        backup_name: Name of the backup to inspect
    
    Returns:
        JSON string with backup details
    """
    backup_info = ctx.get_backup_info(backup_name)
    
    if 'error' in backup_info:
        return json.dumps({
            'status': 'error',
            'message': backup_info['error']
        }, indent=2)
    
    # Format timestamp for readability
    import datetime
    backup_info['created_formatted'] = datetime.datetime.fromtimestamp(backup_info['created']).strftime('%Y-%m-%d %H:%M:%S')
    backup_info['modified_formatted'] = datetime.datetime.fromtimestamp(backup_info['modified']).strftime('%Y-%m-%d %H:%M:%S')
    backup_info['total_size_mb'] = backup_info['total_size_bytes'] / (1024 * 1024)
    
    return json.dumps({
        'status': 'success',
        'backup_info': backup_info
    }, indent=2)

@mcp.tool
def cleanup_old_backups(max_backups: int = 10) -> str:
    """Clean up old backups, keeping only the most recent ones.
    
    Args:
        max_backups: Maximum number of backups to keep
    
    Returns:
        JSON string with cleanup results
    """
    backup_root = ctx.project_root / "artifact_backups"
    if not backup_root.exists():
        return json.dumps({
            'status': 'no_backups',
            'message': 'No backup directory found',
            'cleaned_count': 0
        }, indent=2)
    
    try:
        # Get all backup directories sorted by modification time
        backups = [d for d in backup_root.iterdir() if d.is_dir()]
        backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        cleaned_count = 0
        for backup in backups[max_backups:]:
            try:
                shutil.rmtree(backup, ignore_errors=True)
                cleaned_count += 1
                logger.info(f"Removed old backup: {backup}")
            except Exception as e:
                logger.warning(f"Failed to remove backup {backup}: {e}")
        
        return json.dumps({
            'status': 'success',
            'cleaned_count': cleaned_count,
            'remaining_backups': len(backups[:max_backups]),
            'max_backups': max_backups,
            'message': f'Cleaned up {cleaned_count} old backups, kept {len(backups[:max_backups])} most recent'
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            'status': 'error',
            'message': f'Failed to cleanup backups: {str(e)}'
        }, indent=2)

@mcp.tool
def export_web_app(code: str, app_type: str = 'flask', export_name: str = None) -> str:
    """Export a web application as Docker container for persistence.
    
    Args:
        code: The web application code
        app_type: Type of web app ('flask' or 'streamlit')
        export_name: Optional custom name for the export
    
    Returns:
        JSON string with export results
    """
    if app_type == 'flask':
        result = export_flask_app(code, export_name)
    elif app_type == 'streamlit':
        result = export_streamlit_app(code, export_name)
    else:
        return json.dumps({
            'status': 'error',
            'message': f'Unsupported app type: {app_type}. Use "flask" or "streamlit"'
        }, indent=2)
    
    return json.dumps(result, indent=2)

@mcp.tool
def list_web_app_exports() -> str:
    """List all exported web applications.
    
    Returns:
        JSON string with export listing
    """
    if not ctx.artifacts_dir:
        return json.dumps({
            'status': 'no_exports',
            'message': 'No artifacts directory found',
            'exports': []
        }, indent=2)
    
    exports_dir = ctx.artifacts_dir / "exports"
    if not exports_dir.exists():
        return json.dumps({
            'status': 'no_exports',
            'message': 'No exports directory found',
            'exports': []
        }, indent=2)
    
    exports = []
    for export_dir in exports_dir.iterdir():
        if export_dir.is_dir():
            try:
                # Determine app type from files
                app_type = 'unknown'
                if (export_dir / 'app.py').exists():
                    with open(export_dir / 'app.py', 'r') as f:
                        content = f.read()
                        if 'Flask' in content or 'flask' in content:
                            app_type = 'flask'
                        elif 'streamlit' in content or 'st.' in content:
                            app_type = 'streamlit'
                
                # Get export info
                stat = export_dir.stat()
                files = list(export_dir.glob('*'))
                
                export_info = {
                    'name': export_dir.name,
                    'path': str(export_dir),
                    'app_type': app_type,
                    'created': stat.st_ctime,
                    'modified': stat.st_mtime,
                    'files': [f.name for f in files if f.is_file()],
                    'has_dockerfile': (export_dir / 'Dockerfile').exists(),
                    'has_compose': (export_dir / 'docker-compose.yml').exists(),
                    'has_requirements': (export_dir / 'requirements.txt').exists()
                }
                
                # Format timestamps
                import datetime
                export_info['created_formatted'] = datetime.datetime.fromtimestamp(export_info['created']).strftime('%Y-%m-%d %H:%M:%S')
                export_info['modified_formatted'] = datetime.datetime.fromtimestamp(export_info['modified']).strftime('%Y-%m-%d %H:%M:%S')
                
                exports.append(export_info)
                
            except Exception as e:
                logger.warning(f"Failed to read export {export_dir}: {e}")
    
    # Sort by creation time (newest first)
    exports.sort(key=lambda x: x['created'], reverse=True)
    
    return json.dumps({
        'status': 'success',
        'total_exports': len(exports),
        'exports': exports,
        'message': f'Found {len(exports)} exported web applications'
    }, indent=2)

@mcp.tool
def get_export_details(export_name: str) -> str:
    """Get detailed information about a specific web app export.
    
    Args:
        export_name: Name of the export to inspect
    
    Returns:
        JSON string with export details
    """
    if not ctx.artifacts_dir:
        return json.dumps({
            'status': 'error',
            'message': 'No artifacts directory found'
        }, indent=2)
    
    export_dir = ctx.artifacts_dir / "exports" / export_name
    if not export_dir.exists():
        return json.dumps({
            'status': 'error',
            'message': f'Export "{export_name}" not found'
        }, indent=2)
    
    try:
        # Read all files in the export
        files = {}
        for file_path in export_dir.glob('*'):
            if file_path.is_file():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        files[file_path.name] = f.read()
                except Exception as e:
                    files[file_path.name] = f"Error reading file: {str(e)}"
        
        # Get directory stats
        stat = export_dir.stat()
        
        # Determine app type
        app_type = 'unknown'
        if 'app.py' in files:
            if 'Flask' in files['app.py'] or 'flask' in files['app.py']:
                app_type = 'flask'
            elif 'streamlit' in files['app.py'] or 'st.' in files['app.py']:
                app_type = 'streamlit'
        
        export_info = {
            'name': export_name,
            'path': str(export_dir),
            'app_type': app_type,
            'created': stat.st_ctime,
            'modified': stat.st_mtime,
            'files': files,
            'total_files': len(files)
        }
        
        # Format timestamps
        import datetime
        export_info['created_formatted'] = datetime.datetime.fromtimestamp(export_info['created']).strftime('%Y-%m-%d %H:%M:%S')
        export_info['modified_formatted'] = datetime.datetime.fromtimestamp(export_info['modified']).strftime('%Y-%m-%d %H:%M:%S')
        
        return json.dumps({
            'status': 'success',
            'export_info': export_info
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            'status': 'error',
            'message': f'Failed to get export details: {str(e)}'
        }, indent=2)

@mcp.tool
def build_docker_image(export_name: str) -> str:
    """Build Docker image for an exported web application.
    
    Args:
        export_name: Name of the export to build
    
    Returns:
        JSON string with build results
    """
    if not ctx.artifacts_dir:
        return json.dumps({
            'status': 'error',
            'message': 'No artifacts directory found'
        }, indent=2)
    
    export_dir = ctx.artifacts_dir / "exports" / export_name
    if not export_dir.exists():
        return json.dumps({
            'status': 'error',
            'message': f'Export "{export_name}" not found'
        }, indent=2)
    
    dockerfile_path = export_dir / "Dockerfile"
    if not dockerfile_path.exists():
        return json.dumps({
            'status': 'error',
            'message': f'No Dockerfile found in export "{export_name}"'
        }, indent=2)
    
    try:
        # Build Docker image
        image_name = f'sandbox-{export_name}'
        build_result = subprocess.run(
            ['docker', 'build', '-t', image_name, str(export_dir)],
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )
        
        if build_result.returncode == 0:
            return json.dumps({
                'status': 'success',
                'image_name': image_name,
                'export_name': export_name,
                'build_output': build_result.stdout,
                'message': f'Docker image "{image_name}" built successfully'
            }, indent=2)
        else:
            return json.dumps({
                'status': 'error',
                'build_output': build_result.stdout,
                'build_error': build_result.stderr,
                'message': f'Docker build failed for "{export_name}"'
            }, indent=2)
            
    except subprocess.TimeoutExpired:
        return json.dumps({
            'status': 'error',
            'message': f'Docker build timed out for "{export_name}"'
        }, indent=2)
    except FileNotFoundError:
        return json.dumps({
            'status': 'error',
            'message': 'Docker not found. Please install Docker to build images.'
        }, indent=2)
    except Exception as e:
        return json.dumps({
            'status': 'error',
            'message': f'Failed to build Docker image: {str(e)}'
        }, indent=2)

@mcp.tool
def cleanup_web_app_export(export_name: str) -> str:
    """Remove an exported web application.
    
    Args:
        export_name: Name of the export to remove
    
    Returns:
        JSON string with cleanup results
    """
    if not ctx.artifacts_dir:
        return json.dumps({
            'status': 'error',
            'message': 'No artifacts directory found'
        }, indent=2)
    
    export_dir = ctx.artifacts_dir / "exports" / export_name
    if not export_dir.exists():
        return json.dumps({
            'status': 'error',
            'message': f'Export "{export_name}" not found'
        }, indent=2)
    
    try:
        # Remove export directory
        shutil.rmtree(export_dir)
        
        # Try to remove Docker image if it exists
        docker_cleaned = False
        try:
            image_name = f'sandbox-{export_name}'
            remove_result = subprocess.run(
                ['docker', 'rmi', image_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            if remove_result.returncode == 0:
                docker_cleaned = True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass  # Docker not available or image doesn't exist
        
        return json.dumps({
            'status': 'success',
            'export_name': export_name,
            'docker_image_removed': docker_cleaned,
            'message': f'Export "{export_name}" cleaned up successfully'
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            'status': 'error',
            'message': f'Failed to cleanup export: {str(e)}'
        }, indent=2)

@mcp.tool
def install_package(package_name: str, version: str = None) -> str:
    """Install a Python package in the virtual environment using uv or pip.
    
    Args:
        package_name: Name of the package to install
        version: Optional version specification
    
    Returns:
        JSON string with installation results
    """
    if not ctx.venv_path.exists():
        return json.dumps({
            'status': 'error',
            'message': 'Virtual environment not found. Cannot install packages.'
        }, indent=2)
    
    # Check network connectivity first
    try:
        import socket
        socket.create_connection(('pypi.org', 443), timeout=5)
    except (socket.error, OSError):
        return json.dumps({
            'status': 'error',
            'message': 'Network access blocked. Cannot install packages from PyPI.'
        }, indent=2)
    
    # Construct package specification
    if version:
        package_spec = f"{package_name}=={version}"
    else:
        package_spec = package_name
    
    # Cascading fallback installation methods
    uv_executable = shutil.which('uv')
    pip_executable = ctx.venv_path / 'bin' / 'pip'
    python3_executable = shutil.which('python3') or sys.executable
    
    # Define installation methods in order of preference
    installation_methods = []
    
    if uv_executable:
        # Method 1: uv add (preferred for project dependency management)
        installation_methods.append({
            'tool': 'uv add',
            'executable': uv_executable,
            'command': [uv_executable, 'add', package_spec]
        })
        
        # Method 2: uv pip install (fallback for uv)
        installation_methods.append({
            'tool': 'uv pip',
            'executable': uv_executable,
            'command': [uv_executable, 'pip', 'install', package_spec]
        })
    
    if pip_executable.exists():
        # Method 3: pip install (standard fallback)
        installation_methods.append({
            'tool': 'pip',
            'executable': str(pip_executable),
            'command': [str(pip_executable), 'install', package_spec]
        })
    
    if python3_executable:
        # Method 4: python3 -m pip install (final fallback)
        installation_methods.append({
            'tool': 'python3 -m pip',
            'executable': python3_executable,
            'command': [python3_executable, '-m', 'pip', 'install', package_spec]
        })
    
    if not installation_methods:
        return json.dumps({
            'status': 'error',
            'message': 'No installation tools found. Cannot install packages.'
        }, indent=2)
    
    # Try each installation method in order
    last_error = None
    attempts = []
    
    for method in installation_methods:
        try:
            # Set up environment for package installation
            env = os.environ.copy()
            env['VIRTUAL_ENV'] = str(ctx.venv_path)
            
            # Set working directory for uv commands (need project root)
            working_dir = str(ctx.project_root) if method['tool'].startswith('uv') else None
            
            # Attempt installation
            install_result = subprocess.run(
                method['command'],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                env=env,
                cwd=working_dir
            )
            
            attempts.append({
                'method': method['tool'],
                'success': install_result.returncode == 0,
                'stdout': install_result.stdout,
                'stderr': install_result.stderr
            })
            
            if install_result.returncode == 0:
                return json.dumps({
                    'status': 'success',
                    'package': package_name,
                    'version': version,
                    'installer_used': method['tool'],
                    'install_output': install_result.stdout,
                    'attempts': attempts,
                    'message': f'Successfully installed {package_spec} using {method["tool"]}'
                }, indent=2)
            else:
                last_error = {
                    'method': method['tool'],
                    'stdout': install_result.stdout,
                    'stderr': install_result.stderr
                }
                
        except subprocess.TimeoutExpired:
            attempts.append({
                'method': method['tool'],
                'success': False,
                'error': f'Installation timed out after 300 seconds'
            })
            last_error = {
                'method': method['tool'],
                'error': 'Installation timed out'
            }
        except Exception as e:
            attempts.append({
                'method': method['tool'],
                'success': False,
                'error': str(e)
            })
            last_error = {
                'method': method['tool'],
                'error': str(e)
            }
    
    # All methods failed
    return json.dumps({
        'status': 'error',
        'package': package_name,
        'attempts': attempts,
        'last_error': last_error,
        'message': f'Failed to install {package_spec} using all available methods: {[m["tool"] for m in installation_methods]}'
    }, indent=2)

@mcp.tool
def list_installed_packages() -> str:
    """List all installed packages in the virtual environment.
    
    Returns:
        JSON string with package listing
    """
    if not ctx.venv_path.exists():
        return json.dumps({
            'status': 'error',
            'message': 'Virtual environment not found'
        }, indent=2)
    
    pip_executable = ctx.venv_path / 'bin' / 'pip'
    if not pip_executable.exists():
        return json.dumps({
            'status': 'error',
            'message': 'pip not found in virtual environment'
        }, indent=2)
    
    try:
        # List installed packages
        list_result = subprocess.run(
            [str(pip_executable), 'list', '--format=json'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if list_result.returncode == 0:
            try:
                packages = json.loads(list_result.stdout)
                return json.dumps({
                    'status': 'success',
                    'total_packages': len(packages),
                    'packages': packages,
                    'message': f'Found {len(packages)} installed packages'
                }, indent=2)
            except json.JSONDecodeError:
                return json.dumps({
                    'status': 'error',
                    'message': 'Failed to parse package list',
                    'raw_output': list_result.stdout
                }, indent=2)
        else:
            return json.dumps({
                'status': 'error',
                'message': 'Failed to list packages',
                'error': list_result.stderr
            }, indent=2)
            
    except subprocess.TimeoutExpired:
        return json.dumps({
            'status': 'error',
            'message': 'Package listing timed out'
        }, indent=2)
    except Exception as e:
        return json.dumps({
            'status': 'error',
            'message': f'Failed to list packages: {str(e)}'
        }, indent=2)

@mcp.tool
def get_sandbox_limitations() -> str:
    """Get detailed information about sandbox limitations and restrictions.
    
    Returns:
        JSON string with limitation details
    """
    # Check network connectivity
    network_tests = {
        'dns_resolution': False,
        'http_access': False,
        'pypi_access': False
    }
    
    try:
        import socket
        socket.create_connection(('8.8.8.8', 53), timeout=3)
        network_tests['dns_resolution'] = True
        
        socket.create_connection(('httpbin.org', 80), timeout=3)
        network_tests['http_access'] = True
        
        socket.create_connection(('pypi.org', 443), timeout=3)
        network_tests['pypi_access'] = True
    except (socket.error, OSError):
        pass
    
    # Check available commands
    restricted_commands = [
        'rm', 'rmdir', 'sudo', 'su', 'chmod', 'chown', 'mount', 'umount',
        'systemctl', 'service', 'reboot', 'shutdown', 'fdisk', 'mkfs',
        'ping', 'curl', 'wget', 'ssh', 'scp', 'rsync'
    ]
    
    command_availability = {}
    for cmd in restricted_commands:
        command_availability[cmd] = shutil.which(cmd) is not None
    
    limitations = {
        'network_access': {
            'dns_resolution': network_tests['dns_resolution'],
            'http_access': network_tests['http_access'],
            'pypi_access': network_tests['pypi_access'],
            'description': 'Network access may be restricted by firewall or security policies'
        },
        'file_system_access': {
            'sandboxed_area': str(ctx.sandbox_area),
            'artifacts_dir': str(ctx.artifacts_dir) if ctx.artifacts_dir else None,
            'home_directory_access': os.path.expanduser('~') != '/root',
            'description': 'File system access is limited to sandbox area and artifacts directory'
        },
        'package_installation': {
            'virtual_env_available': ctx.venv_path.exists(),
            'pip_available': (ctx.venv_path / 'bin' / 'pip').exists() if ctx.venv_path.exists() else False,
            'network_required': True,
            'description': 'Package installation requires network access and virtual environment'
        },
        'system_commands': {
            'restricted_commands': {cmd: {'available': available, 'blocked': available} 
                                    for cmd, available in command_availability.items()},
            'description': 'Many system administration commands are restricted or blocked'
        },
        'repl_functionality': {
            'ipython_available': False,
            'tab_completion': False,
            'magic_commands': False,
            'description': 'Enhanced REPL features require IPython installation'
        }
    }
    
    # Check IPython availability
    try:
        import IPython
        limitations['repl_functionality']['ipython_available'] = True
        limitations['repl_functionality']['tab_completion'] = True
        limitations['repl_functionality']['magic_commands'] = True
    except ImportError:
        pass
    
    return json.dumps({
        'status': 'success',
        'limitations': limitations,
        'recommendations': [
            'Install IPython for enhanced REPL functionality: install_package("ipython")',
            'Install common data science packages: install_package("numpy"), install_package("pandas")',
            'Use artifact management tools for persistent storage',
            'Export web applications for external deployment',
            'Use shell_execute() for safe command execution in sandbox area'
        ],
        'message': 'Sandbox limitations and recommendations provided'
    }, indent=2)

@mcp.tool
def get_comprehensive_help() -> str:
    """Get comprehensive help and usage examples for the sandbox environment.
    
    Returns:
        JSON string with help information
    """
    help_info = {
        'getting_started': {
            'basic_execution': {
                'description': 'Execute Python code with artifact management',
                'examples': [
                    'execute("import numpy as np; print(np.array([1, 2, 3]))")',
                    'execute("import matplotlib.pyplot as plt; plt.plot([1, 2, 3]); plt.show()")',
                    'execute("print(\'Hello, Sandbox!\')", interactive=True)'
                ]
            },
            'artifact_management': {
                'description': 'Create, manage, and backup artifacts',
                'examples': [
                    'list_artifacts()',
                    'backup_current_artifacts("my_backup")',
                    'list_artifact_backups()',
                    'rollback_to_backup("backup_20240101_120000")',
                    'cleanup_artifacts_by_type("plots")'
                ]
            },
            'web_applications': {
                'description': 'Create and export web applications',
                'examples': [
                    'start_web_app("from flask import Flask; app = Flask(__name__); @app.route(\'/\') def hello(): return \'Hello!\'", "flask")',
                    'export_web_app("import streamlit as st; st.title(\'My App\'); st.write(\'Hello!\')", "streamlit", "my_app")',
                    'list_web_app_exports()',
                    'build_docker_image("my_app")'
                ]
            }
        },
        'advanced_features': {
            'manim_animations': {
                'description': 'Create mathematical animations with Manim',
                'examples': [
                    'get_manim_examples()',
                    'create_manim_animation("from manim import *; class MyScene(Scene): def construct(self): circle = Circle(); self.play(Create(circle))", "medium_quality")',
                    'list_manim_animations()'
                ]
            },
            'package_management': {
                'description': 'Install and manage Python packages',
                'examples': [
                    'install_package("numpy")',
                    'install_package("pandas", "1.5.0")',
                    'list_installed_packages()'
                ]
            },
            'shell_commands': {
                'description': 'Execute shell commands safely',
                'examples': [
                    'shell_execute("ls -la")',
                    'shell_execute("python --version")',
                    'shell_execute("find . -name \"*.py\"")',
                    'shell_execute("git status", "/path/to/repo")'
                ]
            }
        },
        'troubleshooting': {
            'common_issues': {
                'import_errors': {
                    'description': 'Module not found errors',
                    'solutions': [
                        'Check if package is installed: list_installed_packages()',
                        'Install missing package: install_package("package_name")',
                        'Check virtual environment: get_execution_info()'
                    ]
                },
                'network_issues': {
                    'description': 'Network access blocked',
                    'solutions': [
                        'Check limitations: get_sandbox_limitations()',
                        'Use offline packages when possible',
                        'Export applications for external deployment'
                    ]
                },
                'artifact_issues': {
                    'description': 'Artifacts not appearing or disappearing',
                    'solutions': [
                        'Check artifacts directory: get_execution_info()',
                        'List current artifacts: list_artifacts()',
                        'Create backup before cleanup: backup_current_artifacts()'
                    ]
                }
            }
        },
        'best_practices': [
            'Always backup important artifacts before cleanup',
            'Use descriptive names for backups and exports',
            'Check sandbox limitations before attempting network operations',
            'Use virtual environment for package installations',
            'Export web applications for persistence beyond sandbox session',
            'Use shell_execute() instead of os.system() for safety'
        ],
        'tool_categories': {
            'execution': ['execute', 'execute_with_artifacts', 'start_enhanced_repl'],
            'artifacts': ['list_artifacts', 'backup_current_artifacts', 'list_artifact_backups', 'rollback_to_backup', 'cleanup_artifacts_by_type'],
            'web_apps': ['start_web_app', 'export_web_app', 'list_web_app_exports', 'build_docker_image'],
            'manim': ['create_manim_animation', 'list_manim_animations', 'get_manim_examples'],
            'packages': ['install_package', 'list_installed_packages'],
            'system': ['shell_execute', 'get_execution_info', 'get_sandbox_limitations'],
            'help': ['get_comprehensive_help']
        }
    }
    
    return json.dumps(help_info, indent=2)

def main():
    """Entry point for the stdio MCP server."""
    mcp.run()

if __name__ == "__main__":
    # Run FastMCP server using stdio transport for LM Studio
    main()
