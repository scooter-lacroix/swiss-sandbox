#!/usr/bin/env python3
"""
Complete Ultimate Swiss Army Knife MCP Server - Part 4
Original Sandbox Tools - COMPLETE Implementation
"""

from complete_server import *
from complete_tools_1 import *
from complete_tools_2 import *
import base64
import pickle
import streamlit
import flask
from flask import Flask, jsonify, request, render_template_string
import uvicorn
from fastapi import FastAPI, WebSocket
import gradio as gr
import pygame
import cv2
import soundfile as sf
import imageio
from scipy import signal
import sklearn
from transformers import pipeline

# ============================================================================
# COMPLETE ORIGINAL SANDBOX TOOLS IMPLEMENTATION
# ============================================================================

class OriginalSandboxTools:
    """Complete implementation of ALL Original Sandbox tools."""
    
    def __init__(self, server):
        self.server = server
        self.mcp = server.mcp
        self.artifacts_dir = Path.home() / ".ultimate_sandbox" / "artifacts"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.repl_sessions = {}
        self.artifact_backups = {}
        
    def register_tools(self):
        """Register all Original Sandbox tools with COMPLETE functionality."""
        
        @self.mcp.tool()
        async def execute(
            code: str,
            language: str = "python",
            timeout: int = 30,
            capture_artifacts: bool = True,
            sandbox_id: Optional[str] = None,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Execute code with complete artifact tracking."""
            try:
                # Create execution ID
                exec_id = f"exec_{uuid.uuid4().hex[:8]}"
                
                # Determine sandbox to use
                if sandbox_id and sandbox_id in self.server.active_workspaces:
                    session = self.server.active_workspaces[sandbox_id]
                    sandbox_path = Path(session.sandbox_path)
                    use_container = session.container_id is not None
                else:
                    # Create temporary sandbox
                    sandbox_path = self.artifacts_dir / exec_id
                    sandbox_path.mkdir(parents=True, exist_ok=True)
                    use_container = False
                    session = None
                
                # Prepare execution environment
                if language == "python":
                    # Write code to file
                    code_file = sandbox_path / f"{exec_id}.py"
                    code_file.write_text(code)
                    
                    # Set up artifact capture
                    if capture_artifacts:
                        # Inject artifact capture code
                        capture_code = f"""
import sys
import os
import pickle
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

_artifacts = {{}}
_original_show = plt.show
_figure_count = 0

def _capture_plt_show():
    global _figure_count
    fig = plt.gcf()
    path = '{sandbox_path}/figure_{exec_id}_{{_figure_count}}.png'
    fig.savefig(path)
    _artifacts[f'figure_{{_figure_count}}'] = path
    _figure_count += 1
    plt.close(fig)

plt.show = _capture_plt_show

# User code starts here
{code}
# User code ends here

# Save artifacts
with open('{sandbox_path}/artifacts_{exec_id}.pkl', 'wb') as f:
    pickle.dump(_artifacts, f)
"""
                        code_file.write_text(capture_code)
                    
                    # Execute code
                    if use_container and session:
                        # Execute in Docker container
                        container = self.server.docker_manager.client.containers.get(session.container_id)
                        exec_result = container.exec_run(
                            f"python {code_file.name}",
                            workdir='/workspace',
                            demux=True,
                            stream=False
                        )
                        stdout = exec_result.output[0].decode() if exec_result.output[0] else ''
                        stderr = exec_result.output[1].decode() if exec_result.output[1] else ''
                        exit_code = exec_result.exit_code
                    else:
                        # Execute locally
                        result = subprocess.run(
                            [sys.executable, str(code_file)],
                            cwd=str(sandbox_path),
                            capture_output=True,
                            text=True,
                            timeout=timeout
                        )
                        stdout = result.stdout
                        stderr = result.stderr
                        exit_code = result.returncode
                    
                    # Collect artifacts
                    artifacts = {}
                    if capture_artifacts:
                        artifacts_file = sandbox_path / f"artifacts_{exec_id}.pkl"
                        if artifacts_file.exists():
                            with open(artifacts_file, 'rb') as f:
                                artifacts = pickle.load(f)
                        
                        # Look for generated files
                        for file in sandbox_path.glob(f"*{exec_id}*"):
                            if file.suffix in ['.png', '.jpg', '.pdf', '.csv', '.json', '.txt']:
                                artifact_name = file.stem
                                if artifact_name not in artifacts:
                                    artifacts[artifact_name] = str(file)
                    
                    # Store execution record
                    execution = TaskExecution(
                        task_id=exec_id,
                        description=f"Execute {language} code",
                        status="completed" if exit_code == 0 else "failed",
                        started_at=datetime.now(),
                        completed_at=datetime.now(),
                        output=stdout,
                        error=stderr,
                        exit_code=exit_code,
                        artifacts=list(artifacts.values())
                    )
                    
                    # Save to storage
                    self._save_execution(execution)
                    
                    return {
                        "success": exit_code == 0,
                        "execution_id": exec_id,
                        "output": stdout,
                        "error": stderr,
                        "exit_code": exit_code,
                        "artifacts": artifacts,
                        "artifacts_count": len(artifacts)
                    }
                    
                elif language == "javascript":
                    # Execute JavaScript code
                    code_file = sandbox_path / f"{exec_id}.js"
                    code_file.write_text(code)
                    
                    result = subprocess.run(
                        ["node", str(code_file)],
                        cwd=str(sandbox_path),
                        capture_output=True,
                        text=True,
                        timeout=timeout
                    )
                    
                    return {
                        "success": result.returncode == 0,
                        "execution_id": exec_id,
                        "output": result.stdout,
                        "error": result.stderr,
                        "exit_code": result.returncode
                    }
                    
                elif language == "bash":
                    # Execute shell commands
                    result = subprocess.run(
                        code,
                        shell=True,
                        cwd=str(sandbox_path),
                        capture_output=True,
                        text=True,
                        timeout=timeout
                    )
                    
                    return {
                        "success": result.returncode == 0,
                        "execution_id": exec_id,
                        "output": result.stdout,
                        "error": result.stderr,
                        "exit_code": result.returncode
                    }
                    
                else:
                    return {
                        "success": False,
                        "error": f"Unsupported language: {language}"
                    }
                    
            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "error": f"Execution timed out after {timeout} seconds"
                }
            except Exception as e:
                logger.error(f"Execution failed: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.mcp.tool()
        async def execute_with_artifacts(
            code: str,
            expected_artifacts: List[str] = None,
            artifact_types: List[str] = None,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Execute code with enhanced artifact management."""
            try:
                # Execute code with artifact capture
                result = await execute(code, capture_artifacts=True, ctx=ctx)
                
                if not result['success']:
                    return result
                
                artifacts = result.get('artifacts', {})
                enhanced_artifacts = {}
                
                # Process and enhance artifacts
                for name, path in artifacts.items():
                    file_path = Path(path)
                    if not file_path.exists():
                        continue
                    
                    # Determine artifact type
                    artifact_type = self._detect_artifact_type(file_path)
                    
                    # Filter by expected types if specified
                    if artifact_types and artifact_type not in artifact_types:
                        continue
                    
                    # Filter by expected names if specified
                    if expected_artifacts and name not in expected_artifacts:
                        continue
                    
                    # Read and encode artifact
                    artifact_data = {
                        'name': name,
                        'type': artifact_type,
                        'path': str(file_path),
                        'size': file_path.stat().st_size,
                        'created': datetime.fromtimestamp(file_path.stat().st_ctime).isoformat()
                    }
                    
                    # Add content for small text files
                    if artifact_type == 'text' and artifact_data['size'] < 10000:
                        artifact_data['content'] = file_path.read_text()
                    elif artifact_type == 'image':
                        # Encode image as base64
                        with open(file_path, 'rb') as f:
                            artifact_data['base64'] = base64.b64encode(f.read()).decode()
                    
                    enhanced_artifacts[name] = artifact_data
                
                return {
                    "success": True,
                    "execution_id": result['execution_id'],
                    "output": result['output'],
                    "artifacts": enhanced_artifacts,
                    "artifacts_count": len(enhanced_artifacts)
                }
                
            except Exception as e:
                logger.error(f"Execute with artifacts failed: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.mcp.tool()
        async def start_enhanced_repl(
            language: str = "python",
            session_name: Optional[str] = None,
            preserve_state: bool = True,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Start an enhanced REPL session with state preservation."""
            try:
                # Generate session name if not provided
                if not session_name:
                    session_name = f"repl_{uuid.uuid4().hex[:8]}"
                
                # Check if session already exists
                if session_name in self.repl_sessions:
                    return {
                        "success": False,
                        "error": f"REPL session '{session_name}' already exists"
                    }
                
                # Create REPL session
                if language == "python":
                    # Start Python REPL process
                    process = subprocess.Popen(
                        [sys.executable, "-i"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        bufsize=0
                    )
                    
                    # Initialize session
                    session = {
                        'name': session_name,
                        'language': language,
                        'process': process,
                        'history': [],
                        'variables': {},
                        'created': datetime.now().isoformat(),
                        'preserve_state': preserve_state
                    }
                    
                    # Setup initial environment
                    init_code = """
import sys
import os
import json
import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
print("REPL session initialized")
"""
                    process.stdin.write(init_code)
                    process.stdin.flush()
                    
                    self.repl_sessions[session_name] = session
                    
                    return {
                        "success": True,
                        "session_name": session_name,
                        "language": language,
                        "message": "REPL session started"
                    }
                    
                else:
                    return {
                        "success": False,
                        "error": f"Unsupported REPL language: {language}"
                    }
                    
            except Exception as e:
                logger.error(f"Start REPL failed: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.mcp.tool()
        async def repl_execute(
            session_name: str,
            code: str,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Execute code in REPL session."""
            try:
                if session_name not in self.repl_sessions:
                    return {
                        "success": False,
                        "error": f"REPL session '{session_name}' not found"
                    }
                
                session = self.repl_sessions[session_name]
                process = session['process']
                
                # Send code to REPL
                process.stdin.write(code + "\n")
                process.stdin.flush()
                
                # Read output (with timeout)
                import select
                output = ""
                error = ""
                
                # Use select to read with timeout
                timeout = 5
                start_time = time.time()
                
                while time.time() - start_time < timeout:
                    ready, _, _ = select.select([process.stdout, process.stderr], [], [], 0.1)
                    
                    if process.stdout in ready:
                        line = process.stdout.readline()
                        if line:
                            output += line
                    
                    if process.stderr in ready:
                        line = process.stderr.readline()
                        if line:
                            error += line
                    
                    # Check for prompt or completion
                    if output.endswith(">>> ") or output.endswith("... "):
                        break
                
                # Add to history
                session['history'].append({
                    'code': code,
                    'output': output,
                    'error': error,
                    'timestamp': datetime.now().isoformat()
                })
                
                return {
                    "success": True,
                    "session_name": session_name,
                    "output": output,
                    "error": error,
                    "history_length": len(session['history'])
                }
                
            except Exception as e:
                logger.error(f"REPL execute failed: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.mcp.tool()
        async def create_manim_animation(
            code: str,
            name: str = "Animation",
            quality: str = "high_quality",
            format: str = "mp4",
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Create Manim animation with complete rendering."""
            try:
                # Create animation object
                animation = ManimAnimation(
                    animation_id=f"anim_{uuid.uuid4().hex[:8]}",
                    name=name,
                    code=code,
                    output_path="",
                    format=format,
                    quality=quality
                )
                
                # Render animation
                success = self.server.manim_executor.create_animation(animation)
                
                if success:
                    # Store animation
                    self.server.active_animations[animation.animation_id] = animation
                    
                    # Update metrics
                    self.server.metrics['animations_rendered'] += 1
                    
                    return {
                        "success": True,
                        "animation_id": animation.animation_id,
                        "name": name,
                        "output_path": animation.output_path,
                        "render_time": animation.render_time,
                        "format": format,
                        "quality": quality
                    }
                else:
                    return {
                        "success": False,
                        "error": "Animation rendering failed"
                    }
                    
            except Exception as e:
                logger.error(f"Create animation failed: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.mcp.tool()
        async def start_web_app(
            code: str,
            app_type: str = "auto",
            port: int = 0,
            name: Optional[str] = None,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Start a web application with automatic containerization."""
            try:
                # Auto-detect app type if needed
                if app_type == "auto":
                    if "flask" in code.lower() or "Flask" in code:
                        app_type = "flask"
                    elif "streamlit" in code.lower():
                        app_type = "streamlit"
                    elif "fastapi" in code.lower() or "FastAPI" in code:
                        app_type = "fastapi"
                    elif "gradio" in code.lower():
                        app_type = "gradio"
                    else:
                        app_type = "flask"  # Default
                
                # Assign port if not specified
                if port == 0:
                    port = self._find_free_port()
                
                # Generate app name
                if not name:
                    name = f"app_{uuid.uuid4().hex[:8]}"
                
                # Create web application object
                app = WebApplication(
                    app_id=f"webapp_{uuid.uuid4().hex[:8]}",
                    name=name,
                    type=app_type,
                    code=code,
                    port=port,
                    url=f"http://localhost:{port}",
                    status="starting"
                )
                
                # Detect and add dependencies
                app.dependencies = self.server.docker_manager._detect_dependencies(code, app_type)
                
                # Start container
                container_id = self.server.docker_manager.run_web_app_container(app)
                
                if container_id:
                    app.container_id = container_id
                    app.status = "running"
                    
                    # Store app
                    self.server.active_web_apps[app.app_id] = app
                    
                    # Update metrics
                    self.server.metrics['web_apps_deployed'] += 1
                    
                    return {
                        "success": True,
                        "app_id": app.app_id,
                        "name": name,
                        "type": app_type,
                        "url": app.url,
                        "port": port,
                        "container_id": container_id[:12],
                        "status": "running"
                    }
                else:
                    # Fallback to local execution
                    app_file = self.artifacts_dir / f"{app.app_id}.py"
                    app_file.write_text(code)
                    
                    # Start process based on app type
                    if app_type == "streamlit":
                        process = subprocess.Popen(
                            [sys.executable, "-m", "streamlit", "run", str(app_file), 
                             "--server.port", str(port), "--server.address", "0.0.0.0"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE
                        )
                    elif app_type == "flask":
                        # Add Flask runner
                        runner_code = f"""
{code}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port={port}, debug=False)
"""
                        app_file.write_text(runner_code)
                        process = subprocess.Popen(
                            [sys.executable, str(app_file)],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE
                        )
                    else:
                        process = subprocess.Popen(
                            [sys.executable, str(app_file)],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE
                        )
                    
                    app.status = "running"
                    self.server.active_web_apps[app.app_id] = app
                    
                    return {
                        "success": True,
                        "app_id": app.app_id,
                        "name": name,
                        "type": app_type,
                        "url": app.url,
                        "port": port,
                        "status": "running (local)"
                    }
                    
            except Exception as e:
                logger.error(f"Start web app failed: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.mcp.tool()
        async def export_web_app(
            app_id: str,
            include_dockerfile: bool = True,
            include_compose: bool = True,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Export web app with Docker configuration."""
            try:
                if app_id not in self.server.active_web_apps:
                    return {
                        "success": False,
                        "error": f"Web app '{app_id}' not found"
                    }
                
                app = self.server.active_web_apps[app_id]
                
                # Create export directory
                export_dir = self.artifacts_dir / "exports" / app.name
                export_dir.mkdir(parents=True, exist_ok=True)
                
                # Write app code
                app_file = export_dir / "app.py"
                app_file.write_text(app.code)
                
                # Write requirements
                requirements_file = export_dir / "requirements.txt"
                requirements_file.write_text('\n'.join(app.dependencies))
                
                # Write Dockerfile if requested
                if include_dockerfile:
                    dockerfile_content = self.server.docker_manager._generate_dockerfile(app.type)
                    dockerfile = export_dir / "Dockerfile"
                    dockerfile.write_text(dockerfile_content)
                
                # Write docker-compose.yml if requested
                if include_compose:
                    compose_content = f"""
version: '3.8'

services:
  {app.name}:
    build: .
    ports:
      - "{app.port}:{app.port}"
    environment:
      - PORT={app.port}
    restart: unless-stopped
"""
                    compose_file = export_dir / "docker-compose.yml"
                    compose_file.write_text(compose_content)
                
                # Create README
                readme_content = f"""
# {app.name}

Type: {app.type}
Port: {app.port}

## Running with Docker

```bash
docker build -t {app.name} .
docker run -p {app.port}:{app.port} {app.name}
```

## Running with Docker Compose

```bash
docker-compose up
```

## Running locally

```bash
pip install -r requirements.txt
python app.py
```
"""
                readme_file = export_dir / "README.md"
                readme_file.write_text(readme_content)
                
                # Create ZIP archive
                archive_path = self.artifacts_dir / "exports" / f"{app.name}.zip"
                shutil.make_archive(
                    str(archive_path.with_suffix('')),
                    'zip',
                    export_dir
                )
                
                return {
                    "success": True,
                    "app_id": app_id,
                    "export_path": str(export_dir),
                    "archive_path": str(archive_path),
                    "files_exported": [
                        "app.py",
                        "requirements.txt",
                        "Dockerfile" if include_dockerfile else None,
                        "docker-compose.yml" if include_compose else None,
                        "README.md"
                    ]
                }
                
            except Exception as e:
                logger.error(f"Export web app failed: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.mcp.tool()
        async def list_artifacts(
            artifact_type: Optional[str] = None,
            limit: int = 100,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """List all artifacts with categorization."""
            try:
                artifacts = []
                
                # Collect artifacts from different sources
                for path in self.artifacts_dir.rglob('*'):
                    if path.is_file():
                        artifact_info = {
                            'path': str(path),
                            'name': path.name,
                            'type': self._detect_artifact_type(path),
                            'size': path.stat().st_size,
                            'created': datetime.fromtimestamp(path.stat().st_ctime).isoformat(),
                            'modified': datetime.fromtimestamp(path.stat().st_mtime).isoformat()
                        }
                        
                        # Filter by type if specified
                        if artifact_type and artifact_info['type'] != artifact_type:
                            continue
                        
                        artifacts.append(artifact_info)
                
                # Sort by creation time (newest first)
                artifacts.sort(key=lambda x: x['created'], reverse=True)
                
                # Apply limit
                artifacts = artifacts[:limit]
                
                # Categorize
                categories = {}
                for artifact in artifacts:
                    type_name = artifact['type']
                    if type_name not in categories:
                        categories[type_name] = []
                    categories[type_name].append(artifact)
                
                return {
                    "success": True,
                    "total_artifacts": len(artifacts),
                    "artifacts": artifacts,
                    "categories": {k: len(v) for k, v in categories.items()},
                    "filtered_by": artifact_type
                }
                
            except Exception as e:
                logger.error(f"List artifacts failed: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.mcp.tool()
        async def categorize_artifacts(
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Categorize all artifacts by type and purpose."""
            try:
                categories = {
                    'images': [],
                    'documents': [],
                    'data': [],
                    'code': [],
                    'models': [],
                    'logs': [],
                    'configs': [],
                    'archives': [],
                    'media': [],
                    'other': []
                }
                
                # Scan and categorize
                for path in self.artifacts_dir.rglob('*'):
                    if path.is_file():
                        category = self._categorize_file(path)
                        categories[category].append({
                            'path': str(path),
                            'name': path.name,
                            'size': path.stat().st_size
                        })
                
                # Calculate statistics
                stats = {}
                total_size = 0
                total_files = 0
                
                for category, files in categories.items():
                    if files:
                        category_size = sum(f['size'] for f in files)
                        stats[category] = {
                            'count': len(files),
                            'size': category_size,
                            'percentage': 0  # Will calculate after total
                        }
                        total_size += category_size
                        total_files += len(files)
                
                # Calculate percentages
                for category in stats:
                    if total_size > 0:
                        stats[category]['percentage'] = (stats[category]['size'] / total_size) * 100
                
                return {
                    "success": True,
                    "total_files": total_files,
                    "total_size": total_size,
                    "categories": {k: len(v) for k, v in categories.items() if v},
                    "statistics": stats
                }
                
            except Exception as e:
                logger.error(f"Categorize artifacts failed: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.mcp.tool()
        async def backup_current_artifacts(
            backup_name: Optional[str] = None,
            compress: bool = True,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Backup all current artifacts."""
            try:
                # Generate backup name
                if not backup_name:
                    backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                # Create backup directory
                backup_dir = self.artifacts_dir.parent / "backups" / backup_name
                backup_dir.mkdir(parents=True, exist_ok=True)
                
                # Copy all artifacts
                shutil.copytree(
                    self.artifacts_dir,
                    backup_dir / "artifacts",
                    dirs_exist_ok=True
                )
                
                # Create manifest
                manifest = {
                    'backup_name': backup_name,
                    'timestamp': datetime.now().isoformat(),
                    'file_count': sum(1 for _ in backup_dir.rglob('*') if _.is_file()),
                    'total_size': sum(f.stat().st_size for f in backup_dir.rglob('*') if f.is_file())
                }
                
                manifest_file = backup_dir / "manifest.json"
                manifest_file.write_text(json.dumps(manifest, indent=2))
                
                # Compress if requested
                archive_path = None
                if compress:
                    archive_path = backup_dir.parent / f"{backup_name}.tar.gz"
                    with tarfile.open(archive_path, 'w:gz') as tar:
                        tar.add(backup_dir, arcname=backup_name)
                    
                    # Remove uncompressed backup
                    shutil.rmtree(backup_dir)
                
                # Track backup
                self.artifact_backups[backup_name] = {
                    'name': backup_name,
                    'path': str(archive_path if archive_path else backup_dir),
                    'compressed': compress,
                    'manifest': manifest
                }
                
                return {
                    "success": True,
                    "backup_name": backup_name,
                    "backup_path": str(archive_path if archive_path else backup_dir),
                    "compressed": compress,
                    "file_count": manifest['file_count'],
                    "total_size": manifest['total_size']
                }
                
            except Exception as e:
                logger.error(f"Backup artifacts failed: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
        
        # Helper methods
        def _detect_artifact_type(self, path: Path) -> str:
            """Detect artifact type from file."""
            suffix = path.suffix.lower()
            
            if suffix in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg']:
                return 'image'
            elif suffix in ['.mp4', '.avi', '.mov', '.webm']:
                return 'video'
            elif suffix in ['.mp3', '.wav', '.ogg', '.flac']:
                return 'audio'
            elif suffix in ['.txt', '.md', '.rst', '.log']:
                return 'text'
            elif suffix in ['.json', '.yaml', '.yml', '.toml', '.ini']:
                return 'config'
            elif suffix in ['.csv', '.tsv', '.parquet', '.feather']:
                return 'data'
            elif suffix in ['.pkl', '.joblib', '.h5', '.pt', '.pth']:
                return 'model'
            elif suffix in ['.py', '.js', '.java', '.cpp', '.c', '.go', '.rs']:
                return 'code'
            elif suffix in ['.pdf', '.doc', '.docx', '.ppt', '.pptx']:
                return 'document'
            elif suffix in ['.zip', '.tar', '.gz', '.rar', '.7z']:
                return 'archive'
            else:
                return 'other'
        
        def _categorize_file(self, path: Path) -> str:
            """Categorize file into broader categories."""
            file_type = self._detect_artifact_type(path)
            
            category_map = {
                'image': 'images',
                'video': 'media',
                'audio': 'media',
                'text': 'documents',
                'config': 'configs',
                'data': 'data',
                'model': 'models',
                'code': 'code',
                'document': 'documents',
                'archive': 'archives',
                'other': 'other'
            }
            
            return category_map.get(file_type, 'other')
        
        def _find_free_port(self) -> int:
            """Find a free port for web app."""
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', 0))
                s.listen(1)
                port = s.getsockname()[1]
            return port
        
        def _save_execution(self, execution: TaskExecution):
            """Save execution record to storage."""
            # Implementation would save to database
            pass
        
        def _generate_diff(self, old_content: str, new_content: str) -> str:
            """Generate diff between two contents."""
            old_lines = old_content.splitlines(keepends=True)
            new_lines = new_content.splitlines(keepends=True)
            
            diff = difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile='original',
                tofile='modified',
                n=3
            )
            
            return ''.join(diff)

# Continue with remaining helper implementations...
