"""
In-memory results backend implementation for testing
"""

from typing import Dict, List, Set


class KeyNotFoundError(Exception):
    """Raised when a key is not found"""
    pass


class MemoryResults:
    """
    In-memory results backend implementation.
    Useful for testing and development.
    """

    def __init__(self):
        self._store: Dict[str, bytes] = {}
        self._failed: Set[str] = set()
        self._success: Set[str] = set()

    async def get(self, id: str) -> bytes:
        """Get result by ID"""
        if id not in self._store:
            raise KeyNotFoundError(f"Key {id} not found")
        return self._store[id]

    async def set(self, id: str, data: bytes) -> None:
        """Set result"""
        self._store[id] = data

    async def delete_job(self, id: str) -> None:
        """Delete job metadata"""
        if id in self._store:
            del self._store[id]
        self._failed.discard(id)
        self._success.discard(id)

    async def get_failed(self) -> List[str]:
        """Get list of failed job IDs"""
        return list(self._failed)

    async def get_success(self) -> List[str]:
        """Get list of successful job IDs"""
        return list(self._success)

    async def set_failed(self, id: str) -> None:
        """Mark job as failed"""
        self._failed.add(id)
        self._success.discard(id)

    async def set_success(self, id: str) -> None:
        """Mark job as successful"""
        self._success.add(id)
        self._failed.discard(id)

    def is_not_found_error(self, error: Exception) -> bool:
        """Check if error indicates key not found"""
        return isinstance(error, KeyNotFoundError)
