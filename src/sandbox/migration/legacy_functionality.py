"""
Legacy Functionality Migration Module

This module extracts and consolidates working functionality from scattered
server implementations to integrate into the unified server.
"""

import json
import logging
import sys
import os
import uuid
import tempfile
import shutil
import subprocess
import time
import socket
import base64
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import io

logger = logging.getLogger(__name__)


class ManimExecutor:
    """Manim execution capabilities extracted from legacy servers."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.venv_path = project_root / ".venv"
        self.manim_available = self._check_manim_availability()
    
    def _check_manim_availability(self) -> bool:
        """Check if Manim is available in the environment."""
        try:
            # Try virtual environment first
            if self.venv_path.exists():
                venv_python = self.venv_path / 'bin' / 'python'
                if venv_python.exists():
                    result = subprocess.run(
                        [str(venv_python), '-c', 'import manim'],
                        capture_output=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        return True
            
            # Try system python
            result = subprocess.run(
                [sys.executable, '-c', 'import manim'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
            
        except Exception as e:
            logger.warning(f"Failed to check Manim availability: {e}")
            return False
    
    def execute_manim_code(self, manim_code: str, artifacts_dir: Path, 
                          quality: str = 'medium_quality') -> Dict[str, Any]:
        """Execute Manim code and save animation to artifacts directory."""
        if not self.manim_available:
            return {
                'success': False,
                'error': 'Manim is not available in the environment',
                'output': '',
                'video_path': None,
                'animation_id': None,
                'execution_time': 0
            }
        
        # Create a subdirectory for this specific animation
        animation_id = str(uuid.uuid4())[:8]
        manim_dir = artifacts_dir / f"manim_{animation_id}"
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
            if self.venv_path.exists():
                venv_manim = self.venv_path / 'bin' / 'manim'
                if venv_manim.exists():
                    manim_executable = str(venv_manim)
            
            # Fallback to system manim or python -m manim
            if not manim_executable:
                # Try python -m manim with virtual environment python
                if self.venv_path.exists():
                    venv_python = self.venv_path / 'bin' / 'python'
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
            if self.venv_path.exists():
                env['VIRTUAL_ENV'] = str(self.venv_path)
                env['PATH'] = f"{self.venv_path / 'bin'}{os.pathsep}{env.get('PATH', '')}"
            
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


class WebAppManager:
    """Web application building and serving functionality."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.venv_path = project_root / ".venv"
        self.active_web_servers = {}
    
    def find_free_port(self, start_port: int = 8000) -> int:
        """Find a free port starting from start_port."""
        for port in range(start_port, start_port + 100):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('127.0.0.1', port))
                    return port
            except OSError:
                continue
        raise RuntimeError("No free ports available")

    def _determine_deployment_environment(self) -> str:
        """Determine the current deployment environment."""
        if os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER'):
            return 'docker'
        elif os.environ.get('KUBERNETES_SERVICE_HOST'):
            return 'kubernetes'
        elif os.environ.get('AWS_REGION') or os.environ.get('GOOGLE_CLOUD_PROJECT'):
            return 'cloud'
        else:
            return 'local'

    def _determine_default_port(self, app_type: str) -> str:
        """Determine default port based on app type and environment."""
        env = self._determine_deployment_environment()

        if app_type == 'flask':
            if env == 'docker':
                return '8000'
            elif env == 'kubernetes':
                return '8080'
            else:  # local or cloud
                return '5000'
        elif app_type == 'streamlit':
            if env == 'docker':
                return '8501'
            elif env == 'kubernetes':
                return '8080'
            else:  # local or cloud
                return '8501'
        else:
            return '8000'

    def _determine_default_host(self) -> str:
        """Determine default host based on deployment environment."""
        env = self._determine_deployment_environment()

        if env in ['docker', 'kubernetes', 'cloud']:
            return '0.0.0.0'
        else:  # local
            return '127.0.0.1'

    def _determine_access_host(self) -> str:
        """Determine access host based on deployment environment."""
        env = self._determine_deployment_environment()

        if env == 'docker':
            return 'localhost'
        elif env == 'kubernetes':
            return os.environ.get('SERVICE_NAME', 'localhost')
        elif env == 'cloud':
            # For cloud deployments, try to get the service URL
            service_url = os.environ.get('SERVICE_URL')
            if service_url:
                return service_url
            return '0.0.0.0'
        else:  # local
            return 'localhost'
    
    def launch_web_app(self, code: str, app_type: str, artifacts_dir: Path) -> Optional[str]:
        """Launch a web application and return the URL."""
        try:
            port = self.find_free_port()
            
            if app_type == 'flask':
                # Modify Flask code to run on specific port
                modified_code = code + f"\nif __name__ == '__main__': app.run(host='127.0.0.1', port={port}, debug=False)"
                
                # Execute the modified Flask code in a separate thread
                def run_flask():
                    # Create a proper globals dict with __name__ set
                    flask_globals = {'__name__': '__main__', '__file__': '<flask_app>'}
                    exec(modified_code, flask_globals)
                
                thread = threading.Thread(target=run_flask, daemon=True)
                thread.start()
                time.sleep(1)  # Give Flask time to start
                
                url = f"http://127.0.0.1:{port}"
                self.active_web_servers[url] = {'type': 'flask', 'thread': thread, 'port': port}
                return url
                
            elif app_type == 'streamlit':
                # For Streamlit, we need to create a temporary file and run it
                script_path = artifacts_dir / f"streamlit_app_{uuid.uuid4().hex[:8]}.py"
                with open(script_path, 'w') as f:
                    f.write(code)
                
                # Launch Streamlit in subprocess
                cmd = [sys.executable, '-m', 'streamlit', 'run', str(script_path), 
                      '--server.port', str(port), '--server.headless', 'true']
                
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Give it time to start
                time.sleep(2)
                
                if process.poll() is None:  # Still running
                    url = f"http://127.0.0.1:{port}"
                    self.active_web_servers[url] = {'type': 'streamlit', 'process': process, 'port': port}
                    return url
                else:
                    return None
            else:
                return None
                
        except Exception as e:
            logger.error(f"Failed to launch web app: {e}")
            return None
    
    def export_flask_app(self, code: str, artifacts_dir: Path, export_name: Optional[str] = None) -> Dict[str, Any]:
        """Export Flask application as static files and Docker container."""
        export_id = str(uuid.uuid4())[:8]
        export_name = export_name or f"flask_app_{export_id}"
        export_dir = artifacts_dir / "exports" / export_name
        export_dir.mkdir(parents=True, exist_ok=True)

        result = {
            'success': False,
            'export_name': export_name,
            'export_dir': str(export_dir),
            'files_created': [],
            'docker_image': None,
            'error': None
        }

        # Dynamically determine URLs based on deployment environment and port allocation
        port = os.environ.get('FLASK_PORT', self._determine_default_port('flask'))
        host = os.environ.get('FLASK_HOST', self._determine_default_host())
        access_host = os.environ.get('ACCESS_HOST', self._determine_access_host())

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
            dockerfile_content = f'''FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE {port}

CMD ["gunicorn", "--bind", "{host}:{port}", "app:app"]
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
      - "{port}:{port}"
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

The application will be available at http://{access_host}:{port}

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
            
            result['success'] = True
            
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Failed to export Flask app: {e}")
        
        return result
    
    def export_streamlit_app(self, code: str, artifacts_dir: Path, export_name: Optional[str] = None) -> Dict[str, Any]:
        """Export Streamlit application as Docker container."""
        export_id = str(uuid.uuid4())[:8]
        export_name = export_name or f"streamlit_app_{export_id}"
        export_dir = artifacts_dir / "exports" / export_name
        export_dir.mkdir(parents=True, exist_ok=True)

        result = {
            'success': False,
            'export_name': export_name,
            'export_dir': str(export_dir),
            'files_created': [],
            'docker_image': None,
            'error': None
        }

        # Dynamically determine URLs based on deployment environment and port allocation
        port = os.environ.get('STREAMLIT_PORT', self._determine_default_port('streamlit'))
        host = os.environ.get('STREAMLIT_HOST', self._determine_default_host())
        access_host = os.environ.get('ACCESS_HOST', self._determine_access_host())

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
            dockerfile_content = f'''FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE {port}

CMD ["streamlit", "run", "app.py", "--server.port={port}", "--server.address={host}"]
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
      - "{port}:{port}"
    environment:
      - STREAMLIT_SERVER_PORT={port}
      - STREAMLIT_SERVER_ADDRESS={host}
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

The application will be available at http://{access_host}:{port}

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
            
            result['success'] = True
            
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Failed to export Streamlit app: {e}")
        
        return result
    
    def cleanup_web_servers(self):
        """Clean up all active web servers."""
        for url, server_info in self.active_web_servers.items():
            try:
                if server_info['type'] == 'streamlit' and 'process' in server_info:
                    server_info['process'].terminate()
                # Flask threads will be cleaned up automatically as they're daemon threads
            except Exception as e:
                logger.error(f"Error cleaning up web server {url}: {e}")
        
        self.active_web_servers.clear()


class ArtifactInterceptor:
    """Artifact interception and monkey patching functionality."""
    
    def __init__(self, artifacts_dir: Path):
        self.artifacts_dir = artifacts_dir
        self.matplotlib_patched = False
        self.pil_patched = False
    
    def monkey_patch_matplotlib(self) -> bool:
        """Monkey patch matplotlib to save plots to artifacts directory."""
        try:
            import matplotlib
            matplotlib.use('Agg')  # Use non-interactive backend
            import matplotlib.pyplot as plt
            
            original_show = plt.show
            
            def patched_show(*args, **kwargs):
                if self.artifacts_dir:
                    plots_dir = self.artifacts_dir / "plots"
                    plots_dir.mkdir(exist_ok=True)
                    figure_path = plots_dir / f"plot_{uuid.uuid4().hex[:8]}.png"
                    plt.savefig(figure_path, dpi=150, bbox_inches='tight')
                    logger.info(f"Plot saved to: {figure_path}")
                return original_show(*args, **kwargs)
            
            plt.show = patched_show
            self.matplotlib_patched = True
            return True
        except ImportError:
            return False
    
    def monkey_patch_pil(self) -> bool:
        """Monkey patch PIL to save images to artifacts directory."""
        try:
            from PIL import Image
            
            original_show = Image.Image.show
            original_save = Image.Image.save
            
            def patched_show(self, title=None, command=None):
                if self.artifacts_dir:
                    images_dir = self.artifacts_dir / "images"
                    images_dir.mkdir(exist_ok=True)
                    image_path = images_dir / f"image_{uuid.uuid4().hex[:8]}.png"
                    self.save(image_path)
                    logger.info(f"Image saved to: {image_path}")
                return original_show(self)
            
            def patched_save(self, fp, format=None, **params):
                result = original_save(self, fp, format, **params)
                # If saving to artifacts dir, log it
                if self.artifacts_dir and str(fp).startswith(str(self.artifacts_dir)):
                    logger.info(f"Image saved to artifacts: {fp}")
                return result
            
            Image.Image.show = patched_show
            Image.Image.save = patched_save
            self.pil_patched = True
            return True
        except ImportError:
            return False
    
    def collect_artifacts(self) -> List[Dict[str, Any]]:
        """Collect all artifacts from the artifacts directory (recursive)."""
        artifacts = []
        if not self.artifacts_dir or not self.artifacts_dir.exists():
            return artifacts
        
        # Use rglob to search recursively through all subdirectories
        for file_path in self.artifacts_dir.rglob('*'):
            if file_path.is_file():
                try:
                    # Calculate relative path from artifacts_dir for better organization
                    relative_path = file_path.relative_to(self.artifacts_dir)
                    file_size = file_path.stat().st_size
                    
                    # Only read small files as base64 to prevent memory issues
                    content_base64 = None
                    if file_size < 1024 * 1024:  # Only files smaller than 1MB
                        try:
                            with open(file_path, 'rb') as f:
                                content = base64.b64encode(f.read()).decode('utf-8')
                                content_base64 = content
                        except Exception as e:
                            logger.warning(f"Failed to read content for {file_path}: {e}")
                    
                    artifacts.append({
                        'name': file_path.name,
                        'path': str(file_path),
                        'relative_path': str(relative_path),
                        'type': file_path.suffix.lower(),
                        'content_base64': content_base64,
                        'size': file_size,
                        'category': file_path.parent.name,  # e.g., 'plots', 'images', etc.
                        'content_available': content_base64 is not None
                    })
                except Exception as e:
                    logger.error(f"Error reading artifact {file_path}: {e}")
        
        return artifacts


class IntelligentSandboxIntegration:
    """Integration with intelligent sandbox features."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.src_path = project_root / "src"
        
        # Add src to path for imports
        if str(self.src_path) not in sys.path:
            sys.path.insert(0, str(self.src_path))
        
        # Try to import intelligent sandbox components
        self.components_available = self._check_components()
    
    def _check_components(self) -> Dict[str, bool]:
        """Check which intelligent sandbox components are available."""
        components = {}
        
        try:
            from sandbox.intelligent.workspace.cloner import WorkspaceCloner
            components['workspace_cloner'] = True
        except ImportError:
            components['workspace_cloner'] = False
        
        try:
            from sandbox.intelligent.workspace.lifecycle import WorkspaceLifecycleManager
            components['lifecycle_manager'] = True
        except ImportError:
            components['lifecycle_manager'] = False
        
        try:
            from sandbox.intelligent.analyzer.analyzer import CodebaseAnalyzer
            components['codebase_analyzer'] = True
        except ImportError:
            components['codebase_analyzer'] = False
        
        try:
            from sandbox.intelligent.planner.planner import TaskPlanner
            components['task_planner'] = True
        except ImportError:
            components['task_planner'] = False
        
        return components
    
    def create_workspace_session(self, source_path: str, workspace_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Create a workspace session using intelligent sandbox components."""
        if not self.components_available.get('lifecycle_manager', False):
            return None
        
        try:
            from sandbox.intelligent.workspace.lifecycle import WorkspaceLifecycleManager
            
            lifecycle_manager = WorkspaceLifecycleManager()
            
            # Generate workspace ID if not provided
            if not workspace_id:
                workspace_id = f"sandbox_{uuid.uuid4().hex[:8]}"
            
            # Create workspace session
            session = lifecycle_manager.create_workspace(
                source_path=source_path,
                session_id=workspace_id
            )
            
            return {
                'success': True,
                'workspace_id': workspace_id,
                'sandbox_path': str(session.workspace.sandbox_path),
                'isolation_enabled': session.workspace.isolation_config.use_docker,
                'session': session
            }
            
        except Exception as e:
            logger.error(f"Failed to create workspace session: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def analyze_codebase(self, workspace_session: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyze codebase using intelligent sandbox analyzer."""
        if not self.components_available.get('codebase_analyzer', False):
            return None
        
        try:
            from sandbox.intelligent.analyzer.analyzer import CodebaseAnalyzer
            
            analyzer = CodebaseAnalyzer()
            workspace = workspace_session['session'].workspace
            
            # Perform analysis
            analysis = analyzer.analyze_codebase(workspace)
            
            return {
                'success': True,
                'analysis': {
                    'languages': analysis.structure.languages,
                    'frameworks': analysis.structure.frameworks,
                    'dependencies_count': len(analysis.dependencies.dependencies),
                    'files_count': len(analysis.structure.file_tree),
                    'lines_of_code': analysis.metrics.lines_of_code,
                    'complexity_score': getattr(analysis.metrics, 'complexity_score', 0),
                    'file_structure': analysis.structure.file_tree
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze codebase: {e}")
            return {
                'success': False,
                'error': str(e)
            }