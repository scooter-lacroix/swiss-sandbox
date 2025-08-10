"""
Configuration management for the intelligent sandbox system.
"""

import os
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional
from pathlib import Path


@dataclass
class IsolationConfig:
    """Configuration for sandbox isolation settings."""
    use_docker: bool = True
    container_image: str = "ubuntu:22.04"
    resource_limits: 'ResourceLimits' = field(default_factory=lambda: ResourceLimits())
    network_isolation: bool = True
    allowed_hosts: list = field(default_factory=list)


@dataclass
class ResourceLimits:
    """Resource limit configuration."""
    memory_mb: int = 2048
    cpu_cores: int = 2
    disk_mb: int = 5120


@dataclass
class SandboxConfig:
    """Configuration settings for the sandbox system."""
    
    # Isolation settings
    isolation: IsolationConfig = field(default_factory=IsolationConfig)
    
    # Workspace settings
    default_isolation_enabled: bool = True
    default_container_image: str = "ubuntu:22.04"
    default_cpu_limit: str = "2.0"
    default_memory_limit: str = "4G"
    default_disk_limit: str = "10G"
    workspace_cleanup_timeout: int = 300  # seconds
    
    # Execution settings
    default_command_timeout: int = 300  # seconds
    max_task_retries: int = 3
    enable_parallel_execution: bool = False
    
    # Logging settings
    log_level: str = "INFO"
    log_retention_days: int = 30
    max_log_file_size: str = "100MB"
    enable_detailed_logging: bool = True
    
    # Analysis settings
    enable_codebase_caching: bool = True
    cache_expiry_hours: int = 24
    max_analysis_depth: int = 10
    
    # Security settings
    allowed_network_hosts: list = field(default_factory=list)
    blocked_commands: list = field(default_factory=list)
    enable_command_validation: bool = True
    
    # Performance settings
    max_concurrent_sandboxes: int = 5
    resource_monitoring_interval: int = 30  # seconds
    
    # Custom settings
    custom_settings: Dict[str, Any] = field(default_factory=dict)


class ConfigManager:
    """Manages configuration for the intelligent sandbox system."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._get_default_config_path()
        self._config: Optional[SandboxConfig] = None
        self._load_config()
    
    def _get_default_config_path(self) -> str:
        """Get the default configuration file path."""
        # Try to use XDG config directory, fallback to home directory
        config_dir = os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))
        config_dir = os.path.join(config_dir, 'sandbox')
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, 'config.json')
    
    def _load_config(self) -> None:
        """Load configuration from file or create default."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config_data = json.load(f)
                
                # Handle nested isolation config
                if 'isolation' in config_data:
                    isolation_data = config_data['isolation']
                    if 'resource_limits' in isolation_data:
                        isolation_data['resource_limits'] = ResourceLimits(**isolation_data['resource_limits'])
                    config_data['isolation'] = IsolationConfig(**isolation_data)
                
                self._config = SandboxConfig(**config_data)
            except (json.JSONDecodeError, TypeError) as e:
                print(f"Warning: Failed to load config from {self.config_path}: {e}")
                print("Using default configuration.")
                self._config = SandboxConfig()
        else:
            self._config = SandboxConfig()
            self.save_config()
    
    def save_config(self) -> None:
        """Save current configuration to file."""
        if self._config is None:
            return
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        
        try:
            # Convert to dict with proper nested structure
            config_dict = asdict(self._config)
            with open(self.config_path, 'w') as f:
                json.dump(config_dict, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save config to {self.config_path}: {e}")
    
    @property
    def config(self) -> SandboxConfig:
        """Get the current configuration."""
        if self._config is None:
            self._config = SandboxConfig()
        return self._config
    
    def update_config(self, **kwargs) -> None:
        """Update configuration settings."""
        if self._config is None:
            self._config = SandboxConfig()
        
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
            else:
                self._config.custom_settings[key] = value
        
        self.save_config()
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a specific configuration setting."""
        if hasattr(self.config, key):
            return getattr(self.config, key)
        return self.config.custom_settings.get(key, default)
    
    def set_setting(self, key: str, value: Any) -> None:
        """Set a specific configuration setting."""
        if hasattr(self.config, key):
            setattr(self._config, key, value)
        else:
            self._config.custom_settings[key] = value
        self.save_config()
    
    def reset_to_defaults(self) -> None:
        """Reset configuration to default values."""
        self._config = SandboxConfig()
        self.save_config()
    
    def export_config(self, export_path: str) -> None:
        """Export configuration to a file."""
        with open(export_path, 'w') as f:
            json.dump(asdict(self.config), f, indent=2)
    
    def import_config(self, import_path: str) -> None:
        """Import configuration from a file."""
        with open(import_path, 'r') as f:
            config_data = json.load(f)
        self._config = SandboxConfig(**config_data)
        self.save_config()


# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get the global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_config() -> SandboxConfig:
    """Get the current sandbox configuration."""
    return get_config_manager().config