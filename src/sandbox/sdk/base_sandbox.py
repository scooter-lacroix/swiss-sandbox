"""
Base sandbox implementation for the enhanced Sandbox SDK.
"""

import asyncio
import os
import uuid
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Optional

import aiohttp
from dotenv import load_dotenv

from .command import Command
from .metrics import Metrics


class BaseSandbox(ABC):
    """
    Base sandbox environment for executing code safely.

    This class provides the base interface for interacting with 
    both local and remote sandboxes with microVM isolation.
    """

    def __init__(
        self,
        remote: bool = False,
        server_url: Optional[str] = None,
        namespace: str = "default",
        name: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize a base sandbox instance.

        Args:
            remote: Whether this is a remote microsandbox
            server_url: URL of the Microsandbox server for remote sandboxes
            namespace: Namespace for the sandbox
            name: Optional name for the sandbox (random if not provided)
            api_key: API key for authentication for remote sandboxes
        """
        # Load environment variables if needed
        if "MSB_API_KEY" not in os.environ:
            try:
                load_dotenv()
            except Exception:
                pass

        self.remote = remote
        self._server_url = server_url or os.environ.get(
            "MSB_SERVER_URL", "http://127.0.0.1:5555"
        )
        self._namespace = namespace
        self._name = name or f"sandbox-{uuid.uuid4().hex[:8]}"
        self._api_key = api_key or os.environ.get("MSB_API_KEY")
        self._session = aiohttp.ClientSession() if remote else None
        self._is_started = False

    @abstractmethod
    async def get_default_image(self) -> str:
        """
        Get the default Docker image for this sandbox type.

        Returns:
            A string containing the Docker image name and tag
        """
        pass

    @classmethod
    @asynccontextmanager
    async def create(
        cls,
        remote: bool = False,
        server_url: Optional[str] = None,
        namespace: str = "default",
        name: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        Create and initialize a new sandbox within an async context manager.

        Args:
            remote: Whether this is a remote microsandbox
            server_url: URL of the Microsandbox server for remote sandboxes
            namespace: Namespace for the sandbox
            name: Optional name for the sandbox
            api_key: API key for authentication for remote sandboxes

        Returns:
            An instance of the sandbox ready for use
        """
        sandbox = cls(
            remote=remote,
            server_url=server_url,
            namespace=namespace,
            name=name,
            api_key=api_key,
        )
        try:
            await sandbox.start()
            yield sandbox
        finally:
            await sandbox.stop()
            if sandbox._session:
                await sandbox._session.close()
                sandbox._session = None

    async def start(
        self,
        image: Optional[str] = None,
        memory: int = 512,
        cpus: float = 1.0,
        timeout: float = 180.0,
    ) -> None:
        """
        Start the sandbox container.

        Args:
            image: Docker image to use for the sandbox (defaults to language-specific image)
            memory: Memory limit in MB
            cpus: CPU limit
            timeout: Maximum time in seconds to wait for the sandbox to start

        Raises:
            RuntimeError: If the sandbox fails to start
            TimeoutError: If the sandbox doesn't start within the specified time
        """
        if self._is_started:
            return

        sandbox_image = image or await self.get_default_image()

        if self.remote:
            # Handle starting the sandbox remotely using server commands
            request_data = {
                "jsonrpc": "2.0",
                "method": "sandbox.start",
                "params": {
                    "namespace": self._namespace,
                    "sandbox": self._name,
                    "config": {
                        "image": sandbox_image,
                        "memory": memory,
                        "cpus": int(round(cpus)),
                    },
                },
                "id": str(uuid.uuid4()),
            }
            headers = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"

            try:
                client_timeout = aiohttp.ClientTimeout(total=timeout + 30)
                async with self._session.post(
                    f"{self._server_url}/api/v1/rpc",
                    json=request_data,
                    headers=headers,
                    timeout=client_timeout,
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise RuntimeError(f"Failed to start sandbox: {error_text}")
                    
                    response_data = await response.json()
                    if "error" in response_data:
                        raise RuntimeError(
                            f"Failed to start sandbox: {response_data['error']['message']}"
                        )
                    self._is_started = True
            except aiohttp.ClientError as e:
                if isinstance(e, asyncio.TimeoutError):
                    raise TimeoutError(
                        f"Timed out waiting for sandbox to start after {timeout} seconds"
                    ) from e
                raise RuntimeError(f"Failed to communicate with Microsandbox server: {e}")
        else:
            # Local sandbox initialization should be handled here
            pass  # Implement local sandbox starting logic

    async def stop(self) -> None:
        """
        Stop the sandbox container.

        Raises:
            RuntimeError: If the sandbox fails to stop
        """
        if not self._is_started:
            return

        if self.remote:
            request_data = {
                "jsonrpc": "2.0",
                "method": "sandbox.stop",
                "params": {"namespace": self._namespace, "sandbox": self._name},
                "id": str(uuid.uuid4()),
            }
            headers = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"

            try:
                async with self._session.post(
                    f"{self._server_url}/api/v1/rpc",
                    json=request_data,
                    headers=headers,
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise RuntimeError(f"Failed to stop sandbox: {error_text}")
                    
                    response_data = await response.json()
                    if "error" in response_data:
                        raise RuntimeError(
                            f"Failed to stop sandbox: {response_data['error']['message']}"
                        )
                    self._is_started = False
            except aiohttp.ClientError as e:
                raise RuntimeError(f"Failed to communicate with Microsandbox server: {e}")
        else:
            # Local sandbox stopping logic should be handled here
            pass  # Implement local sandbox stopping logic

    @abstractmethod
    async def run(self, code: str):
        """
        Execute code in the sandbox.

        Args:
            code: Code to execute

        Returns:
            An object representing the executed code

        Raises:
            RuntimeError: If execution fails
        """
        pass

    @property
    def command(self):
        """
        Access the command namespace for executing shell commands in the sandbox.

        Returns:
            A Command instance
        """
        return Command(self)

    @property
    def metrics(self):
        """
        Access the metrics namespace for retrieving sandbox metrics.

        Returns:
            A Metrics instance
        """
        return Metrics(self)

