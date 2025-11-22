"""
Redis results backend implementation
"""

from typing import List, Optional
import redis.asyncio as aioredis


class RedisResults:
    """
    Redis-based results backend implementation.
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

    async def _get_redis(self) -> aioredis.Redis:
        """Get or create Redis connection"""
        if self.redis is None:
            self.redis = await aioredis.from_url(
                f"redis://{self.host}:{self.port}/{self.db}",
                password=self.password,
                decode_responses=False
            )
        return self.redis

    async def get(self, id: str) -> bytes:
        """Get result by ID"""
        redis = await self._get_redis()
        result = await redis.get(f"tasqueue:result:{id}")
        if result is None:
            raise KeyError(f"Key {id} not found")
        return result

    async def set(self, id: str, data: bytes) -> None:
        """Set result"""
        redis = await self._get_redis()
        await redis.set(f"tasqueue:result:{id}", data)

    async def delete_job(self, id: str) -> None:
        """Delete job metadata"""
        redis = await self._get_redis()
        await redis.delete(f"tasqueue:result:{id}")
        await redis.srem("tasqueue:failed", id)
        await redis.srem("tasqueue:success", id)

    async def get_failed(self) -> List[str]:
        """Get list of failed job IDs"""
        redis = await self._get_redis()
        results = await redis.smembers("tasqueue:failed")
        return [r.decode() if isinstance(r, bytes) else str(r) for r in results]

    async def get_success(self) -> List[str]:
        """Get list of successful job IDs"""
        redis = await self._get_redis()
        results = await redis.smembers("tasqueue:success")
        return [r.decode() if isinstance(r, bytes) else str(r) for r in results]

    async def set_failed(self, id: str) -> None:
        """Mark job as failed"""
        redis = await self._get_redis()
        await redis.sadd("tasqueue:failed", id)
        await redis.srem("tasqueue:success", id)

    async def set_success(self, id: str) -> None:
        """Mark job as successful"""
        redis = await self._get_redis()
        await redis.sadd("tasqueue:success", id)
        await redis.srem("tasqueue:failed", id)

    def is_not_found_error(self, error: Exception) -> bool:
        """Check if error indicates key not found"""
        return isinstance(error, KeyError)

    async def close(self) -> None:
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()
