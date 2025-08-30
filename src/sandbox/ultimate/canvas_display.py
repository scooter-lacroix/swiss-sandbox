#!/usr/bin/env python3
"""
Canvas-like Display Component for Intelligent Sandbox

Provides a ChatGPT Canvas-style interface for code preview and execution.

Requirements: 6.4, 6.5
"""

import os
import sys
import json
import asyncio
import logging
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List

# Web framework imports
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Enhanced connection management
from ..core.connection_manager import get_connection_manager, ConnectionState

logger = logging.getLogger(__name__)


class CanvasDisplay:
    """
    Canvas-like display component for real-time code preview and execution.
    """

    def __init__(self, port: int = 8888, heartbeat_interval: int = 30,
                 execution_timeout: Optional[int] = None):
        """Initialize the Canvas display server with enhanced error recovery.

        Args:
            port: Port to run the server on
            heartbeat_interval: Heartbeat interval in seconds (default 30)
            execution_timeout: Maximum execution time in seconds (default None = no timeout)
        """
        self.port = port
        self.heartbeat_interval = heartbeat_interval

        # Configure timeout from environment variable if not explicitly set
        if execution_timeout is None:
            env_timeout = os.getenv('SANDBOX_EXECUTION_TIMEOUT')
            if env_timeout:
                try:
                    # Allow "none" or "0" to disable timeout
                    if env_timeout.lower() in ('none', '0'):
                        self.execution_timeout = None
                    else:
                        self.execution_timeout = int(env_timeout)
                except ValueError:
                    logger.warning(f"Invalid SANDBOX_EXECUTION_TIMEOUT value: {env_timeout}, using no timeout")
                    self.execution_timeout = None
            else:
                self.execution_timeout = None  # Default to no timeout for canvas
        else:
            self.execution_timeout = execution_timeout

        # Initialize connection manager for enhanced error recovery
        self.connection_manager = get_connection_manager()

        # Enhanced session tracking with connection state
        self.active_sessions: Dict[str, WebSocket] = {}  # session_id -> websocket (for backward compatibility)
        self.session_info: Dict[str, Dict[str, Any]] = {}  # session_id -> session_info
        self.execution_history = []

        # Error recovery settings
        self.max_reconnect_attempts = 5
        self.reconnect_base_delay = 1.0
        self.reconnect_max_delay = 30.0

        self.app = FastAPI(title="Intelligent Sandbox Canvas")

        # Configure CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Setup routes
        self._setup_routes()

        logger.info(f"Canvas Display initialized on port {port} with timeout: {execution_timeout}")
    
    def _setup_routes(self):
        """Setup API routes for the Canvas display."""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def root():
            """Serve the main Canvas interface."""
            return self._get_html_interface()
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """Enhanced WebSocket endpoint with comprehensive error recovery."""
            session_id = f"session_{datetime.now().timestamp()}"
            client_ip = websocket.client.host if websocket.client else "unknown"

            # Initialize session info
            self.session_info[session_id] = {
                'connection_id': session_id,
                'client_ip': client_ip,
                'connected_at': datetime.now(),
                'last_activity': datetime.now(),
                'state': 'connecting',
                'error_count': 0,
                'reconnect_count': 0
            }

            try:
                # Accept WebSocket connection
                await websocket.accept()
                self.active_sessions[session_id] = websocket

                # Register with connection manager
                success, message = self.connection_manager.add_connection(
                    session_id, client_ip, session_id=session_id
                )

                if not success:
                    logger.warning(f"Connection rejected by manager: {message}")
                    await websocket.send_json({
                        "action": "error",
                        "message": "Connection rejected",
                        "details": message
                    })
                    await websocket.close(code=1008)  # Policy violation
                    return

                # Update session state
                self.session_info[session_id]['state'] = 'connected'
                logger.info(f"WebSocket connection established: {session_id} from {client_ip}")

                # Start heartbeat
                heartbeat_task = asyncio.create_task(self._send_heartbeat(websocket, session_id))

                # Main message loop with enhanced error handling
                consecutive_errors = 0
                max_consecutive_errors = 3

                while True:
                    try:
                        # Receive message with timeout
                        data = await asyncio.wait_for(
                            websocket.receive_json(),
                            timeout=300  # 5 minute timeout
                        )

                        # Update activity
                        self.session_info[session_id]['last_activity'] = datetime.now()
                        self.connection_manager.update_activity(session_id)

                        if data.get("action") == "pong":
                            continue

                        # Handle message
                        response = await self._handle_websocket_message(data, session_id)
                        await websocket.send_json(response)

                        # Reset error counter on successful message
                        consecutive_errors = 0

                    except asyncio.TimeoutError:
                        logger.debug(f"WebSocket timeout for session {session_id}")
                        await websocket.send_json({"action": "ping"})
                        continue

                    except Exception as e:
                        consecutive_errors += 1
                        error_type = self.connection_manager.record_connection_error(
                            session_id, e, "websocket_message_handling"
                        )

                        logger.error(f"WebSocket message error for {session_id} "
                                   f"(error {consecutive_errors}/{max_consecutive_errors}): {e}")

                        if consecutive_errors >= max_consecutive_errors:
                            logger.warning(f"Too many consecutive errors for {session_id}, closing connection")
                            await websocket.send_json({
                                "action": "error",
                                "message": "Too many errors, closing connection",
                                "error_type": error_type.value
                            })
                            break

                        # Send error response but keep connection alive
                        try:
                            await websocket.send_json({
                                "action": "error",
                                "message": str(e),
                                "error_type": error_type.value,
                                "recoverable": True
                            })
                        except Exception:
                            # Connection might be closed
                            break

            except Exception as e:
                error_type = self.connection_manager.record_connection_error(
                    session_id, e, "websocket_connection"
                )
                logger.error(f"WebSocket connection error for {session_id}: {e}")

                # Try to send error message before closing
                try:
                    if websocket.client_state.name == "CONNECTED":
                        await websocket.send_json({
                            "action": "error",
                            "message": "Connection error",
                            "error_type": error_type.value
                        })
                except Exception:
                    pass  # Connection already closed

            finally:
                # Cleanup
                if session_id in self.active_sessions:
                    del self.active_sessions[session_id]

                if session_id in self.session_info:
                    self.session_info[session_id]['state'] = 'disconnected'
                    logger.info(f"WebSocket connection closed: {session_id}")

                # Remove from connection manager
                self.connection_manager.remove_connection(session_id, "websocket_closed")

                # Cancel heartbeat task
                if 'heartbeat_task' in locals() and not heartbeat_task.done():
                    heartbeat_task.cancel()
        
        @self.app.post("/api/execute")
        async def execute_code(request: Dict[str, Any]):
            """Execute code and return results."""
            code = request.get("code", "")
            language = request.get("language", "python")
            
            result = await self._execute_code(code, language)
            
            # Store in history
            self.execution_history.append({
                "timestamp": datetime.now().isoformat(),
                "code": code,
                "language": language,
                "result": result
            })
            
            return JSONResponse(result)
        
        @self.app.post("/api/render")
        async def render_code(request: Dict[str, Any]):
            """Render code with syntax highlighting."""
            code = request.get("code", "")
            language = request.get("language", "python")
            
            rendered = self._render_code(code, language)
            return JSONResponse({"rendered": rendered})
        
        @self.app.get("/api/status")
        async def get_status():
            """Get comprehensive Canvas display status with connection health."""
            # Get connection manager stats
            conn_stats = self.connection_manager.get_connection_stats()

            # Calculate session health
            healthy_sessions = 0
            total_sessions = len(self.active_sessions)

            for session_id, info in self.session_info.items():
                if info.get('state') == 'connected':
                    last_activity = info.get('last_activity')
                    if last_activity and (datetime.now() - last_activity).total_seconds() < 300:  # 5 minutes
                        healthy_sessions += 1

            health_percentage = (healthy_sessions / max(1, total_sessions)) * 100

            # Get degradation status
            degradation_info = conn_stats.get('degradation_status', {})

            return JSONResponse({
                "status": "running",
                "active_sessions": total_sessions,
                "healthy_sessions": healthy_sessions,
                "health_percentage": round(health_percentage, 1),
                "executions": len(self.execution_history),
                "connection_stats": conn_stats,
                "degradation_level": degradation_info.get('degradation_level', 'normal'),
                "circuit_breaker_state": conn_stats.get('circuit_breaker_state', 'CLOSED'),
                "error_rate": degradation_info.get('error_rate', 0),
                "connection_utilization": degradation_info.get('connection_utilization', 0)
            })
        
        @self.app.get("/api/history")
        async def get_history(limit: int = 10):
            """Get execution history."""
            history = self.execution_history[-limit:] if limit else self.execution_history
            return JSONResponse({"history": history})
        
        @self.app.post("/api/clear")
        async def clear_display():
            """Clear the display content with enhanced error handling."""
            success_count = 0
            error_count = 0

            # Notify all connected clients
            for session_id, websocket in self.active_sessions.items():
                try:
                    await websocket.send_json({"action": "clear"})
                    success_count += 1

                    # Update session activity
                    if session_id in self.session_info:
                        self.session_info[session_id]['last_activity'] = datetime.now()
                        self.connection_manager.update_activity(session_id)

                except Exception as e:
                    error_count += 1
                    logger.debug(f"Failed to send clear message to {session_id}: {e}")

                    # Record error but don't remove session - connection might still be usable
                    if session_id in self.session_info:
                        self.session_info[session_id]['error_count'] += 1

            logger.info(f"Clear display: sent to {success_count} clients, {error_count} failed")
            return JSONResponse({
                "success": True,
                "clients_notified": success_count,
                "errors": error_count
            })
    
    async def _handle_websocket_message(
        self,
        data: Dict[str, Any],
        session_id: str
    ) -> Dict[str, Any]:
        """Handle WebSocket messages."""
        action = data.get("action")
        
        if action == "execute":
            code = data.get("code", "")
            language = data.get("language", "python")
            result = await self._execute_code(code, language)
            return {"action": "execution_result", "result": result}
        
        elif action == "render":
            code = data.get("code", "")
            language = data.get("language", "python")
            rendered = self._render_code(code, language)
            return {"action": "render_result", "rendered": rendered}
        
        elif action == "save":
            code = data.get("code", "")
            filename = data.get("filename", "canvas_code.py")
            saved_path = self._save_code(code, filename)
            return {"action": "save_result", "path": saved_path}
        
        else:
            return {"action": "error", "message": f"Unknown action: {action}"}

    async def _send_heartbeat(self, websocket: WebSocket, session_id: str):
        """Send heartbeat pings to the client with enhanced error handling."""
        consecutive_failures = 0
        max_consecutive_failures = 3

        try:
            while True:
                await asyncio.sleep(self.heartbeat_interval)

                try:
                    await websocket.send_json({"action": "ping"})

                    # Update session activity
                    if session_id in self.session_info:
                        self.session_info[session_id]['last_activity'] = datetime.now()
                        self.connection_manager.update_activity(session_id)

                    # Reset failure counter
                    consecutive_failures = 0

                except Exception as e:
                    consecutive_failures += 1
                    logger.debug(f"Heartbeat failed for {session_id} "
                               f"(failure {consecutive_failures}/{max_consecutive_failures}): {e}")

                    if consecutive_failures >= max_consecutive_failures:
                        logger.warning(f"Heartbeat failed too many times for {session_id}, ending heartbeat")
                        break

                    # Continue trying - connection might still be alive

        except asyncio.CancelledError:
            logger.debug(f"Heartbeat cancelled for session {session_id}")
        except Exception as e:
            logger.error(f"Heartbeat error for session {session_id}: {e}")

    async def _execute_code(
        self,
        code: str,
        language: str = "python"
    ) -> Dict[str, Any]:
        """Execute code and return results."""
        try:
            if language == "python":
                # Create temporary file
                with tempfile.NamedTemporaryFile(
                    mode='w',
                    suffix='.py',
                    delete=False
                ) as f:
                    f.write(code)
                    temp_file = f.name
                
                # Execute Python code
                result = await asyncio.create_subprocess_exec(
                    sys.executable,
                    temp_file,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                # Use configurable timeout or no timeout if None
                if self.execution_timeout is not None:
                    stdout, stderr = await asyncio.wait_for(
                        result.communicate(),
                        timeout=self.execution_timeout
                    )
                else:
                    stdout, stderr = await result.communicate()
                
                # Clean up
                os.unlink(temp_file)
                
                return {
                    "success": result.returncode == 0,
                    "output": stdout.decode('utf-8'),
                    "error": stderr.decode('utf-8'),
                    "language": language
                }
            
            elif language == "javascript":
                # Execute with Node.js if available
                result = await asyncio.create_subprocess_exec(
                    "node",
                    "-e",
                    code,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                # Use configurable timeout or no timeout if None
                if self.execution_timeout is not None:
                    stdout, stderr = await asyncio.wait_for(
                        result.communicate(),
                        timeout=self.execution_timeout
                    )
                else:
                    stdout, stderr = await result.communicate()
                
                return {
                    "success": result.returncode == 0,
                    "output": stdout.decode('utf-8'),
                    "error": stderr.decode('utf-8'),
                    "language": language
                }
            
            else:
                return {
                    "success": False,
                    "error": f"Unsupported language: {language}",
                    "language": language
                }
                
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": f"Execution timed out after {self.execution_timeout} seconds",
                "language": language
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "language": language
            }
    
    def _render_code(self, code: str, language: str) -> str:
        """Render code with basic syntax highlighting."""
        # Simple HTML rendering with pre tags
        # In production, use a proper syntax highlighter like Pygments
        return f'<pre class="language-{language}"><code>{code}</code></pre>'
    
    def _save_code(self, code: str, filename: str) -> str:
        """Save code to a file."""
        save_dir = Path.home() / "canvas_saves"
        save_dir.mkdir(exist_ok=True)
        
        save_path = save_dir / filename
        with open(save_path, 'w') as f:
            f.write(code)
        
        return str(save_path)
    
    def _get_html_interface(self) -> str:
        """Get the HTML interface for the Canvas display."""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Intelligent Sandbox Canvas</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }
        
        .header {
            background: rgba(255, 255, 255, 0.95);
            padding: 1rem 2rem;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .header h1 {
            color: #333;
            font-size: 1.5rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .container {
            flex: 1;
            display: flex;
            gap: 1rem;
            padding: 1rem;
            max-width: 1400px;
            width: 100%;
            margin: 0 auto;
        }
        
        .editor-panel, .output-panel {
            background: white;
            border-radius: 10px;
            padding: 1rem;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            flex: 1;
            display: flex;
            flex-direction: column;
        }
        
        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid #f0f0f0;
        }
        
        .panel-title {
            font-size: 1.1rem;
            font-weight: 600;
            color: #333;
        }
        
        .controls {
            display: flex;
            gap: 0.5rem;
        }
        
        button {
            background: #667eea;
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 5px;
            cursor: pointer;
            font-size: 0.9rem;
            transition: all 0.3s;
        }
        
        button:hover {
            background: #5a67d8;
            transform: translateY(-1px);
        }
        
        button:active {
            transform: translateY(0);
        }
        
        .run-button {
            background: #48bb78;
        }
        
        .run-button:hover {
            background: #38a169;
        }
        
        .clear-button {
            background: #f56565;
        }
        
        .clear-button:hover {
            background: #e53e3e;
        }
        
        #code-editor {
            flex: 1;
            font-family: 'Fira Code', 'Courier New', monospace;
            font-size: 14px;
            padding: 1rem;
            border: 1px solid #e0e0e0;
            border-radius: 5px;
            resize: none;
            background: #fafafa;
        }
        
        #output {
            flex: 1;
            font-family: 'Fira Code', 'Courier New', monospace;
            font-size: 14px;
            padding: 1rem;
            background: #1e1e1e;
            color: #00ff00;
            border-radius: 5px;
            overflow-y: auto;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        
        .status-bar {
            background: rgba(255, 255, 255, 0.95);
            padding: 0.5rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.85rem;
            color: #666;
        }
        
        .status-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            background: #48bb78;
            border-radius: 50%;
            margin-right: 0.5rem;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        select {
            padding: 0.3rem 0.5rem;
            border: 1px solid #d0d0d0;
            border-radius: 3px;
            background: white;
            cursor: pointer;
        }
        
        .error-output {
            color: #ff6b6b;
        }
        
        .success-output {
            color: #51cf66;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>
            🎨 Intelligent Sandbox Canvas
            <span style="font-size: 0.8rem; color: #888;">Real-time Code Preview & Execution</span>
        </h1>
    </div>
    
    <div class="container">
        <div class="editor-panel">
            <div class="panel-header">
                <span class="panel-title">Code Editor</span>
                <div class="controls">
                    <select id="language-select">
                        <option value="python">Python</option>
                        <option value="javascript">JavaScript</option>
                        <option value="html">HTML</option>
                        <option value="css">CSS</option>
                    </select>
                    <button onclick="saveCode()">💾 Save</button>
                    <button class="run-button" onclick="runCode()">▶ Run</button>
                </div>
            </div>
            <textarea id="code-editor" placeholder="Enter your code here...">#!/usr/bin/env python3
# Welcome to Intelligent Sandbox Canvas!
# Type your code and click Run to execute

def hello_world():
    return "Hello from the Canvas!"

if __name__ == "__main__":
    print(hello_world())
    print("✨ Code executed successfully!")</textarea>
        </div>
        
        <div class="output-panel">
            <div class="panel-header">
                <span class="panel-title">Output</span>
                <div class="controls">
                    <button class="clear-button" onclick="clearOutput()">🗑️ Clear</button>
                </div>
            </div>
            <div id="output">Ready to execute code...</div>
        </div>
    </div>
    
    <div class="status-bar">
        <div>
            <span class="status-indicator"></span>
            <span id="status-text">Connected</span>
        </div>
        <div id="execution-time"></div>
    </div>
    
    <script>
        let ws = null;
        let reconnectAttempts = 0;
        const maxReconnectAttempts = 10;
        const initialReconnectDelay = 1000; // 1 second
        const maxReconnectDelay = 30000; // 30 seconds

        // Initialize WebSocket connection
        function initWebSocket() {
            ws = new WebSocket(`ws://${window.location.host}/ws`);

            ws.onopen = () => {
                document.getElementById('status-text').textContent = 'Connected';
                document.querySelector('.status-indicator').style.background = '#48bb78';
                reconnectAttempts = 0; // Reset attempts on successful connection
            };

            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                document.getElementById('status-text').textContent = 'Connection Error';
                document.querySelector('.status-indicator').style.background = '#f56565';
            };

            ws.onclose = () => {
                document.getElementById('status-text').textContent = 'Disconnected';
                document.querySelector('.status-indicator').style.background = '#f56565';

                if (reconnectAttempts < maxReconnectAttempts) {
                    reconnectAttempts++;
                    const delay = Math.min(
                        initialReconnectDelay * Math.pow(2, reconnectAttempts - 1),
                        maxReconnectDelay
                    );

                    document.getElementById('status-text').textContent =
                        `Reconnecting... (attempt ${reconnectAttempts}/${maxReconnectAttempts})`;

                    setTimeout(initWebSocket, delay);
                } else {
                    document.getElementById('status-text').textContent =
                        'Failed to reconnect after maximum attempts';
                }
            };
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                handleServerMessage(data);
            };
        }
        
        function handleServerMessage(data) {
            if (data.action === 'execution_result') {
                displayResult(data.result);
            } else if (data.action === 'clear') {
                clearOutput();
            } else if (data.action === 'ping') {
                ws.send(JSON.stringify({"action": "pong"}));
            }
        }
        
        async function runCode() {
            const code = document.getElementById('code-editor').value;
            const language = document.getElementById('language-select').value;
            const output = document.getElementById('output');
            
            output.textContent = 'Executing...';
            output.className = '';
            
            const startTime = performance.now();
            
            try {
                const response = await fetch('/api/execute', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({code, language})
                });
                
                const result = await response.json();
                displayResult(result);
                
                const endTime = performance.now();
                const executionTime = ((endTime - startTime) / 1000).toFixed(3);
                document.getElementById('execution-time').textContent = `Execution time: ${executionTime}s`;
                
            } catch (error) {
                output.textContent = `Error: ${error.message}`;
                output.className = 'error-output';
            }
        }
        
        function displayResult(result) {
            const output = document.getElementById('output');
            
            if (result.success) {
                output.textContent = result.output || 'Code executed successfully (no output)';
                output.className = 'success-output';
            } else {
                output.textContent = result.error || 'Execution failed';
                output.className = 'error-output';
            }
        }
        
        function clearOutput() {
            document.getElementById('output').textContent = 'Ready to execute code...';
            document.getElementById('output').className = '';
            document.getElementById('execution-time').textContent = '';
        }
        
        async function saveCode() {
            const code = document.getElementById('code-editor').value;
            const language = document.getElementById('language-select').value;
            
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    action: 'save',
                    code,
                    filename: `canvas_code.${language === 'python' ? 'py' : 'js'}`
                }));
            }
            
            alert('Code saved!');
        }
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey || e.metaKey) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    runCode();
                } else if (e.key === 's') {
                    e.preventDefault();
                    saveCode();
                }
            }
        });
        
        // Initialize on load
        window.addEventListener('load', () => {
            initWebSocket();
        });
    </script>
</body>
</html>
        """
    
    def start(self):
        """Start the Canvas display server."""
        logger.info(f"Starting Canvas Display on http://localhost:{self.port}")
        uvicorn.run(self.app, host="0.0.0.0", port=self.port)
    
    async def start_async(self):
        """Start the Canvas display server asynchronously."""
        config = uvicorn.Config(self.app, host="0.0.0.0", port=self.port)
        server = uvicorn.Server(config)
        await server.serve()


if __name__ == "__main__":
    # Example usage
    canvas = CanvasDisplay(port=8888)
    print("\n" + "="*60)
    print("🎨 CANVAS DISPLAY COMPONENT")
    print("="*60)
    print(f"Starting server on http://localhost:8888")
    print("Open your browser to see the Canvas interface")
    print("Press Ctrl+C to stop")
    print("="*60)
    
    try:
        canvas.start()
    except KeyboardInterrupt:
        print("\nCanvas Display stopped.")
