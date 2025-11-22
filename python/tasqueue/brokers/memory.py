"""
In-memory broker implementation for testing
"""

import asyncio
from typing import Dict, List, Callable
from datetime import datetime
from collections import deque


class MemoryBroker:
    """
    In-memory broker implementation.
    Useful for testing and development.
    """

    def __init__(self):
        self._queues: Dict[str, deque] = {}
        self._consumers: Dict[str, bool] = {}
        self._scheduled: Dict[str, List[tuple[datetime, bytes]]] = {}

    async def enqueue(self, msg: bytes, queue: str) -> None:
        """Enqueue a message"""
        if queue not in self._queues:
            self._queues[queue] = deque()

        self._queues[queue].append(msg)

    async def enqueue_scheduled(self, msg: bytes, queue: str, eta: datetime) -> None:
        """Enqueue a scheduled message"""
        if queue not in self._scheduled:
            self._scheduled[queue] = []

        self._scheduled[queue].append((eta, msg))

    async def consume(self, queue: str, callback: Callable[[bytes], None]) -> None:
        """Start consuming messages from a queue"""
        if queue not in self._queues:
            self._queues[queue] = deque()

        self._consumers[queue] = True

        # Start scheduled job processor
        asyncio.create_task(self._process_scheduled(queue))

        # Main consumer loop
        while self._consumers.get(queue, False):
            try:
                if self._queues[queue]:
                    msg = self._queues[queue].popleft()
                    await callback(msg)
                else:
                    await asyncio.sleep(0.1)  # Short sleep if queue is empty
            except Exception as e:
                # Log error but continue consuming
                print(f"Error in consumer: {e}")

    async def _process_scheduled(self, queue: str) -> None:
        """Process scheduled messages"""
        while self._consumers.get(queue, False):
            if queue in self._scheduled:
                now = datetime.now()
                remaining = []

                for eta, msg in self._scheduled[queue]:
                    if eta <= now:
                        # Time to enqueue
                        await self.enqueue(msg, queue)
                    else:
                        remaining.append((eta, msg))

                self._scheduled[queue] = remaining

            await asyncio.sleep(0.5)  # Check every 0.5 seconds

    async def get_pending(self, queue: str) -> List[str]:
        """Get pending messages"""
        if queue not in self._queues:
            return []

        # Return message IDs (for in-memory, just return indices)
        return [str(i) for i in range(len(self._queues[queue]))]

    def stop(self, queue: str) -> None:
        """Stop consuming from a queue"""
        self._consumers[queue] = False
