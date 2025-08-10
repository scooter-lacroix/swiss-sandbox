"""
Command execution results for the enhanced Sandbox SDK.
"""

from typing import Any, Dict, List, Optional


class CommandExecution:
    """
    Represents a command execution in a sandbox environment.

    This class provides access to the results and output of shell commands
    that were executed in a sandbox, supporting both local and remote execution.
    """

    def __init__(
        self,
        output_data: Optional[Dict[str, Any]] = None,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None,
        exit_code: Optional[int] = None,
        command: Optional[str] = None,
        timeout: Optional[bool] = None,
    ):
        """
        Initialize a command execution instance.

        Args:
            output_data: Output data from the sandbox.command.run response (remote)
            stdout: Standard output from command execution (local)
            stderr: Standard error from command execution (local)
            exit_code: Exit code from command execution
            command: The command that was executed
            timeout: Whether the command timed out
        """
        self._stdout = stdout or ""
        self._stderr = stderr or ""
        self._exit_code = exit_code or 0
        self._command = command or ""
        self._timeout = timeout or False

        # Process output data if provided (remote execution)
        if output_data and isinstance(output_data, dict):
            self._process_output_data(output_data)

    def _process_output_data(self, output_data: Dict[str, Any]) -> None:
        """
        Process output data from the sandbox.command.run response.

        Args:
            output_data: Dictionary containing the output data
        """
        self._stdout = output_data.get("stdout", "")
        self._stderr = output_data.get("stderr", "")
        self._exit_code = output_data.get("exit_code", 0)
        self._command = output_data.get("command", "")
        self._timeout = output_data.get("timeout", False)

    async def output(self) -> str:
        """
        Get the standard output from the command execution.

        Returns:
            String containing the stdout output of the command
        """
        return self._stdout

    async def error(self) -> str:
        """
        Get the error output from the command execution.

        Returns:
            String containing the stderr output of the command
        """
        return self._stderr

    def has_error(self) -> bool:
        """
        Check if the command execution contains an error.

        Returns:
            Boolean indicating whether the command encountered an error
        """
        return self._exit_code != 0 or bool(self._stderr) or self._timeout

    @property
    def exit_code(self) -> int:
        """
        Get the exit code of the command execution.

        Returns:
            Integer representing the exit code (0 for success)
        """
        return self._exit_code

    @property
    def command(self) -> str:
        """
        Get the command that was executed.

        Returns:
            String containing the executed command
        """
        return self._command

    @property
    def timeout(self) -> bool:
        """
        Check if the command execution timed out.

        Returns:
            Boolean indicating whether the command timed out
        """
        return self._timeout

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the command execution result to a dictionary.

        Returns:
            Dictionary representation of the command execution result
        """
        return {
            "stdout": self._stdout,
            "stderr": self._stderr,
            "exit_code": self._exit_code,
            "command": self._command,
            "timeout": self._timeout,
            "has_error": self.has_error(),
        }
