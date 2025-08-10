"""
Data models for workspace management.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional
from ..types import WorkspaceStatus


@dataclass
class IsolationConfig:
    """Configuration for workspace isolation."""
    use_docker: bool = True
    container_image: str = "ubuntu:22.04"
    cpu_limit: Optional[str] = "2.0"  # CPU cores
    memory_limit: Optional[str] = "4G"  # Memory limit
    disk_limit: Optional[str] = "10G"  # Disk space limit
    network_isolation: bool = True
    allowed_hosts: list = field(default_factory=list)
    environment_vars: Dict[str, str] = field(default_factory=dict)
    mount_points: Dict[str, str] = field(default_factory=dict)


@dataclass
class SandboxWorkspace:
    """Represents an isolated sandbox workspace."""
    id: str
    source_path: str
    sandbox_path: str
    isolation_config: IsolationConfig
    created_at: datetime
    status: WorkspaceStatus
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now()