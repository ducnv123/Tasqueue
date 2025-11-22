"""
Factory functions to create broker and results instances from configuration
"""

from typing import Union
from .interfaces import Broker, Results
from .config import get_config, Config


def create_broker_from_config(config: Union[Config, dict, None] = None) -> Broker:
    """
    Create broker instance from configuration.

    Args:
        config: Config instance, dict, or None to use global config

    Returns:
        Broker instance

    Examples:
        >>> from tasqueue.config import init_config
        >>> from tasqueue.factory import create_broker_from_config
        >>>
        >>> init_config('config.yaml')
        >>> broker = create_broker_from_config()
    """
    if config is None:
        config = get_config()
    elif isinstance(config, dict):
        # If dict provided, use it directly
        broker_config = config
    else:
        broker_config = config.get_broker_config()

    broker_type = broker_config.get('type', 'memory')

    if broker_type == 'redis':
        from .brokers.redis_broker import RedisBroker
        redis_config = broker_config.get('redis', {})
        return RedisBroker(
            host=redis_config.get('host', 'localhost'),
            port=redis_config.get('port', 6379),
            db=redis_config.get('db', 0),
            password=redis_config.get('password'),
        )
    elif broker_type == 'memory':
        from .brokers.memory import MemoryBroker
        return MemoryBroker()
    else:
        raise ValueError(f"Unknown broker type: {broker_type}")


def create_results_from_config(config: Union[Config, dict, None] = None) -> Results:
    """
    Create results backend instance from configuration.

    Args:
        config: Config instance, dict, or None to use global config

    Returns:
        Results instance

    Examples:
        >>> from tasqueue.config import init_config
        >>> from tasqueue.factory import create_results_from_config
        >>>
        >>> init_config('config.yaml')
        >>> results = create_results_from_config()
    """
    if config is None:
        config = get_config()
    elif isinstance(config, dict):
        results_config = config
    else:
        results_config = config.get_results_config()

    results_type = results_config.get('type', 'memory')

    if results_type == 'redis':
        from .results.redis_results import RedisResults
        redis_config = results_config.get('redis', {})
        return RedisResults(
            host=redis_config.get('host', 'localhost'),
            port=redis_config.get('port', 6379),
            db=redis_config.get('db', 0),
            password=redis_config.get('password'),
        )
    elif results_type == 'memory':
        from .results.memory import MemoryResults
        return MemoryResults()
    else:
        raise ValueError(f"Unknown results type: {results_type}")
