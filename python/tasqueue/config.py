"""
Configuration management for Tasqueue using YAML files
"""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path


class Config:
    """
    Configuration manager for Tasqueue.
    Loads and manages configuration from YAML files.
    """

    _instance = None
    _config: Dict[str, Any] = {}
    _env: str = "production"

    def __new__(cls):
        """Singleton pattern to ensure only one config instance"""
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
        return cls._instance

    @classmethod
    def load(cls, config_path: Optional[str] = None, env: Optional[str] = None) -> 'Config':
        """
        Load configuration from YAML file.

        Args:
            config_path: Path to config.yaml file. If None, searches in common locations.
            env: Environment (production, development, testing). Defaults to TASQUEUE_ENV or "production"

        Returns:
            Config instance
        """
        instance = cls()

        # Determine environment
        if env:
            instance._env = env
        else:
            instance._env = os.getenv('TASQUEUE_ENV', 'production')

        # Find config file
        if config_path is None:
            config_path = instance._find_config_file()

        if not config_path or not os.path.exists(config_path):
            raise FileNotFoundError(
                f"Config file not found. Searched: {config_path}\n"
                "Please create a config.yaml file or specify path with Config.load(config_path='path/to/config.yaml')"
            )

        # Load YAML
        with open(config_path, 'r') as f:
            instance._config = yaml.safe_load(f)

        # Apply environment-specific overrides
        if instance._env in instance._config:
            instance._apply_overrides(instance._config, instance._config[instance._env])

        return instance

    @classmethod
    def _find_config_file(cls) -> Optional[str]:
        """Search for config.yaml in common locations"""
        search_paths = [
            'config.yaml',
            'config/config.yaml',
            '../config.yaml',
            os.path.expanduser('~/.tasqueue/config.yaml'),
            '/etc/tasqueue/config.yaml',
        ]

        for path in search_paths:
            if os.path.exists(path):
                return path

        return None

    @classmethod
    def _apply_overrides(cls, base: Dict, overrides: Dict) -> None:
        """Apply environment-specific overrides to base config"""
        for key, value in overrides.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                cls._apply_overrides(base[key], value)
            else:
                base[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-notation key.

        Args:
            key: Configuration key in dot notation (e.g., "broker.redis.host")
            default: Default value if key not found

        Returns:
            Configuration value

        Examples:
            >>> config = Config.load()
            >>> host = config.get('broker.redis.host')
            >>> port = config.get('broker.redis.port', 6379)
        """
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_broker_config(self) -> Dict[str, Any]:
        """Get broker configuration"""
        return self._config.get('broker', {})

    def get_results_config(self) -> Dict[str, Any]:
        """Get results backend configuration"""
        return self._config.get('results', {})

    def get_server_config(self) -> Dict[str, Any]:
        """Get server configuration"""
        return self._config.get('server', {})

    def get_queue_config(self, queue_name: str = 'default') -> Dict[str, Any]:
        """Get queue-specific configuration"""
        queues = self._config.get('queues', {})
        return queues.get(queue_name, queues.get('default', {}))

    def get_job_defaults(self) -> Dict[str, Any]:
        """Get default job configuration"""
        return self._config.get('job_defaults', {})

    @property
    def environment(self) -> str:
        """Get current environment"""
        return self._env

    def __getitem__(self, key: str) -> Any:
        """Allow dict-like access: config['broker.redis.host']"""
        return self.get(key)

    def to_dict(self) -> Dict[str, Any]:
        """Get full configuration as dictionary"""
        return self._config.copy()


# Global config instance
_global_config: Optional[Config] = None


def get_config() -> Config:
    """
    Get the global configuration instance.

    Returns:
        Config instance

    Raises:
        RuntimeError: If config not loaded yet

    Examples:
        >>> from tasqueue.config import get_config
        >>> config = get_config()
        >>> host = config.get('broker.redis.host')
    """
    global _global_config

    if _global_config is None:
        raise RuntimeError(
            "Configuration not loaded. Call Config.load() first:\n"
            "  from tasqueue.config import Config\n"
            "  Config.load()  # or Config.load('path/to/config.yaml')"
        )

    return _global_config


def init_config(config_path: Optional[str] = None, env: Optional[str] = None) -> Config:
    """
    Initialize global configuration.

    Args:
        config_path: Path to config.yaml
        env: Environment name

    Returns:
        Config instance

    Examples:
        >>> from tasqueue.config import init_config
        >>> config = init_config('config.yaml', env='development')
    """
    global _global_config
    _global_config = Config.load(config_path, env)
    return _global_config
