"""
User interface components for the intelligent sandbox MCP client.

This module provides:
- Interactive command-line interface
- Progress visualization and status updates
- Error reporting and retry mechanisms
- Workflow management and monitoring
"""

import asyncio
import time
import sys
import os
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path

from .client import SandboxMCPClient, ProgressUpdate, OperationResult, OperationStatus, ClientStatus


class UITheme:
    """UI color and styling theme."""
    
    # Colors (ANSI escape codes)
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Background colors
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"
    
    # Status colors
    SUCCESS = GREEN
    ERROR = RED
    WARNING = YELLOW
    INFO = BLUE
    PROGRESS = CYAN


class ProgressBar:
    """ASCII progress bar for operation tracking."""
    
    def __init__(self, width: int = 50):
        self.width = width
    
    def render(self, progress: float, message: str = "") -> str:
        """
        Render a progress bar.
        
        Args:
            progress: Progress percentage (0-100)
            message: Optional message to display
            
        Returns:
            Formatted progress bar string
        """
        filled = int(self.width * progress / 100)
        bar = "█" * filled + "░" * (self.width - filled)
        percentage = f"{progress:5.1f}%"
        
        if message:
            return f"{UITheme.PROGRESS}[{bar}] {percentage} {message}{UITheme.RESET}"
        else:
            return f"{UITheme.PROGRESS}[{bar}] {percentage}{UITheme.RESET}"


class StatusDisplay:
    """Real-time status display for operations."""
    
    def __init__(self):
        self.active_operations: Dict[str, Dict[str, Any]] = {}
        self.last_update = 0
        self.progress_bar = ProgressBar()
    
    def update_operation(self, update: ProgressUpdate):
        """Update operation status."""
        self.active_operations[update.operation_id] = {
            "status": update.status,
            "progress": update.progress_percent,
            "message": update.message,
            "details": update.details,
            "timestamp": update.timestamp
        }
        self._refresh_display()
    
    def remove_operation(self, operation_id: str):
        """Remove completed operation from display."""
        self.active_operations.pop(operation_id, None)
        self._refresh_display()
    
    def _refresh_display(self):
        """Refresh the status display."""
        current_time = time.time()
        if current_time - self.last_update < 0.1:  # Throttle updates
            return
        
        self.last_update = current_time
        
        # Clear previous lines
        if self.active_operations:
            print(f"\033[{len(self.active_operations)}A", end="")  # Move cursor up
        
        # Display active operations
        for operation_id, operation in self.active_operations.items():
            status_color = self._get_status_color(operation["status"])
            status_text = operation["status"].value.upper()
            
            if operation["status"] == OperationStatus.RUNNING:
                progress_bar = self.progress_bar.render(
                    operation["progress"], 
                    operation["message"]
                )
                print(f"{status_color}[{status_text}]{UITheme.RESET} {progress_bar}")
            else:
                print(f"{status_color}[{status_text}]{UITheme.RESET} {operation['message']}")
    
    def _get_status_color(self, status: OperationStatus) -> str:
        """Get color for operation status."""
        color_map = {
            OperationStatus.PENDING: UITheme.YELLOW,
            OperationStatus.RUNNING: UITheme.CYAN,
            OperationStatus.COMPLETED: UITheme.SUCCESS,
            OperationStatus.FAILED: UITheme.ERROR,
            OperationStatus.CANCELLED: UITheme.WARNING
        }
        return color_map.get(status, UITheme.RESET)


class InteractiveCLI:
    """Interactive command-line interface for the sandbox client."""
    
    def __init__(self, client: SandboxMCPClient):
        self.client = client
        self.status_display = StatusDisplay()
        self.running = False
        
        # Register callbacks
        self.client.add_progress_callback(self._on_progress_update)
        self.client.add_error_callback(self._on_error)
        
        # Command history
        self.command_history: List[str] = []
        self.history_index = 0
    
    async def start(self):
        """Start the interactive CLI."""
        self.running = True
        
        # Display welcome message
        self._print_welcome()
        
        # Main command loop
        while self.running:
            try:
                # Display prompt
                prompt = self._get_prompt()
                command = await self._get_user_input(prompt)
                
                if command:
                    self.command_history.append(command)
                    await self._execute_command(command)
                    
            except KeyboardInterrupt:
                print(f"\n{UITheme.WARNING}Use 'quit' or 'exit' to exit gracefully.{UITheme.RESET}")
            except EOFError:
                break
        
        print(f"{UITheme.INFO}Goodbye!{UITheme.RESET}")
    
    def stop(self):
        """Stop the interactive CLI."""
        self.running = False
    
    def _print_welcome(self):
        """Print welcome message."""
        print(f"{UITheme.BOLD}{UITheme.BLUE}")
        print("╔══════════════════════════════════════════════════════════════╗")
        print("║                 Intelligent Sandbox Client                  ║")
        print("║                                                              ║")
        print("║  A comprehensive AI-assisted development sandbox            ║")
        print("║  Type 'help' for available commands                         ║")
        print("╚══════════════════════════════════════════════════════════════╝")
        print(f"{UITheme.RESET}")
        
        # Display connection status
        status_color = UITheme.SUCCESS if self.client.status == ClientStatus.CONNECTED else UITheme.ERROR
        print(f"Connection Status: {status_color}{self.client.status.value.upper()}{UITheme.RESET}")
        print()
    
    def _get_prompt(self) -> str:
        """Get command prompt."""
        status_indicator = "●" if self.client.status == ClientStatus.CONNECTED else "○"
        status_color = UITheme.SUCCESS if self.client.status == ClientStatus.CONNECTED else UITheme.ERROR
        
        active_ops = len(self.client.get_active_operations())
        ops_indicator = f" ({active_ops} active)" if active_ops > 0 else ""
        
        return f"{status_color}{status_indicator}{UITheme.RESET} sandbox{ops_indicator}> "
    
    async def _get_user_input(self, prompt: str) -> str:
        """Get user input asynchronously."""
        # In a real implementation, this would use proper async input
        # For now, we'll use a simple synchronous input
        try:
            return input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            return ""
    
    async def _execute_command(self, command: str):
        """Execute a user command."""
        parts = command.split()
        if not parts:
            return
        
        cmd = parts[0].lower()
        args = parts[1:]
        
        try:
            if cmd in ["help", "h"]:
                self._show_help()
            elif cmd in ["status", "st"]:
                await self._show_status()
            elif cmd in ["create", "c"]:
                await self._create_workspace(args)
            elif cmd in ["analyze", "a"]:
                await self._analyze_codebase(args)
            elif cmd in ["plan", "p"]:
                await self._create_task_plan(args)
            elif cmd in ["execute", "exec", "e"]:
                await self._execute_task_plan(args)
            elif cmd in ["history", "hist", "h"]:
                await self._show_history(args)
            elif cmd in ["cleanup", "clean"]:
                await self._cleanup_workspace(args)
            elif cmd in ["operations", "ops"]:
                self._show_operations()
            elif cmd in ["clear", "cls"]:
                os.system('clear' if os.name == 'posix' else 'cls')
            elif cmd in ["quit", "exit", "q"]:
                self.running = False
            else:
                print(f"{UITheme.ERROR}Unknown command: {cmd}{UITheme.RESET}")
                print(f"Type 'help' for available commands.")
                
        except Exception as e:
            print(f"{UITheme.ERROR}Error executing command: {e}{UITheme.RESET}")
    
    def _show_help(self):
        """Show help information."""
        print(f"{UITheme.BOLD}Available Commands:{UITheme.RESET}")
        print()
        
        commands = [
            ("help, h", "Show this help message"),
            ("status, st", "Show sandbox system status"),
            ("create, c <path> [id]", "Create a new workspace from source path"),
            ("analyze, a <workspace_id>", "Analyze codebase in workspace"),
            ("plan, p <workspace_id> <description>", "Create task plan"),
            ("execute, exec, e <plan_id>", "Execute task plan"),
            ("history, hist <workspace_id>", "Show execution history"),
            ("cleanup, clean <workspace_id>", "Clean up workspace"),
            ("operations, ops", "Show active operations"),
            ("clear, cls", "Clear screen"),
            ("quit, exit, q", "Exit the client")
        ]
        
        for cmd, desc in commands:
            print(f"  {UITheme.CYAN}{cmd:<30}{UITheme.RESET} {desc}")
        print()
    
    async def _show_status(self):
        """Show system status."""
        print(f"{UITheme.INFO}Getting sandbox status...{UITheme.RESET}")
        
        result = await self.client.get_sandbox_status()
        
        if result.success:
            status = result.result
            print(f"{UITheme.BOLD}Sandbox System Status:{UITheme.RESET}")
            print(f"  Active Workspaces: {status.get('system_status', {}).get('active_workspaces', 0)}")
            print(f"  Active Sessions: {status.get('system_status', {}).get('active_sessions', 0)}")
            print(f"  Total Users: {status.get('system_status', {}).get('total_users', 0)}")
            
            config = status.get('configuration', {})
            print(f"\n{UITheme.BOLD}Configuration:{UITheme.RESET}")
            print(f"  Isolation Enabled: {config.get('isolation_enabled', False)}")
            print(f"  Authentication: {config.get('authentication_enabled', False)}")
            print(f"  Max Sandboxes: {config.get('max_concurrent_sandboxes', 'N/A')}")
        else:
            print(f"{UITheme.ERROR}Failed to get status: {result.error}{UITheme.RESET}")
    
    async def _create_workspace(self, args: List[str]):
        """Create a new workspace."""
        if not args:
            print(f"{UITheme.ERROR}Usage: create <source_path> [workspace_id]{UITheme.RESET}")
            return
        
        source_path = args[0]
        workspace_id = args[1] if len(args) > 1 else None
        
        print(f"{UITheme.INFO}Creating workspace from {source_path}...{UITheme.RESET}")
        
        result = await self.client.create_workspace(source_path, workspace_id)
        
        if result.success:
            workspace_info = result.result
            print(f"{UITheme.SUCCESS}✓ Workspace created successfully!{UITheme.RESET}")
            print(f"  Workspace ID: {workspace_info.get('workspace_id')}")
            print(f"  Sandbox Path: {workspace_info.get('sandbox_path')}")
            print(f"  Status: {workspace_info.get('status')}")
        else:
            print(f"{UITheme.ERROR}✗ Failed to create workspace: {result.error}{UITheme.RESET}")
    
    async def _analyze_codebase(self, args: List[str]):
        """Analyze codebase in a workspace."""
        if not args:
            print(f"{UITheme.ERROR}Usage: analyze <workspace_id>{UITheme.RESET}")
            return
        
        workspace_id = args[0]
        
        print(f"{UITheme.INFO}Analyzing codebase in workspace {workspace_id}...{UITheme.RESET}")
        
        result = await self.client.analyze_codebase(workspace_id)
        
        if result.success:
            analysis = result.result.get('analysis', {})
            print(f"{UITheme.SUCCESS}✓ Codebase analysis completed!{UITheme.RESET}")
            print(f"  Languages: {', '.join(analysis.get('languages', []))}")
            print(f"  Frameworks: {', '.join(analysis.get('frameworks', []))}")
            print(f"  Dependencies: {analysis.get('dependencies_count', 0)}")
            print(f"  Lines of Code: {analysis.get('lines_of_code', 0)}")
            print(f"  Patterns Found: {analysis.get('patterns_found', 0)}")
            
            if analysis.get('summary'):
                print(f"\n{UITheme.BOLD}Summary:{UITheme.RESET}")
                print(f"  {analysis['summary']}")
        else:
            print(f"{UITheme.ERROR}✗ Failed to analyze codebase: {result.error}{UITheme.RESET}")
    
    async def _create_task_plan(self, args: List[str]):
        """Create a task plan."""
        if len(args) < 2:
            print(f"{UITheme.ERROR}Usage: plan <workspace_id> <task_description>{UITheme.RESET}")
            return
        
        workspace_id = args[0]
        task_description = " ".join(args[1:])
        
        print(f"{UITheme.INFO}Creating task plan for workspace {workspace_id}...{UITheme.RESET}")
        
        result = await self.client.create_task_plan(workspace_id, task_description)
        
        if result.success:
            plan_info = result.result
            print(f"{UITheme.SUCCESS}✓ Task plan created successfully!{UITheme.RESET}")
            print(f"  Plan ID: {plan_info.get('plan_id')}")
            print(f"  Description: {plan_info.get('description')}")
            print(f"  Tasks Count: {plan_info.get('tasks_count')}")
            print(f"  Status: {plan_info.get('status')}")
            print(f"  Approval Status: {plan_info.get('approval_status')}")
            
            # Show task preview
            tasks_preview = plan_info.get('tasks_preview', [])
            if tasks_preview:
                print(f"\n{UITheme.BOLD}Task Preview:{UITheme.RESET}")
                for task in tasks_preview:
                    status_color = UITheme.SUCCESS if task['status'] == 'completed' else UITheme.YELLOW
                    print(f"  {status_color}[{task['status'].upper()}]{UITheme.RESET} {task['description']}")
        else:
            print(f"{UITheme.ERROR}✗ Failed to create task plan: {result.error}{UITheme.RESET}")
    
    async def _execute_task_plan(self, args: List[str]):
        """Execute a task plan."""
        if not args:
            print(f"{UITheme.ERROR}Usage: execute <plan_id>{UITheme.RESET}")
            return
        
        plan_id = args[0]
        
        print(f"{UITheme.INFO}Executing task plan {plan_id}...{UITheme.RESET}")
        
        result = await self.client.execute_task_plan(plan_id)
        
        if result.success:
            execution_info = result.result
            print(f"{UITheme.SUCCESS}✓ Task plan execution completed!{UITheme.RESET}")
            print(f"  Plan ID: {execution_info.get('plan_id')}")
            print(f"  Tasks Completed: {execution_info.get('tasks_completed')}")
            print(f"  Tasks Failed: {execution_info.get('tasks_failed')}")
            print(f"  Duration: {execution_info.get('total_duration', 0):.2f}s")
            
            if execution_info.get('summary'):
                print(f"\n{UITheme.BOLD}Summary:{UITheme.RESET}")
                print(f"  {execution_info['summary']}")
        else:
            print(f"{UITheme.ERROR}✗ Failed to execute task plan: {result.error}{UITheme.RESET}")
    
    async def _show_history(self, args: List[str]):
        """Show execution history."""
        if not args:
            print(f"{UITheme.ERROR}Usage: history <workspace_id>{UITheme.RESET}")
            return
        
        workspace_id = args[0]
        
        print(f"{UITheme.INFO}Getting execution history for workspace {workspace_id}...{UITheme.RESET}")
        
        result = await self.client.get_execution_history(workspace_id)
        
        if result.success:
            history = result.result
            print(f"{UITheme.SUCCESS}✓ Execution history retrieved!{UITheme.RESET}")
            print(f"  Total Actions: {history.get('total_actions', 0)}")
            print(f"  Files Modified: {history.get('files_modified', 0)}")
            print(f"  Commands Executed: {history.get('commands_executed', 0)}")
            print(f"  Errors Encountered: {history.get('errors_encountered', 0)}")
            
            actions = history.get('actions', [])
            if actions:
                print(f"\n{UITheme.BOLD}Recent Actions:{UITheme.RESET}")
                for action in actions[-10:]:  # Show last 10 actions
                    timestamp = action.get('timestamp', '')
                    action_type = action.get('type', '')
                    description = action.get('description', '')
                    print(f"  {UITheme.DIM}[{timestamp}]{UITheme.RESET} {UITheme.CYAN}{action_type}{UITheme.RESET}: {description}")
        else:
            print(f"{UITheme.ERROR}✗ Failed to get execution history: {result.error}{UITheme.RESET}")
    
    async def _cleanup_workspace(self, args: List[str]):
        """Clean up a workspace."""
        if not args:
            print(f"{UITheme.ERROR}Usage: cleanup <workspace_id>{UITheme.RESET}")
            return
        
        workspace_id = args[0]
        
        # Confirm cleanup
        confirm = input(f"{UITheme.WARNING}Are you sure you want to cleanup workspace {workspace_id}? (y/N): {UITheme.RESET}")
        if confirm.lower() not in ['y', 'yes']:
            print("Cleanup cancelled.")
            return
        
        print(f"{UITheme.INFO}Cleaning up workspace {workspace_id}...{UITheme.RESET}")
        
        result = await self.client.cleanup_workspace(workspace_id)
        
        if result.success:
            print(f"{UITheme.SUCCESS}✓ Workspace cleaned up successfully!{UITheme.RESET}")
        else:
            print(f"{UITheme.ERROR}✗ Failed to cleanup workspace: {result.error}{UITheme.RESET}")
    
    def _show_operations(self):
        """Show active operations."""
        active_ops = self.client.get_active_operations()
        history = self.client.get_operation_history()
        
        print(f"{UITheme.BOLD}Active Operations ({len(active_ops)}):{UITheme.RESET}")
        if active_ops:
            for op in active_ops:
                status_color = self._get_status_color(op.get('status', 'unknown'))
                print(f"  {status_color}[{op.get('status', 'UNKNOWN').upper()}]{UITheme.RESET} {op.get('description', 'No description')}")
        else:
            print("  No active operations")
        
        print(f"\n{UITheme.BOLD}Recent Operations ({len(history[-5:])}):{UITheme.RESET}")
        if history:
            for result in history[-5:]:  # Show last 5
                status_color = UITheme.SUCCESS if result.success else UITheme.ERROR
                status_text = "SUCCESS" if result.success else "FAILED"
                print(f"  {status_color}[{status_text}]{UITheme.RESET} {result.operation_id} ({result.duration:.2f}s)")
        else:
            print("  No operation history")
    
    def _get_status_color(self, status: str) -> str:
        """Get color for status string."""
        status_lower = status.lower()
        if status_lower in ['completed', 'success']:
            return UITheme.SUCCESS
        elif status_lower in ['failed', 'error']:
            return UITheme.ERROR
        elif status_lower in ['running', 'pending']:
            return UITheme.CYAN
        else:
            return UITheme.RESET
    
    def _on_progress_update(self, update: ProgressUpdate):
        """Handle progress updates."""
        self.status_display.update_operation(update)
        
        if update.status in [OperationStatus.COMPLETED, OperationStatus.FAILED, OperationStatus.CANCELLED]:
            # Remove from display after a short delay
            asyncio.create_task(self._delayed_remove_operation(update.operation_id))
    
    async def _delayed_remove_operation(self, operation_id: str):
        """Remove operation from display after delay."""
        await asyncio.sleep(2.0)  # Show completion status for 2 seconds
        self.status_display.remove_operation(operation_id)
    
    def _on_error(self, error: str, details: Dict[str, Any]):
        """Handle errors."""
        print(f"\n{UITheme.ERROR}Error: {error}{UITheme.RESET}")
        if details:
            print(f"{UITheme.DIM}Details: {json.dumps(details, indent=2)}{UITheme.RESET}")


async def run_interactive_cli(api_key: Optional[str] = None, server_command: Optional[List[str]] = None):
    """
    Run the interactive CLI for the sandbox client.
    
    Args:
        api_key: API key for authentication
        server_command: Command to start the MCP server
    """
    try:
        # Create and connect client
        print(f"{UITheme.INFO}Connecting to sandbox server...{UITheme.RESET}")
        
        client = SandboxMCPClient(server_command, api_key)
        
        if not await client.connect():
            print(f"{UITheme.ERROR}Failed to connect to sandbox server{UITheme.RESET}")
            return
        
        # Start interactive CLI
        cli = InteractiveCLI(client)
        await cli.start()
        
    except KeyboardInterrupt:
        print(f"\n{UITheme.WARNING}Interrupted by user{UITheme.RESET}")
    except Exception as e:
        print(f"{UITheme.ERROR}Error: {e}{UITheme.RESET}")
    finally:
        # Cleanup
        if 'client' in locals():
            await client.disconnect()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Intelligent Sandbox MCP Client")
    parser.add_argument("--api-key", help="API key for authentication")
    parser.add_argument("--server-command", nargs="+", help="Command to start MCP server")
    
    args = parser.parse_args()
    
    asyncio.run(run_interactive_cli(args.api_key, args.server_command))