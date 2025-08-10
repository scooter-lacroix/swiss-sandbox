"""
Command execution interface for the enhanced Sandbox SDK.
"""

import subprocess
import uuid
from typing import List, Optional

import aiohttp

from .command_execution import CommandExecution


class Command:
    """
    Command class for executing shell commands in a sandbox.
    
    Supports both local and remote command execution.
    """

    def __init__(self, sandbox_instance):
        """
        Initialize the command instance.

        Args:
            sandbox_instance: The sandbox instance this command belongs to
        """
        self._sandbox = sandbox_instance

    async def run(
        self,
        command: str,
        args: Optional[List[str]] = None,
        timeout: Optional[int] = None,
        working_directory: Optional[str] = None,
    ) -> CommandExecution:
        """
        Execute a shell command in the sandbox.

        Args:
            command: The command to execute
            args: Optional list of command arguments
            timeout: Optional timeout in seconds
            working_directory: Optional working directory for command execution

        Returns:
            A CommandExecution object containing the results

        Raises:
            RuntimeError: If the sandbox is not started or execution fails
        """
        if not self._sandbox._is_started:
            raise RuntimeError("Sandbox is not started. Call start() first.")

        if args is None:
            args = []

        if self._sandbox.remote:
            # Remote execution via microsandbox server
            return await self._run_remote(command, args, timeout, working_directory)
        else:
            # Local execution
            return await self._run_local(command, args, timeout, working_directory)

    async def _run_remote(
        self,
        command: str,
        args: List[str],
        timeout: Optional[int],
        working_directory: Optional[str],
    ) -> CommandExecution:
        """
        Execute a command remotely via the microsandbox server.
        """
        headers = {"Content-Type": "application/json"}
        if self._sandbox._api_key:
            headers["Authorization"] = f"Bearer {self._sandbox._api_key}"

        request_data = {
            "jsonrpc": "2.0",
            "method": "sandbox.command.run",
            "params": {
                "sandbox": self._sandbox._name,
                "namespace": self._sandbox._namespace,
                "command": command,
                "args": args,
            },
            "id": str(uuid.uuid4()),
        }

        if timeout is not None:
            request_data["params"]["timeout"] = timeout
        if working_directory is not None:
            request_data["params"]["working_directory"] = working_directory

        try:
            async with self._sandbox._session.post(
                f"{self._sandbox._server_url}/api/v1/rpc",
                json=request_data,
                headers=headers,
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"Failed to execute command: {error_text}")

                response_data = await response.json()
                if "error" in response_data:
                    raise RuntimeError(
                        f"Failed to execute command: {response_data['error']['message']}"
                    )

                result = response_data.get("result", {})
                return CommandExecution(output_data=result)
        except aiohttp.ClientError as e:
            raise RuntimeError(f"Failed to execute command: {e}")

    async def _run_local(
        self,
        command: str,
        args: List[str],
        timeout: Optional[int],
        working_directory: Optional[str],
    ) -> CommandExecution:
        """
        Execute a command locally.
        """
        # Security check for dangerous commands
        dangerous_patterns = [
            "rm -rf",
            "sudo",
            "chmod 777",
            ">/dev/null",
            "format",
            "del /f",
            "rmdir /s",
        ]
        
        full_command = f"{command} {' '.join(args)}"
        for pattern in dangerous_patterns:
            if pattern in full_command.lower():
                return CommandExecution(
                    stdout="",
                    stderr=f"Command blocked for security: contains '{pattern}'",
                    exit_code=1,
                    command=full_command,
                    timeout=False,
                )

        try:
            # Use subprocess to execute the command
            result = subprocess.run(
                [command] + args,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=working_directory,
            )
            
            return CommandExecution(
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                command=full_command,
                timeout=False,
            )
        except subprocess.TimeoutExpired:
            return CommandExecution(
                stdout="",
                stderr=f"Command timed out after {timeout} seconds",
                exit_code=124,  # Standard timeout exit code
                command=full_command,
                timeout=True,
            )
        except Exception as e:
            return CommandExecution(
                stdout="",
                stderr=f"Command execution failed: {str(e)}",
                exit_code=1,
                command=full_command,
                timeout=False,
            )
