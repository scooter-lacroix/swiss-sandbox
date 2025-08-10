"""
Classes representing code execution results in a sandbox environment.
"""

from typing import Any, Dict, List, Optional


class Execution:
    """
    Represents a code execution in a sandbox environment.

    This class provides access to the results and output of code
    that was executed in a sandbox, supporting both local and remote execution.
    """

    def __init__(
        self,
        output_data: Optional[Dict[str, Any]] = None,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None,
        return_value: Optional[Any] = None,
        exception: Optional[Exception] = None,
        artifacts: Optional[List[str]] = None,
    ):
        """
        Initialize an execution instance.

        Args:
            output_data: Output data from the sandbox.repl.run response (remote)
            stdout: Standard output from execution (local)
            stderr: Standard error from execution (local)
            return_value: Return value from execution (local)
            exception: Exception that occurred during execution (local)
            artifacts: List of artifact files created during execution
        """
        self._output_lines: List[Dict[str, str]] = []
        self._status = "unknown"
        self._language = "unknown"
        self._has_error = False
        self._stdout = stdout or ""
        self._stderr = stderr or ""
        self._return_value = return_value
        self._exception = exception
        self._artifacts = artifacts or []

        # Process output data if provided (remote execution)
        if output_data and isinstance(output_data, dict):
            self._process_output_data(output_data)
        
        # Process direct values (local execution)
        if stderr:
            self._has_error = True
        if exception:
            self._has_error = True
            self._status = "error"

    def _process_output_data(self, output_data: Dict[str, Any]) -> None:
        """
        Process output data from the sandbox.repl.run response.

        Args:
            output_data: Dictionary containing the output data
        """
        # Extract output lines from the response
        self._output_lines = output_data.get("output", [])

        # Store additional metadata that might be useful
        self._status = output_data.get("status", "unknown")
        self._language = output_data.get("language", "unknown")

        # Check for errors in the output or status
        if self._status == "error" or self._status == "exception":
            self._has_error = True
        else:
            # Check if there's any stderr output
            for line in self._output_lines:
                if (
                    isinstance(line, dict)
                    and line.get("stream") == "stderr"
                    and line.get("text")
                ):
                    self._has_error = True
                    break

    async def output(self) -> str:
        """
        Get the standard output from the execution.

        Returns:
            String containing the stdout output of the execution
        """
        if self._output_lines:
            # Remote execution - combine stdout output lines
            output_text = ""
            for line in self._output_lines:
                if isinstance(line, dict) and line.get("stream") == "stdout":
                    output_text += line.get("text", "") + "\n"
            return output_text.rstrip()
        else:
            # Local execution - return stored stdout
            return self._stdout

    async def error(self) -> str:
        """
        Get the error output from the execution.

        Returns:
            String containing the stderr output of the execution
        """
        if self._output_lines:
            # Remote execution - combine stderr output lines
            error_text = ""
            for line in self._output_lines:
                if isinstance(line, dict) and line.get("stream") == "stderr":
                    error_text += line.get("text", "") + "\n"
            return error_text.rstrip()
        else:
            # Local execution - return stored stderr
            return self._stderr

    def has_error(self) -> bool:
        """
        Check if the execution contains an error.

        Returns:
            Boolean indicating whether the execution encountered an error
        """
        return self._has_error

    @property
    def status(self) -> str:
        """
        Get the status of the execution.

        Returns:
            String containing the execution status (e.g., "success", "error")
        """
        return self._status

    @property
    def language(self) -> str:
        """
        Get the language used for the execution.

        Returns:
            String containing the execution language (e.g., "python")
        """
        return self._language

    @property
    def return_value(self) -> Any:
        """
        Get the return value from the execution (local execution only).

        Returns:
            The return value from the executed code
        """
        return self._return_value

    @property
    def exception(self) -> Optional[Exception]:
        """
        Get the exception that occurred during execution (local execution only).

        Returns:
            The exception that occurred, or None if no exception
        """
        return self._exception

    @property
    def artifacts(self) -> List[str]:
        """
        Get the list of artifacts created during execution.

        Returns:
            List of artifact file paths
        """
        return self._artifacts

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the execution result to a dictionary.

        Returns:
            Dictionary representation of the execution result
        """
        return {
            "status": self._status,
            "language": self._language,
            "has_error": self._has_error,
            "stdout": self._stdout,
            "stderr": self._stderr,
            "return_value": self._return_value,
            "exception": str(self._exception) if self._exception else None,
            "artifacts": self._artifacts,
        }
