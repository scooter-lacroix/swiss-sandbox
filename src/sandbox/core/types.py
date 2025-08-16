"""
Core data types for the Swiss Sandbox execution system.

This module contains shared data types to avoid circular imports.
"""

import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class SecurityLevel(Enum):
    """Security levels for execution environment."""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    STRICT = "strict"


@dataclass
class ResourceLimits:
    """Resource limits for execution."""
    max_execution_time: int = 30
    max_memory_mb: int = 512
    max_processes: int = 10
    max_file_size_mb: int = 100


@dataclass
class ExecutionContext:
    """Context for code execution with all necessary environment information."""
    workspace_id: str
    user_id: Optional[str] = None
    environment_vars: Dict[str, str] = field(default_factory=dict)
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)
    security_level: SecurityLevel = SecurityLevel.MODERATE
    artifacts_dir: Optional[Path] = None
    execution_globals: Dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None
    
    def __post_init__(self):
        """Initialize context after creation."""
        if self.artifacts_dir is None:
            import tempfile
            import uuid
            temp_dir = Path(tempfile.gettempdir())
            self.artifacts_dir = temp_dir / f"sandbox_artifacts_{uuid.uuid4().hex[:8]}"
            self.artifacts_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class ExecutionResult:
    """Result of code execution with comprehensive information."""
    success: bool
    output: str = ""
    error: Optional[str] = None
    error_type: Optional[str] = None
    execution_time: float = 0.0
    artifacts: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for JSON serialization."""
        return {
            'success': self.success,
            'output': self.output,
            'error': self.error,
            'error_type': self.error_type,
            'execution_time': self.execution_time,
            'artifacts': self.artifacts,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class ServerConfig:
    """Configuration for the unified server."""
    max_execution_time: int = 30
    max_memory_mb: int = 512
    security_level: SecurityLevel = SecurityLevel.MODERATE
    artifacts_retention_days: int = 7
    enable_manim: bool = True
    enable_web_apps: bool = True
    enable_intelligent_features: bool = True
    log_level: str = "INFO"
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'ServerConfig':
        """Create config from dictionary."""
        # Convert security level string to enum if needed
        if 'security_level' in config_dict and isinstance(config_dict['security_level'], str):
            config_dict['security_level'] = SecurityLevel(config_dict['security_level'])
        
        return cls(**{k: v for k, v in config_dict.items() if hasattr(cls, k)})
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, Enum):
                result[key] = value.value
            else:
                result[key] = value
        return result


@dataclass
class ExecutionRecord:
    """Record of a single execution for history tracking."""
    execution_id: str
    code: str
    language: str
    context_id: str
    result: ExecutionResult
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'execution_id': self.execution_id,
            'code': self.code,
            'language': self.language,
            'context_id': self.context_id,
            'result': self.result.to_dict(),
            'timestamp': self.timestamp
        }