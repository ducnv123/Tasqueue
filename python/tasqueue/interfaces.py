"""
Core interfaces for Tasqueue brokers and results backends
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Callable
from datetime import datetime


class Broker(ABC):
    """
    Broker interface for queue operations.

    Implementations must guarantee atomicity to prevent duplicate job consumption.
    """

    @abstractmethod
    async def enqueue(self, msg: bytes, queue: str) -> None:
        """
        Enqueue a message to the specified queue.

        Args:
            msg: Serialized message bytes
            queue: Queue name
        """
        pass

    @abstractmethod
    async def enqueue_scheduled(self, msg: bytes, queue: str, eta: datetime) -> None:
        """
        Enqueue a scheduled message to be processed at a specific time.

        Args:
            msg: Serialized message bytes
            queue: Queue name
            eta: Time when the job should be processed
        """
        pass

    @abstractmethod
    async def consume(self, queue: str, callback: Callable[[bytes], None]) -> None:
        """
        Start consuming messages from a queue.

        Args:
            queue: Queue name
            callback: Function to call with each message
        """
        pass

    @abstractmethod
    async def get_pending(self, queue: str) -> List[str]:
        """
        Get list of pending job messages in the queue.

        Args:
            queue: Queue name

        Returns:
            List of pending job message IDs
        """
        pass


class Results(ABC):
    """
    Results interface for job metadata and results storage.
    """

    @abstractmethod
    async def get(self, id: str) -> bytes:
        """
        Get result data by ID.

        Args:
            id: Job ID

        Returns:
            Result bytes

        Raises:
            KeyError: If ID not found
        """
        pass

    @abstractmethod
    async def set(self, id: str, data: bytes) -> None:
        """
        Store result data by ID.

        Args:
            id: Job ID
            data: Result bytes
        """
        pass

    @abstractmethod
    async def delete_job(self, id: str) -> None:
        """
        Delete job metadata from store.

        Args:
            id: Job ID
        """
        pass

    @abstractmethod
    async def get_failed(self) -> List[str]:
        """
        Get list of failed job IDs.

        Returns:
            List of failed job IDs
        """
        pass

    @abstractmethod
    async def get_success(self) -> List[str]:
        """
        Get list of successful job IDs.

        Returns:
            List of successful job IDs
        """
        pass

    @abstractmethod
    async def set_failed(self, id: str) -> None:
        """
        Mark a job as failed.

        Args:
            id: Job ID
        """
        pass

    @abstractmethod
    async def set_success(self, id: str) -> None:
        """
        Mark a job as successful.

        Args:
            id: Job ID
        """
        pass

    @abstractmethod
    def is_not_found_error(self, error: Exception) -> bool:
        """
        Check if an error indicates a missing key.

        Args:
            error: Exception to check

        Returns:
            True if error indicates key not found
        """
        pass
