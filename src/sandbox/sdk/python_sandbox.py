"""
Python-specific sandbox implementation for the enhanced Sandbox SDK.
"""

from typing import Optional

from .local_sandbox import LocalSandbox
from .remote_sandbox import RemoteSandbox


class PythonSandbox:
    """
    Python-specific sandbox for executing Python code.
    
    This is a factory class that creates either a local or remote sandbox
    depending on the configuration.
    """

    @classmethod
    async def create(
        cls,
        remote: bool = False,
        server_url: Optional[str] = None,
        namespace: str = "default",
        name: Optional[str] = None,
        api_key: Optional[str] = None,
        **kwargs
    ):
        """
        Create a Python sandbox instance.

        Args:
            remote: Whether to use remote execution
            server_url: URL of the Microsandbox server (for remote)
            namespace: Namespace for the sandbox
            name: Optional name for the sandbox
            api_key: API key for authentication (for remote)
            **kwargs: Additional arguments passed to the sandbox

        Returns:
            A context manager that yields the appropriate sandbox instance
        """
        if remote:
            return RemoteSandbox.create(
                remote=True,
                server_url=server_url,
                namespace=namespace,
                name=name,
                api_key=api_key,
                **kwargs
            )
        else:
            return LocalSandbox.create(
                remote=False,
                server_url=server_url,
                namespace=namespace,
                name=name,
                api_key=api_key,
                **kwargs
            )

    @classmethod
    async def create_local(
        cls,
        namespace: str = "default",
        name: Optional[str] = None,
        **kwargs
    ):
        """
        Create a local Python sandbox instance.

        Args:
            namespace: Namespace for the sandbox
            name: Optional name for the sandbox
            **kwargs: Additional arguments passed to the sandbox

        Returns:
            A context manager that yields a LocalSandbox instance
        """
        return LocalSandbox.create(
            remote=False,
            namespace=namespace,
            name=name,
            **kwargs
        )

    @classmethod
    async def create_remote(
        cls,
        server_url: Optional[str] = None,
        namespace: str = "default",
        name: Optional[str] = None,
        api_key: Optional[str] = None,
        **kwargs
    ):
        """
        Create a remote Python sandbox instance.

        Args:
            server_url: URL of the Microsandbox server
            namespace: Namespace for the sandbox
            name: Optional name for the sandbox
            api_key: API key for authentication
            **kwargs: Additional arguments passed to the sandbox

        Returns:
            A context manager that yields a RemoteSandbox instance
        """
        return RemoteSandbox.create(
            remote=True,
            server_url=server_url,
            namespace=namespace,
            name=name,
            api_key=api_key,
            **kwargs
        )
