"""
Metrics interface for the enhanced Sandbox SDK.
"""

import uuid
from typing import Dict, Optional


class Metrics:
    """
    Metrics class for retrieving resource metrics for a sandbox.
    
    Supports both local and remote metric retrieval.
    """

    def __init__(self, sandbox_instance):
        """
        Initialize the metrics instance.

        Args:
            sandbox_instance: The sandbox instance this metrics object belongs to
        """
        self._sandbox = sandbox_instance

    async def all(self) -> Dict[str, Optional[str]]:
        """
        Get all metrics for the current sandbox.

        Returns:
            A dictionary containing all metrics for the sandbox
        """
        if self._sandbox.remote:
            return await self._get_remote_metrics()
        else:
            return await self._get_local_metrics()

    async def _get_remote_metrics(self) -> dict:
        """
        Internal method to fetch current metrics from the remote server.
        """
        if not self._sandbox._is_started:
            raise RuntimeError("Sandbox is not started. Call start() first.")

        headers = {"Content-Type": "application/json"}
        if self._sandbox._api_key:
            headers["Authorization"] = f"Bearer {self._sandbox._api_key}"

        request_data = {
            "jsonrpc": "2.0",
            "method": "sandbox.metrics.get",
            "params": {
                "namespace": self._sandbox._namespace,
                "sandbox": self._sandbox._name,
            },
            "id": str(uuid.uuid4()),
        }

        try:
            async with self._sandbox._session.post(
                f"{self._sandbox._server_url}/api/v1/rpc",
                json=request_data,
                headers=headers,
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"Failed to get sandbox metrics: {error_text}")

                response_data = await response.json()
                if "error" in response_data:
                    raise RuntimeError(
                        f"Failed to get sandbox metrics: {response_data['error']['message']}"
                    )

                result = response_data.get("result", {})
                sandboxes = result.get("sandboxes", [])

                # We expect exactly one sandbox in the response (our own)
                if not sandboxes:
                    return {}

                # Return the first (and should be only) sandbox data
                return sandboxes[0]
        except Exception as e:
            raise RuntimeError(f"Failed to get sandbox metrics: {e}")

    async def _get_local_metrics(self) -> dict:
        # Placeholder for local metric retrieval logic
        return {}

