"""
Redis broker implementation
"""

import asyncio
from typing import List, Callable, Optional
from datetime import datetime
import redis.asyncio as aioredis


class RedisBroker:
    """
    Redis-based broker implementation using Redis lists.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        **kwargs
    ):
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.redis: Optional[aioredis.Redis] = None
        self._consuming = {}

    async def _get_redis(self) -> aioredis.Redis:
        """Get or create Redis connection"""
        if self.redis is None:
            self.redis = await aioredis.from_url(
                f"redis://{self.host}:{self.port}/{self.db}",
                password=self.password,
                decode_responses=False
            )
        return self.redis

    async def enqueue(self, msg: bytes, queue: str) -> None:
        """Enqueue a message to Redis list"""
        import logging
        logger = logging.getLogger(__name__)

        redis = await self._get_redis()
        queue_key = f"tasqueue:queue:{queue}"
        await redis.rpush(queue_key, msg)
        logger.info(f"Enqueued message to {queue_key}, size: {len(msg)} bytes")

    async def enqueue_scheduled(self, msg: bytes, queue: str, eta: datetime) -> None:
        """Enqueue a scheduled message using Redis sorted set"""
        redis = await self._get_redis()
        score = eta.timestamp()
        await redis.zadd(f"tasqueue:scheduled:{queue}", {msg: score})

        # Start scheduled processor if not running
        if queue not in self._consuming:
            asyncio.create_task(self._process_scheduled(queue))

    async def consume(self, queue: str, callback: Callable[[bytes], None]) -> None:
        """Consume messages from Redis list"""
        import logging
        logger = logging.getLogger(__name__)

        redis = await self._get_redis()
        queue_key = f"tasqueue:queue:{queue}"
        self._consuming[queue] = True

        logger.info(f"Redis consumer started for queue: {queue_key}")

        # Start scheduled processor
        asyncio.create_task(self._process_scheduled(queue))

        while self._consuming.get(queue, False):
            try:
                # BLPOP with timeout to allow checking _consuming flag
                logger.debug(f"Waiting for messages on {queue_key}...")
                result = await redis.blpop([queue_key], timeout=1)
                if result:
                    _, msg = result
                    logger.info(f"Received message from {queue_key}, size: {len(msg)} bytes")
                    await callback(msg)
            except Exception as e:
                logger.error(f"Error in Redis consumer: {e}")
                await asyncio.sleep(1)

        logger.info(f"Redis consumer stopped for queue: {queue_key}")

    async def _process_scheduled(self, queue: str) -> None:
        """Process scheduled messages"""
        redis = await self._get_redis()
        scheduled_key = f"tasqueue:scheduled:{queue}"

        while self._consuming.get(queue, False):
            try:
                now = datetime.now().timestamp()

                # Get messages ready to be enqueued
                messages = await redis.zrangebyscore(
                    scheduled_key,
                    min=0,
                    max=now
                )

                for msg in messages:
                    # Move to regular queue
                    await self.enqueue(msg, queue)
                    # Remove from scheduled set
                    await redis.zrem(scheduled_key, msg)

            except Exception as e:
                print(f"Error processing scheduled jobs: {e}")

            await asyncio.sleep(1)  # Check every second

    async def get_pending(self, queue: str) -> List[str]:
        """Get pending messages"""
        redis = await self._get_redis()
        queue_key = f"tasqueue:queue:{queue}"
        messages = await redis.lrange(queue_key, 0, -1)
        return [msg.decode() if isinstance(msg, bytes) else str(msg) for msg in messages]

    async def close(self) -> None:
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()

    def stop(self, queue: str) -> None:
        """Stop consuming from queue"""
        self._consuming[queue] = False
